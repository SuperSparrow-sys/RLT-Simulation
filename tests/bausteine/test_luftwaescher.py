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


def test_luftwaescher_rechnet_den_zustand_auch_ohne_volumenstrom():
    """Absichtlich wie in der Excel, genau wie beim Kuehler.

    Anlage!AE131 und AE132 rechnen T_aus und F_aus ohne Volumenstrompruefung,
    weil dort nicht durch V geteilt wird. Nur Wasserverbrauch (AE134) und
    Pumpenleistung (AE133) sind an V gebunden. Der Erhitzer (Anlage!S131) braucht
    die Pruefung dagegen, weil er durch V teilt. Der Luftzustand eines Stranges
    ohne Volumenstrom wird nirgends weiterverwendet.
    """
    p = parameter(V_nenn=4000.0, dp_nenn=50.0, pumpenart="H")
    ein = {"luft_ein": Luft(V=0.0, T=32.0, x=5.0), "stellgroesse": 100.0}
    aus, _ = Luftwaescher().berechne(ein, p, {})
    assert aus["wasser"] == 0.0
    assert aus["PE_Pumpe"] == 0.0
    assert aus["luft_aus"].V == 0.0
    assert aus["luft_aus"].T < 32.0


def test_pumpenkennlinien_unterscheiden_sich_je_bauart():
    """Anlage!AE133 - drei Bauarten mit unterschiedlichem Exponenten.

    Der gespeicherte Rechenstand der Mappe kennt nur die Bauart 'H'; die
    Exponenten der beiden anderen sind deshalb hier festgehalten, damit ein
    Zahlendreher auffaellt. Die Rangfolge V > F > H bei Teillast ist die
    eigentliche Aussage: Hochdruck spart am meisten, Ventilbetrieb am wenigsten.
    """
    grund = 4000.0 * 1.2 / 3600.0 * 200.0 / 0.6 / 1000.0
    ein = {"luft_ein": Luft(V=4000.0, T=30.0, x=6.0), "stellgroesse": 50.0}

    werte = {}
    for art in ("F", "V", "H"):
        p = parameter(V_nenn=4000.0, dp_nenn=50.0, pumpenart=art)
        werte[art], _ = Luftwaescher().berechne(ein, p, {})

    assert werte["F"]["PE_Pumpe"] == pytest.approx(grund * 0.5**2)
    assert werte["V"]["PE_Pumpe"] == pytest.approx(grund * 0.5**0.3)
    assert werte["H"]["PE_Pumpe"] == pytest.approx(grund * 0.4 * 0.5**2)
    assert werte["V"]["PE_Pumpe"] > werte["F"]["PE_Pumpe"] > werte["H"]["PE_Pumpe"]
