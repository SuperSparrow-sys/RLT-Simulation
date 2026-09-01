import pytest

from core.bausteine.hysterese_regler import HystereseRegler
from core.bausteine.kaskade import RaumZuluftKaskade
from core.bausteine.p_regler import PRegler
from core.bausteine.sequenzregler import Sequenzregler


# ---------------------------------------------------------------- P-Regler

def test_p_regler_faehrt_bei_zu_kaltem_istwert_auf():
    """Anlage!K51/J57 - der Ausgang integriert ueber die Iterationen."""
    p = {"xp_1": 5.0, "xp_2": 5.0}
    ein = {"sollwert_2": 20.0, "istwert_2": 18.0}
    zustand = {"y1": 0.0, "y2": 50.0}
    aus, zustand = PRegler().berechne(ein, p, zustand)
    assert aus["ausgang_2"] == pytest.approx(50.0 + 2.0 / 5.0)


def test_p_regler_faehrt_bei_zu_warmem_istwert_zu():
    p = {"xp_1": 5.0, "xp_2": 5.0}
    ein = {"sollwert_2": 20.0, "istwert_2": 25.0}
    aus, _ = PRegler().berechne(ein, p, {"y1": 0.0, "y2": 50.0})
    assert aus["ausgang_2"] == pytest.approx(50.0 - 1.0)


def test_p_regler_bleibt_zwischen_null_und_hundert():
    p = {"xp_1": 5.0, "xp_2": 1.0}
    ein = {"sollwert_2": 20.0, "istwert_2": -200.0}
    aus, _ = PRegler().berechne(ein, p, {"y1": 0.0, "y2": 50.0})
    assert aus["ausgang_2"] == 100.0

    ein = {"sollwert_2": 20.0, "istwert_2": 400.0}
    aus, _ = PRegler().berechne(ein, p, {"y1": 0.0, "y2": 50.0})
    assert aus["ausgang_2"] == 0.0


def test_p_regler_konvergiert_auf_den_sollwert():
    """Wiederholtes Rechnen wie im Vorwaertslauf treibt den Ausgang an den Anschlag."""
    p = {"xp_1": 5.0, "xp_2": 5.0}
    zustand = {"y1": 0.0, "y2": 0.0}
    for _ in range(100):
        aus, zustand = PRegler().berechne(
            {"sollwert_2": 20.0, "istwert_2": 15.0}, p, zustand
        )
    assert aus["ausgang_2"] == 100.0


# ----------------------------------------------------------- Sequenzregler

def test_sequenzregler_ist_im_totband_ruhig():
    p = {"oberer_sw": 24.0, "unterer_sw": 20.0, "xp": 5.0}
    aus, zustand = Sequenzregler().berechne({"istwert": 22.0}, p, {"e": 0.0})
    assert zustand["e"] == 0.0
    assert aus["waermer_1"] == 0.0
    assert aus["kaelter_1"] == 0.0


def test_sequenzregler_oeffnet_die_erste_waermestufe():
    p = {"oberer_sw": 24.0, "unterer_sw": 20.0, "xp": 5.0}
    aus, _ = Sequenzregler().berechne({"istwert": 10.0}, p, {"e": -20.0})
    assert aus["waermer_1"] == 100.0
    assert aus["kaelter_1"] == 0.0


def test_sequenzregler_staffelt_die_stufen():
    p = {"oberer_sw": 24.0, "unterer_sw": 20.0, "xp": 5.0}
    aus, _ = Sequenzregler().berechne({"istwert": 10.0}, p, {"e": -251.0})
    assert aus["waermer_1"] == 100.0
    assert aus["waermer_2"] == 100.0
    assert aus["waermer_3"] == pytest.approx(52.0)


def test_sequenzregler_begrenzt_die_regelabweichung():
    p = {"oberer_sw": 24.0, "unterer_sw": 20.0, "xp": 5.0}
    _, zustand = Sequenzregler().berechne({"istwert": -500.0}, p, {"e": -299.0})
    assert zustand["e"] == -300.0


def test_sequenzregler_kuehlt_bei_zu_warmem_istwert():
    p = {"oberer_sw": 24.0, "unterer_sw": 20.0, "xp": 5.0}
    aus, _ = Sequenzregler().berechne({"istwert": 30.0}, p, {"e": 150.0})
    assert aus["kaelter_1"] == 100.0
    assert aus["kaelter_2"] == pytest.approx(50.6)
    assert aus["waermer_1"] == 0.0


# -------------------------------------------------------- Hysterese-Regler

def test_hysterese_schaltet_oberhalb_der_schaltdifferenz_ein():
    p = {"hysterese": 0.2}
    aus, zustand = HystereseRegler().berechne(
        {"sollwert": 5.0, "istwert": 5.2}, p, {"zustand": 0.0}
    )
    assert aus["ausgang"] == 100.0
    assert zustand["zustand"] == 100.0


def test_hysterese_schaltet_unterhalb_der_schaltdifferenz_aus():
    p = {"hysterese": 0.2}
    aus, _ = HystereseRegler().berechne(
        {"sollwert": 5.0, "istwert": 4.8}, p, {"zustand": 100.0}
    )
    assert aus["ausgang"] == 0.0


def test_hysterese_haelt_den_zustand_im_totband():
    p = {"hysterese": 1.0}
    aus, _ = HystereseRegler().berechne(
        {"sollwert": 5.0, "istwert": 5.2}, p, {"zustand": 100.0}
    )
    assert aus["ausgang"] == 100.0

    aus, _ = HystereseRegler().berechne(
        {"sollwert": 5.0, "istwert": 5.2}, p, {"zustand": 0.0}
    )
    assert aus["ausgang"] == 0.0


# ----------------------------------------------------------------- Kaskade

def test_kaskade_haelt_den_mindestsollwert_bei_kalter_aussenluft():
    p = {
        "T_Raum_min": 22.0, "T_AU_min": 20.0,
        "T_Raum_max": 28.0, "T_AU_max": 32.0,
        "T_ZU_min": 16.0, "T_ZU_max": 25.0, "xp": 5.0,
    }
    assert RaumZuluftKaskade().gleitender_sollwert(10.0, p) == pytest.approx(22.0)


def test_kaskade_hebt_den_sollwert_bei_warmer_aussenluft():
    p = {
        "T_Raum_min": 22.0, "T_AU_min": 20.0,
        "T_Raum_max": 28.0, "T_AU_max": 32.0,
        "T_ZU_min": 16.0, "T_ZU_max": 25.0, "xp": 5.0,
    }
    assert RaumZuluftKaskade().gleitender_sollwert(26.0, p) == pytest.approx(25.0)


def test_kaskade_begrenzt_den_sollwert_nach_oben():
    p = {
        "T_Raum_min": 22.0, "T_AU_min": 20.0,
        "T_Raum_max": 28.0, "T_AU_max": 32.0,
        "T_ZU_min": 16.0, "T_ZU_max": 25.0, "xp": 5.0,
    }
    assert RaumZuluftKaskade().gleitender_sollwert(40.0, p) == pytest.approx(28.0)


def test_kaskade_greift_ein_wenn_die_zuluft_zu_warm_wird():
    p = {
        "T_Raum_min": 22.0, "T_AU_min": 20.0,
        "T_Raum_max": 28.0, "T_AU_max": 32.0,
        "T_ZU_min": 16.0, "T_ZU_max": 25.0, "xp": 5.0,
    }
    ein = {"T_AU": 10.0, "T_Raum": 22.0, "T_ZU": 31.0}
    _, zustand = RaumZuluftKaskade().berechne(ein, p, {"e": 0.0})
    assert zustand["e"] == pytest.approx(2.0)
