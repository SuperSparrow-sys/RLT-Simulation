"""Zweistufiger P-Regler.

Formeln aus Anlage!K51/J57 (schnelle Stufe) und K53/J61 (traege Stufe). Der
Ausgang bezieht sich auf seinen eigenen Vorwert; ueber die Iterationen des
Vorwaertslaufs wirkt der Regler dadurch integrierend. Das ist in der Excel so
gewollt und wird bewusst uebernommen.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, ISTWERT, SIGNAL, SOLLWERT, STELLGROESSE,
    Baustein, Param, Port, registriere,
)


def klemme(wert, unten=0.0, oben=100.0):
    return max(unten, min(oben, wert))


@registriere
class PRegler(Baustein):
    # Der Ausgang bezieht sich auf seinen eigenen Vorwert - er baut sich ueber
    # die Iterationen des Vorwaertslaufs auf, genau wie in der Excel.
    ZUSTAND_UEBER_ITERATION = True

    KENNUNG = "p_regler"
    NAME = "P-Regler"
    GRUPPE = "Regelung"
    SYMBOL = "p_regler.svg"

    PARAMETER = [
        Param("xp_1", "Xp Regler 1 (schnell)", "-", 10.0),
        Param("xp_2", "Xp Regler 2 (träge)", "-", 5.0),
        Param("sollwert_1", "Sollwert 1", "-", 0.0),
        Param("sollwert_2", "Sollwert 2", "°C", 20.0),
    ]

    PORTS = [
        # Stufe 2 steht bewusst zuerst: In der Excel traegt nur der traege Regler
        # einen Sollwert (Anlage!M59), waehrend der schnelle auf '???' steht. Bei
        # gleicher Bewertung entscheidet die Reihenfolge, und ein Pfeil soll die
        # Stufe treffen, die tatsaechlich regelt.
        Port("sollwert_2", SIGNAL, EINGANG, SOLLWERT),
        Port("istwert_2", SIGNAL, EINGANG, ISTWERT),
        Port("ausgang_2", SIGNAL, AUSGANG, STELLGROESSE),
        Port("sollwert_1", SIGNAL, EINGANG, SOLLWERT),
        Port("istwert_1", SIGNAL, EINGANG, ISTWERT),
        Port("ausgang_1", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["ausgang_1", "ausgang_2"]

    def _stufe(self, y_alt, sollwert, istwert, xp):
        if not xp:
            return y_alt
        return klemme(y_alt - (istwert - sollwert) / xp)

    def berechne(self, ein, p, zustand):
        # Ist der Sollwert-Port nicht belegt, gilt der eingestellte Parameter -
        # in der Excel steht der Sollwert ebenfalls als feste Zelle (Anlage!M59).
        # p traegt, aus vorgabeparameter() kommend, immer alle deklarierten
        # Parameter; ein fehlender Sollwert soll deshalb laut mit KeyError
        # zuschlagen statt still zu 0 zu werden.
        y1 = self._stufe(
            float(zustand.get("y1", 0.0)),
            float(ein.get("sollwert_1", p["sollwert_1"])),
            float(ein.get("istwert_1", 0.0)),
            p["xp_1"],
        )
        y2 = self._stufe(
            float(zustand.get("y2", 0.0)),
            float(ein.get("sollwert_2", p["sollwert_2"])),
            float(ein.get("istwert_2", 0.0)),
            p["xp_2"],
        )
        return {"ausgang_1": y1, "ausgang_2": y2}, {"y1": y1, "y2": y2}

    def anfangszustand(self, p):
        return {"y1": 0.0, "y2": 0.0}
