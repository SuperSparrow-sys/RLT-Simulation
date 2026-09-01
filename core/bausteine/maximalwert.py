"""Groesster von mehreren Signalwerten.

In der Mappe stellt nicht immer ein Regler allein ein Ventil. Der Kuehler etwa
folgt Anlage!S16 = MAX(100-S61; S72): ein Regler entfeuchtet, der andere kuehlt,
und geoeffnet wird so weit, wie der fordernde von beiden es verlangt.

Die Umkehrung "100-S61" gehoert bewusst NICHT hierher, sondern in ein eigenes
Umkehrglied davor (core/bausteine/umkehrglied.py). Ein Parameter wie
"invertiert=['ein_1']" waere nur an der Vorlage richtig, die ihn schreibt - die
Nummerierung der dynamischen Eingaenge folgt der Reihenfolge, in der ihre Pfeile
angelegt werden (core/graph.py), und die kann niemand vorhersehen, der die Karte
im Editor aus der Palette zieht und frei verdrahtet. Ohne den Parameter ist das
Maximalglied symmetrisch und ordnungsunabhaengig - ein gewoehnlicher Baustein wie
jeder andere.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, SIGNAL, STELLGROESSE, Baustein, Port, registriere,
)


@registriere
class Maximalwert(Baustein):
    KENNUNG = "maximalwert"
    NAME = "Maximalwert"
    GRUPPE = "Regelung"
    SYMBOL = "maximalwert.svg"

    PARAMETER = []

    PORTS = [
        Port("ein", SIGNAL, EINGANG, STELLGROESSE, dynamisch=True),
        Port("ausgang", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["ausgang"]

    def berechne(self, ein, p, zustand):
        werte = [
            float(wert) for schluessel, wert in ein.items()
            if schluessel.startswith("ein") and isinstance(wert, (int, float))
        ]
        return {"ausgang": max(werte) if werte else 0.0}, zustand
