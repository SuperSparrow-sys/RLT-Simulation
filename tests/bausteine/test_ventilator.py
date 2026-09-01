import pytest

from core.bausteine.basis import Luft
from core.bausteine.ventilator import Ventilator


def parameter(**abweichend):
    p = Ventilator.vorgabeparameter()
    p.update(abweichend)
    return p


def test_ventilator_entspricht_der_excel():
    """Anlage!X9:Z21 - Zuluftventilator mit Frequenzumrichter bei 100 %."""
    p = parameter(
        V_max=8200.0, dp_max=1400.0, dp_konst=1400.0, PE_max=4.9, regelart="F"
    )
    ein = {
        "luft_ein": Luft(V=8200.0, T=37.3471794996003, x=0.0),
        "stellgroesse": 100.0,
    }
    aus, _ = Ventilator().berechne(ein, p, {})

    assert aus["luft_aus"].V == pytest.approx(8200.0, rel=1e-12)
    assert aus["dp"] == pytest.approx(1400.0, rel=1e-12)
    assert aus["PE"] == pytest.approx(4.9, rel=1e-9)
    assert aus["luft_aus"].T == pytest.approx(39.127400876789245, rel=1e-10)


def test_wirkungsgrad_entspricht_der_excel():
    """Anlage!Z7 - V_max * dp_max / 3600000 / PE_max."""
    p = parameter(V_max=8200.0, dp_max=1400.0, PE_max=4.9)
    assert Ventilator().wirkungsgrad(p) == pytest.approx(0.6507936507936508, rel=1e-12)


def test_teillast_senkt_volumenstrom_und_druck():
    p = parameter(
        V_max=8200.0, dp_max=1400.0, dp_konst=0.0, PE_max=4.9, regelart="F"
    )
    ein = {"luft_ein": Luft(V=8200.0, T=20.0, x=5.0), "stellgroesse": 50.0}
    aus, _ = Ventilator().berechne(ein, p, {})
    assert aus["luft_aus"].V == pytest.approx(4100.0)
    assert aus["dp"] == pytest.approx(1400.0 * 0.25)


def test_ungeregelter_ventilator_laeuft_mit_nennleistung():
    p = parameter(
        V_max=8200.0, dp_max=1400.0, dp_konst=1400.0, PE_max=4.9, regelart="-"
    )
    ein = {"luft_ein": Luft(V=8200.0, T=20.0, x=5.0), "stellgroesse": 60.0}
    aus, _ = Ventilator().berechne(ein, p, {})
    assert aus["luft_aus"].V == pytest.approx(8200.0)
    assert aus["PE"] == pytest.approx(4.9)


def test_drallregler_hat_grundlast():
    p = parameter(
        V_max=8200.0, dp_max=1400.0, dp_konst=0.0, PE_max=4.9, regelart="D"
    )
    ein = {"luft_ein": Luft(V=8200.0, T=20.0, x=5.0), "stellgroesse": 0.0}
    aus, _ = Ventilator().berechne(ein, p, {})
    assert aus["PE"] == pytest.approx(0.0)


def test_ventilator_bestimmt_den_volumenstrom_im_rueckwaertslauf():
    p = parameter(V_max=8200.0, regelart="F")
    assert Ventilator().bedarf({"luft_aus": 0.0}, p) == {"luft_ein": 8200.0}


def test_ohne_angeschlossenen_regler_gilt_die_feste_stellgroesse():
    """Anlage!Y16 - in der Excel ist die Stellgroesse des Ventilators eine Konstante."""
    p = parameter(
        V_max=8200.0, dp_max=1400.0, dp_konst=1400.0, PE_max=4.9,
        regelart="F", stellgroesse=100.0,
    )
    aus, _ = Ventilator().berechne({"luft_ein": Luft(V=8200.0, T=20.0, x=5.0)}, p, {})
    assert aus["PE"] == pytest.approx(4.9, rel=1e-9)
    assert aus["luft_aus"].V == pytest.approx(8200.0)


def test_abluftrolle_vergibt_abluftports():
    p = parameter(rolle="abluft")
    rollen = {port.schluessel: port.rolle for port in Ventilator.ports_fuer(p)}
    assert rollen["luft_ein"] == "abluft"
    assert rollen["luft_aus"] == "abluft"
