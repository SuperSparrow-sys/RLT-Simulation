import pytest

from core.bausteine.basis import Luft
from core.bausteine.raum import Raum


def parameter(**abweichend):
    """Die Geometrie aus Anlage!AG100:AL134 der Beispielanlage."""
    p = Raum.vorgabeparameter()
    p.update(
        {
            "laenge_a": 22.0, "laenge_b": 33.0, "laenge_c": 22.0, "laenge_d": 33.0,
            "laenge_e": 0.0,
            "aw_anteil_a": 1.0, "aw_anteil_b": 0.5, "aw_anteil_c": 0.35,
            "aw_anteil_d": 1.0, "aw_anteil_e": 0.0,
            "u_wand_a": 1.62, "u_wand_b": 1.9, "u_wand_c": 1.9, "u_wand_d": 1.9,
            "fenster_a": 0.0, "fenster_b": 72.6, "fenster_c": 0.0, "fenster_d": 123.8,
            "u_fenster_a": 2.5, "u_fenster_b": 2.5, "u_fenster_c": 2.5,
            "u_fenster_d": 2.5,
            "dach_laenge": 0.0, "dach_anteil": 1.0, "u_dach": 0.91,
            "fenster_dach": 0.0, "u_fenster_dach": 2.5,
            "boden_anteil": 1.0, "u_boden": 0.16,
            "geschosse": 1.0, "hoehe": 6.15,
            "bauart": 90.0, "ausrichtung": 65.0,
            "waermebruecke": 0.1, "waermeuebergang": 7.7,
            "g_faktor": 0.8, "verschattung_1": 0.7, "verschattung_2": 0.9,
            "verschattung_3": 0.9, "verschattung_4": 1.0,
            "spez_beleuchtung": 2.0,
        }
    )
    p.update(abweichend)
    return p


def test_geometrie_entspricht_der_excel():
    g = Raum().geometrie(parameter())
    assert g["grundflaeche"] == pytest.approx(726.0)
    assert g["volumen"] == pytest.approx(4464.9)
    assert g["dachflaeche"] == pytest.approx(726.0)
    assert g["fensterflaeche"] == pytest.approx(196.4)
    assert g["aussenwand"] == pytest.approx(290.68000000000006, rel=1e-12)
    assert g["innenwand"] == pytest.approx(1932.1, rel=1e-12)


def test_spezifische_transmission_entspricht_der_excel():
    g = Raum().geometrie(parameter())
    assert g["trans_aw"] == pytest.approx(583.378, rel=1e-10)
    assert g["trans_fe"] == pytest.approx(491.0, rel=1e-12)
    assert g["trans_fb"] == pytest.approx(116.16, rel=1e-12)
    assert g["trans_da"] == pytest.approx(660.66, rel=1e-12)


def test_luftwechsel_und_lueftungsverlust_entsprechen_der_excel():
    g = Raum().geometrie(parameter())
    assert g["luftwechsel"] == pytest.approx(0.308371027346637, rel=1e-12)
    assert g["spez_verlust"] == pytest.approx(468.127572, rel=1e-10)


def test_beleuchtungswaerme_entspricht_der_excel():
    """Anlage!AK134 - 2 W/m² auf 726 m²."""
    assert Raum().beleuchtungswaerme(parameter()) == pytest.approx(1.452)


def test_solargewinn_wird_ueber_22_grad_aussentemperatur_abgemindert():
    """Anlage!AK122 prueft AJ75 - und AI75 beschriftet diese Zelle als T_AU."""
    p = parameter()
    strahlung = {"QH_S": 400.0, "QH_O": 100.0, "QH_W": 100.0, "QH_N": 50.0, "QH_H": 300.0}
    kalt = Raum().solargewinn(p, strahlung, T_AU=18.0)
    warm = Raum().solargewinn(p, strahlung, T_AU=25.0)
    assert warm == pytest.approx(0.2 * kalt)
    assert kalt > 0.0


def test_solargewinn_ist_nachts_null():
    p = parameter()
    strahlung = {"QH_S": 0.0, "QH_O": 0.0, "QH_W": 0.0, "QH_N": 0.0, "QH_H": 0.0}
    assert Raum().solargewinn(p, strahlung, T_AU=18.0) == pytest.approx(0.0)


def test_raumtemperatur_strebt_dem_beharrungswert_entgegen():
    """Ohne Last und ohne Zuluft naehert sich der Raum der Aussentemperatur."""
    p = parameter(spez_beleuchtung=0.0)
    ein = {
        "zuluft_ein": Luft(V=0.0, T=0.0, x=0.0),
        "abluft_aus": Luft(V=0.0),
        "T_AU": 0.0, "F_AU": 0.0,
        "QH_S": 0.0, "QH_O": 0.0, "QH_W": 0.0, "QH_N": 0.0, "QH_H": 0.0,
        "waermelast": 0.0, "feuchtelast": 0.0,
    }
    zustand = {"T_Raum": 20.0, "T_Wand": 20.0}
    for _ in range(200):
        aus, zustand = Raum().berechne(ein, p, zustand)
    assert aus["T_Raum"] < 5.0


def test_wandspeicher_entspricht_der_excel():
    """Anlage!AK127 und AK128 - der einzige belastbare Rechenstand des Wandspeichers.

    Aus T_Wand = 0 °C und der Raumtemperatur AJ89 = 0.15028844280554668 °C ergibt
    die Mappe QH_Wand = -2.2358667126533947 kW und T_Wand_neu =
    0.04628884038410837 °C. Der Test haelt beides fest, weil der Teiler 3600 in
    C_Wand von der Beschriftung der Bauart abweicht (siehe Kommentar im Baustein) -
    ohne diesen Anker saehe die Abweichung wie ein Fehler aus und wuerde
    frueher oder spaeter 'korrigiert'.
    """
    p = parameter()
    raum = Raum()
    g = raum.geometrie(p)

    T_Wand, T_Raum = 0.0, 0.15028844280554668
    QH_Wand = (T_Wand - T_Raum) * p["waermeuebergang"] * g["innenwand"] / 1000.0
    C_Wand = g["innenwand"] * p["bauart"] / 3600.0

    assert QH_Wand == pytest.approx(-2.2358667126533947, rel=1e-12)
    assert T_Wand - QH_Wand / C_Wand == pytest.approx(0.04628884038410837, rel=1e-12)


def test_wandtemperatur_folgt_der_raumtemperatur():
    p = parameter(spez_beleuchtung=0.0)
    ein = {
        "zuluft_ein": Luft(V=8200.0, T=30.0, x=6.0),
        "abluft_aus": Luft(V=8200.0),
        "T_AU": 10.0, "F_AU": 4.0,
        "QH_S": 0.0, "QH_O": 0.0, "QH_W": 0.0, "QH_N": 0.0, "QH_H": 0.0,
        "waermelast": 0.0, "feuchtelast": 0.0,
    }
    zustand = {"T_Raum": 10.0, "T_Wand": 10.0}
    vorher = zustand["T_Wand"]
    for _ in range(50):
        aus, zustand = Raum().berechne(ein, p, zustand)
    assert zustand["T_Wand"] > vorher
    assert zustand["T_Wand"] < aus["T_Raum"] + 0.5


def test_raumfeuchte_folgt_der_zuluft_und_der_feuchtelast():
    p = parameter()
    ein = {
        "zuluft_ein": Luft(V=10000.0, T=20.0, x=6.0),
        "abluft_aus": Luft(V=10000.0),
        "T_AU": 10.0, "F_AU": 4.0,
        "QH_S": 0.0, "QH_O": 0.0, "QH_W": 0.0, "QH_N": 0.0, "QH_H": 0.0,
        "waermelast": 0.0, "feuchtelast": 12.0,
    }
    aus, _ = Raum().berechne(ein, p, {"T_Raum": 20.0, "T_Wand": 20.0})
    assert aus["F_Raum"] == pytest.approx(6.0 + 12.0 * 1000.0 / (10000.0 * 1.2))


def test_abluft_traegt_den_raumzustand():
    p = parameter()
    ein = {
        "zuluft_ein": Luft(V=8200.0, T=20.0, x=6.0),
        "abluft_aus": Luft(V=4500.0),
        "T_AU": 10.0, "F_AU": 4.0,
        "QH_S": 0.0, "QH_O": 0.0, "QH_W": 0.0, "QH_N": 0.0, "QH_H": 0.0,
        "waermelast": 0.0, "feuchtelast": 0.0,
    }
    aus, _ = Raum().berechne(ein, p, {"T_Raum": 18.0, "T_Wand": 18.0})
    assert aus["abluft_aus"].V == pytest.approx(4500.0)
    assert aus["abluft_aus"].T == pytest.approx(aus["T_Raum"])


def test_anfangszustand_setzt_raum_und_wand_auf_den_startwert():
    p = parameter(start_temperatur=15.0)
    assert Raum().anfangszustand(p) == {"T_Raum": 15.0, "T_Wand": 15.0}
