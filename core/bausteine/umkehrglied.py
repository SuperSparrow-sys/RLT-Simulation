"""Ein Signal gegen einen Bezugswert gespiegelt, begrenzt auf 0 bis 100 Prozent.

Anlage!S16 = MAX(100-S61; S72) zieht den Ausgang des Entfeuchtungsreglers von 100
ab, bevor er mit dem Kuehlregler verglichen wird - je feuchter der Raum, desto
weiter soll der Kuehler oeffnen, aber der Entfeuchtungsregler selbst zaehlt
umgekehrt (er meldet, wie weit er ZU-fahren moechte). Diese Umkehr steht als
eigene Karte VOR dem Maximalglied, statt als Parameter AM Maximalglied zu haengen:
so bleibt das Maximalglied ein gewoehnlicher, ordnungsunabhaengiger Baustein, den
sich jeder frei zusammenstecken kann, ohne die Ports zu kennen, die die
automatische Verdrahtung am Ende vergibt.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, PROZENT, SIGNAL, STELLGROESSE,
    Baustein, Param, Port, registriere,
)


@registriere
class Umkehrglied(Baustein):
    KENNUNG = "umkehrglied"
    NAME = "Umkehrglied"
    GRUPPE = "Regelung"
    SYMBOL = "umkehrglied.svg"

    # "bezug" war mit "-" beschriftet, obwohl gegen ein 0-100-Prozent-Signal
    # gespiegelt wird (siehe Docstring oben und berechne() unten).
    PARAMETER = [
        Param("bezug", "Bezugswert", "%", 100.0, darstellung=PROZENT, dezimalstellen=1)
    ]

    PORTS = [
        Port("ein", SIGNAL, EINGANG, STELLGROESSE),
        Port("ausgang", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["ausgang"]

    def berechne(self, ein, p, zustand):
        wert = p["bezug"] - float(ein.get("ein", 0.0))
        return {"ausgang": max(0.0, min(wert, 100.0))}, zustand
