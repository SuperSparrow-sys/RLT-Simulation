"""Stoffgleichungen feuchter Luft, uebernommen aus der Excel-Mappe.

Die Polynome stehen dort in Anlage!T6, Anlage!T7, Anlage!S20 und Anlage!X147/X148.
Sie werden bewusst unveraendert nachgebildet, damit die Ergebnisse vergleichbar
bleiben - eine genauere Zustandsgleichung wuerde andere Zahlen liefern.
"""

import math


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
    return 0.622 * p / (100000.0 - p) * 1000.0


def enthalpie(T: float, x: float) -> float:
    """Spezifische Enthalpie feuchter Luft in kJ/kg."""
    return 1.01 * T + x / 1000.0 * (2501.0 + 1.86 * T)


def rel_feuchte(T: float, x: float) -> float:
    """Relative Feuchte in Prozent."""
    p_dampf = x / 1000.0 / (0.6222 + x / 1000.0) * 100000.0
    return p_dampf / p_saett(T) * 100.0
