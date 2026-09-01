import pytest

from core.bausteine.faktor import Faktor
from core.bausteine.maximalwert import Maximalwert


def test_maximalwert_nimmt_den_groessten_eingang():
    """Anlage!S16 = MAX(100-S61; S72) - zwei Regler stellen ein Ventil."""
    aus, _ = Maximalwert().berechne({"ein_1": 30.0, "ein_2": 75.0}, {}, {})
    assert aus["ausgang"] == pytest.approx(75.0)


def test_maximalwert_ohne_eingang_ist_null():
    aus, _ = Maximalwert().berechne({}, {}, {})
    assert aus["ausgang"] == 0.0


def test_maximalwert_kann_einen_eingang_invertieren():
    """Der Entfeuchtungsregler geht in der Excel als 100 - Ausgang ein."""
    p = {"invertiert": ["ein_1"]}
    aus, _ = Maximalwert().berechne({"ein_1": 30.0, "ein_2": 55.0}, p, {})
    assert aus["ausgang"] == pytest.approx(70.0)


def test_faktor_skaliert_und_begrenzt():
    """Anlage!V16 - IF(Waescher=100; 50; 0) ist 0,5 mal das Waeschersignal."""
    aus, _ = Faktor().berechne({"ein": 100.0}, {"faktor": 0.5}, {})
    assert aus["ausgang"] == pytest.approx(50.0)

    aus, _ = Faktor().berechne({"ein": 0.0}, {"faktor": 0.5}, {})
    assert aus["ausgang"] == pytest.approx(0.0)
