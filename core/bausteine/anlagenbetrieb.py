"""Anlagenbetrieb. Verknuepft Zeitplan, Ferien und Tagesprofil.

Formeln aus Anlage!AL37 (Betrieb) und AL38 (Stellgrad in Prozent).
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, MESSWERT, SIGNAL, STELLGROESSE,
    Baustein, Port, registriere,
)


@registriere
class Anlagenbetrieb(Baustein):
    KENNUNG = "anlagenbetrieb"
    NAME = "Anlagenbetrieb"
    GRUPPE = "Zeit und Betrieb"
    SYMBOL = "anlagenbetrieb.svg"

    PARAMETER = []

    PORTS = [
        Port("zeitplan", SIGNAL, EINGANG, MESSWERT),
        Port("ferien", SIGNAL, EINGANG, MESSWERT),
        Port("tagesprofil", SIGNAL, EINGANG, MESSWERT),
        Port("betrieb", SIGNAL, AUSGANG, MESSWERT),
        Port("stellgrad", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["betrieb", "stellgrad"]

    def berechne(self, ein, p, zustand):
        zeitplan = float(ein.get("zeitplan", 1.0))
        ferien = float(ein.get("ferien", 0.0))
        profil = float(ein.get("tagesprofil", 1.0))

        betrieb = zeitplan * (1.0 - ferien)
        stellgrad = betrieb * profil * 100.0
        return {"betrieb": betrieb, "stellgrad": stellgrad}, zustand
