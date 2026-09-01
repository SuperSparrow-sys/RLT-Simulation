"""Monatsprofil. Formel aus Anlage!AR16 bis AR28."""

from core.bausteine.basis import (
    AUSGANG, MESSWERT, SIGNAL, Baustein, Param, Port, registriere,
)


@registriere
class Monatsprofil(Baustein):
    KENNUNG = "monatsprofil"
    NAME = "Monatsprofil"
    GRUPPE = "Zeit und Betrieb"
    SYMBOL = "monatsprofil.svg"

    PARAMETER = [Param("monate", "Monate ein/aus", "-", [True] * 12)]

    PORTS = [Port("betrieb", SIGNAL, AUSGANG, MESSWERT)]

    AUSGABEN = ["betrieb"]

    def berechne(self, ein, p, zustand):
        s = zustand.get("stunde") or {}
        zeitpunkt = s.get("zeitpunkt")
        if zeitpunkt is None:
            return {"betrieb": 0.0}, zustand
        monate = p.get("monate") or [True] * 12
        return {"betrieb": 1.0 if monate[zeitpunkt.month - 1] else 0.0}, zustand
