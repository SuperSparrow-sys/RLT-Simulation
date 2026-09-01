"""Raum-/Zuluft-Kaskade mit aussentemperaturgefuehrtem Sollwert.

Formeln aus Anlage!P143 (gleitender Raumsollwert), Q140 (Regelabweichung mit
Vorrang der Zuluftbegrenzung) und Q138/P153 bis P157 (Sequenzausgaenge).
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, ISTWERT, MESSWERT, SIGNAL, STELLGROESSE,
    Baustein, Param, Port, registriere,
)
from core.bausteine.sequenzregler import STUFEN


@registriere
class RaumZuluftKaskade(Baustein):
    # Der Ausgang bezieht sich auf seinen eigenen Vorwert - er baut sich ueber
    # die Iterationen des Vorwaertslaufs auf, genau wie in der Excel.
    ZUSTAND_UEBER_ITERATION = True

    KENNUNG = "kaskade"
    NAME = "Raum-/Zuluft-Kaskade"
    GRUPPE = "Regelung"
    SYMBOL = "kaskade.svg"

    PARAMETER = [
        Param("T_Raum_min", "min. T_Raum", "°C", 22.0),
        Param("T_AU_min", "bei T_AU", "°C", 20.0),
        Param("T_Raum_max", "max. T_Raum", "°C", 28.0),
        Param("T_AU_max", "bei T_AU", "°C", 32.0),
        Param("T_ZU_min", "min. T_ZU", "°C", 16.0),
        Param("T_ZU_max", "max. T_ZU", "°C", 25.0),
        Param("xp", "Xp", "-", 5.0),
    ]

    PORTS = [
        Port("T_AU", SIGNAL, EINGANG, MESSWERT),
        Port("T_Raum", SIGNAL, EINGANG, ISTWERT),
        Port("T_ZU", SIGNAL, EINGANG, ISTWERT),
        Port("sollwert", SIGNAL, AUSGANG, MESSWERT),
        Port("waermer_3", SIGNAL, AUSGANG, STELLGROESSE),
        Port("waermer_2", SIGNAL, AUSGANG, STELLGROESSE),
        Port("waermer_1", SIGNAL, AUSGANG, STELLGROESSE),
        Port("kaelter_1", SIGNAL, AUSGANG, STELLGROESSE),
        Port("kaelter_2", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = [
        "sollwert", "waermer_3", "waermer_2", "waermer_1",
        "kaelter_1", "kaelter_2", "e",
    ]

    def gleitender_sollwert(self, T_AU, p):
        if T_AU < p["T_AU_min"]:
            return p["T_Raum_min"]
        spanne = p["T_AU_max"] - p["T_AU_min"]
        if spanne == 0:
            return p["T_Raum_max"]
        gleitend = p["T_Raum_min"] + (T_AU - p["T_AU_min"]) * (
            p["T_Raum_max"] - p["T_Raum_min"]
        ) / spanne
        return min(gleitend, p["T_Raum_max"])

    def berechne(self, ein, p, zustand):
        T_AU = float(ein.get("T_AU", 0.0))
        T_Raum = float(ein.get("T_Raum", 0.0))
        T_ZU = float(ein.get("T_ZU", 0.0))
        e_alt = float(zustand.get("e", 0.0))

        soll = self.gleitender_sollwert(T_AU, p)

        if T_ZU > p["T_ZU_max"]:
            delta = (T_ZU - p["T_ZU_max"]) / 3.0
        elif T_ZU < p["T_ZU_min"]:
            delta = (T_ZU - p["T_ZU_min"]) / 3.0
        else:
            delta = (T_Raum - soll) / 3.0

        e = max(-300.0, min(200.0, e_alt + delta))

        aus = {"sollwert": soll, "e": e}
        for name, versatz, vorzeichen in STUFEN:
            aus[name] = max(0.0, min(vorzeichen * (e + versatz), 100.0))
        return aus, {"e": e}

    def anfangszustand(self, p):
        return {"e": 0.0}
