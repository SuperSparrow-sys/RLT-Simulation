"""Die Wärmerückgewinnung kühlt die Fortluft - dabei fällt Wasser aus.

Ein Plattentauscher kühlt im Winter die Abluft von Raumtemperatur bis dicht
an die Außentemperatur herunter. Unterschreitet sie dabei ihren Taupunkt,
kondensiert Wasser aus - jeder Tauscher hat dafür einen Kondensatablauf, und
bei Frost eine Vereisungssicherung.

Gerechnet wurde das nicht: Die Fortluft behielt ihren Wassergehalt und verließ
den Tauscher übersättigt. Gemessen an der Vorlage „Schwimmhalle": 14,3 g/kg
bei 10,8 °C, wo höchstens 8,1 g/kg möglich sind - in 274 von 504 Stunden.

Die freiwerdende Kondensationswärme erwärmt die Fortluft wieder etwas: 1 g/kg
setzt rund 2,5 kJ/kg frei, das sind etwa 2,5 K. Sie wird der ZULUFT bewusst
NICHT gutgeschrieben - die Rückwärmzahl ist ein eingestellter Auslegungswert,
der den üblichen Betrieb schon abbildet; sie zusätzlich zu erhöhen hieße,
dieselbe Wärme zweimal zu zählen. Die Rechnung bleibt damit auf der sicheren
Seite: sie gewinnt eher zu wenig zurück als zu viel.
"""

import pytest

from core.bausteine import lade_alle, stoffdaten as st
from core.bausteine.basis import Luft, hole

lade_alle()

PARAMETER = {
    "V_nenn": 10000.0, "dp_WRG_nenn": 160.0, "dp_Bypass_nenn": 40.0,
    "rueckwaermzahl": 75.0, "rueckfeuchtzahl": 0.0,
}


def durch_die_wrg(t_aussen, x_aussen, t_ab, x_ab, V=10000.0):
    karte = hole("wrg")()
    werte, _ = karte.berechne(
        {
            "zuluft_ein": Luft(V=V, T=t_aussen, x=x_aussen),
            "abluft_ein": Luft(V=V, T=t_ab, x=x_ab),
            "stellgroesse": 100.0, "stellgroesse_bypass": 0.0,
        },
        PARAMETER, {},
    )
    return werte


def test_die_fortluft_verlaesst_den_tauscher_nie_uebersaettigt():
    """Der Fall aus der Schwimmhalle: warme, sehr feuchte Abluft gegen kalte
    Außenluft."""
    werte = durch_die_wrg(t_aussen=2.0, x_aussen=3.0, t_ab=30.0, x_ab=14.3)
    fort = werte["abluft_aus"]
    grenze = st.x_saett(fort.T)
    assert fort.x <= grenze + 0.1, (
        f"{fort.x:.1f} g/kg bei {fort.T:.1f} °C, möglich sind {grenze:.1f}"
    )


def test_ohne_taupunktunterschreitung_bleibt_alles_wie_bisher():
    """Trockene Abluft kondensiert nicht - dort darf sich nichts ändern."""
    werte = durch_die_wrg(t_aussen=2.0, x_aussen=3.0, t_ab=22.0, x_ab=4.0)
    fort = werte["abluft_aus"]
    assert fort.x == pytest.approx(4.0)
    # 22 °C, 75 % Rückwärmzahl, 20 K Spanne -> rund 7 °C
    assert fort.T == pytest.approx(22.0 - 0.75 * 20.0, abs=0.5)


def test_die_kondensationswaerme_erwaermt_die_fortluft():
    """Sie verschwindet nicht - sie steckt danach in der Fortluft."""
    feucht = durch_die_wrg(t_aussen=2.0, x_aussen=3.0, t_ab=30.0, x_ab=14.3)
    trocken = durch_die_wrg(t_aussen=2.0, x_aussen=3.0, t_ab=30.0, x_ab=5.0)
    assert feucht["abluft_aus"].T > trocken["abluft_aus"].T, (
        "die feuchte Abluft muss den Tauscher wärmer verlassen als die trockene"
    )


def test_die_ausgewiesene_kondensatmenge_stimmt_mit_der_luft_ueberein():
    werte = durch_die_wrg(t_aussen=2.0, x_aussen=3.0, t_ab=30.0, x_ab=14.3)
    fort = werte["abluft_aus"]
    # kg/h aus g/kg: V/3600 * 1,2 kg/m3 * dx/1000 * 3600
    erwartet = 10000.0 * 1.2 * (14.3 - fort.x) / 1000.0
    assert werte["kondensat"] == pytest.approx(erwartet, rel=0.02)


def test_ohne_kondensation_faellt_kein_wasser_an():
    werte = durch_die_wrg(t_aussen=2.0, x_aussen=3.0, t_ab=22.0, x_ab=4.0)
    assert werte["kondensat"] == pytest.approx(0.0)


def test_die_zuluft_bleibt_unveraendert():
    """Die Kondensationswärme wird der Zuluft bewusst nicht gutgeschrieben -
    siehe Kopf dieser Datei."""
    feucht = durch_die_wrg(t_aussen=2.0, x_aussen=3.0, t_ab=30.0, x_ab=14.3)
    trocken = durch_die_wrg(t_aussen=2.0, x_aussen=3.0, t_ab=30.0, x_ab=5.0)
    assert feucht["zuluft_aus"].T == pytest.approx(trocken["zuluft_aus"].T)


# --- Feuchteübertragung (Rotationstauscher) --------------------------------
#
# Alle zwölf mitgelieferten Vorlagen setzen rueckfeuchtzahl auf 0 - sie
# benutzen Plattentauscher, die keine Feuchte übertragen. Der Pfad war damit
# im ganzen Programm ungeprüft, obwohl die Karte ihn anbietet und ein
# Rotationstauscher der häufigste Fall in neuen Anlagen ist.


def mit_feuchteuebertragung(rueckfeuchtzahl, t_aussen, x_aussen, t_ab, x_ab):
    karte = hole("wrg")()
    werte, _ = karte.berechne(
        {
            "zuluft_ein": Luft(V=10000.0, T=t_aussen, x=x_aussen),
            "abluft_ein": Luft(V=10000.0, T=t_ab, x=x_ab),
            "stellgroesse": 100.0, "stellgroesse_bypass": 0.0,
        },
        dict(PARAMETER, rueckfeuchtzahl=rueckfeuchtzahl), {},
    )
    return werte


def test_ohne_rueckfeuchtzahl_bleibt_die_zuluftfeuchte_unveraendert():
    werte = mit_feuchteuebertragung(0.0, 2.0, 3.0, 22.0, 9.0)
    assert werte["zuluft_aus"].x == pytest.approx(3.0)


def test_mit_rueckfeuchtzahl_wird_feuchte_uebertragen():
    """Ein Rotationstauscher gibt der trockenen Winterluft Feuchte aus der
    Abluft mit - das ist sein wesentlicher Vorzug gegenüber dem Plattentauscher."""
    werte = mit_feuchteuebertragung(60.0, 2.0, 3.0, 22.0, 9.0)
    # 60 % der Spanne von 3 auf 9 g/kg
    assert werte["zuluft_aus"].x == pytest.approx(3.0 + 0.6 * 6.0, abs=0.1)


def test_die_abluft_verliert_genau_was_die_zuluft_gewinnt():
    """Massenerhaltung: Bei gleichen Volumenströmen muss die Bilanz aufgehen."""
    werte = mit_feuchteuebertragung(60.0, 2.0, 3.0, 22.0, 9.0)
    gewonnen = werte["zuluft_aus"].x - 3.0
    verloren = 9.0 - werte["abluft_aus"].x
    assert gewonnen == pytest.approx(verloren, abs=0.1)


def test_uebertragene_feuchte_macht_die_zuluft_nicht_uebersaettigt():
    """Die Grenze gilt auch hier: Die kalte Zuluft kann die Feuchte der warmen
    Abluft nicht unbegrenzt aufnehmen."""
    werte = mit_feuchteuebertragung(100.0, -10.0, 1.0, 24.0, 12.0)
    zu = werte["zuluft_aus"]
    assert zu.x <= st.x_saett(zu.T) + 0.1, (
        f"{zu.x:.1f} g/kg bei {zu.T:.1f} °C, möglich sind "
        f"{st.x_saett(zu.T):.1f}"
    )
