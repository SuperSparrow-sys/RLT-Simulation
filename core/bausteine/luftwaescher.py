"""Luftwaescher, adiabate Befeuchtung.

Formeln aus Anlage!AF120 bis AF122 (Saettigungszustand aus der Enthalpie) und
AE131 bis AE135. Der feste Faktor 0,9 ist der Saettigungswirkungsgrad der Excel.
"""

from core.bausteine import stoffdaten as st
from core.bausteine.basis import (
    AUSGANG, AUSWAHL, EINGANG, LUFT, MESSWERT, PROZENT, SIGNAL, STELLGROESSE,
    STROM, WASSER, ZAHL, ZULUFT,
    Baustein, Luft, Param, Port, druckverlust, registriere, wahl,
    strangparameter, strangrolle,
)

SAETTIGUNGSWIRKUNGSGRAD = 0.9


def _ports(rolle):
    """Die Anschluesse des Luftwaeschers. Die Luftrolle haengt am Einbauort -
    siehe core/bausteine/basis.py, strangparameter().
    """
    return [
        Port("luft_ein", LUFT, EINGANG, rolle),
        Port("luft_aus", LUFT, AUSGANG, rolle),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
        Port("PE_Pumpe", SIGNAL, AUSGANG, STROM),
        Port("wasser", SIGNAL, AUSGANG, WASSER),
    ]


@registriere
class Luftwaescher(Baustein):
    KENNUNG = "luftwaescher"
    NAME = "Luftwäscher"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "luftwaescher.svg"

    PARAMETER = strangparameter() + [
        Param("V_nenn", "Nennvolumenstrom (V_nenn)", "m³/h", 8200.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0,
              hinweis="Bestimmt zugleich die Pumpenleistung - der Wäscher wird auf "
                      "diese Luftmenge ausgelegt."),
        Param("dp_nenn", "Druckverlust bei Nennvolumenstrom (dp_nenn)", "Pa", 50.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0),
        Param("absalzverlust", "Absalzverlust", "%", 10.0,
              darstellung=PROZENT, dezimalstellen=1, minimum=0.0, maximum=100.0,
              hinweis="Zusätzliches Wasser, das abgeschlämmt wird, damit sich keine "
                      "Salze aufkonzentrieren. 10 % heißt: Verbraucht werden 110 % "
                      "des Wassers, das tatsächlich verdunstet."),
        Param(
            "pumpenart", "Art der Pumpenregelung", "-", "H",
            auswahl=(
                wahl("V", "Ventil (V)"),
                wahl("F", "Frequenzumrichter (F)"),
                wahl("H", "HD (Hochdruck)"),
            ),
            darstellung=AUSWAHL,
        ),
    ]

    PORTS = _ports(ZULUFT)

    @classmethod
    def ports_fuer(cls, p):
        return _ports(strangrolle(p))

    AUSGABEN = ["T_aus", "F_aus", "PE_Pumpe", "wasser", "dp"]
    AUSGABE_LABEL = {
        "T_aus": "Austrittstemperatur (°C)",
        "F_aus": "Austrittsfeuchte, absolut (g/kg)",
        "PE_Pumpe": "elektrische Leistung der Pumpe (kW)",
        "wasser": "Wasserverbrauch (l/h)",
        "dp": "Druckverlust (Pa)",
    }

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        u = float(ein.get("stellgroesse", 0.0))

        h_ein = st.enthalpie(luft.T, luft.x)
        x_saett = 0.0009 * h_ein**2 + 0.1669 * h_ein + 2.0433
        t_saett = -0.0024 * h_ein**2 + 0.5746 * h_ein - 5.0241

        anteil = SAETTIGUNGSWIRKUNGSGRAD * u / 100.0
        T_aus = luft.T - anteil * (luft.T - t_saett)
        x_aus = luft.x + anteil * (x_saett - luft.x)

        wasser = 0.0
        if luft.V > 0:
            wasser = (
                luft.V * 1.2 * (x_aus - luft.x) / 1000.0
                * (100.0 + p["absalzverlust"]) / 100.0
            )

        PE = 0.0
        if luft.V > 0:
            art = str(p["pumpenart"]).upper()
            if art == "F":
                kennlinie = (u / 100.0) ** 2
            elif art == "V":
                kennlinie = (u / 100.0) ** 0.3
            elif art == "H":
                kennlinie = 0.4 * (u / 100.0) ** 2
            else:
                kennlinie = 1.0
            PE = p["V_nenn"] * 1.2 / 3600.0 * 200.0 / 0.6 / 1000.0 * kennlinie

        dp = druckverlust(luft.V, p["V_nenn"], p["dp_nenn"])

        return (
            {
                "luft_aus": Luft(V=luft.V, T=T_aus, x=x_aus, dp=dp),
                "PE_Pumpe": PE, "wasser": wasser,
                "T_aus": T_aus, "F_aus": x_aus, "dp": dp,
            },
            zustand,
        )
