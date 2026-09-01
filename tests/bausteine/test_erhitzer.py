import pytest

from core.bausteine.basis import Luft
from core.bausteine.erhitzer import Erhitzer


def parameter(**abweichend):
    p = Erhitzer.vorgabeparameter()
    p.update(abweichend)
    return p


def test_erhitzer_entspricht_der_excel():
    """Anlage!L9:N21 - Erhitzer 1 der ersten Anlage."""
    p = parameter(V_nenn=12200.0, dp_nenn=30.0, QH_max=27.0)
    ein = {
        "luft_ein": Luft(V=12200.0, T=12.614754098360613, x=0.0),
        "stellgroesse": 96.84604938271573,
    }
    aus, _ = Erhitzer().berechne(ein, p, {})
    assert aus["QH"] == pytest.approx(26.148433333333248, rel=1e-12)
    assert aus["luft_aus"].T == pytest.approx(18.999999999999936, rel=1e-12)
    assert aus["luft_aus"].x == 0.0
    assert aus["luft_aus"].dp == pytest.approx(30.0, rel=1e-12)


def test_erhitzer_bei_stellgroesse_null_veraendert_nichts():
    p = parameter(V_nenn=12200.0, dp_nenn=30.0, QH_max=27.0)
    ein = {"luft_ein": Luft(V=12200.0, T=5.0, x=3.0), "stellgroesse": 0.0}
    aus, _ = Erhitzer().berechne(ein, p, {})
    assert aus["QH"] == 0.0
    assert aus["luft_aus"].T == pytest.approx(5.0)


def test_erhitzer_ohne_volumenstrom_heizt_nicht():
    p = parameter(V_nenn=12200.0, dp_nenn=30.0, QH_max=27.0)
    ein = {"luft_ein": Luft(V=0.0, T=5.0, x=3.0), "stellgroesse": 100.0}
    aus, _ = Erhitzer().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(5.0)


def test_druckverlust_steigt_quadratisch_mit_dem_volumenstrom():
    p = parameter(V_nenn=12200.0, dp_nenn=30.0, QH_max=27.0)
    ein = {"luft_ein": Luft(V=6100.0, T=5.0, x=3.0), "stellgroesse": 0.0}
    aus, _ = Erhitzer().berechne(ein, p, {})
    assert aus["luft_aus"].dp == pytest.approx(30.0 * 0.25)
