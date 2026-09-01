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
    """Zeitreihen und Bilanz einer Zeile schreiben - gemeinsam von speichere()
    und abschliesse() genutzt, ohne selbst zu committen."""
    # Alle vorkommenden Groessen einsammeln
    reihen = {}
    for nummer, stunde in enumerate(lauf.stunden):
        for karte_id, werte in stunde.items():
            for groesse, wert in werte.items():
                if isinstance(wert, Luft) or not isinstance(wert, (int, float)):
                    continue
                reihen.setdefault((karte_id, groesse), [0.0] * len(lauf.stunden))
                reihen[(karte_id, groesse)][nummer] = float(wert)

    def _name(karte_id):
        karte = graph.karten.get(karte_id)
        return karte.name if karte is not None else ""

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


def reihen(simulation_id):
    db = get_db()
    return [
        {"karte_id": z["karte_id"], "karte_name": z["karte_name"],
         "groesse": z["groesse"], "einheit": z["einheit"]}
        for z in db.execute(
            "SELECT karte_id, karte_name, groesse, einheit FROM zeitreihe "
            "WHERE simulation_id = ? ORDER BY karte_name, groesse",
            (simulation_id,),
        )
    ]


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
