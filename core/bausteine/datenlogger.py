"""Datenlogger. Entspricht den Spalten Wert1 bis Wert10 aus Anlage!B26:D46.

Angeschlossene Groessen erscheinen als eigene Spalte im Stundenprotokoll.
"""

from core.bausteine.basis import (
    EINGANG, PROTOKOLL, SIGNAL, TEXTLISTE, Baustein, Param, Port, registriere,
)

ANZAHL = 10


@registriere
class Datenlogger(Baustein):
    KENNUNG = "datenlogger"
    NAME = "Datenlogger"
    GRUPPE = "Verbraucher"
    SYMBOL = "datenlogger.svg"

    PARAMETER = [
        Param("namen", "Spaltennamen", "", [""] * ANZAHL, darstellung=TEXTLISTE),
        Param("einheiten", "Einheiten", "", [""] * ANZAHL, darstellung=TEXTLISTE),
    ]

    PORTS = [
        Port(f"wert_{i}", SIGNAL, EINGANG, PROTOKOLL) for i in range(1, ANZAHL + 1)
    ]

    AUSGABEN = [f"wert_{i}" for i in range(1, ANZAHL + 1)]

    def spalten(self, p):
        """Die belegten Spalten als (Portschluessel, Name, Einheit)."""
        namen = p.get("namen") or [""] * ANZAHL
        einheiten = p.get("einheiten") or [""] * ANZAHL
        return [
            (f"wert_{i + 1}", namen[i], einheiten[i])
            for i in range(ANZAHL)
            if namen[i]
        ]

    def berechne(self, ein, p, zustand):
        return {
            f"wert_{i}": float(ein.get(f"wert_{i}", 0.0))
            for i in range(1, ANZAHL + 1)
        }, zustand
