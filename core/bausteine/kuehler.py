"""Luftkuehler mit Taupunktentfeuchtung.

Formeln aus Anlage!AC117, AB131 bis AB135 sowie der Warnung in AA136.
Die Oberflaechentemperatur wird wie in der Excel als Kaltwassertemperatur plus
15 Prozent der Spreizung zur Eintrittsluft angesetzt.
"""

from core.bausteine import stoffdaten as st
from core.bausteine.basis import (
    AUSGANG, EINGANG, KAELTE, LUFT, MESSWERT, SIGNAL, STELLGROESSE, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)


@registriere
class Kuehler(Baustein):
    KENNUNG = "kuehler"
    NAME = "Kühler"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "kuehler.svg"

    PARAMETER = [
        Param("V_nenn", "V_nenn", "m³/h", 8200.0),
        Param("dp_nenn", "dp_nenn", "Pa", 240.0),
        Param("QK_nenn", "QK_nenn", "kW", 63.0),
        Param("T_KW_mittel", "T_KW_mittel", "°C", 6.0),
    ]

    PORTS = [
        Port("luft_ein", LUFT, EINGANG, ZULUFT),
        Port("luft_aus", LUFT, AUSGANG, ZULUFT),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
        Port("QK", SIGNAL, AUSGANG, KAELTE),
    ]

    AUSGABEN = ["T_aus", "F_aus", "QK", "dp"]

    def oberflaechentemperatur(self, T_ein, p):
        return p["T_KW_mittel"] + 0.15 * (T_ein - p["T_KW_mittel"])

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        u = float(ein.get("stellgroesse", 0.0))

        T_O = self.oberflaechentemperatur(luft.T, p)
        x_O = st.x_saett(T_O)

        T_aus = luft.T - u / 100.0 * (luft.T - T_O)
        x_aus = luft.x
        if x_O < luft.x:
            x_aus = luft.x - u / 100.0 * (luft.x - x_O)

        QK = 0.0
        if luft.V > 0:
            QK = luft.V / 3600.0 * 1.2 * (
                st.enthalpie(luft.T, luft.x) - st.enthalpie(T_aus, x_aus)
            )

        dp = 0.0
        if p["V_nenn"]:
            dp = p["dp_nenn"] * (luft.V / p["V_nenn"]) ** 2

        warnung = "Kuehlleistung zu niedrig" if QK > p["QK_nenn"] else ""

        aus = Luft(V=luft.V, T=T_aus, x=x_aus, dp=dp)
        return (
            {
                "luft_aus": aus, "QK": QK, "warnung": warnung,
                "T_aus": T_aus, "F_aus": x_aus, "dp": dp,
            },
            zustand,
        )
