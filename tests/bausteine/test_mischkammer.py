import pytest

from core.bausteine.basis import Luft
from core.bausteine.mischkammer import Mischkammer


def test_mischt_nach_umluftanteil():
    p = {"max_umluft": 80.0}
    ein = {
        "aussenluft_ein": Luft(V=7000.0, T=0.0, x=2.0),
        "umluft_ein": Luft(V=3000.0, T=20.0, x=10.0),
        "umluftanteil": 30.0,
    }
    aus, _ = Mischkammer().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(6.0)
    assert aus["luft_aus"].x == pytest.approx(0.7 * 2.0 + 0.3 * 10.0)


def test_umluftanteil_wird_auf_das_maximum_begrenzt():
    p = {"max_umluft": 40.0}
    ein = {
        "aussenluft_ein": Luft(V=7000.0, T=0.0, x=0.0),
        "umluft_ein": Luft(V=3000.0, T=20.0, x=0.0),
        "umluftanteil": 90.0,
    }
    aus, _ = Mischkammer().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(0.4 * 20.0)


def test_ohne_umluft_bleibt_die_aussenluft_unveraendert():
    p = {"max_umluft": 80.0}
    ein = {
        "aussenluft_ein": Luft(V=10000.0, T=-5.0, x=1.5),
        "umluft_ein": Luft(V=0.0, T=20.0, x=10.0),
        "umluftanteil": 0.0,
    }
    aus, _ = Mischkammer().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(-5.0)
    assert aus["luft_aus"].x == pytest.approx(1.5)
