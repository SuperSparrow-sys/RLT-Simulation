"""Lufterhitzer. Formeln aus Anlage!M19, M17, M21 und dem Block R116:T136."""

from core.bausteine.basis import (
    AUSGANG, EINGANG, LUFT, MESSWERT, SIGNAL, STELLGROESSE, WAERME, ZAHL, ZULUFT,
    Baustein, Luft, Param, Port, druckverlust, registriere,
    uebertragbare_leistung,
    strangparameter, strangrolle,
)


def _ports(rolle):
    """Die Anschluesse des Erhitzers. Die Luftrolle haengt am Einbauort -
    siehe core/bausteine/basis.py, strangparameter().
    """
    return [
        Port("luft_ein", LUFT, EINGANG, rolle),
        Port("luft_aus", LUFT, AUSGANG, rolle),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
        Port("QH", SIGNAL, AUSGANG, WAERME),
    ]


@registriere
class Erhitzer(Baustein):
    KENNUNG = "erhitzer"
    NAME = "Erhitzer"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "erhitzer.svg"

    PARAMETER = strangparameter() + [
        Param("V_nenn", "Nennvolumenstrom (V_nenn)", "m³/h", 8200.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0),
        Param("dp_nenn", "Druckverlust bei Nennvolumenstrom (dp_nenn)", "Pa", 240.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0,
              hinweis="Bei anderen Luftmengen wächst der Druckverlust im Quadrat: "
                      "halbe Luftmenge, ein Viertel Druckverlust. Auf die "
                      "Heizleistung hat er keinen Einfluss."),
        Param("QH_max", "Höchste Heizleistung (QH_max)", "kW", 101.0,
              darstellung=ZAHL, dezimalstellen=1, minimum=0.0,
              hinweis="Die Leistung folgt geradlinig der Stellgröße: 100 % ergeben "
                      "diesen Wert, 40 % ergeben 40 % davon."),
    ]

    PORTS = _ports(ZULUFT)

    @classmethod
    def ports_fuer(cls, p):
        return _ports(strangrolle(p))

    AUSGABEN = ["T_aus", "F_aus", "QH", "dp"]
    AUSGABE_LABEL = {
        "T_aus": "Austrittstemperatur (°C)",
        "F_aus": "Austrittsfeuchte, absolut (g/kg)",
        "QH": "Heizleistung (kW)",
        "dp": "Druckverlust (Pa)",
    }

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        u = float(ein.get("stellgroesse", 0.0))

        # Die Ventilstellung fordert an, das Register liefert - aber nur so
        # viel, wie es bei DIESER Luftmenge uebertragen kann. Ohne die zweite
        # Grenze gaebe ein 70-kW-Register auch bei einem Fuenftel der Luft
        # 70 kW ab, was ueber 300 K Temperaturerhoehung entspraeche. Bei
        # Nennvolumenstrom ist der Faktor genau 1,0; die Mappe faehrt
        # durchgehend dort und bleibt deshalb unberuehrt.
        moeglich = p["QH_max"] * uebertragbare_leistung(
            u / 100.0, luft.V, p["V_nenn"]
        )
        QH = 0.0 if luft.V <= 0 else min(u / 100.0 * p["QH_max"], moeglich)

        T_aus = luft.T
        if luft.V > 0:
            T_aus = luft.T + 3600.0 * QH / (1.2 * 1.007 * luft.V)

        dp = druckverlust(luft.V, p["V_nenn"], p["dp_nenn"])

        aus = Luft(V=luft.V, T=T_aus, x=luft.x, dp=dp)
        return {"luft_aus": aus, "QH": QH, "T_aus": T_aus, "F_aus": luft.x, "dp": dp}, zustand
