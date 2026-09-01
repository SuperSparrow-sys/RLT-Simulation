"""Tageslastprofil mit drei Lastgaengen. Formel aus Anlage!AT32 bis AV32."""

from core.bausteine.basis import (
    AUSGANG, LASTGANG, SIGNAL, ZEITREIHE, Baustein, Param, Port, registriere,
)


@registriere
class Tageslastprofil(Baustein):
    KENNUNG = "tageslastprofil"
    NAME = "Tageslastprofil"
    GRUPPE = "Zeit und Betrieb"
    SYMBOL = "tageslastprofil.svg"

    PARAMETER = [
        Param("lastgang_1", "Lastgang 1", "-", [1.0] * 24, darstellung=ZEITREIHE),
        Param("lastgang_2", "Lastgang 2", "-", [0.0] * 24, darstellung=ZEITREIHE),
        Param("lastgang_3", "Lastgang 3", "-", [0.0] * 24, darstellung=ZEITREIHE),
    ]

    PORTS = [
        Port("lastgang_1", SIGNAL, AUSGANG, LASTGANG),
        Port("lastgang_2", SIGNAL, AUSGANG, LASTGANG),
        Port("lastgang_3", SIGNAL, AUSGANG, LASTGANG),
    ]

    AUSGABEN = ["lastgang_1", "lastgang_2", "lastgang_3"]

    def berechne(self, ein, p, zustand):
        s = zustand.get("stunde") or {}
        zeitpunkt = s.get("zeitpunkt")
        if zeitpunkt is None:
            return {name: 0.0 for name in self.AUSGABEN}, zustand

        stunde_des_tages = zeitpunkt.hour
        aus = {}
        for name in self.AUSGABEN:
            werte = p.get(name) or [0.0] * 24
            aus[name] = float(werte[stunde_des_tages])
        return aus, zustand
