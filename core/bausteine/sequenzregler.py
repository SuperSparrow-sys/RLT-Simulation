"""Sequenzregler: eine Regelabweichung auf fuenf Stufen.

Formeln aus Anlage!T138 bis S148. Die Regelabweichung laeuft zwischen -300 und
+200; daraus werden drei Waerme- und zwei Kaeltestufen abgeleitet.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, ISTWERT, SIGNAL, STELLGROESSE,
    Baustein, Param, Port, registriere,
)

# Anlage!S144 bis S148: MAX(0;MIN(-(e+200);100)) fuer waermer_3 bis
# MAX(0;MIN(e-100;100)) fuer kaelter_2. Mit "vorzeichen * (e + versatz)"
# braucht die Vorzeichen-(-1)-Haelfte den Versatz mit demselben Vorzeichen wie
# in der Excel-Formel (+200/+100/0), nicht das umgekehrte - sonst reproduziert
# die Tabelle nicht -(e+200) sondern -(e-200).
STUFEN = (
    ("waermer_3", 200.0, -1.0),
    ("waermer_2", 100.0, -1.0),
    ("waermer_1", 0.0, -1.0),
    ("kaelter_1", 0.0, 1.0),
    ("kaelter_2", -100.0, 1.0),
)


@registriere
class Sequenzregler(Baustein):
    # Der Ausgang bezieht sich auf seinen eigenen Vorwert - er baut sich ueber
    # die Iterationen des Vorwaertslaufs auf, genau wie in der Excel.
    ZUSTAND_UEBER_ITERATION = True

    KENNUNG = "sequenzregler"
    NAME = "Sequenzregler"
    GRUPPE = "Regelung"
    SYMBOL = "sequenzregler.svg"

    PARAMETER = [
        Param("oberer_sw", "oberer Sollwert", "°C", 24.0),
        Param("unterer_sw", "unterer Sollwert", "°C", 20.0),
        Param("xp", "Xp", "-", 5.0),
    ]

    PORTS = [
        Port("istwert", SIGNAL, EINGANG, ISTWERT),
        Port("waermer_3", SIGNAL, AUSGANG, STELLGROESSE),
        Port("waermer_2", SIGNAL, AUSGANG, STELLGROESSE),
        Port("waermer_1", SIGNAL, AUSGANG, STELLGROESSE),
        Port("kaelter_1", SIGNAL, AUSGANG, STELLGROESSE),
        Port("kaelter_2", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["waermer_3", "waermer_2", "waermer_1", "kaelter_1", "kaelter_2", "e"]

    def berechne(self, ein, p, zustand):
        istwert = float(ein.get("istwert", 0.0))
        e_alt = float(zustand.get("e", 0.0))

        if p["unterer_sw"] < istwert < p["oberer_sw"]:
            e = 0.0
        else:
            if istwert < p["unterer_sw"]:
                delta = (istwert - p["unterer_sw"]) / 10.0
            else:
                delta = (istwert - p["oberer_sw"]) / 10.0
            e = max(-300.0, min(200.0, e_alt + delta))

        aus = {}
        for name, versatz, vorzeichen in STUFEN:
            aus[name] = max(0.0, min(vorzeichen * (e + versatz) * 1.0, 100.0))
        aus["e"] = e
        return aus, {"e": e}

    def anfangszustand(self, p):
        return {"e": 0.0}
