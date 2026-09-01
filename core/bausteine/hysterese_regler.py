"""Zweipunktregler mit Schaltdifferenz. Formel aus Anlage!V155/AB57."""

from core.bausteine.basis import (
    AUSGANG, EINGANG, ISTWERT, SIGNAL, SOLLWERT, STELLGROESSE,
    Baustein, Param, Port, registriere,
)


@registriere
class HystereseRegler(Baustein):
    # Der Ausgang bezieht sich auf seinen eigenen Vorwert - er baut sich ueber
    # die Iterationen des Vorwaertslaufs auf, genau wie in der Excel.
    ZUSTAND_UEBER_ITERATION = True

    KENNUNG = "hysterese_regler"
    NAME = "Hysterese-Regler"
    GRUPPE = "Regelung"
    SYMBOL = "hysterese_regler.svg"

    PARAMETER = [
        Param("hysterese", "Hysterese", "-", 0.1),
        Param("sollwert", "Sollwert", "-", 0.0),
    ]

    PORTS = [
        Port("sollwert", SIGNAL, EINGANG, SOLLWERT),
        Port("istwert", SIGNAL, EINGANG, ISTWERT),
        Port("ausgang", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["ausgang"]

    def berechne(self, ein, p, zustand):
        # Ist der Sollwert-Port nicht belegt, gilt der eingestellte Parameter.
        # "ein.get(schluessel, p[schluessel])" wertet den Default eager aus und
        # wirft KeyError, sobald p den Schluessel nicht hat - auch wenn ein ihn
        # liefert. Deshalb hier mit kurzgeschlossener Fallback-Kette.
        sollwert = ein["sollwert"] if "sollwert" in ein else p.get("sollwert", 0.0)
        sollwert = float(sollwert)
        istwert = float(ein.get("istwert", 0.0))
        vorher = float(zustand.get("zustand", 0.0))
        halb = p["hysterese"] / 2.0

        if istwert > sollwert + halb:
            y = 100.0
        elif istwert < sollwert - halb:
            y = 0.0
        else:
            y = vorher

        return {"ausgang": y}, {"zustand": y}

    def anfangszustand(self, p):
        return {"zustand": 0.0}
