"""Beleuchtung. Formel aus Anlage!AK134.

In der Excel steckt die Beleuchtung fest im Raumblock. Hier ist sie eine eigene
Karte, damit Raeume unterschiedlich beleuchtet gerechnet werden koennen. Die
abgegebene Waerme entspricht der aufgenommenen elektrischen Leistung.
"""

from core.bausteine.basis import (
    AUSGANG, BETRIEB, EINGANG, MESSWERT, SIGNAL, STROM, ZAHL,
    Baustein, Param, Port, registriere,
)


@registriere
class Beleuchtung(Baustein):
    KENNUNG = "beleuchtung"
    NAME = "Beleuchtung"
    GRUPPE = "Verbraucher"
    SYMBOL = "beleuchtung.svg"

    PARAMETER = [
        Param("spez_leistung", "Spezifische Anschlussleistung", "W/m²", 2.0,
              darstellung=ZAHL, dezimalstellen=1, minimum=0.0,
              hinweis="Elektrische Leistung je m² Grundfläche. Die Beleuchtung gibt "
                      "ihre gesamte Stromaufnahme als Wärme an den Raum ab - beide "
                      "Ausgänge tragen deshalb denselben Wert."),
        Param("grundflaeche", "Beleuchtete Grundfläche", "m²", 726.0,
              darstellung=ZAHL, dezimalstellen=1, minimum=0.0),
        # AK134 = spez. Leistung * Grundflaeche / 1000; die Nennbeleuchtungs-
        # staerke steht in der Mappe daneben, geht aber in keine Formel ein.
        Param("nennbeleuchtung", "Nennbeleuchtungsstärke", "lx", 300.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0,
              hinweis="Wird nicht gerechnet: Sie hält nur fest, auf welche Helligkeit "
                      "ausgelegt wurde. Wärme und Strom folgen allein aus "
                      "spezifischer Anschlussleistung mal Grundfläche.", ohne_wirkung=True),
    ]

    PORTS = [
        Port("betrieb", SIGNAL, EINGANG, BETRIEB),
        Port("Q_Bel", SIGNAL, AUSGANG, MESSWERT),
        Port("PE", SIGNAL, AUSGANG, STROM),
    ]

    AUSGABEN = ["Q_Bel", "PE"]
    AUSGABE_LABEL = {
        "Q_Bel": "Beleuchtungswärme (kW)",
        "PE": "elektrische Leistung (kW)",
    }

    def berechne(self, ein, p, zustand):
        betrieb = float(ein.get("betrieb", 1.0))
        Q = p["spez_leistung"] * p["grundflaeche"] / 1000.0 * betrieb
        return {"Q_Bel": Q, "PE": Q}, zustand
