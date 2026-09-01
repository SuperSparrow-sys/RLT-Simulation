"""Simulationslaeufe im Hintergrund, mit Fortschritt und Abbruch."""

import threading
import time
import uuid

from core import anlagen, ergebnisse, solver
from core.wetter import speicher

_AUFTRAEGE = {}
_SPERRE = threading.Lock()

# Abgeschlossene Auftraege bleiben nur begrenzt im Speicher - sonst waechst
# _AUFTRAEGE ueber die Lebenszeit des Prozesses unbegrenzt. Kein Verfallsdatum,
# keine eigene Aufraeum-Infrastruktur: einfach die aeltesten abgeschlossenen
# Eintraege verwerfen, sobald es zu viele werden.
_MAX_AUFTRAEGE = 200
_ABGESCHLOSSEN = ("fertig", "abgebrochen", "fehler")


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


def _laufen(app, kennung, anlage_id, wetterdatensatz_id, von, bis):
    with app.app_context():
        begonnen = time.time()
        try:
            stunden = speicher.lade_stunden(wetterdatensatz_id, von, bis)
            graph = anlagen.lade_graph(anlage_id)

            def fortschritt(nummer, gesamt):
                _setze(kennung, fertig=nummer, gesamt=gesamt)

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
            simulation_id = ergebnisse.speichere(
                anlage_id, wetterdatensatz_id, von, bis, lauf, graph,
                dauer=time.time() - begonnen,
                status=status,
            )
            _setze(
                kennung,
                status=status,
                simulation_id=simulation_id,
                warnungen=len(lauf.warnungen),
                dauer=time.time() - begonnen,
            )
        except Exception as fehler:  # noqa: BLE001 - der Lauf darf die App nicht kippen
            _setze(kennung, status="fehler", fehler=str(fehler))


def starte(app, anlage_id, wetterdatensatz_id, von, bis):
    kennung = uuid.uuid4().hex
    _setze(
        kennung,
        status="laeuft", fertig=0, gesamt=max(bis - von, 0),
        abbruch=False, simulation_id=0,
    )
    faden = threading.Thread(
        target=_laufen,
        args=(app, kennung, anlage_id, wetterdatensatz_id, von, bis),
        daemon=True,
    )
    faden.start()
    return kennung
