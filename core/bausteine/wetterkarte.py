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
    # Die Einheit steht in der Beschriftung, weil diese Karte fast nur ueber
    # ihre Anschluesse wahrgenommen wird - im Parameterfenster hat sie kein
    # einziges Feld, an dem sonst eine Einheit haengen koennte.
    AUSGABE_LABEL = {
        "T_AU": "Außentemperatur (°C)",
        "F_AU": "Außenfeuchte, absolut (g/kg)",
        "QH_S": "Sonneneinstrahlung Süd (W/m²)",
        "QH_O": "Sonneneinstrahlung Ost (W/m²)",
        "QH_W": "Sonneneinstrahlung West (W/m²)",
        "QH_N": "Sonneneinstrahlung Nord (W/m²)",
        "QH_H": "Sonneneinstrahlung waagerecht (W/m²)",
    }

    def berechne(self, ein, p, zustand):
        stunde = zustand.get("stunde") or {}
        return {
            port: float(stunde.get(feld, 0.0)) for port, feld in FELDER.items()
        }, zustand

    def bedarf(self, aus_bedarf, p):
        return {}
