"""Hinter einem Kühlregister darf keine übersättigte Luft austreten.

Der Fall kam aus dem Jahreslauf der Testanlage: 53 Stunden mit Luft über der
Sättigungslinie, alle hinter dem Kühler. Die Ursache lag nicht am Kühler
allein, sondern an zwei harmlosen Umständen zugleich.

Erstens enthält das Testreferenzjahr Nebelstunden, deren Feuchte knapp über
der Sättigung liegt - 13,60 °C mit 9,900 g/kg, möglich sind 9,833. Das sind
Messwerte bei 100 % relativer Feuchte und kein Fehler der Datei.

Zweitens ist die Sättigungskurve nach oben gekrümmt. Der Kühler mischt den
Eintrittszustand geradlinig mit dem Zustand an seiner Registeroberfläche, und
eine Gerade zwischen zwei Punkten auf oder dicht über einer gekrümmten Kurve
verläuft dazwischen weiter darüber. Aus 0,067 g/kg Überschuss am Eintritt
wurden 0,118 g/kg am Austritt: Die Anlage machte aus einer Nebelstunde einen
unmöglichen Zustand und reichte ihn weiter.
"""

import pytest

from core.bausteine import stoffdaten as st
from core.bausteine.basis import Luft
from core.bausteine.kuehler import Kuehler


def vorgaben():
    return Kuehler.vorgabeparameter()


def kuehle(T_ein, x_ein, u, **anders):
    p = vorgaben()
    p.update(anders)
    aus, _ = Kuehler().berechne(
        {"luft_ein": Luft(V=5000.0, T=T_ein, x=x_ein), "stellgroesse": u}, p, {},
    )
    return aus


def test_der_austritt_bleibt_auf_oder_unter_der_saettigungslinie():
    """Genau der Zustand aus Stunde 3797 des Testreferenzjahres."""
    aus = kuehle(13.60, 9.900, 24.5, V_nenn=5000.0, T_KW_mittel=7.0,
                 kontaktfaktor=0.15)
    luft = aus["luft_aus"]
    assert luft.x <= st.x_saett(luft.T) + 1e-9, (
        f"{luft.x:.3f} g/kg bei {luft.T:.2f} °C, möglich sind "
        f"{st.x_saett(luft.T):.3f}"
    )


@pytest.mark.parametrize("u", [0.0, 5.0, 25.0, 50.0, 80.0, 100.0])
def test_ueber_die_ganze_stellgroesse_bleibt_der_austritt_moeglich(u):
    """Nicht nur an einem Punkt: Die Mischgerade läuft über den ganzen
    Stellbereich, und die Krümmung schlägt in der Mitte am stärksten zu."""
    luft = kuehle(13.60, 9.900, u)["luft_aus"]
    assert luft.x <= st.x_saett(luft.T) + 1e-9


def test_trockene_luft_wird_nicht_angetastet():
    """Die Deckelung darf nur greifen, wo sie muss - sonst rechnete sie
    Feuchte weg, die es gibt."""
    aus = kuehle(28.0, 8.0, 60.0)
    trocken = aus["luft_aus"]
    # 8 g/kg bei 28 °C ist weit von der Sättigung entfernt; gekühlt wird auf
    # eine Temperatur, deren Sättigung noch darüber liegt.
    assert trocken.x < 8.0, "der Kühler entfeuchtet gar nicht mehr"
    assert trocken.x > 0.0


def test_das_kondensat_zaehlt_zur_kuehlleistung():
    """Was am Register niederschlägt, gibt seine Verdampfungswärme ab. Wird
    erst gedeckelt und dann die Leistung gerechnet, ist sie mit drin."""
    feucht = kuehle(13.60, 9.900, 50.0)
    trockener = kuehle(13.60, 8.000, 50.0)
    assert feucht["QK"] > trockener["QK"], (
        "feuchtere Luft muss bei gleicher Abkühlung mehr Kälte brauchen"
    )
