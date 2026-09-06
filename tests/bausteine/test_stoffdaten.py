"""Die vier Stoffdatenfunktionen gegen Tafelwerte.

Auf ihnen ruht alles: jede Temperatur, jede Feuchte, jede Kälteleistung im
ganzen Programm. Geprüft hatte sie trotzdem niemand - andere Tests benutzen
sie als Maßstab für ihre eigenen Erwartungen, was den Fehler mitschleppen
würde, statt ihn zu finden.

Der Sättigungsdruck ist der Anker: Bei 100 °C muss Wasser bei Normaldruck
sieden, also 101 325 Pa erreichen. Das ist keine Tabelle, sondern die
Definition der Celsius-Skala - eine Formel, die das trifft, stimmt auch
dazwischen.

BEZUGSDRUCK. Das Programm rechnet mit 100 000 Pa (1 bar), nicht mit der
Normatmosphäre von 101 325 Pa. Das ist vertretbar - der Luftdruck schwankt
ohnehin um mehr -, verschiebt aber alle Feuchtewerte systematisch um +1,2 %:
Bei 20 °C kommen 14,88 g/kg heraus statt der 14,70 g/kg der üblichen Tafeln.
Wer die Zahlen des Programms mit einem h,x-Diagramm vergleicht, muss das
wissen. Die Tests unten prüfen deshalb gegen den Bezugsdruck des Programms
und weisen die Abweichung zur Normatmosphäre ausdrücklich aus.
"""

import pytest

from core.bausteine import stoffdaten as st

#: Tafelwerte des Sättigungsdampfdrucks über Wasser, in Pa.
SAETTIGUNGSDRUCK = {0.0: 611.2, 10.0: 1228.0, 20.0: 2339.0, 30.0: 4246.0,
                    40.0: 7384.0, 100.0: 101325.0}


def x_bei(T, gesamtdruck):
    """Sättigungsgehalt aus dem Tafelwert des Drucks - die Vergleichsrechnung."""
    p = SAETTIGUNGSDRUCK[T]
    return 0.622 * p / (gesamtdruck - p) * 1000.0


# --- Sättigungsdruck ------------------------------------------------------

@pytest.mark.parametrize("T", sorted(SAETTIGUNGSDRUCK))
def test_saettigungsdruck_trifft_die_tafel(T):
    assert st.p_saett(T) == pytest.approx(SAETTIGUNGSDRUCK[T], rel=0.005)


def test_bei_hundert_grad_siedet_wasser_bei_normaldruck():
    """Der härteste Einzelwert - er folgt aus der Definition, nicht aus einer
    Messung."""
    assert st.p_saett(100.0) == pytest.approx(101325.0, rel=0.001)


def test_der_saettigungsdruck_waechst_streng_monoton():
    werte = [st.p_saett(T) for T in range(-10, 60, 5)]
    assert all(b > a for a, b in zip(werte, werte[1:]))


# --- Sättigungsgehalt -----------------------------------------------------

@pytest.mark.parametrize("T", [0.0, 10.0, 20.0, 30.0])
def test_saettigungsgehalt_passt_zum_bezugsdruck_des_programms(T):
    assert st.x_saett(T) == pytest.approx(x_bei(T, st.GESAMTDRUCK), rel=0.005)


def test_der_bezugsdruck_ist_ausdruecklich_ein_bar():
    """Nicht die Normatmosphäre - siehe Kopf dieser Datei."""
    assert st.GESAMTDRUCK == 100000.0


def test_die_abweichung_zur_normatmosphaere_ist_bekannt_und_klein():
    """Wer die Zahlen mit einem h,x-Diagramm vergleicht, findet diesen
    Unterschied - er soll gemessen und benannt sein, nicht überraschen."""
    for T in (0.0, 20.0, 30.0):
        norm = x_bei(T, 101325.0)
        abweichung = (st.x_saett(T) - norm) / norm
        assert 0.010 < abweichung < 0.015, f"bei {T} °C um {abweichung:.1%}"


# --- Enthalpie ------------------------------------------------------------

def test_trockene_luft_bei_null_grad_hat_die_enthalpie_null():
    """Der Nullpunkt der Skala."""
    assert st.enthalpie(0.0, 0.0) == pytest.approx(0.0)


def test_enthalpie_feuchter_luft_gegen_die_handrechnung():
    """h = 1,01·t + x·(2501 + 1,86·t), mit x in kg/kg.
    Bei 20 °C und 10 g/kg: 20,2 + 0,010·2538,2 = 45,58 kJ/kg."""
    assert st.enthalpie(20.0, 10.0) == pytest.approx(45.58, abs=0.05)


def test_feuchte_luft_traegt_mehr_energie_als_trockene():
    assert st.enthalpie(20.0, 10.0) > st.enthalpie(20.0, 0.0)


# --- Relative Feuchte und Umkehrbarkeit -----------------------------------

def test_gesaettigte_luft_hat_hundert_prozent():
    """Die wichtigste Probe: Die beiden Funktionen müssen zueinander passen.
    Rechnen sie mit verschiedenen Konstanten, klafft hier eine Lücke."""
    for T in (0.0, 10.0, 20.0, 30.0):
        assert st.rel_feuchte(T, st.x_saett(T)) == pytest.approx(100.0, abs=0.1), (
            f"bei {T} °C ergibt die Sättigungsfeuchte "
            f"{st.rel_feuchte(T, st.x_saett(T)):.2f} % statt 100 %"
        )


def test_halbe_saettigung_gibt_rund_fuenfzig_prozent():
    """Nicht exakt 50 %: Die relative Feuchte ist am Dampfdruck gemessen, der
    Wassergehalt am Mischungsverhältnis - beide hängen nichtlinear zusammen."""
    T = 20.0
    assert st.rel_feuchte(T, st.x_saett(T) / 2) == pytest.approx(50.0, abs=1.0)


def test_trockene_luft_hat_null_prozent():
    assert st.rel_feuchte(20.0, 0.0) == pytest.approx(0.0)
