"""Ein Register kann bei wenig Luft nicht dieselbe Leistung übertragen.

Erhitzer und Kühler rechneten ihre Leistung allein aus der Ventilstellung:
`QH = u/100 · QH_max`, unabhängig davon, wieviel Luft durchströmt. Bei 20 %
Luftmenge hätte ein 70-kW-Register also weiter 70 kW abgeben können - das
entspräche einer Temperaturerhöhung von über 300 K.

Physikalisch übertragbar ist

    Q = eps · m_L · cp · (T_Wasser − T_ein),   eps = 1 − exp(−NTU)

mit NTU = UA/(m_L·cp). Bei einem Rippenrohrregister bestimmt die Luftseite den
Wärmeübergang; dort gilt näherungsweise alpha ~ v^0,8, also UA ~ V^0,8. Mit
m_L ~ V folgt NTU(r) = NTU_nenn · r^−0,2 und daraus eine übertragbare Leistung,
die mit r^0,88 bis r^0,91 fällt - nahezu proportional zur Luftmenge, und kaum
abhängig davon, welche Auslegungsgüte man annimmt.

Bei Nennvolumenstrom ändert sich nichts. AX_SIM 2.1 fährt durchgehend auf
Nennmenge (nachgemessen), der Abgleich gegen die Mappe bleibt deshalb
unberührt - was hier korrigiert wird, ist ein Betriebsbereich, den die Mappe
gar nicht kennt.
"""

import math

import pytest

from core.bausteine import lade_alle
from core.bausteine.basis import Luft, hole, uebertragbare_leistung

lade_alle()

V_NENN = 8000.0
QH_MAX = 70.0


def heizleistung(volumenstrom, stellgroesse=100.0, t_ein=0.0):
    karte = hole("erhitzer")()
    werte, _ = karte.berechne(
        {"luft_ein": Luft(V=volumenstrom, T=t_ein, x=3.0),
         "stellgroesse": stellgroesse},
        {"V_nenn": V_NENN, "dp_nenn": 150.0, "QH_max": QH_MAX},
        {},
    )
    return werte["QH"], werte["luft_aus"].T


# --- Die Kennlinie selbst -------------------------------------------------

def test_bei_nennvolumenstrom_bleibt_alles_wie_in_der_mappe():
    assert uebertragbare_leistung(1.0, V_NENN, V_NENN) == pytest.approx(1.0)
    leistung, _ = heizleistung(V_NENN)
    assert leistung == pytest.approx(QH_MAX)


def test_die_leistung_faellt_nahezu_proportional_zur_luftmenge():
    """Der hergeleitete Exponent liegt zwischen 0,85 und 0,95."""
    for anteil in (0.2, 0.3, 0.5, 0.8):
        faktor = uebertragbare_leistung(1.0, anteil * V_NENN, V_NENN)
        exponent = math.log(faktor) / math.log(anteil)
        assert 0.85 < exponent < 0.95, (
            f"bei {anteil:.0%} Luftmenge fällt die Leistung mit r^{exponent:.2f}"
        )


def test_mehr_luft_als_nenn_gibt_keine_zusaetzliche_leistung():
    """Ein Register wächst nicht, wenn man mehr Luft hindurchschickt - seine
    Fläche bleibt dieselbe. Über Nennvolumenstrom gilt die Nennleistung."""
    assert uebertragbare_leistung(1.0, 2.0 * V_NENN, V_NENN) == pytest.approx(1.0)


def test_ohne_luft_ueberträgt_das_register_nichts():
    assert uebertragbare_leistung(1.0, 0.0, V_NENN) == 0.0


# --- Wirkung an der Karte -------------------------------------------------

def test_erhitzer_gibt_bei_wenig_luft_weniger_ab():
    voll, _ = heizleistung(V_NENN)
    fuenftel, _ = heizleistung(0.2 * V_NENN)
    assert fuenftel < 0.3 * voll, (
        f"bei einem Fünftel der Luft noch {fuenftel:.1f} von {voll:.1f} kW"
    )


def test_die_temperaturerhoehung_bleibt_im_moeglichen():
    """Der eigentliche Zweck: keine Zuluft jenseits jeder RLT-Anlage.

    Vorher erwärmte ein 70-kW-Register 1600 m³/h um 130 K.
    """
    for anteil in (0.2, 0.3, 0.5, 1.0):
        _, t_aus = heizleistung(anteil * V_NENN, t_ein=0.0)
        assert t_aus < 60.0, f"bei {anteil:.0%} Luftmenge {t_aus:.0f} °C Zuluft"


def test_die_ventilstellung_wirkt_weiterhin_linear():
    """Die Kennlinie begrenzt nur nach oben - darunter regelt das Ventil wie
    bisher, sonst verschöbe sich das Verhalten aller vorhandenen Anlagen."""
    halb, _ = heizleistung(V_NENN, stellgroesse=50.0)
    assert halb == pytest.approx(0.5 * QH_MAX)


def test_kuehler_folgt_derselben_kennlinie():
    karte = hole("kuehler")()
    p = {"V_nenn": V_NENN, "dp_nenn": 190.0, "QK_nenn": 80.0,
         "T_KW_mittel": 6.0, "kontaktfaktor": 0.55}

    def kaelte(volumenstrom):
        werte, _ = karte.berechne(
            {"luft_ein": Luft(V=volumenstrom, T=30.0, x=10.0), "stellgroesse": 100.0},
            p, {},
        )
        return werte["QK"]

    assert kaelte(0.2 * V_NENN) < 0.3 * kaelte(V_NENN)
