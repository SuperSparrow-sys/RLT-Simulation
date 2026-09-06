"""Das Konvergenzmaß muss für große Anlagen dasselbe bedeuten wie für kleine.

Der Solver bricht die Iteration ab, wenn sich nichts mehr ändert. Für
Temperaturen misst er in Kelvin, für Volumenströme in Tausend m³/h. Beides
absolut - und genau daran hakt es bei den Volumenströmen: Die Schranke
MAX_AENDERUNG von 0,001 heißt für eine Anlage mit 5000 m³/h eine relative
Genauigkeit von 2·10⁻⁷, für eine mit 25 000 m³/h aber 4·10⁻⁸. Dieselbe
Anlage, fünfmal größer gebaut, müsste fünfmal genauer einschwingen.

Aufgefallen an der Vorlage „Rechenzentrum" (25 000 m³/h): Ihr Umluftstrom
pendelte sich auf 8 Promille genau ein - für jede praktische Frage genug,
für die absolute Schranke aber nicht. Temperaturen und Feuchten bleiben
absolut, weil ein halbes Kelvin ein halbes Kelvin ist, egal wie groß die
Anlage ist.
"""

import pytest

from core import solver
from core.bausteine.basis import Luft


def abweichung(alt_v, neu_v):
    s = solver.Solver.__new__(solver.Solver)
    return solver.Solver._abweichung(
        s, {1: {"luft": Luft(V=alt_v, T=20.0, x=8.0)}},
        {1: {"luft": Luft(V=neu_v, T=20.0, x=8.0)}},
    )


def test_gleiche_relative_aenderung_gibt_gleiche_abweichung():
    """Ein Promille Änderung ist ein Promille - bei 5000 wie bei 25 000 m³/h."""
    klein = abweichung(5000.0, 5005.0)
    gross = abweichung(25000.0, 25025.0)
    assert klein == pytest.approx(gross, rel=0.01)


def test_kleine_anlagen_bleiben_beim_bisherigen_massstab():
    """Unterhalb von 1000 m³/h bleibt das Maß absolut - sonst würde ein
    Nebenstrang mit 50 m³/h an eine unerreichbar feine Schranke geraten."""
    assert abweichung(500.0, 501.0) == pytest.approx(0.001, rel=0.01)


def test_temperatur_bleibt_absolut():
    """Ein Kelvin ist ein Kelvin - unabhängig von der Größe der Anlage."""
    s = solver.Solver.__new__(solver.Solver)
    fuer = lambda t1, t2: solver.Solver._abweichung(
        s, {1: {"luft": Luft(V=25000.0, T=t1, x=8.0)}},
        {1: {"luft": Luft(V=25000.0, T=t2, x=8.0)}},
    )
    assert fuer(20.0, 20.5) == pytest.approx(0.5)
    assert fuer(20.0, 21.0) == pytest.approx(1.0)


def test_unveraenderter_volumenstrom_bleibt_null():
    """Die Anlagen, die durchgehend auf Nennstrom fahren - AX_SIM 2.1 etwa -
    sehen von dieser Änderung nichts: null bleibt null."""
    assert abweichung(12200.0, 12200.0) == 0.0


def test_mitgeschriebene_volumenstroeme_zaehlen_nicht_wie_kelvin():
    """Der Solver schreibt zu jedem Lufteingang 'V_<name>' als reine Zahl mit,
    damit sie im Protokoll erscheint (core/solver.py, „Eingangsgroessen
    mitschreiben"). Im Abweichungsmaß landeten diese Zahlen bisher im Zweig für
    gewöhnliche Zahlen - eine Änderung um 1 m³/h zählte damit so viel wie eine
    um 1 Kelvin.

    Gefunden an der Vorlage „Rechenzentrum": Ihr Umluftstrom pendelte sich auf
    2 m³/h von 15 000 genau ein - vier Zehntausendstel. Gemeldet wurde eine
    Restabweichung von 2,06, also mehr als die Schwelle, ab der eine Rechnung
    als nicht eingeschwungen gilt.
    """
    s = solver.Solver.__new__(solver.Solver)
    abw = solver.Solver._abweichung(
        s,
        {1: {"V_umluft_ein": 15000.0, "T_umluft_ein": 22.0}},
        {1: {"V_umluft_ein": 15002.0, "T_umluft_ein": 22.0}},
    )
    assert abw < 0.01, (
        f"2 m³/h von 15 000 ergeben eine Abweichung von {abw:.4f} - "
        f"das ist der Maßstab für Kelvin, nicht für Volumenströme"
    )


def test_eine_echte_temperaturabweichung_wird_weiter_gesehen():
    """Gegenprobe: Die Lockerung darf nur Volumenströme betreffen."""
    s = solver.Solver.__new__(solver.Solver)
    abw = solver.Solver._abweichung(
        s,
        {1: {"V_umluft_ein": 15000.0, "T_umluft_ein": 22.0}},
        {1: {"V_umluft_ein": 15000.0, "T_umluft_ein": 25.0}},
    )
    assert abw == pytest.approx(3.0)


def test_auch_der_schlichte_schluessel_V_gilt_als_volumenstrom():
    """Die Außenluft- und die Fortluftkarte nennen ihren Volumenstrom schlicht
    „V", nicht „V_irgendwas". Ein Muster, das nur „V_" erkennt, lässt gerade
    die Quelle und die Senke der ganzen Anlage durchfallen.

    Gefunden an der Vorlage „Rechenzentrum": Der Außenluftstrom pendelte sich
    auf 4 m³/h von 25 000 genau ein - anderthalb Zehntausendstel. Gemeldet
    wurde eine Restabweichung von 4,29.
    """
    s = solver.Solver.__new__(solver.Solver)
    abw = solver.Solver._abweichung(
        s, {1: {"V": 25000.0}}, {1: {"V": 25004.0}},
    )
    assert abw < 0.01, f"4 m³/h von 25 000 ergeben {abw:.4f}"


def test_eine_gewoehnliche_zahl_bleibt_absolut():
    """Gegenprobe: Stellgrößen, Leistungen und Regelabweichungen werden
    weiterhin absolut gemessen."""
    s = solver.Solver.__new__(solver.Solver)
    abw = solver.Solver._abweichung(
        s, {1: {"QH": 25000.0}}, {1: {"QH": 25004.0}},
    )
    assert abw == pytest.approx(4.0)
