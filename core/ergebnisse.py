"""Ergebnisse einer Simulation speichern und lesen.

Zeitreihen liegen als Block von 32-Bit-Gleitkommazahlen, eine je Stunde. Ein
Jahr belegt damit rund 35 KB je Groesse; ein Diagramm laedt seine Reihe in einem
einzigen Zugriff, und die Datenbank waechst nicht auf Millionen Zeilen.
"""

import array
import json

from core.bausteine.basis import Luft
from core.database import get_db

# Preisschluessel der Bilanzkarte und die Umrechnung der Stundensummen
BILANZ = {
    "strom_ht": ("MWh", "preis_strom_ht", 1 / 1000.0),
    "strom_nt": ("MWh", "preis_strom_nt", 1 / 1000.0),
    "waerme": ("MWh", "preis_waerme", 1 / 1000.0),
    "kaelte": ("MWh", "preis_kaelte", 1 / 1000.0),
    "wasser": ("m³", "preis_wasser", 1 / 1000.0),
}


def _als_blob(werte):
    return array.array("f", werte).tobytes()


def _aus_blob(rohdaten):
    feld = array.array("f")
    feld.frombytes(rohdaten)
    return list(feld)


def _preise(graph):
    """Die Preise der ersten Bilanzkarte dieser Anlage.

    Liest aus dem bereits geladenen Anlagengraph statt selbst die
    'karte'-Tabelle abzufragen - core/anlagen.py bleibt so die einzige Stelle,
    die das Schema der Karten kennt.
    """
    for karte in graph.karten.values():
        if karte.typ == "bilanz":
            return karte.parameter
    return {}


# Status, den core/laeufe.py._laufen() waehrend der Rechnung setzt - siehe
# beginne()/abschliesse(). Umlautfreies "laeuft" nach demselben Muster wie
# die uebrigen Statuswerte hier (fertig/abgebrochen/fehler) und wie das
# in-memory-Feld status="laeuft" in core.laeufe._AUFTRAEGE.
STATUS_LAEUFT = "laeuft"


def beginne(anlage_id, wetterdatensatz_id, von, bis, kennung):
    """Legt die Zeile eines neu gestarteten Laufs sofort an, Status 'laeuft'.

    Vorher entstand die Zeile erst am Ende (in speichere()) - ein Neuladen
    der Editorseite oder ein Neustart des Dienstes waehrend der Rechnung
    fand dann ueberhaupt keine Spur des Laufs. Mit dieser Zeile ab dem Start
    kann core.laeufe.laufender_auftrag() sie wiederfinden, und
    core.database._aufraeume_verwaiste_laeufe() erkennt sie nach einem
    Neustart als verwaist.
    """
    db = get_db()
    cur = db.execute(
        "INSERT INTO simulation (anlage_id, wetterdatensatz_id, von_stunde, "
        "bis_stunde, status, kennung, fortschritt) "
        "VALUES (?, ?, ?, ?, ?, ?, 0)",
        (anlage_id, wetterdatensatz_id, von, bis, STATUS_LAEUFT, kennung),
    )
    db.commit()
    return cur.lastrowid


def fortschritt_speichern(simulation_id, fertig):
    """Schreibt den Zwischenstand in die beim Start angelegte Zeile.

    core.laeufe._laufen() ruft dies in groesserem Abstand auf, nicht bei
    jeder Stunde (Begruendung dort) - die laufende Zeile zeigt trotzdem
    immer einen einigermassen aktuellen Stand, falls die Seite neu laedt.
    """
    db = get_db()
    db.execute(
        "UPDATE simulation SET fortschritt = ? WHERE id = ?", (fertig, simulation_id)
    )
    db.commit()


def abschliesse(simulation_id, lauf, graph, dauer, status):
    """Schreibt den Endstand in die von beginne() angelegte Zeile und
    speichert Zeitreihen und Bilanz - das Gegenstueck zu beginne(), fuer
    einen Lauf, der ueber core.laeufe.starte() gestartet wurde."""
    db = get_db()
    db.execute(
        "UPDATE simulation SET status = ?, dauer_s = ?, warnungen = ?, "
        "fortschritt = ? WHERE id = ?",
        (
            status, dauer, json.dumps(lauf.warnungen, ensure_ascii=False),
            len(lauf.stunden), simulation_id,
        ),
    )
    _ergebnisse_einfuegen(db, simulation_id, lauf, graph)
    db.commit()


def speichere(anlage_id, wetterdatensatz_id, von, bis, lauf, graph, dauer, status="fertig"):
    """Legt Zeile und Ergebnisse eines bereits abgeschlossenen Laufs in einem
    Schritt an - fuer Aufrufer ohne vorherigen beginne()-Aufruf (Tests, die
    direkt ein fertiges Ergebnis anlegen, und werkzeuge/durchstich.py)."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO simulation (anlage_id, wetterdatensatz_id, von_stunde, "
        "bis_stunde, status, dauer_s, warnungen, fortschritt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (anlage_id, wetterdatensatz_id, von, bis, status, dauer,
         json.dumps(lauf.warnungen, ensure_ascii=False), len(lauf.stunden)),
    )
    simulation_id = cur.lastrowid
    _ergebnisse_einfuegen(db, simulation_id, lauf, graph)
    db.commit()
    return simulation_id


def _ergebnisse_einfuegen(db, simulation_id, lauf, graph):
    """Zeitreihen, Bilanz und Bausteinwarnungen einer Zeile schreiben -
    gemeinsam von speichere() und abschliesse() genutzt, ohne selbst zu
    committen."""

    def _name(karte_id):
        karte = graph.karten.get(karte_id)
        return karte.name if karte is not None else ""

    # Alle vorkommenden Groessen einsammeln, und nebenbei die Warntexte, die
    # manche Bausteine unter dem Schluessel 'warnung' in ihre Ausgabe
    # schreiben (z.B. ein unterdimensionierter Kuehler, siehe
    # core/bausteine/kuehler.py) - gruppiert nach Karte und Wortlaut, mit den
    # Stunden, in denen sie auftraten.
    reihen = {}
    warnstunden = {}
    for nummer, stunde in enumerate(lauf.stunden):
        for karte_id, werte in stunde.items():
            text = werte.get("warnung")
            if text:
                warnstunden.setdefault((karte_id, text), []).append(nummer + 1)
            for groesse, wert in werte.items():
                if isinstance(wert, Luft) or not isinstance(wert, (int, float)):
                    continue
                reihen.setdefault((karte_id, groesse), [0.0] * len(lauf.stunden))
                reihen[(karte_id, groesse)][nummer] = float(wert)

    if warnstunden:
        baustein_warnungen = sorted(
            (
                {
                    "karte_id": karte_id,
                    "karte_name": _name(karte_id),
                    "text": text,
                    "anzahl": len(stunden),
                    "beispiele": _stichprobe(stunden, 5),
                }
                for (karte_id, text), stunden in warnstunden.items()
            ),
            key=lambda eintrag: (-eintrag["anzahl"], eintrag["karte_name"], eintrag["text"]),
        )
        db.execute(
            "UPDATE simulation SET baustein_warnungen = ? WHERE id = ?",
            (json.dumps(baustein_warnungen, ensure_ascii=False), simulation_id),
        )

    db.executemany(
        "INSERT INTO zeitreihe (simulation_id, karte_id, karte_name, groesse, werte) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (simulation_id, karte_id, _name(karte_id), groesse, _als_blob(werte))
            for (karte_id, groesse), werte in sorted(reihen.items())
        ],
    )

    preise = _preise(graph)
    zeilen = []
    for groesse, (einheit, preisschluessel, faktor) in BILANZ.items():
        menge = lauf.bilanz.get(groesse, 0.0) * faktor
        preis = float(preise.get(preisschluessel, 0.0))
        zeilen.append((simulation_id, groesse, menge, einheit, preis, menge * preis))
    db.executemany(
        "INSERT INTO bilanz (simulation_id, groesse, menge, einheit, preis, kosten) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        zeilen,
    )


def simulation_loeschen(simulation_id):
    """Loescht einen einzelnen Simulationslauf mitsamt seiner Zeitreihe und
    Bilanz (ON DELETE CASCADE, siehe core/database.py).

    Ein noch laufender Lauf (status='laeuft') laesst sich hierueber nicht
    loeschen - sein Rechen-Thread (core/laeufe.py) schreibt am Ende noch in
    genau diese Zeile, und ihn mitten im Lauf verschwinden zu lassen waere
    kein 'sauberer' Abbruch, sondern ein Wettlauf mit dem Hintergrund-Thread.
    Erst abbrechen (core.laeufe.abbrechen), dann loeschen - oder die ganze
    Anlage loeschen (core.anlagen.anlage_loeschen), was den laufenden Lauf
    ueber ON DELETE CASCADE ohnehin mitnimmt und dem Thread vorher sauber
    Bescheid gibt (core.laeufe.abbrich_vor_loeschen)."""
    db = get_db()
    zeile = db.execute(
        "SELECT status FROM simulation WHERE id = ?", (simulation_id,)
    ).fetchone()
    if zeile is None:
        raise KeyError(f"Simulationslauf {simulation_id} gibt es nicht")
    if zeile["status"] == STATUS_LAEUFT:
        raise ValueError(
            "Ein laufender Simulationslauf kann nicht geloescht werden - "
            "zuerst abbrechen."
        )
    db.execute("DELETE FROM simulation WHERE id = ?", (simulation_id,))
    db.commit()


def laufende_simulation(anlage_id):
    """Die Zeile des aktuell laufenden Simulationslaufs dieser Anlage, falls
    es einen gibt - sonst None. Juengste zuerst, falls durch einen Randfall
    (z.B. ein umgangener Client) doch mehr als eine Zeile 'laeuft'."""
    db = get_db()
    zeile = db.execute(
        "SELECT id, kennung, von_stunde, bis_stunde, fortschritt FROM simulation "
        "WHERE anlage_id = ? AND status = ? ORDER BY id DESC LIMIT 1",
        (anlage_id, STATUS_LAEUFT),
    ).fetchone()
    return dict(zeile) if zeile else None


def lade_bilanz(simulation_id):
    db = get_db()
    return [
        dict(z)
        for z in db.execute(
            "SELECT groesse, menge, einheit, preis, kosten FROM bilanz "
            "WHERE simulation_id = ? ORDER BY id",
            (simulation_id,),
        )
    ]


def lade_zeitreihe(simulation_id, karte_id, groesse):
    db = get_db()
    zeile = db.execute(
        "SELECT werte FROM zeitreihe WHERE simulation_id = ? AND karte_id = ? "
        "AND groesse = ?",
        (simulation_id, karte_id, groesse),
    ).fetchone()
    return _aus_blob(zeile["werte"]) if zeile else []


def simulation_anlage_id(simulation_id):
    """Die Anlage, zu der ein Simulationslauf gehoert - fuer Aufrufer, die aus
    einer simulation_id zuerst den aktuellen Anlagengraph laden muessen
    (siehe lade_protokoll() und routes/simulation.py:protokoll())."""
    db = get_db()
    zeile = db.execute(
        "SELECT anlage_id FROM simulation WHERE id = ?", (simulation_id,)
    ).fetchone()
    if zeile is None:
        raise KeyError(f"Simulationslauf {simulation_id} gibt es nicht")
    return zeile["anlage_id"]


def lade_protokoll(simulation_id, graph):
    """Das Stundenprotokoll der am Datenlogger angeschlossenen Werte.

    Die 'zeitreihe'-Tabelle traegt die Ausgabe JEDER Karte, aber nur der
    Datenlogger ist die Stelle, an der eine Anlage auswaehlt, was sie davon
    im Protokoll sehen will: ein Anschluss zaehlt erst, sobald er im
    Parameterfenster einen Namen bekommen hat (core/bausteine/datenlogger.py,
    Baustein.spalten()) - genau das verspricht der Erklaertext in
    templates/bausteine.html. Namen und Einheiten kommen deshalb live aus dem
    aktuellen Anlagengraph statt aus der Zeitreihe selbst - wird eine Spalte
    nach dem Lauf umbenannt, zeigt ein spaeter geoeffnetes Protokoll den
    neuen Namen, nicht den zur Laufzeit gueltigen. Das ist ein bewusster
    Kompromiss: eine dritte Stelle, die Spaltennamen einfriert, haette diese
    Funktion nur unwesentlich richtiger und dafuer eine weitere Spalte in der
    Datenbank gebraucht.
    """
    spalten = []
    for karte in graph.karten.values():
        if karte.typ != "datenlogger":
            continue
        for schluessel, name, einheit in karte.baustein.spalten(karte.parameter):
            werte = lade_zeitreihe(simulation_id, karte.id, schluessel)
            if not werte:
                continue
            spalten.append(
                {
                    "karte_id": karte.id, "karte_name": karte.name,
                    "name": name, "einheit": einheit, "werte": werte,
                }
            )
    return spalten


def letzte_werte(simulation_id):
    """Der letzte Wert jeder Zeitreihe, gruppiert nach Karte.

    Fuer die Leinwand: nach einem Lauf zeigt jede Karte ihre Werte unter dem
    Namen (Panel.zeigeWerte). Nur die letzten 4 Bytes des Blocks werden
    gelesen statt die ganze Zeitreihe zu entpacken - bei einem Jahreslauf mit
    vielen Karten summiert sich das sonst auf mehrere zehn Megabyte, die hier
    niemand braucht.
    """
    db = get_db()
    ergebnis = {}
    for zeile in db.execute(
        "SELECT karte_id, groesse, werte FROM zeitreihe WHERE simulation_id = ?",
        (simulation_id,),
    ):
        rohdaten = zeile["werte"]
        if len(rohdaten) < 4:
            continue
        letzter = array.array("f")
        letzter.frombytes(rohdaten[-4:])
        ergebnis.setdefault(zeile["karte_id"], {})[zeile["groesse"]] = letzter[0]
    return ergebnis


def _stichprobe(elemente, anzahl):
    """Bis zu 'anzahl' ueber die Liste verteilte Eintraege - kein Ausschnitt vom
    Anfang, der bei einer taktenden Regelschleife immer dieselbe Ursache zeigt."""
    if len(elemente) <= anzahl:
        return list(elemente)
    schritt = len(elemente) / anzahl
    return [elemente[int(i * schritt)] for i in range(anzahl)]


def lade_warnungen(simulation_id, anzahl=5):
    """Anzahl und eine repraesentative Stichprobe der Konvergenzwarnungen.

    Ein Jahreslauf kann tausende Warnungen erzeugen (siehe core/solver.py) -
    die Bilanz zeigt deshalb nur die Zahl und ein paar Beispiele, nie die
    volle Liste.
    """
    db = get_db()
    zeile = db.execute(
        "SELECT warnungen FROM simulation WHERE id = ?", (simulation_id,)
    ).fetchone()
    alle = json.loads(zeile["warnungen"]) if zeile else []
    return {"anzahl": len(alle), "beispiele": _stichprobe(alle, anzahl)}


def lade_baustein_warnungen(simulation_id):
    """Warnungen, die Bausteine waehrend der Rechnung in ihre Ausgabe
    geschrieben haben (z.B. 'Kuehlleistung zu niedrig'), gruppiert nach Karte
    und Wortlaut - eine Zeile je Kombination, mit Anzahl und einer Stichprobe
    der betroffenen Stunden. Siehe _ergebnisse_einfuegen(), das die Gruppen
    beim Speichern des Laufs bildet; analog zu lade_warnungen() fuer die
    Konvergenzwarnungen des Solvers."""
    db = get_db()
    zeile = db.execute(
        "SELECT baustein_warnungen FROM simulation WHERE id = ?", (simulation_id,)
    ).fetchone()
    if not zeile or not zeile["baustein_warnungen"]:
        return []
    return json.loads(zeile["baustein_warnungen"])


def simulationen_von(anlage_id):
    """Die Simulationslaeufe einer Anlage, juengster zuerst."""
    db = get_db()
    zeilen = db.execute(
        "SELECT s.*, w.name AS wetter_name, "
        "       (SELECT SUM(b.kosten) FROM bilanz b WHERE b.simulation_id = s.id) "
        "         AS kosten_gesamt "
        "FROM simulation s JOIN wetterdatensatz w ON w.id = s.wetterdatensatz_id "
        "WHERE s.anlage_id = ? ORDER BY s.id DESC",
        (anlage_id,),
    ).fetchall()
    return [
        {
            "id": z["id"], "wetter_name": z["wetter_name"],
            "von_stunde": z["von_stunde"], "bis_stunde": z["bis_stunde"],
            "status": z["status"], "gestartet_am": z["gestartet_am"],
            "dauer_s": z["dauer_s"],
            # Nur bei einem noch laufenden Lauf gesetzt (siehe beginne()) -
            # der Dialog kann so eine 'laeuft'-Zeile statt einer (bei einem
            # laufenden Lauf noch nicht vorhandenen) Bilanz wieder aufgreifen.
            "kennung": z["kennung"],
            "kosten_gesamt": z["kosten_gesamt"] or 0.0,
        }
        for z in zeilen
    ]
