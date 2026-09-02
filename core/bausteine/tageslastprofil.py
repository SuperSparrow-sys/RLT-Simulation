"""Tageslastprofil mit drei Lastgaengen. Formel aus Anlage!AT32 bis AV32."""

from core.bausteine.basis import (
    AUSGANG, LASTGANG, SIGNAL, ZEITREIHE, Baustein, Param, Port, registriere,
)


# Die 24 Zahlen sind ANTEILE, keine Prozentwerte und keine Leistungen - ohne
# Einheit stand dort nur "0,4" und niemand konnte wissen, dass das 40 % der
# Nennlast sind. Die Einheit sagt es an jedem der drei Felder, der ausfuehrliche
# Hinweis nur am ersten.
ANTEIL = "Anteil 0–1"


@registriere
class Tageslastprofil(Baustein):
    KENNUNG = "tageslastprofil"
    NAME = "Tageslastprofil"
    GRUPPE = "Zeit und Betrieb"
    SYMBOL = "tageslastprofil.svg"

    PARAMETER = [
        Param("lastgang_1", "Lastgang 1", ANTEIL, [1.0] * 24, darstellung=ZEITREIHE,
              hinweis="Ein Wert je Stunde des Tages, als Anteil der Nennlast: 1,0 ist "
                      "voller Betrieb, 0,4 sind 40 %, 0 ist aus. Die Karte "
                      "„Anlagenbetrieb“ macht daraus den Stellgrad in Prozent."),
        Param("lastgang_2", "Lastgang 2", ANTEIL, [0.0] * 24, darstellung=ZEITREIHE),
        Param("lastgang_3", "Lastgang 3", ANTEIL, [0.0] * 24, darstellung=ZEITREIHE),
    ]

    PORTS = [
        Port("lastgang_1", SIGNAL, AUSGANG, LASTGANG),
        Port("lastgang_2", SIGNAL, AUSGANG, LASTGANG),
        Port("lastgang_3", SIGNAL, AUSGANG, LASTGANG),
    ]

    AUSGABEN = ["lastgang_1", "lastgang_2", "lastgang_3"]
    AUSGABE_LABEL = {
        "lastgang_1": "Lastgang 1 (Anteil 0–1)",
        "lastgang_2": "Lastgang 2 (Anteil 0–1)",
        "lastgang_3": "Lastgang 3 (Anteil 0–1)",
    }

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
