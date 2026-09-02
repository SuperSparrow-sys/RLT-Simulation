"""Ein Signal mit einem festen Faktor, begrenzt auf 0 bis 100 Prozent.

Damit laesst sich die Verriegelung aus Anlage!V16 ausdruecken: IF(AB16=100; 50; 0)
ist nichts anderes als das halbe Waeschersignal, weil ein Hystereseregler nur 0
oder 100 ausgibt. Der Erhitzer oeffnet dadurch auf 50 Prozent, sobald der
Luftwaescher laeuft, und waermt die adiabatisch gekuehlte Luft nach.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, SIGNAL, STELLGROESSE, ZAHL, Baustein, Param, Port, registriere,
)


@registriere
class Faktor(Baustein):
    KENNUNG = "faktor"
    NAME = "Faktor"
    GRUPPE = "Regelung"
    SYMBOL = "faktor.svg"

    PARAMETER = [
        Param("faktor", "Faktor", "dimensionslos", 1.0,
              darstellung=ZAHL, dezimalstellen=2,
              hinweis="Das Eingangssignal wird damit malgenommen, das Ergebnis auf "
                      "0 bis 100 % begrenzt. 0,5 heißt: Der Ausgang folgt dem "
                      "Eingang mit halbem Ausschlag.")
    ]

    PORTS = [
        Port("ein", SIGNAL, EINGANG, STELLGROESSE),
        Port("ausgang", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["ausgang"]
    AUSGABE_LABEL = {"ausgang": "Ausgangssignal (0–100 %)"}
    PORT_LABEL = {"ein": "Eingangssignal (0–100 %)"}

    def berechne(self, ein, p, zustand):
        wert = float(ein.get("ein", 0.0)) * p["faktor"]
        return {"ausgang": max(0.0, min(wert, 100.0))}, zustand
