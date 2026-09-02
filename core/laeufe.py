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
