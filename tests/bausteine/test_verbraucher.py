import pytest

from core.bausteine.beleuchtung import Beleuchtung
from core.bausteine.heizungspumpen import Heizungspumpen
from core.bausteine.warmwasser import Warmwasserbereitung
from core.bausteine.zirkulation import Zirkulation


def test_heizungspumpen_entsprechen_der_excel():
    """Anlage!AE145 - Allgemein voll, WWB und Kessel je zur Haelfte."""
    p = {"P_allgemein": 2.0, "P_wwb": 1.0, "P_kessel": 3.0}
    aus, _ = Heizungspumpen().berechne({"betrieb": 1.0}, p, {})
    assert aus["PE"] == pytest.approx(2.0 + 0.5 * 1.0 + 0.5 * 3.0)


def test_heizungspumpen_stehen_ausser_betrieb():
    p = {"P_allgemein": 2.0, "P_wwb": 1.0, "P_kessel": 3.0}
    aus, _ = Heizungspumpen().berechne({"betrieb": 0.0}, p, {})
    assert aus["PE"] == 0.0


def test_speicherverlust_entspricht_der_excel():
    """Anlage!AF148 fuer 1000 Liter."""
    erwartet = ((1000.0 / 1000.0) ** 0.333) ** 2 * 5.0 * 8.0 * 20.0 / 1000.0
    assert Warmwasserbereitung().speicherverlust({"speichervolumen": 1000.0}) == pytest.approx(erwartet)


def test_warmwasserleistung_entspricht_der_excel():
    """Anlage!AE156 - 462 m³/a auf 50 °C bei 1000 Liter Speicher."""
    p = {"speichervolumen": 1000.0, "verbrauch": 462.0, "sollwert": 50.0}
    aus, _ = Warmwasserbereitung().berechne({}, p, {})
    assert aus["QH"] == pytest.approx(3.2494672754946725, rel=1e-10)


def test_zirkulation_entspricht_der_excel():
    """Anlage!AE157/AE158 - 1,5 m³/h bei 5 K Spreizung."""
    p = {"volumenstrom": 1.5, "spreizung": 5.0, "P_pumpe": 0.04}
    aus, _ = Zirkulation().berechne({"betrieb": 1.0}, p, {})
    assert aus["QH"] == pytest.approx(1.5 * 1000.0 / 3600.0 * 4.18 * 5.0 * 0.75)
    assert aus["PE"] == pytest.approx(0.04)


def test_zirkulation_steht_ausser_betrieb():
    p = {"volumenstrom": 1.5, "spreizung": 5.0, "P_pumpe": 0.04}
    aus, _ = Zirkulation().berechne({"betrieb": 0.0}, p, {})
    assert aus["QH"] == 0.0
    assert aus["PE"] == 0.0


def test_beleuchtung_entspricht_der_excel():
    """Anlage!AK134 - 2 W/m² auf 726 m²."""
    p = {"spez_leistung": 2.0, "grundflaeche": 726.0, "nennbeleuchtung": 300.0}
    aus, _ = Beleuchtung().berechne({"betrieb": 1.0}, p, {})
    assert aus["Q_Bel"] == pytest.approx(1.452)
    assert aus["PE"] == pytest.approx(1.452)


def test_beleuchtung_folgt_dem_betriebssignal():
    p = {"spez_leistung": 2.0, "grundflaeche": 726.0, "nennbeleuchtung": 300.0}
    aus, _ = Beleuchtung().berechne({"betrieb": 0.5}, p, {})
    assert aus["Q_Bel"] == pytest.approx(0.726)
