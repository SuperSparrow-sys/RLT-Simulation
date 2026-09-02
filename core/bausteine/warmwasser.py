"""Warmwasserbereitung. Formeln aus Anlage!AE156 und AF148.

Der Jahresverbrauch wird gleichmaessig auf 8760 Stunden verteilt; dazu kommt
der Speicherverlust, der nur von der Speichergroesse abhaengt.
"""

from core.bausteine.basis import (
    AUSGANG, SIGNAL, WAERME, ZAHL, Baustein, Param, Port, registriere,
)

KALTWASSER = 10.0  # °C, Anlage!AE156


@registriere
class Warmwasserbereitung(Baustein):
    KENNUNG = "warmwasser"
    NAME = "Warmwasserbereitung"
    GRUPPE = "Verbraucher"
    SYMBOL = "warmwasser.svg"

    PARAMETER = [
        Param("speichervolumen", "Speichervolumen", "l", 1000.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0,
              hinweis="Bestimmt allein den Bereitschaftsverlust des Speichers - der "
                      "fällt rund um die Uhr an, auch wenn kein Wasser gezapft wird."),
        Param("verbrauch", "Warmwasserverbrauch im Jahr", "m³/a", 462.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0,
              hinweis="Wird gleichmäßig auf alle 8760 Stunden des Jahres verteilt - "
                      "die Karte kennt keine Zapfspitzen."),
        Param("sollwert", "Warmwassertemperatur", "°C", 50.0,
              darstellung=ZAHL, dezimalstellen=1,
              hinweis="Aufgeheizt wird von fest angenommenen 10 °C Kaltwasser auf "
                      "diesen Wert."),
    ]

    PORTS = [Port("QH", SIGNAL, AUSGANG, WAERME)]

    AUSGABEN = ["QH", "speicherverlust"]
    AUSGABE_LABEL = {
        "QH": "Wärmeleistung für Warmwasser (kW)",
        "speicherverlust": "Bereitschaftsverlust des Speichers (kW)",
    }

    def speicherverlust(self, p):
        return ((p["speichervolumen"] / 1000.0) ** 0.333) ** 2 * 5.0 * 8.0 * 20.0 / 1000.0

    def berechne(self, ein, p, zustand):
        verlust = self.speicherverlust(p)
        QH = (
            p["verbrauch"] * 1000.0 / 8760.0 * 4.18 * (p["sollwert"] - KALTWASSER) / 3600.0
            + verlust
        )
        return {"QH": QH, "speicherverlust": verlust}, zustand
