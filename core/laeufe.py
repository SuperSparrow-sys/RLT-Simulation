"""Simulationslaeufe im Hintergrund, mit Fortschritt und Abbruch."""

import threading
import time
import uuid

from core import anlagen, database, ergebnisse, solver
from core.wetter import speicher

_AUFTRAEGE = {}
_SPERRE = threading.Lock()

# Abgeschlossene Auftraege bleiben nur begrenzt im Speicher - sonst waechst
# _AUFTRAEGE ueber die Lebenszeit des Prozesses unbegrenzt. Kein Verfallsdatum,
# keine eigene Aufraeum-Infrastruktur: einfach die aeltesten abgeschlossenen
# Eintraege verwerfen, sobald es zu viele werden.
_MAX_AUFTRAEGE = 200
_ABGESCHLOSSEN = ("fertig", "abgebrochen", "fehler")

# Wie oft _laufen() den Fortschritt zusaetzlich zum Arbeitsspeicher in die
# 'simulation'-Zeile schreibt. Bei einem Jahreslauf (8760 Stunden, ~8 Minuten)
# waere ein Schreibzugriff je Stunde reiner Overhead, den niemand braucht,
# solange der Dienst laeuft (dort ist _AUFTRAEGE die schnellere, massgebliche
# Quelle - siehe stand()). Der DB-Stand ist nur fuer den Moment direkt nach
# einem Neuladen der Seite gedacht, bevor die erste Abfrage von dort eine
# frische Antwort liefert - 5s halten ihn dafuer nah genug am echten Stand,
# ohne bei einem Jahreslauf mehr als rund 100 zusaetzliche Schreibzugriffe zu
# verursachen.
_FORTSCHRITT_SCHREIB_ABSTAND_S = 5.0


def _aufraeumen():
    """Verwirft die aeltesten abgeschlossenen Auftraege. Nur unter _SPERRE aufrufen."""
    ueberschuss = len(_AUFTRAEGE) - _MAX_AUFTRAEGE
    if ueberschuss <= 0:
        return
    for kennung, eintrag in list(_AUFTRAEGE.items()):
        if ueberschuss <= 0:
            break
        if eintrag.get("status") in _ABGESCHLOSSEN:
            del _AUFTRAEGE[kennung]
            ueberschuss -= 1


def _setze(kennung, **felder):
    with _SPERRE:
        _AUFTRAEGE.setdefault(kennung, {}).update(felder)
        _aufraeumen()


def stand(kennung):
    with _SPERRE:
        return dict(_AUFTRAEGE.get(kennung, {"status": "unbekannt"}))


def abbrechen(kennung):
    _setze(kennung, abbruch=True)


def _laufen(app, kennung, simulation_id, anlage_id, wetterdatensatz_id, von, bis):
    with app.app_context():
        begonnen = time.time()
        letzte_schreibzeit = [begonnen]  # Liste als Zelle, da fortschritt() sie neu bindet
        try:
            stunden = speicher.lade_stunden(wetterdatensatz_id, von, bis)
            graph = anlagen.lade_graph(anlage_id)

            def fortschritt(nummer, gesamt):
                _setze(kennung, fertig=nummer, gesamt=gesamt)
                jetzt = time.time()
                if jetzt - letzte_schreibzeit[0] >= _FORTSCHRITT_SCHREIB_ABSTAND_S:
                    letzte_schreibzeit[0] = jetzt
                    ergebnisse.fortschritt_speichern(simulation_id, nummer)

            def abbruch():
                return bool(stand(kennung).get("abbruch"))

            lauf = solver.Solver(graph).starte(
                stunden, fortschritt=fortschritt, abbruch=abbruch
            )
            # Der Abbruch-Merker sagt nur, ob abbrechen() aufgerufen wurde - nicht,
            # ob der Lauf dadurch wirklich vorzeitig endete. Ein Abbruch, der erst
            # nach der letzten Stunde eintrifft, waere sonst faelschlich
            # "abgebrochen", obwohl jede angeforderte Stunde gerechnet wurde.
            # Massgeblich ist daher, ob weniger Stunden herauskamen als angefordert.
            vollstaendig = len(lauf.stunden) >= len(stunden)
            status = "fertig" if vollstaendig else "abgebrochen"
            ergebnisse.abschliesse(
                simulation_id, lauf, graph, dauer=time.time() - begonnen, status=status
            )
            _setze(
                kennung,
                status=status,
                simulation_id=simulation_id,
                warnungen=len(lauf.warnungen),
                dauer=time.time() - begonnen,
            )
        except Exception as fehler:  # noqa: BLE001 - der Lauf darf die App nicht kippen
            # War die Anlage (oder ihr Projekt) waehrend des Laufs geloescht
            # worden, ist die beim Start angelegte 'simulation'-Zeile laengst
            # weg (ON DELETE CASCADE, core/database.py) - der Schreibversuch
            # oben (ergebnisse.fortschritt_speichern()/abschliesse()) scheitert
            # dann an genau dieser Fremdschluesselpruefung. Kein echter
            # Fehler, sondern der erwartete, saubere Ausgang von
            # laeufe.abbrich_vor_loeschen(): statt der rohen SQL-Meldung
            # ("FOREIGN KEY constraint failed") zeigt der Stand denselben
            # Status wie ein normaler Abbruch.
            try:
                db = database.get_db()
                noch_da = db.execute(
                    "SELECT 1 FROM simulation WHERE id = ?", (simulation_id,)
                ).fetchone()
            except Exception:  # noqa: BLE001 - die Pruefung selbst darf nicht kippen
                noch_da = True
            if noch_da is None:
                _setze(kennung, status="abgebrochen", simulation_id=simulation_id)
                return

            _setze(kennung, status="fehler", fehler=str(fehler), simulation_id=simulation_id)
            try:
                # Die beim Start angelegte Zeile (status='laeuft') darf nicht
                # fuer immer so stehen bleiben - sonst haette
                # _aufraeume_verwaiste_laeufe() beim naechsten Dienststart
                # nichts mehr aufzuraeumen, obwohl dieser Lauf nie fertig wurde.
                db = database.get_db()
                db.execute(
                    "UPDATE simulation SET status = 'fehler' WHERE id = ?",
                    (simulation_id,),
                )
                db.commit()
            except Exception:  # noqa: BLE001 - das Markieren darf nicht nachtraeglich kippen
                pass


def starte(app, anlage_id, wetterdatensatz_id, von, bis):
    kennung = uuid.uuid4().hex
    try:
        simulation_id = ergebnisse.beginne(anlage_id, wetterdatensatz_id, von, bis, kennung)
    except Exception as fehler:  # noqa: BLE001 - z.B. ein ungueltiger Wetterdatensatz
        # Vor dieser Zeile stand dieselbe Pruefung erst am Ende von _laufen()
        # (dort ebenfalls abgefangen) - jetzt schlaegt sie schon hier fehl, weil
        # beginne() sofort schreibt statt erst nach dem ganzen Lauf. Damit
        # starte() weiterhin nie eine Ausnahme an den aufrufenden Request
        # durchreicht (die Anrufenden erwarten immer eine Kennung und lesen den
        # Fehler ueber stand()), wird der Fehlschlag hier genauso wie ein
        # spaeter Fehlschlag im Hintergrund-Thread im Speicher vermerkt.
        _setze(kennung, status="fehler", fehler=str(fehler), simulation_id=0)
        return kennung
    _setze(
        kennung,
        status="laeuft", fertig=0, gesamt=max(bis - von, 0),
        abbruch=False, simulation_id=simulation_id,
    )
    faden = threading.Thread(
        target=_laufen,
        args=(app, kennung, simulation_id, anlage_id, wetterdatensatz_id, von, bis),
        daemon=True,
    )
    faden.start()
    return kennung


def abbrich_vor_loeschen(anlage_id=None, projekt_id=None):
    """Signalisiert jedem noch laufenden Simulationslauf einer Anlage (oder
    aller Anlagen eines Projekts) den Abbruch, bevor die zugehoerigen
    Datenbankzeilen geloescht werden. Genau eines der beiden Argumente wird
    angegeben.

    Ohne dieses Signal rechnete der Hintergrund-Thread eines laufenden Laufs
    (_laufen()) bis zum natuerlichen Ende weiter - bei einem Jahreslauf bis
    zu acht Minuten -, obwohl niemand das Ergebnis mehr abholen kann: die
    'simulation'-Zeile ist durch ON DELETE CASCADE (core/database.py,
    anlage -> simulation) bereits mit der Anlage geloescht, und sein
    abschliessender Schreibversuch in core.ergebnisse.abschliesse() scheitert
    dann an genau dieser Fremdschluesselpruefung (INSERT INTO zeitreihe mit
    einer nicht mehr vorhandenen simulation_id). Das ist an sich schon
    unschaedlich - der breite except in _laufen() faengt es ab, es entsteht
    keine verwaiste Zeile -, aber unnoetig spaet und mit einer rohen
    SQL-Fehlermeldung als 'fehler'-Text. abbrechen() laesst den Solver
    stattdessen an der naechsten Stunde von selbst aufhoeren (siehe
    core/solver.py, Parameter 'abbruch' von Solver.starte())."""
    if anlage_id is not None:
        anlage_ids = [anlage_id]
    else:
        anlage_ids = [a["id"] for a in anlagen.anlagen_von(projekt_id)]
    for aid in anlage_ids:
        zeile = ergebnisse.laufende_simulation(aid)
        if zeile and zeile.get("kennung"):
            abbrechen(zeile["kennung"])


def laufender_auftrag(anlage_id):
    """Fuer die Editorseite nach einem Neuladen: laeuft fuer diese Anlage
    gerade ein Lauf, und unter welcher Kennung? None, wenn nicht.

    Liest die Zeile aus der Datenbank (core.ergebnisse.laufende_simulation)
    und ergaenzt fertig/gesamt aus _AUFTRAEGE, falls dort vorhanden - das ist
    waehrend des Laufs der aktuellere Stand (siehe _FORTSCHRITT_SCHREIB_ABSTAND_S).
    Eine 'laeuft'-Zeile ohne Eintrag in _AUFTRAEGE kann in diesem Prozess nicht
    vorkommen: _aufraeume_verwaiste_laeufe() raeumt beim Start jede Zeile weg,
    die von einem fruaheren Prozess stammt, bevor je wieder ein Lauf startet.
    """
    zeile = ergebnisse.laufende_simulation(anlage_id)
    if zeile is None:
        return None
    gesamt = zeile["bis_stunde"] - zeile["von_stunde"]
    im_speicher = stand(zeile["kennung"]) if zeile["kennung"] else {}
    return {
        "kennung": zeile["kennung"],
        "simulation_id": zeile["id"],
        "status": "laeuft",
        "fertig": im_speicher.get("fertig", zeile["fortschritt"]),
        "gesamt": im_speicher.get("gesamt", gesamt),
    }


# ---------------------------------------------------------------------------
# Reihen: derselbe Anlagenlauf ueber mehrere Wetterjahre, nacheinander
# (Vergleich mehrerer Wetterjahre - core/vergleich.py stellt daraus die
# Gegenueberstellung zusammen).
#
# Jedes Jahr einer Reihe laeuft ueber genau denselben Weg wie ein einzeln
# gestarteter Lauf (_laufen() oben, mit eigener Kennung, eigenem Eintrag in
# _AUFTRAEGE und eigener 'simulation'-Zeile) - eine Reihe fuegt nur eine
# duenne Schicht Buchfuehrung drumherum: welches Jahr laeuft gerade, wie
# viele insgesamt, und ein Abbruch-Merker, der VOR jedem naechsten Jahr
# geprueft wird (nicht nur im laufenden). Bestehende Endpunkte
# (GET /api/simulation/<kennung> usw.) funktionieren fuer das aktuell
# laufende Jahr einer Reihe deshalb unveraendert weiter.
# ---------------------------------------------------------------------------

_REIHEN = {}
# Kleiner als _MAX_AUFTRAEGE (siehe dort) - eine Reihe fasst mehrere Jahre,
# es braucht darum insgesamt weit weniger gleichzeitige Reihen als einzelne
# Laeufe, um denselben Arbeitsspeicher zu belegen.
_MAX_REIHEN = 50


def _aufraeumen_reihen():
    """Analog zu _aufraeumen() fuer _AUFTRAEGE - nur unter _SPERRE aufrufen."""
    ueberschuss = len(_REIHEN) - _MAX_REIHEN
    if ueberschuss <= 0:
        return
    for kennung, eintrag in list(_REIHEN.items()):
        if ueberschuss <= 0:
            break
        if eintrag.get("status") in _ABGESCHLOSSEN:
            del _REIHEN[kennung]
            ueberschuss -= 1


def _setze_reihe(kennung, **felder):
    with _SPERRE:
        _REIHEN.setdefault(kennung, {}).update(felder)
        _aufraeumen_reihen()


def _reihe_ergebnis_anhaengen(kennung, eintrag):
    with _SPERRE:
        _REIHEN.setdefault(kennung, {}).setdefault("ergebnisse", []).append(eintrag)


def reihen_stand(reihen_kennung):
    with _SPERRE:
        return dict(_REIHEN.get(reihen_kennung, {"status": "unbekannt"}))


def reihe_abbrechen(reihen_kennung):
    """Bricht eine laufende Reihe ab: das laufende Jahr wird ueber seine
    eigene Kennung wie ein einzelner Lauf abgebrochen (abbrechen() oben,
    greift an der naechsten Stunde), UND das Reihen-eigene Abbruch-Merkmal
    verhindert, dass danach noch ein weiteres Jahr beginnt (siehe
    _reihe_laufen()) - ohne Letzteres liefe die Reihe nach dem abgebrochenen
    Jahr einfach beim naechsten weiter, als waere nichts gewesen."""
    _setze_reihe(reihen_kennung, abbruch=True)
    aktuell = reihen_stand(reihen_kennung).get("aktuelle_kennung")
    if aktuell:
        abbrechen(aktuell)


def _reihe_laufen(app, reihen_kennung, anlage_id, wetterdatensatz_ids, von, bis):
    with app.app_context():
        gesamt = len(wetterdatensatz_ids)
        for index, wetterdatensatz_id in enumerate(wetterdatensatz_ids, start=1):
            # VOR jedem Jahr geprueft, nicht nur einmal am Anfang - genau das
            # verhindert, dass ein waehrend eines laufenden Jahres
            # eingetroffener Abbruch (reihe_abbrechen()) die noch nicht
            # begonnenen Jahre trotzdem startet.
            if reihen_stand(reihen_kennung).get("abbruch"):
                _setze_reihe(reihen_kennung, status="abgebrochen")
                return

            jahr_kennung = uuid.uuid4().hex
            _setze_reihe(
                reihen_kennung, jahr_index=index, jahr_gesamt=gesamt,
                aktuelle_kennung=jahr_kennung,
                aktueller_wetterdatensatz_id=wetterdatensatz_id,
            )
            try:
                # Vorab geprueft statt die rohe Fremdschluesselmeldung von
                # ergebnisse.beginne() abzuwarten (die faengt der except
                # darunter zwar genauso ab, aber mit einem Text, der nicht
                # fuer Benutzer gedacht ist) - z.B. ein Wetterdatensatz, der
                # zwischen der Auswahl im Dialog und dem Start dieses Jahres
                # geloescht wurde.
                if speicher.datensatz(wetterdatensatz_id) is None:
                    raise KeyError(f"Wetterdatensatz {wetterdatensatz_id} gibt es nicht")
                simulation_id = ergebnisse.beginne(
                    anlage_id, wetterdatensatz_id, von, bis, jahr_kennung,
                    reihen_kennung=reihen_kennung, reihen_index=index,
                    reihen_gesamt=gesamt,
                )
            except Exception as fehler:  # noqa: BLE001 - z.B. ein geloeschter/ungueltiger Wetterdatensatz
                # Scheitert ein Jahr schon beim Start, duerfen die uebrigen
                # nicht mit untergehen (siehe Vorhaben B, "Zu bedenken") -
                # dieses Jahr wird als fehlend vermerkt, die Reihe geht mit
                # dem naechsten weiter.
                _reihe_ergebnis_anhaengen(reihen_kennung, {
                    "wetterdatensatz_id": wetterdatensatz_id, "status": "fehler",
                    "fehler": str(fehler), "simulation_id": None,
                })
                continue

            _setze(
                jahr_kennung, status="laeuft", fertig=0, gesamt=max(bis - von, 0),
                abbruch=False, simulation_id=simulation_id,
            )
            _laufen(app, jahr_kennung, simulation_id, anlage_id, wetterdatensatz_id, von, bis)
            ergebnis = stand(jahr_kennung)
            _reihe_ergebnis_anhaengen(reihen_kennung, {
                "wetterdatensatz_id": wetterdatensatz_id,
                "simulation_id": ergebnis.get("simulation_id"),
                "status": ergebnis.get("status"),
                "warnungen": ergebnis.get("warnungen", 0),
                "fehler": ergebnis.get("fehler"),
            })

        _setze_reihe(
            reihen_kennung,
            status="abgebrochen" if reihen_stand(reihen_kennung).get("abbruch") else "fertig",
        )


def starte_reihe(app, anlage_id, wetterdatensatz_ids, von, bis):
    """Startet eine Reihe: ein Lauf je Wetterdatensatz in 'wetterdatensatz_ids',
    nacheinander im Hintergrund, ueber denselben Zeitraum (von/bis). Liefert
    sofort eine Reihen-Kennung, unter der Fortschritt und Abbruch verfolgt
    werden (reihen_stand(), reihe_abbrechen()) - wie starte() fuer einen
    einzelnen Lauf."""
    wetterdatensatz_ids = list(wetterdatensatz_ids)
    reihen_kennung = uuid.uuid4().hex
    _setze_reihe(
        reihen_kennung, status="laeuft", anlage_id=anlage_id, jahr_index=0,
        jahr_gesamt=len(wetterdatensatz_ids), abbruch=False, ergebnisse=[],
        aktuelle_kennung=None, aktueller_wetterdatensatz_id=None,
    )
    faden = threading.Thread(
        target=_reihe_laufen,
        args=(app, reihen_kennung, anlage_id, wetterdatensatz_ids, von, bis),
        daemon=True,
    )
    faden.start()
    return reihen_kennung


def laufende_reihe_auftrag(anlage_id):
    """Fuer die Editorseite nach einem Neuladen: laeuft fuer diese Anlage
    gerade eine Reihe (starte_reihe())? None, wenn nicht.

    Genau wie laufender_auftrag() fuer einen einzelnen Lauf: die Kennung der
    Reihe kommt aus der Datenbank (der gerade laufende Jahreslauf traegt sie
    in seiner 'simulation'-Zeile, core.ergebnisse.laufende_reihe()), der
    ausfuehrliche Stand - welches Jahr, wie viele bereits vorliegende
    Ergebnisse - danach aus _REIHEN, sofern der Dienst seit dem Start der
    Reihe durchgaengig lief.

    Ist _REIHEN inzwischen leer (Dienst neu gestartet), bleibt nur der grobe
    DB-Stand: core.database._aufraeume_verwaiste_laeufe() hat die verwaiste
    'laeuft'-Zeile des zuletzt begonnenen Jahres beim Neustart bereits als
    abgebrochen markiert (siehe dort) - dieselbe Einordnung gilt dann fuer
    die Reihe als Ganzes, ohne dass ihr Rechen-Thread (der mit dem Prozess
    verschwunden ist) das noch selbst melden koennte."""
    zeile = ergebnisse.laufende_reihe(anlage_id)
    if zeile is None:
        return None
    reihen_kennung = zeile["reihen_kennung"]
    im_speicher = reihen_stand(reihen_kennung)
    if im_speicher.get("status") == "unbekannt":
        return {
            "reihen_kennung": reihen_kennung, "status": "abgebrochen",
            "jahr_index": zeile["reihen_index"], "jahr_gesamt": zeile["reihen_gesamt"],
            "aktuelle_kennung": None, "aktueller_wetterdatensatz_id": None,
            "ergebnisse": [],
        }
    return {"reihen_kennung": reihen_kennung, **im_speicher}
