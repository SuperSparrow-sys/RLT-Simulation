"""Ein Takt ist ein Takt - kein Zahlenrauschen knapp über der Schranke.

Der Solver erkennt, wenn die Rechnung zwischen zwei Zuständen pendelt statt
sich einem zu nähern, und weist dann deren Mittel aus. Das ist richtig für
einen Zweipunktregler, dessen Stellglied bei jedem Durchgang voll umschlägt -
sein Ausschlag beträgt viele Kelvin.

Gemeldet wurde es aber auch, wenn die beiden Zustände sich um drei Tausendstel
Kelvin unterschieden. Dann ist die Rechnung praktisch eingeschwungen, das
Mittel beider Zustände ist von jedem einzelnen nicht zu unterscheiden, und die
Meldung „eine Zweipunktregelung taktet" führt in die Irre - sie steht in der
Anlagenprüfung neben echten Grenzzyklen und lässt eine gesunde Anlage
durchfallen.

Gefunden an der Vorlage „Verkaufsraum": eine Stunde mit einem Ausschlag von
0,0033 K wurde als taktende Zweipunktregelung ausgewiesen.
"""

import pytest

from core import config, solver


def test_ein_winziges_pendeln_gilt_nicht_als_takt():
    assert solver.TAKT_MINDESTAUSSCHLAG > config.MAX_AENDERUNG, (
        "Der Mindestausschlag muss über der Konvergenzschranke liegen, sonst "
        "trennt er nichts"
    )


def test_der_mindestausschlag_bleibt_deutlich_unter_einem_echten_takt():
    """Ein Luftwäscher oder ein Heizregister, das voll umschlägt, bewegt die
    Temperatur um Kelvin - der Schwellwert darf so etwas nie verschlucken."""
    assert solver.TAKT_MINDESTAUSSCHLAG < 1.0


def test_zweitakt_mit_grossem_ausschlag_wird_weiterhin_gemeldet(monkeypatch):
    """Gegenprobe an der Vorlage, die dafür gebaut ist: AX_SIM 2.1 hat einen
    Luftwäscher mit schmaler Schaltdifferenz - dort taktet es wirklich."""
    from core.bausteine.basis import Luft

    # Zwei Zustände, die um 8 K auseinanderliegen - ein echter Zweitakt.
    s = solver.Solver.__new__(solver.Solver)
    gross = solver.Solver._abweichung(
        s, {1: {"luft": Luft(V=5000.0, T=20.0, x=8.0)}},
        {1: {"luft": Luft(V=5000.0, T=28.0, x=8.0)}},
    )
    assert gross > solver.TAKT_MINDESTAUSSCHLAG
