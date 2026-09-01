"""Simulationslaeufe im Hintergrund, mit Fortschritt und Abbruch."""

import threading
import time
import uuid

from core import anlagen, ergebnisse, solver
from core.wetter import speicher

_AUFTRAEGE = {}
_SPERRE = threading.Lock()


def _setze(kennung, **felder):
    with _SPERRE:
        _AUFTRAEGE.setdefault(kennung, {}).update(felder)


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
            abgebrochen = bool(stand(kennung).get("abbruch"))
            simulation_id = ergebnisse.speichere(
                anlage_id, wetterdatensatz_id, von, bis, lauf,
                dauer=time.time() - begonnen,
                status="abgebrochen" if abgebrochen else "fertig",
            )
            _setze(
                kennung,
                status="abgebrochen" if abgebrochen else "fertig",
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
