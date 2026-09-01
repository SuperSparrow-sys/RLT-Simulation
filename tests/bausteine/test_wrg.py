import pytest

from core.bausteine.basis import Luft
from core.bausteine.wrg import Waermerueckgewinnung


def parameter(**abweichend):
    p = Waermerueckgewinnung.vorgabeparameter()
    p.update(abweichend)
    return p


def test_wrg_entspricht_der_excel():
    """Anlage!I9:K21 - dieser Block ist im gespeicherten Zustand konsistent."""
    p = parameter(
        V_nenn=12200.0,
        dp_WRG_nenn=170.0,
        dp_Bypass_nenn=50.0,
        rueckwaermzahl=81.0,
        rueckfeuchtzahl=0.0,
    )
    ein = {
        "zuluft_ein": Luft(V=12200.0, T=0.0, x=0.0),
        "abluft_ein": Luft(V=10000.0, T=18.999999999999936, x=0.0),
        "stellgroesse": 100.0,
        "stellgroesse_bypass": 0.0,
    }
    aus, _ = Waermerueckgewinnung().berechne(ein, p, {})

    assert aus["zuluft_aus"].T == pytest.approx(12.614754098360613, rel=1e-12)
    assert aus["abluft_aus"].T == pytest.approx(3.6099999999999888, rel=1e-10)
    assert aus["Q_WRG"] == pytest.approx(51.659099999999825, rel=1e-10)
    assert aus["zuluft_aus"].dp == pytest.approx(170.0, rel=1e-12)
    assert aus["abluft_aus"].dp == pytest.approx(114.21660843859178, rel=1e-12)


def test_wrg_ohne_abluft_uebertraegt_nichts():
    p = parameter(rueckwaermzahl=81.0)
    ein = {
        "zuluft_ein": Luft(V=12200.0, T=0.0, x=0.0),
        "abluft_ein": Luft(V=0.0, T=20.0, x=8.0),
        "stellgroesse": 100.0,
        "stellgroesse_bypass": 0.0,
    }
    aus, _ = Waermerueckgewinnung().berechne(ein, p, {})
    assert aus["zuluft_aus"].T == pytest.approx(0.0)
    assert aus["Q_WRG"] == pytest.approx(0.0)


def test_geoeffneter_bypass_schaltet_die_rueckgewinnung_ab():
    p = parameter(V_nenn=12200.0, rueckwaermzahl=81.0)
    ein = {
        "zuluft_ein": Luft(V=12200.0, T=0.0, x=0.0),
        "abluft_ein": Luft(V=12200.0, T=20.0, x=8.0),
        "stellgroesse": 100.0,
        "stellgroesse_bypass": 100.0,
    }
    aus, _ = Waermerueckgewinnung().berechne(ein, p, {})
    assert aus["zuluft_aus"].T == pytest.approx(0.0)


def test_rueckfeuchtzahl_uebertraegt_feuchte():
    p = parameter(V_nenn=10000.0, rueckwaermzahl=0.0, rueckfeuchtzahl=50.0)
    ein = {
        "zuluft_ein": Luft(V=10000.0, T=0.0, x=2.0),
        "abluft_ein": Luft(V=10000.0, T=20.0, x=10.0),
        "stellgroesse": 100.0,
        "stellgroesse_bypass": 0.0,
    }
    aus, _ = Waermerueckgewinnung().berechne(ein, p, {})
    assert aus["zuluft_aus"].x == pytest.approx(2.0 + 0.5 * 8.0)
