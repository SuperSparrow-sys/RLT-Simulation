"""Stoffgleichungen feuchter Luft, uebernommen aus der Excel-Mappe.

Die Polynome stehen dort in Anlage!T6, Anlage!T7, Anlage!S20 und Anlage!X147/X148.
Sie werden bewusst unveraendert nachgebildet, damit die Ergebnisse vergleichbar
bleiben - eine genauere Zustandsgleichung wuerde andere Zahlen liefern.
"""

import math

#: Gesamtdruck, auf den alle Feuchtegroessen bezogen sind, in Pa.
#:
#: Ein Bar, nicht die Normatmosphaere von 101 325 Pa. So steht es in der Mappe,
#: und der Luftdruck schwankt ohnehin um mehr. Die Folge muss man aber kennen:
#: Alle Feuchtewerte liegen dadurch systematisch um rund 1,2 Prozent ueber den
#: Zahlen der ueblichen h,x-Tafeln - bei 20 GradC sind es 14,88 statt
#: 14,70 g/kg. Wer die Ergebnisse mit einem Diagramm vergleicht, sieht diesen
#: Unterschied und soll wissen, woher er kommt.
#: Geprueft in tests/bausteine/test_stoffdaten.py.
GESAMTDRUCK = 100000.0

#: Verhaeltnis der Molmassen von Wasserdampf und trockener Luft (18,015/28,96).
#:
#: Frueher stand hier zweimal eine andere Zahl: x_saett rechnete mit 0,622,
#: rel_feuchte mit 0,6222. Die beiden Funktionen sind zueinander invers - mit
#: verschiedenen Konstanten ergab gesaettigte Luft nicht 100 Prozent relative
#: Feuchte, sondern 99,96. Der Fehler ist klein, aber er ist einer.
MOLMASSENVERHAELTNIS = 0.622


def p_saett(T: float) -> float:
    """Saettigungsdampfdruck in Pa bei der Temperatur T in °C."""
    return 611.0 * math.exp(
        -1.91275e-4
        + 7.258e-2 * T
        - 2.939e-4 * T**2
        + 9.841e-7 * T**3
        - 1.92e-9 * T**4
    )


def x_saett(T: float) -> float:
    """Saettigungsfeuchte in g/kg bei der Temperatur T in °C."""
    p = p_saett(T)
    return MOLMASSENVERHAELTNIS * p / (GESAMTDRUCK - p) * 1000.0


def enthalpie(T: float, x: float) -> float:
    """Spezifische Enthalpie feuchter Luft in kJ/kg."""
    return 1.01 * T + x / 1000.0 * (2501.0 + 1.86 * T)


def rel_feuchte(T: float, x: float) -> float:
    """Relative Feuchte in Prozent."""
    anteil = x / 1000.0
    p_dampf = anteil / (MOLMASSENVERHAELTNIS + anteil) * GESAMTDRUCK
    return p_dampf / p_saett(T) * 100.0
