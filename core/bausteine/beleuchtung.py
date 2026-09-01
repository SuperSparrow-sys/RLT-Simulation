"""Beleuchtung. Formel aus Anlage!AK134.

In der Excel steckt die Beleuchtung fest im Raumblock. Hier ist sie eine eigene
Karte, damit Raeume unterschiedlich beleuchtet gerechnet werden koennen. Die
abgegebene Waerme entspricht der aufgenommenen elektrischen Leistung.
"""

from core.bausteine.basis import (
    AUSGANG, BETRIEB, EINGANG, MESSWERT, SIGNAL, STROM,
    Baustein, Param, Port, registriere,
)


@registriere
class Beleuchtung(Baustein):
    KENNUNG = "beleuchtung"
    NAME = "Beleuchtung"
    GRUPPE = "Verbraucher"
    SYMBOL = "beleuchtung.svg"

    PARAMETER = [
        Param("spez_leistung", "sp. Leistung", "W/m²", 2.0),
        Param("grundflaeche", "Grundfläche", "m²", 726.0),
        Param("nennbeleuchtung", "Nennbel.", "lx", 300.0),
    ]

    PORTS = [
        Port("betrieb", SIGNAL, EINGANG, BETRIEB),
        Port("Q_Bel", SIGNAL, AUSGANG, MESSWERT),
        Port("PE", SIGNAL, AUSGANG, STROM),
    ]

    AUSGABEN = ["Q_Bel", "PE"]

    def berechne(self, ein, p, zustand):
        betrieb = float(ein.get("betrieb", 1.0))
        Q = p["spez_leistung"] * p["grundflaeche"] / 1000.0 * betrieb
        return {"Q_Bel": Q, "PE": Q}, zustand
