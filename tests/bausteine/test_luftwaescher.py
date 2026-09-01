import pytest

from core.bausteine.basis import Luft
from core.bausteine.luftwaescher import Luftwaescher


def parameter(**abweichend):
    p = Luftwaescher.vorgabeparameter()
    p.update(abweichend)
    return p


def test_luftwaescher_entspricht_der_excel():
    """Anlage!AA31:AC43 - dieser Block ist im gespeicherten Zustand konsistent."""
    p = parameter(
        V_nenn=4000.0, dp_nenn=50.0, absalzverlust=10.0, pumpenart="H"
    )
    ein = {
        "luft_ein": Luft(V=4000.0, T=37.76861966236339, x=0.0),
        "stellgroesse": 100.0,
    }
    aus, _ = Luftwaescher().berechne(ein, p, {})

    assert aus["luft_aus"].T == pytest.approx(15.839048772668132, rel=1e-12)
    assert aus["luft_aus"].x == pytest.approx(8.747590530135225, rel=1e-12)
    assert aus["wasser"] == pytest.approx(46.18727799911399, rel=1e-12)
    assert aus["PE_Pumpe"] == pytest.approx(0.17777777777777778, rel=1e-12)
    assert aus["luft_aus"].dp == pytest.approx(50.0, rel=1e-12)


def test_bei_stellgroesse_null_bleibt_die_luft_unveraendert():
    p = parameter(V_nenn=4000.0, dp_nenn=50.0, pumpenart="H")
    ein = {"luft_ein": Luft(V=4000.0, T=30.0, x=6.0), "stellgroesse": 0.0}
    aus, _ = Luftwaescher().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(30.0)
    assert aus["luft_aus"].x == pytest.approx(6.0)
    assert aus["wasser"] == pytest.approx(0.0)


def test_befeuchtung_kuehlt_die_luft_ab():
    p = parameter(V_nenn=4000.0, dp_nenn=50.0, pumpenart="H")
    ein = {"luft_ein": Luft(V=4000.0, T=32.0, x=5.0), "stellgroesse": 100.0}
    aus, _ = Luftwaescher().berechne(ein, p, {})
    assert aus["luft_aus"].T < 32.0
    assert aus["luft_aus"].x > 5.0
