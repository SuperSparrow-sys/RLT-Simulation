"""Anlagenbetrieb. Verknuepft Zeitplan, Ferien und Tagesprofil.

Formeln aus Anlage!AL37 (Betrieb) und AL38 (Stellgrad in Prozent).
"""

from core.bausteine.basis import (
    AUSGANG, BETRIEB, EINGANG, FERIEN, LASTGANG, SIGNAL, STELLGROESSE, ZEITPLAN,
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
        # zeitplan ist dynamisch: die Mappe fuehrt zwei Zeitplanbloecke
        # nebeneinander (Anlage!AK4 und AO4), und beide duerfen auf dieselbe
        # Betriebskarte laufen.
        Port("zeitplan", SIGNAL, EINGANG, ZEITPLAN, dynamisch=True),
        Port("ferien", SIGNAL, EINGANG, FERIEN),
        Port("tagesprofil", SIGNAL, EINGANG, LASTGANG),
        Port("betrieb", SIGNAL, AUSGANG, BETRIEB),
        Port("stellgrad", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["betrieb", "stellgrad"]

    def berechne(self, ein, p, zustand):
        # Mehrere Zeitplaene wirken wie hintereinandergeschaltete Schalter: die
        # Anlage laeuft nur, wenn alle sie freigeben. Bei einem einzigen Zeitplan
        # ist das genau Anlage!AL37.
        zeitplaene = [
            float(w) for s, w in ein.items()
            if s.startswith("zeitplan") and isinstance(w, (int, float))
        ]
        zeitplan = 1.0
        for wert in zeitplaene:
            zeitplan *= wert

        ferien = float(ein.get("ferien", 0.0))
        profil = float(ein.get("tagesprofil", 1.0))

        betrieb = zeitplan * (1.0 - ferien)
        stellgrad = betrieb * profil * 100.0
        return {"betrieb": betrieb, "stellgrad": stellgrad}, zustand
