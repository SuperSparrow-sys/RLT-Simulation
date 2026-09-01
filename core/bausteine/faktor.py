"""Ein Signal mit einem festen Faktor, begrenzt auf 0 bis 100 Prozent.

Damit laesst sich die Verriegelung aus Anlage!V16 ausdruecken: IF(AB16=100; 50; 0)
ist nichts anderes als das halbe Waeschersignal, weil ein Hystereseregler nur 0
oder 100 ausgibt. Der Erhitzer oeffnet dadurch auf 50 Prozent, sobald der
Luftwaescher laeuft, und waermt die adiabatisch gekuehlte Luft nach.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, SIGNAL, STELLGROESSE, Baustein, Param, Port, registriere,
)


@registriere
class Faktor(Baustein):
    KENNUNG = "faktor"
    NAME = "Faktor"
    GRUPPE = "Regelung"
    SYMBOL = "faktor.svg"

    PARAMETER = [Param("faktor", "Faktor", "-", 1.0)]

    PORTS = [
        Port("ein", SIGNAL, EINGANG, STELLGROESSE),
        Port("ausgang", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["ausgang"]

    def berechne(self, ein, p, zustand):
        wert = float(ein.get("ein", 0.0)) * p["faktor"]
        return {"ausgang": max(0.0, min(wert, 100.0))}, zustand
