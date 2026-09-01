"""Zirkulationsleitung. Formeln aus Anlage!AE157 und AE158."""

from core.bausteine.basis import (
    AUSGANG, EINGANG, MESSWERT, SIGNAL, STROM, WAERME,
    Baustein, Param, Port, registriere,
)


@registriere
class Zirkulation(Baustein):
    KENNUNG = "zirkulation"
    NAME = "Zirkulation"
    GRUPPE = "Verbraucher"
    SYMBOL = "zirkulation.svg"

    PARAMETER = [
        Param("volumenstrom", "Zirkulation", "m³/h", 1.5),
        Param("spreizung", "Zirk. VL-RL", "K", 5.0),
        Param("P_pumpe", "Zirk_PU", "kW", 0.04),
    ]

    PORTS = [
        Port("betrieb", SIGNAL, EINGANG, MESSWERT),
        Port("QH", SIGNAL, AUSGANG, WAERME),
        Port("PE", SIGNAL, AUSGANG, STROM),
    ]

    AUSGABEN = ["QH", "PE"]

    def berechne(self, ein, p, zustand):
        betrieb = float(ein.get("betrieb", 0.0))
        QH = p["volumenstrom"] * 1000.0 / 3600.0 * 4.18 * p["spreizung"] * 0.75 * betrieb
        PE = p["P_pumpe"] * betrieb
        return {"QH": QH, "PE": PE}, zustand
