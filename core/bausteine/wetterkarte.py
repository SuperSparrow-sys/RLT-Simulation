"""Wetterkarte. Liefert die Werte der aktuellen Stunde als Signale.

Entspricht dem Block Anlage!F2:H22, den das VBA-Makro vor jeder Stunde
beschreibt. Der Solver legt die Stundenwerte in zustand['stunde'] ab.
"""

from core.bausteine.basis import (
    AUSGANG, MESSWERT, SIGNAL, Baustein, Port, registriere,
)

FELDER = {
    "T_AU": "t_au",
    "F_AU": "x_au",
    "QH_S": "str_s",
    "QH_O": "str_o",
    "QH_W": "str_w",
    "QH_N": "str_n",
    "QH_H": "str_h",
}


@registriere
class Wetterkarte(Baustein):
    KENNUNG = "wetter"
    NAME = "Wetterdaten"
    GRUPPE = "Quellen und Senken"
    SYMBOL = "wetter.svg"

    PARAMETER = []

    PORTS = [
        Port(name, SIGNAL, AUSGANG, MESSWERT) for name in FELDER
    ]

    AUSGABEN = list(FELDER)

    def berechne(self, ein, p, zustand):
        stunde = zustand.get("stunde") or {}
        return {
            port: float(stunde.get(feld, 0.0)) for port, feld in FELDER.items()
        }, zustand

    def bedarf(self, aus_bedarf, p):
        return {}
