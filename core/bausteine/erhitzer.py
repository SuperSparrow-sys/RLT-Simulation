"""Lufterhitzer. Formeln aus Anlage!M19, M17, M21 und dem Block R116:T136."""

from core.bausteine.basis import (
    AUSGANG, EINGANG, LUFT, MESSWERT, SIGNAL, STELLGROESSE, WAERME, ZAHL, ZULUFT,
    Baustein, Luft, Param, Port, druckverlust, registriere,
)


@registriere
class Erhitzer(Baustein):
    KENNUNG = "erhitzer"
    NAME = "Erhitzer"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "erhitzer.svg"

    PARAMETER = [
        Param("V_nenn", "V_nenn", "m³/h", 8200.0, darstellung=ZAHL, dezimalstellen=0),
        Param("dp_nenn", "dp_nenn", "Pa", 240.0, darstellung=ZAHL, dezimalstellen=0),
        Param("QH_max", "QH_max", "kW", 101.0, darstellung=ZAHL, dezimalstellen=1),
    ]

    PORTS = [
        Port("luft_ein", LUFT, EINGANG, ZULUFT),
        Port("luft_aus", LUFT, AUSGANG, ZULUFT),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
        Port("QH", SIGNAL, AUSGANG, WAERME),
    ]

    AUSGABEN = ["T_aus", "F_aus", "QH", "dp"]
    AUSGABE_LABEL = {"T_aus": "Austrittstemperatur"}

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        u = float(ein.get("stellgroesse", 0.0))

        QH = 0.0 if luft.V <= 0 else u / 100.0 * p["QH_max"]

        T_aus = luft.T
        if luft.V > 0:
            T_aus = luft.T + 3600.0 * QH / (1.2 * 1.007 * luft.V)

        dp = druckverlust(luft.V, p["V_nenn"], p["dp_nenn"])

        aus = Luft(V=luft.V, T=T_aus, x=luft.x, dp=dp)
        return {"luft_aus": aus, "QH": QH, "T_aus": T_aus, "F_aus": luft.x, "dp": dp}, zustand
