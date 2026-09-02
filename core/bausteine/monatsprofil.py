"""Monatsprofil. Formel aus Anlage!AR16 bis AR28."""

from core.bausteine.basis import (
    AUSGANG, MONATSWERTE, SIGNAL, ZEITPLAN, Baustein, Param, Port, registriere,
)


@registriere
class Monatsprofil(Baustein):
    KENNUNG = "monatsprofil"
    NAME = "Monatsprofil"
    GRUPPE = "Zeit und Betrieb"
    SYMBOL = "monatsprofil.svg"

    PARAMETER = [
        Param("monate", "Betriebsmonate", "", [True] * 12, darstellung=MONATSWERTE,
              hinweis="Ein Schalter je Monat: eingeschaltet heißt, die Anlage darf in "
                      "diesem Monat laufen. Damit lässt sich zum Beispiel eine "
                      "Kühlung nur für den Sommer freigeben.")
    ]

    PORTS = [Port("betrieb", SIGNAL, AUSGANG, ZEITPLAN)]

    AUSGABEN = ["betrieb"]
    AUSGABE_LABEL = {"betrieb": "Freigabe (1 = ein, 0 = aus)"}

    def berechne(self, ein, p, zustand):
        s = zustand.get("stunde") or {}
        zeitpunkt = s.get("zeitpunkt")
        if zeitpunkt is None:
            return {"betrieb": 0.0}, zustand
        monate = p.get("monate") or [True] * 12
        return {"betrieb": 1.0 if monate[zeitpunkt.month - 1] else 0.0}, zustand
