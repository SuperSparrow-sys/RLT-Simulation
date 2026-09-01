import pytest

from core.bausteine.aussenluft import Aussenluft
from core.bausteine.wetterkarte import Wetterkarte


def test_wetterkarte_gibt_die_werte_der_aktuellen_stunde_aus():
    zustand = {
        "stunde": {
            "t_au": 2.5, "x_au": 4.4,
            "str_s": 10.0, "str_o": 20.0, "str_w": 30.0,
            "str_n": 40.0, "str_h": 50.0,
        }
    }
    aus, _ = Wetterkarte().berechne({}, {}, zustand)
    assert aus["T_AU"] == 2.5
    assert aus["F_AU"] == 4.4
    assert aus["QH_S"] == 10.0
    assert aus["QH_H"] == 50.0


def test_wetterkarte_ohne_stunde_liefert_nullen():
    aus, _ = Wetterkarte().berechne({}, {}, {})
    assert aus["T_AU"] == 0.0
    assert aus["QH_S"] == 0.0


def test_fortluft_meldet_den_ankommenden_zustand():
    from core.bausteine.basis import Luft
    from core.bausteine.fortluft import Fortluft

    aus, _ = Fortluft().berechne({"luft_ein": Luft(V=9000.0, T=3.61, x=4.2)}, {}, {})
    assert aus["V"] == pytest.approx(9000.0)
    assert aus["T_FO"] == pytest.approx(3.61)
    assert aus["F_FO"] == pytest.approx(4.2)


def test_fortluft_fordert_keinen_volumenstrom_an():
    """Der Endpunkt eines Abluftwegs gibt nichts weiter nach vorn."""
    from core.bausteine.fortluft import Fortluft

    assert Fortluft().bedarf({}, {}) == {}


def test_aussenluft_baut_den_luftzustand_aus_den_signalen():
    ein = {"T_AU": 2.5, "F_AU": 4.4}
    aus, _ = Aussenluft().berechne(ein, {}, {})
    assert aus["luft_aus"].T == pytest.approx(2.5)
    assert aus["luft_aus"].x == pytest.approx(4.4)


def test_aussenluft_reicht_den_geforderten_volumenstrom_durch():
    aus, _ = Aussenluft().berechne(
        {"T_AU": 2.5, "F_AU": 4.4}, {}, {"bedarf": 12200.0}
    )
    assert aus["luft_aus"].V == pytest.approx(12200.0)
