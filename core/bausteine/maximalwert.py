"""Groesster von mehreren Signalwerten, einzelne davon umgekehrt gezaehlt.

In der Mappe stellt nicht immer ein Regler allein ein Ventil. Der Kuehler etwa
folgt Anlage!S16 = MAX(100-S61; S72): ein Regler entfeuchtet, der andere kuehlt,
und geoeffnet wird so weit, wie der fordernde von beiden es verlangt. Der
Entfeuchtungsregler geht dabei umgekehrt ein - sein Ausgang wird von 100 abgezogen.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, SIGNAL, STELLGROESSE, Baustein, Param, Port, registriere,
)


@registriere
class Maximalwert(Baustein):
    KENNUNG = "maximalwert"
    NAME = "Maximalwert"
    GRUPPE = "Regelung"
    SYMBOL = "maximalwert.svg"

    PARAMETER = [
        Param("invertiert", "umgekehrt gezählte Eingänge", "-", []),
    ]

    PORTS = [
        Port("ein", SIGNAL, EINGANG, STELLGROESSE, dynamisch=True),
        Port("ausgang", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["ausgang"]

    def berechne(self, ein, p, zustand):
        umgekehrt = set(p.get("invertiert") or [])
        werte = []
        for schluessel, wert in ein.items():
            if not schluessel.startswith("ein") or not isinstance(wert, (int, float)):
                continue
            werte.append(100.0 - float(wert) if schluessel in umgekehrt else float(wert))

        return {"ausgang": max(werte) if werte else 0.0}, zustand
