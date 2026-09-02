import pytest

from core.bausteine import stoffdaten as st
from core.bausteine.basis import Luft
from core.bausteine.kuehler import Kuehler


def parameter(**abweichend):
    p = Kuehler.vorgabeparameter()
    p.update(abweichend)
    return p


def test_kuehler_bei_stellgroesse_null_entspricht_der_excel():
    """Anlage!R9:T21 - der Kuehler steht im gespeicherten Zustand auf 0 %."""
    p = parameter(V_nenn=8200.0, dp_nenn=240.0, QK_nenn=63.0, T_KW_mittel=6.0)
    ein = {
        "luft_ein": Luft(V=8200.0, T=18.999999999999936, x=0.0),
        "stellgroesse": 0.0,
    }
    aus, _ = Kuehler().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(18.999999999999936, rel=1e-12)
    assert aus["QK"] == pytest.approx(0.0, abs=1e-12)
    assert aus["luft_aus"].dp == pytest.approx(240.0)


def test_oberflaechentemperatur_liegt_zwischen_kaltwasser_und_eintritt():
    p = parameter(T_KW_mittel=6.0)
    assert Kuehler().oberflaechentemperatur(30.0, p) == pytest.approx(6.0 + 0.15 * 24.0)


def test_kuehler_entfeuchtet_bis_zur_saettigung_der_oberflaeche():
    p = parameter(V_nenn=8200.0, dp_nenn=240.0, QK_nenn=250.0, T_KW_mittel=6.0)
    ein = {"luft_ein": Luft(V=8200.0, T=30.0, x=12.0), "stellgroesse": 80.0}
    aus, _ = Kuehler().berechne(ein, p, {})

    T_O = 6.0 + 0.15 * (30.0 - 6.0)
    assert aus["luft_aus"].T == pytest.approx(30.0 - 0.8 * (30.0 - T_O))
    assert aus["luft_aus"].x == pytest.approx(12.0 - 0.8 * (12.0 - st.x_saett(T_O)))
    assert aus["luft_aus"].x < 12.0


def test_kuehler_entfeuchtet_nicht_bei_trockener_luft():
    p = parameter(V_nenn=8200.0, dp_nenn=240.0, QK_nenn=250.0, T_KW_mittel=6.0)
    ein = {"luft_ein": Luft(V=8200.0, T=30.0, x=2.0), "stellgroesse": 80.0}
    aus, _ = Kuehler().berechne(ein, p, {})
    assert aus["luft_aus"].x == pytest.approx(2.0)


def test_kuehler_rechnet_den_zustand_auch_ohne_volumenstrom():
    """Absichtlich wie in der Excel.

    Anlage!AB131 rechnet T_aus ohne Volumenstrompruefung, weil dort nicht durch V
    geteilt wird; nur die Leistung AB133 wird bei V <= 0 zu null. Der Erhitzer
    (Anlage!S131) braucht die Pruefung dagegen, weil er durch V teilt. Diese
    Asymmetrie stammt aus der Vorlage und wird bewusst uebernommen - der
    Luftzustand eines Stranges ohne Volumenstrom wird nirgends weiterverwendet.
    """
    p = parameter(V_nenn=8200.0, dp_nenn=240.0, QK_nenn=250.0, T_KW_mittel=6.0)
    ein = {"luft_ein": Luft(V=0.0, T=30.0, x=12.0), "stellgroesse": 100.0}
    aus, _ = Kuehler().berechne(ein, p, {})
    assert aus["QK"] == 0.0
    assert aus["luft_aus"].V == 0.0
    assert aus["luft_aus"].T < 30.0


def test_kuehler_meldet_zu_niedrige_leistung():
    p = parameter(V_nenn=8200.0, dp_nenn=240.0, QK_nenn=5.0, T_KW_mittel=6.0)
    ein = {"luft_ein": Luft(V=8200.0, T=30.0, x=12.0), "stellgroesse": 100.0}
    aus, _ = Kuehler().berechne(ein, p, {})
    assert aus["warnung"] == "Kühlleistung zu niedrig"
