import pytest

from core.bausteine.basis import Luft
from core.bausteine.sammler import Sammler
from core.bausteine.verteiler import Verteiler


def test_verteiler_gibt_den_zustand_unveraendert_an_alle_abgaenge():
    ein = {"luft_ein": Luft(V=12000.0, T=18.0, x=6.0, dp=100.0)}
    p = {"anteile": {}}
    verteiler = Verteiler()
    verteiler.abgaenge = ["luft_aus_1", "luft_aus_2"]
    verteiler.bedarf_je_abgang = {"luft_aus_1": 8000.0, "luft_aus_2": 4000.0}
    aus, _ = verteiler.berechne(ein, p, {})
    assert aus["luft_aus_1"].T == pytest.approx(18.0)
    assert aus["luft_aus_2"].x == pytest.approx(6.0)
    assert aus["luft_aus_1"].V == pytest.approx(8000.0)
    assert aus["luft_aus_2"].V == pytest.approx(4000.0)


def test_verteiler_kuerzt_proportional_bei_unterdeckung():
    ein = {"luft_ein": Luft(V=6000.0, T=18.0, x=6.0)}
    p = {"anteile": {}}
    verteiler = Verteiler()
    verteiler.abgaenge = ["luft_aus_1", "luft_aus_2"]
    verteiler.bedarf_je_abgang = {"luft_aus_1": 8000.0, "luft_aus_2": 4000.0}
    aus, _ = verteiler.berechne(ein, p, {})
    assert aus["luft_aus_1"].V == pytest.approx(4000.0)
    assert aus["luft_aus_2"].V == pytest.approx(2000.0)
    assert aus["warnung"] == "Volumenstrom reicht nicht fuer alle Gaenge"


def test_verteiler_nutzt_anteile_wenn_kein_bedarf_gemeldet_wird():
    ein = {"luft_ein": Luft(V=10000.0, T=18.0, x=6.0)}
    p = {"anteile": {"luft_aus_1": 70.0, "luft_aus_2": 30.0}}
    verteiler = Verteiler()
    verteiler.abgaenge = ["luft_aus_1", "luft_aus_2"]
    verteiler.bedarf_je_abgang = {"luft_aus_1": 0.0, "luft_aus_2": 0.0}
    aus, _ = verteiler.berechne(ein, p, {})
    assert aus["luft_aus_1"].V == pytest.approx(7000.0)
    assert aus["luft_aus_2"].V == pytest.approx(3000.0)


def test_verteiler_fordert_die_summe_der_abgaenge():
    verteiler = Verteiler()
    assert verteiler.bedarf(
        {"luft_aus_1": 8000.0, "luft_aus_2": 4000.0}, {"anteile": {}}
    ) == {"luft_ein": 12000.0}


def test_sammler_mischt_massenstromgewichtet():
    ein = {
        "luft_ein_1": Luft(V=8000.0, T=20.0, x=8.0),
        "luft_ein_2": Luft(V=2000.0, T=10.0, x=3.0),
    }
    aus, _ = Sammler().berechne(ein, {}, {})
    assert aus["luft_aus"].V == pytest.approx(10000.0)
    assert aus["luft_aus"].T == pytest.approx((8000 * 20.0 + 2000 * 10.0) / 10000)
    assert aus["luft_aus"].x == pytest.approx((8000 * 8.0 + 2000 * 3.0) / 10000)


def test_sammler_ohne_luft_liefert_nullzustand():
    aus, _ = Sammler().berechne({}, {}, {})
    assert aus["luft_aus"].V == 0.0
    assert aus["luft_aus"].T == 0.0
