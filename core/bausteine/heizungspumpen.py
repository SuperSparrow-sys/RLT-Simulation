"""Heizungspumpen. Formel aus Anlage!AE145."""

from core.bausteine.basis import (
    AUSGANG, BETRIEB, EINGANG, SIGNAL, STROM, ZAHL,
    Baustein, Param, Port, registriere,
)


@registriere
class Heizungspumpen(Baustein):
    KENNUNG = "heizungspumpen"
    NAME = "Heizungspumpen"
    GRUPPE = "Verbraucher"
    SYMBOL = "heizungspumpen.svg"

    PARAMETER = [
        Param("P_allgemein", "Allgemein", "kW", 0.0, darstellung=ZAHL, dezimalstellen=2, minimum=0.0),
        Param("P_wwb", "WWB", "kW", 0.0, darstellung=ZAHL, dezimalstellen=2, minimum=0.0),
        Param("P_kessel", "Kessel", "kW", 0.0, darstellung=ZAHL, dezimalstellen=2, minimum=0.0),
    ]

    PORTS = [
        Port("betrieb", SIGNAL, EINGANG, BETRIEB),
        Port("PE", SIGNAL, AUSGANG, STROM),
    ]

    AUSGABEN = ["PE"]

    def berechne(self, ein, p, zustand):
        betrieb = float(ein.get("betrieb", 0.0))
        PE = betrieb * (
            p["P_allgemein"] + 0.5 * p["P_wwb"] + 0.5 * p["P_kessel"]
        )
        return {"PE": PE}, zustand
