"""Ferien und Sondertage. Formel aus Anlage!AN21 bis AL28.

Die Zeitraeume werden als Tag und Monat angegeben, damit sie in jedem
Wetterjahr gelten. Zeitraeume ueber den Jahreswechsel sind erlaubt.
"""

from core.bausteine.basis import (
    AUSGANG, FERIEN, SIGNAL, ZEITRAEUME, Baustein, Param, Port, registriere,
)


def _als_tagesnummer(text):
    tag, monat = text.strip(". ").split(".")[:2]
    return int(monat) * 100 + int(tag)


@registriere
class Ferien(Baustein):
    KENNUNG = "ferien"
    NAME = "Ferien"
    GRUPPE = "Zeit und Betrieb"
    SYMBOL = "ferien.svg"

    PARAMETER = [Param("zeitraeume", "Zeiträume", "", [], darstellung=ZEITRAEUME)]

    PORTS = [Port("ferien", SIGNAL, AUSGANG, FERIEN)]

    AUSGABEN = ["ferien"]

    def berechne(self, ein, p, zustand):
        s = zustand.get("stunde") or {}
        zeitpunkt = s.get("zeitpunkt")
        if zeitpunkt is None:
            return {"ferien": 0.0}, zustand

        heute = zeitpunkt.month * 100 + zeitpunkt.day
        for zeitraum in p.get("zeitraeume") or []:
            von = _als_tagesnummer(zeitraum["von"])
            bis = _als_tagesnummer(zeitraum["bis"])
            if von <= bis:
                treffer = von <= heute <= bis
            else:  # ueber den Jahreswechsel
                treffer = heute >= von or heute <= bis
            if treffer:
                return {"ferien": 1.0}, zustand
        return {"ferien": 0.0}, zustand
