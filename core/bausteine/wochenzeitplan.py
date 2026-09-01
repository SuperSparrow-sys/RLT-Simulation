"""Wochenzeitplan. Formeln aus Anlage!AN7 bis AL14.

Die Zeiten stehen als Tagesbruchteil, wie in der Excel: 0,20833 entspricht
05:00 Uhr. Der Betrieb ist 1, wenn Wochentag und Uhrzeit passen.
"""

from core.bausteine.basis import (
    AUSGANG, SIGNAL, ZEITPLAN, Baustein, Param, Port, registriere,
)

TAGE = ("montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag")


@registriere
class Wochenzeitplan(Baustein):
    KENNUNG = "wochenzeitplan"
    NAME = "Wochenzeitplan"
    GRUPPE = "Zeit und Betrieb"
    SYMBOL = "wochenzeitplan.svg"

    PARAMETER = [
        Param(f"{grenze}_{tag}", f"{tag.capitalize()} {grenze}", "Tagesanteil",
              5.0 / 24.0 if grenze == "von" else 22.0 / 24.0)
        for tag in TAGE
        for grenze in ("von", "bis")
    ]

    PORTS = [Port("betrieb", SIGNAL, AUSGANG, ZEITPLAN)]

    AUSGABEN = ["betrieb"]

    def berechne(self, ein, p, zustand):
        s = zustand.get("stunde") or {}
        zeitpunkt = s.get("zeitpunkt")
        if zeitpunkt is None:
            return {"betrieb": 0.0}, zustand

        tag = TAGE[zeitpunkt.weekday()]
        anteil = (
            zeitpunkt.hour + zeitpunkt.minute / 60.0 + zeitpunkt.second / 3600.0
        ) / 24.0
        von = p.get(f"von_{tag}", 0.0)
        bis = p.get(f"bis_{tag}", 0.0)

        betrieb = 1.0 if (von < bis and von <= anteil < bis) else 0.0
        return {"betrieb": betrieb}, zustand
