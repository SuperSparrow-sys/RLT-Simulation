"""Dampfbefeuchter mit Elektro- oder Fremddampf.

Formeln aus Anlage!Q120 bis Q122 und P131 bis P134. Bei Elektrodampf rechnet die
Excel mit fester Dampfenthalpie 2676 kJ/kg und schlaegt den Absalzverlust auf den
Wasserverbrauch auf.
"""

from core.bausteine import stoffdaten as st
from core.bausteine.basis import (
    AUSGANG, EINGANG, LUFT, MESSWERT, SIGNAL, STELLGROESSE, WAERME, WASSER, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)


@registriere
class Dampfbefeuchter(Baustein):
    KENNUNG = "dampfbefeuchter"
    NAME = "Dampfbefeuchter"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "dampfbefeuchter.svg"

    PARAMETER = [
        Param("dampftemperatur", "Dampftemp.", "°C", 180.0),
        Param("absalzverlust", "Absalzverlust", "%", 10.0),
        Param("max_leistung", "max. Bef.Leist", "kg/h", 32.0),
        Param("dampfart", "E-/Fremddampf", "-", "E", auswahl=("E", "F")),
    ]

    PORTS = [
        Port("luft_ein", LUFT, EINGANG, ZULUFT),
        Port("luft_aus", LUFT, AUSGANG, ZULUFT),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
        Port("QH", SIGNAL, AUSGANG, WAERME),
        Port("wasser", SIGNAL, AUSGANG, WASSER),
    ]

    AUSGABEN = ["T_aus", "F_aus", "QH", "wasser", "warnung"]

    def dampfenthalpie(self, p):
        if str(p["dampfart"]).upper() == "E":
            return 2676.0
        T_D = p["dampftemperatur"]
        return (
            2501.482
            + 1.789736 * T_D
            + 8.957546e-4 * T_D**2
            - 1.300254e-5 * T_D**3
        )

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        u = float(ein.get("stellgroesse", 0.0))
        h_D = self.dampfenthalpie(p)

        if luft.V <= 0:
            return (
                {
                    "luft_aus": luft.kopie(), "QH": 0.0, "wasser": 0.0, "warnung": "",
                    "T_aus": luft.T, "F_aus": luft.x,
                },
                zustand,
            )

        T_aus = luft.T + u / 100.0 * p["max_leistung"] * (h_D - 2256.9) / (
            luft.V * 1.2 * 1.007
        )
        x_grenze = st.x_saett(luft.T)
        x_roh = luft.x + 1000.0 * u / 100.0 * p["max_leistung"] / (luft.V * 1.2)
        x_aus = min(x_grenze, x_roh)

        aufschlag = 1.0
        if str(p["dampfart"]).upper() == "E":
            aufschlag = (100.0 + p["absalzverlust"]) / 100.0
        wasser = aufschlag * u / 100.0 * p["max_leistung"]
        QH = wasser * (h_D - 42.0) / 3600.0

        warnung = "Uebersaettigung" if x_roh >= x_grenze else ""

        return (
            {
                "luft_aus": Luft(V=luft.V, T=T_aus, x=x_aus, dp=luft.dp),
                "QH": QH, "wasser": wasser, "warnung": warnung,
                "T_aus": T_aus, "F_aus": x_aus,
            },
            zustand,
        )
