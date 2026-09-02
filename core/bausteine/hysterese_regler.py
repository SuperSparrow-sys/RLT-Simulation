"""Zweipunktregler mit Schaltdifferenz. Formel aus Anlage!V155/AB57."""

from core.bausteine.basis import (
    AUSGANG, EINGANG, ISTWERT, SIGNAL, SOLLWERT, STELLGROESSE, ZAHL,
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
        Param("hysterese", "Schaltdifferenz (Hysterese)", "Einheit des Istwerts", 0.1,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0,
              hinweis="Der Ausgang springt erst auf 100 %, wenn der Istwert um die "
                      "halbe Schaltdifferenz ÜBER dem Sollwert liegt, und zurück auf "
                      "0 %, wenn er ebenso weit darunter liegt. Dazwischen bleibt er, "
                      "wie er war - das verhindert ständiges Ein- und Ausschalten."),
        Param("sollwert", "Sollwert", "Einheit des Istwerts", 0.0,
              darstellung=ZAHL, dezimalstellen=2),
        # Anlage!AB56: Beim Waescherregler steht hier eine feste Zahl, und der
        # Sollwert kommt als Raumfeuchte von aussen. Befeuchtet wird, wenn der Raum
        # trockener ist als diese Zahl. Der Baustein ist dimensionsneutral - je
        # nachdem, was hier angeschlossen wird, ist es eine Temperatur (°C) oder
        # eine Feuchte (g/kg). Statt eines nichtssagenden "-" nennt die Einheit
        # deshalb ihren Bezug: "Einheit des Istwerts".
        Param("istwert", "Istwert (fest)", "Einheit des Istwerts", 0.0,
              darstellung=ZAHL, dezimalstellen=2),
    ]

    PORTS = [
        Port("sollwert", SIGNAL, EINGANG, SOLLWERT),
        Port("istwert", SIGNAL, EINGANG, ISTWERT),
        Port("ausgang", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["ausgang"]
    AUSGABE_LABEL = {"ausgang": "Schaltausgang (0 oder 100 %)"}

    def berechne(self, ein, p, zustand):
        # Ist der Sollwert-Port nicht belegt, gilt der eingestellte Parameter.
        # p traegt, aus vorgabeparameter() kommend, immer alle deklarierten
        # Parameter; ein fehlender Sollwert soll deshalb laut mit KeyError
        # zuschlagen statt still zu 0 zu werden.
        sollwert = float(ein.get("sollwert", p["sollwert"]))
        istwert = float(ein.get("istwert", p["istwert"]))
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
