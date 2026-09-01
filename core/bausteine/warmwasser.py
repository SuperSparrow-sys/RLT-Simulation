"""Warmwasserbereitung. Formeln aus Anlage!AE156 und AF148.

Der Jahresverbrauch wird gleichmaessig auf 8760 Stunden verteilt; dazu kommt
der Speicherverlust, der nur von der Speichergroesse abhaengt.
"""

from core.bausteine.basis import (
    AUSGANG, SIGNAL, WAERME, Baustein, Param, Port, registriere,
)

KALTWASSER = 10.0  # °C, Anlage!AE156


@registriere
class Warmwasserbereitung(Baustein):
    KENNUNG = "warmwasser"
    NAME = "Warmwasserbereitung"
    GRUPPE = "Verbraucher"
    SYMBOL = "warmwasser.svg"

    PARAMETER = [
        Param("speichervolumen", "Speichervol.", "l", 1000.0),
        Param("verbrauch", "Verbrauch", "m³/a", 462.0),
        Param("sollwert", "Sollwert", "°C", 50.0),
    ]

    PORTS = [Port("QH", SIGNAL, AUSGANG, WAERME)]

    AUSGABEN = ["QH", "speicherverlust"]

    def speicherverlust(self, p):
        return ((p["speichervolumen"] / 1000.0) ** 0.333) ** 2 * 5.0 * 8.0 * 20.0 / 1000.0

    def berechne(self, ein, p, zustand):
        verlust = self.speicherverlust(p)
        QH = (
            p["verbrauch"] * 1000.0 / 8760.0 * 4.18 * (p["sollwert"] - KALTWASSER) / 3600.0
            + verlust
        )
        return {"QH": QH, "speicherverlust": verlust}, zustand
