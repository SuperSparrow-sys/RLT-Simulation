import pytest

from core.bausteine import stoffdaten as st


def test_saettigungsdruck_entspricht_der_excel():
    # Anlage!T6 fuer to = 7,94999999999999 (Anlage!T3)
    assert st.p_saett(7.94999999999999) == pytest.approx(1068.3046916476103, rel=1e-9)


def test_saettigungsfeuchte_entspricht_der_excel():
    # Anlage!T7
    assert st.x_saett(7.94999999999999) == pytest.approx(6.716609031450752, rel=1e-9)


def test_enthalpie_entspricht_der_excel():
    # Anlage!S20 fuer T = 18,999999999999936 und x = 0
    assert st.enthalpie(18.999999999999936, 0.0) == pytest.approx(19.19, rel=1e-9)


def test_enthalpie_mit_feuchte():
    # h = 1,01*20 + 8/1000*(2501 + 1,86*20)
    assert st.enthalpie(20.0, 8.0) == pytest.approx(20.2 + 0.008 * 2538.2, rel=1e-12)


def test_relative_feuchte_bei_saettigung_ist_hundert():
    T = 15.0
    assert st.rel_feuchte(T, st.x_saett(T)) == pytest.approx(100.0, abs=0.05)
