import pytest

from core.bausteine.basis import Luft
from core.bausteine.einfacher_raum import EinfacherRaum


def parameter(**abweichend):
    p = EinfacherRaum.vorgabeparameter()
    p.update(abweichend)
    return p


def eingaben():
    """Anlage!AG31:AI50 - der gespeicherte Zustand des einfachen Raums."""
    return {
        "zuluft_ein_1": Luft(V=8200.0, T=20.78022137718888, x=0.0),
        "zuluft_ein_2": Luft(V=4000.0, T=15.839048772668132, x=8.747590530135225),
        "abluft_aus_1": Luft(V=4500.0),
        "abluft_aus_2": Luft(V=4500.0),
        "T_AU": 0.0,
        "F_AU": 0.0,
        "waermelast": 0.25,
        "feuchtelast": 0.25,
    }


def test_freie_raumtemperatur_entspricht_der_excel():
    """Anlage!AH48."""
    p = parameter(spez_transmission=0.5, sollwert_stat=15.0)
    aus, _ = EinfacherRaum().berechne(eingaben(), p, {})
    assert aus["T_frei"] == pytest.approx(17.12973787168357, rel=1e-10)


def test_raumfeuchte_entspricht_der_excel():
    """Anlage!AH46."""
    p = parameter(spez_transmission=0.5, sollwert_stat=15.0)
    aus, _ = EinfacherRaum().berechne(eingaben(), p, {})
    assert aus["F_Raum"] == pytest.approx(2.885138971629036, rel=1e-12)


def test_statischer_sollwert_hebt_die_raumtemperatur_an():
    p = parameter(spez_transmission=0.5, sollwert_stat=25.0)
    aus, _ = EinfacherRaum().berechne(eingaben(), p, {})
    assert aus["T_Raum"] == pytest.approx(25.0)
    assert aus["QH_stat"] > 0.0


def test_ohne_heizbedarf_ist_die_statische_leistung_null():
    p = parameter(spez_transmission=0.5, sollwert_stat=15.0)
    aus, _ = EinfacherRaum().berechne(eingaben(), p, {})
    assert aus["QH_stat"] == pytest.approx(0.0)
    assert aus["T_Raum"] == pytest.approx(17.12973787168357, rel=1e-10)


def test_ueberwiegende_abluft_zieht_aussenluft_nach():
    """Bei mehr Ab- als Zuluft rechnet die Excel einen Infiltrationsanteil ein."""
    p = parameter(spez_transmission=0.5, sollwert_stat=-50.0)
    ein = eingaben()
    ein["abluft_aus_1"] = Luft(V=12000.0)
    ein["abluft_aus_2"] = Luft(V=12000.0)
    ein["T_AU"] = -10.0
    aus, _ = EinfacherRaum().berechne(ein, p, {})
    assert aus["T_frei"] < 17.12973787168357


def test_abluft_bekommt_den_raumzustand():
    p = parameter(spez_transmission=0.5, sollwert_stat=15.0)
    aus, _ = EinfacherRaum().berechne(eingaben(), p, {})
    assert aus["abluft_aus_1"].T == pytest.approx(aus["T_Raum"])
    assert aus["abluft_aus_1"].x == pytest.approx(aus["F_Raum"])
    assert aus["abluft_aus_1"].V == pytest.approx(4500.0)
