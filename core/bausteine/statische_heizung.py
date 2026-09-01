"""Statische Heizung als eigene Karte.

Nimmt die vom Raum gemeldete Unterdeckung auf und begrenzt sie auf die
Nennleistung, entsprechend Anlage!AH128/AH129.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, MESSWERT, SIGNAL, WAERME, Baustein, Param, Port, registriere,
)


@registriere
class StatischeHeizung(Baustein):
    KENNUNG = "statische_heizung"
    NAME = "Statische Heizung"
    GRUPPE = "Räume"
    SYMBOL = "statische_heizung.svg"

    PARAMETER = [Param("QH_nenn", "QH_nenn", "kW", 0.0)]

    PORTS = [
        Port("bedarf", SIGNAL, EINGANG, MESSWERT),
        Port("QH", SIGNAL, AUSGANG, WAERME),
    ]

    AUSGABEN = ["QH"]

    def berechne(self, ein, p, zustand):
        gefordert = float(ein.get("bedarf", 0.0))
        QH = max(min(gefordert, p["QH_nenn"]), 0.0)
        return {"QH": QH}, zustand
