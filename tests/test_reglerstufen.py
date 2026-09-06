"""Ein Sequenzregler darf nur so weit integrieren, wie er Stufen hat.

Kaskade und Sequenzregler staffeln ihre Regelabweichung über fünf Ausgänge:
drei zum Wärmen, zwei zum Kühlen. Jeder deckt hundert Einheiten ab, die
Abweichung lief deshalb von −300 bis +200.

Verdrahtet werden aber selten alle fünf. Eine Anlage mit einem Kühler nutzt
kaelter_1, also den Bereich 0 bis 100 - der Regler integrierte trotzdem bis
200 weiter, in einen Bereich, den niemand hört. Danach musste er ihn
zurückwandern, bevor die Kühlung überhaupt reagierte. Gemessen über zwei
Wochen:

    Bürogebäude    e bis 164,6 bei wirksam 100  ->  64,6 Leerweg
    Rechenzentrum  e bis 200,0 bei wirksam 100  -> 100,0 Leerweg (am Anschlag)

Das ist Windup im Wortsinn: Der Integrator lädt sich in einen wirkungslosen
Bereich auf. Die Karten bekommen deshalb zwei Parameter, mit denen die Anlage
sagt, wie viele Stufen sie wirklich fährt. Die Vorgabe deckt weiterhin alle
fünf ab - vorhandene Anlagen rechnen unverändert.
"""

import pytest

from core.bausteine import lade_alle
from core.bausteine.basis import hole

lade_alle()

GRUND = {
    "T_Raum_min": 20.0, "T_AU_min": 15.0, "T_Raum_max": 26.0, "T_AU_max": 30.0,
    "T_ZU_min": 16.0, "T_ZU_max": 28.0, "xp": 5.0,
}


def kaskade_lauf(parameter, T_Raum, durchgaenge=400, T_ZU=22.0):
    """Laesst die Kaskade auf ihren Endwert laufen und gibt e zurueck."""
    karte = hole("kaskade")()
    zustand = {"e": 0.0}
    for _ in range(durchgaenge):
        werte, zustand = karte.berechne(
            {"T_AU": 25.0, "T_Raum": T_Raum, "T_ZU": T_ZU},
            dict(GRUND, **parameter), zustand,
        )
    return werte["e"], werte


def test_ohne_angabe_bleibt_der_bisherige_bereich():
    """Vorhandene Anlagen dürfen sich nicht ändern."""
    e, _ = kaskade_lauf({}, T_Raum=40.0)
    assert e == pytest.approx(200.0)
    e, _ = kaskade_lauf({}, T_Raum=0.0)
    assert e == pytest.approx(-300.0)


def test_mit_einer_kuehlstufe_endet_die_abweichung_bei_hundert():
    """Der gemessene Fall: ein Kühler, also kaelter_1 - mehr gibt es nicht."""
    e, _ = kaskade_lauf({"kaeltestufen": 1}, T_Raum=40.0)
    assert e == pytest.approx(100.0)


def test_mit_zwei_waermestufen_endet_sie_bei_minus_zweihundert():
    e, _ = kaskade_lauf({"waermestufen": 2}, T_Raum=0.0)
    assert e == pytest.approx(-200.0)


def test_die_begrenzte_stufe_erreicht_trotzdem_volle_stellung():
    """Der Zweck der Begrenzung ist der Leerweg, nicht die Leistung: Die
    letzte genutzte Stufe muss weiterhin auf 100 % kommen."""
    _, werte = kaskade_lauf({"kaeltestufen": 1}, T_Raum=40.0)
    assert werte["kaelter_1"] == pytest.approx(100.0)


def test_nicht_gefahrene_stufen_bleiben_auf_null():
    """Sonst stünde an einem Ausgang eine Anforderung, die die Anlage nicht
    bedienen kann - und die Bilanz zeigte Leistung, die es nicht gibt."""
    _, werte = kaskade_lauf({"kaeltestufen": 1}, T_Raum=40.0)
    assert werte["kaelter_2"] == pytest.approx(0.0)


def test_der_weg_zurueck_ist_kuerzer():
    """Der eigentliche Gewinn: Nach einem warmen Tag muss der Regler weniger
    zurückwandern, bevor die Kühlung reagiert."""
    karte = hole("kaskade")()

    def zurueck(parameter):
        # erst voll aufheizen, dann Raum auf Sollwert - wieviele Durchgänge,
        # bis die Kühlung wieder schliesst?
        zustand = {"e": 0.0}
        for _ in range(400):
            _, zustand = karte.berechne(
                {"T_AU": 25.0, "T_Raum": 40.0, "T_ZU": 22.0},
                dict(GRUND, **parameter), zustand)
        for durchgang in range(1, 500):
            werte, zustand = karte.berechne(
                {"T_AU": 25.0, "T_Raum": 22.0, "T_ZU": 22.0},
                dict(GRUND, **parameter), zustand)
            if werte["kaelter_1"] < 99.0:
                return durchgang
        return 500

    assert zurueck({"kaeltestufen": 1}) < zurueck({})


def test_der_sequenzregler_kennt_dieselben_stufen():
    karte = hole("sequenzregler")()
    zustand = {"e": 0.0}
    for _ in range(400):
        werte, zustand = karte.berechne(
            {"istwert": 40.0},
            {"oberer_sw": 24.0, "unterer_sw": 20.0, "xp": 5.0, "kaeltestufen": 1},
            zustand)
    assert werte["e"] == pytest.approx(100.0)
