import pytest

from core.bausteine.faktor import Faktor
from core.bausteine.maximalwert import Maximalwert
from core.bausteine.umkehrglied import Umkehrglied


def test_maximalwert_nimmt_den_groessten_eingang():
    """Anlage!S16 = MAX(100-S61; S72) - zwei Regler stellen ein Ventil."""
    aus, _ = Maximalwert().berechne({"ein_1": 30.0, "ein_2": 75.0}, {}, {})
    assert aus["ausgang"] == pytest.approx(75.0)


def test_maximalwert_ohne_eingang_ist_null():
    aus, _ = Maximalwert().berechne({}, {}, {})
    assert aus["ausgang"] == 0.0


def test_maximalwert_ist_unabhaengig_von_der_eingangsnummer():
    """Kein Parameter kennt 'ein_1' oder 'ein_2' - die Karte ist symmetrisch.

    Welcher Regler an welcher Nummer landet, haengt von der Reihenfolge ab, in der
    die Pfeile beim Bauen angelegt werden (core/graph.py) - das darf das Ergebnis
    nicht veraendern. Die Umkehrung eines Eingangs erledigt ein vorgeschaltetes
    Umkehrglied, nicht das Maximalglied selbst.
    """
    a, _ = Maximalwert().berechne({"ein_1": 70.0, "ein_2": 20.0}, {}, {})
    b, _ = Maximalwert().berechne({"ein_1": 20.0, "ein_2": 70.0}, {}, {})
    assert a["ausgang"] == b["ausgang"] == pytest.approx(70.0)


def test_faktor_skaliert_und_begrenzt():
    """Anlage!V16 - IF(Waescher=100; 50; 0) ist 0,5 mal das Waeschersignal."""
    aus, _ = Faktor().berechne({"ein": 100.0}, {"faktor": 0.5}, {})
    assert aus["ausgang"] == pytest.approx(50.0)

    aus, _ = Faktor().berechne({"ein": 0.0}, {"faktor": 0.5}, {})
    assert aus["ausgang"] == pytest.approx(0.0)


def test_umkehrglied_spiegelt_gegen_den_bezugswert():
    """Anlage!S16 = MAX(100-S61; S72) - der Entfeuchtungsregler zaehlt umgekehrt."""
    aus, _ = Umkehrglied().berechne({"ein": 30.0}, {"bezug": 100.0}, {})
    assert aus["ausgang"] == pytest.approx(70.0)


def test_umkehrglied_begrenzt_auf_0_bis_100():
    aus, _ = Umkehrglied().berechne({"ein": 150.0}, {"bezug": 100.0}, {})
    assert aus["ausgang"] == pytest.approx(0.0)

    aus, _ = Umkehrglied().berechne({"ein": -50.0}, {"bezug": 100.0}, {})
    assert aus["ausgang"] == pytest.approx(100.0)


def test_umkehrglied_und_maximalwert_bilden_die_kuehlerformel():
    """Anlage!S16 = MAX(100-S61; S72), end-to-end aus zwei Bausteinen zusammengesetzt.

    Das ist der eigentliche Nachweis: die Komposition muss unabhaengig davon
    stimmen, welcher der beiden Pfeile beim Bau zuerst ankam - das Maximalglied
    kennt seine Eingaenge nicht mehr namentlich.
    """
    entfeuchter = 30.0
    kuehler = 20.0
    umkehr, _ = Umkehrglied().berechne({"ein": entfeuchter}, {"bezug": 100.0}, {})
    aus, _ = Maximalwert().berechne(
        {"ein_1": umkehr["ausgang"], "ein_2": kuehler}, {}, {}
    )
    assert aus["ausgang"] == pytest.approx(70.0)

    entfeuchter = 90.0
    umkehr, _ = Umkehrglied().berechne({"ein": entfeuchter}, {"bezug": 100.0}, {})
    aus, _ = Maximalwert().berechne(
        {"ein_1": umkehr["ausgang"], "ein_2": kuehler}, {}, {}
    )
    assert aus["ausgang"] == pytest.approx(20.0)
