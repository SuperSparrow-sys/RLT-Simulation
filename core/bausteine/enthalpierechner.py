"""Hilfsbaustein zur Zustandsumrechnung. Anlage!U138:W148 und X141:Z148."""

from core.bausteine import stoffdaten as st
from core.bausteine.basis import (
    AUSGANG, EINGANG, MESSWERT, SIGNAL, Baustein, Port, registriere,
)


@registriere
class Enthalpierechner(Baustein):
    KENNUNG = "enthalpierechner"
    NAME = "Enthalpie / rel. Feuchte"
    GRUPPE = "Verbraucher"
    SYMBOL = "enthalpierechner.svg"

    PARAMETER = []

    PORTS = [
        Port("t", SIGNAL, EINGANG, MESSWERT),
        Port("x", SIGNAL, EINGANG, MESSWERT),
        Port("h", SIGNAL, AUSGANG, MESSWERT),
        Port("rF", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["h", "rF"]

    def berechne(self, ein, p, zustand):
        t = float(ein.get("t", 0.0))
        x = float(ein.get("x", 0.0))
        rF = st.rel_feuchte(t, x) if x > 0 else 0.0
        return {"h": st.enthalpie(t, x), "rF": rF}, zustand
