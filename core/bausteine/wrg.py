"""Waermerueckgewinnung mit Bypass.

Formeln aus Anlage!J152 bis J157 (Zuluft, Fortluft, Q_WRG, Druckverluste).
Der Wirkungsgrad wird mit dem Verhaeltnis des kleineren zum jeweiligen
Volumenstrom gewichtet, genau wie in der Excel.
"""

from core.bausteine.basis import (
    ABLUFT, AUSGANG, EINGANG, LUFT, MESSWERT, PROZENT, SIGNAL, STELLGROESSE,
    ZAHL, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)


@registriere
class Waermerueckgewinnung(Baustein):
    KENNUNG = "wrg"
    NAME = "Wärmerückgewinnung"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "wrg.svg"

    PARAMETER = [
        Param("V_nenn", "V_nenn", "m³/h", 12200.0, darstellung=ZAHL, dezimalstellen=0),
        Param("dp_WRG_nenn", "dp_WRG_nenn", "Pa", 170.0, darstellung=ZAHL, dezimalstellen=0),
        Param("dp_Bypass_nenn", "dp_Byp_nenn", "Pa", 50.0, darstellung=ZAHL, dezimalstellen=0),
        Param("rueckwaermzahl", "Rückwärmzahl", "%", 81.0, darstellung=PROZENT, dezimalstellen=1),
        Param("rueckfeuchtzahl", "Rückfeuchtzahl", "%", 0.0, darstellung=PROZENT, dezimalstellen=1),
    ]

    PORTS = [
        Port("zuluft_ein", LUFT, EINGANG, ZULUFT),
        Port("zuluft_aus", LUFT, AUSGANG, ZULUFT),
        Port("abluft_ein", LUFT, EINGANG, ABLUFT),
        Port("abluft_aus", LUFT, AUSGANG, ABLUFT),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("stellgroesse_bypass", SIGNAL, EINGANG, STELLGROESSE),
        Port("Q_WRG", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["T_ZU", "F_ZU", "T_FO", "F_FO", "Q_WRG", "dp_ZU", "dp_AB"]
    AUSGABE_LABEL = {"Q_WRG": "rückgewonnene Leistung"}

    def berechne(self, ein, p, zustand):
        zu = ein.get("zuluft_ein", Luft())
        ab = ein.get("abluft_ein", Luft())
        u = float(ein.get("stellgroesse", 0.0))
        byp = float(ein.get("stellgroesse_bypass", 0.0))

        wirksam = 0.0
        if zu.V > 0 and ab.V > 0:
            wirksam = u / 100.0 * (100.0 - byp) / 100.0

        kleiner = min(zu.V, ab.V) if (zu.V > 0 and ab.V > 0) else 0.0

        T_ZU, F_ZU, T_FO, F_FO = zu.T, zu.x, ab.T, ab.x
        if wirksam > 0:
            anteil_zu = kleiner / zu.V
            anteil_ab = kleiner / ab.V
            T_ZU = zu.T + p["rueckwaermzahl"] / 100.0 * (ab.T - zu.T) * anteil_zu * wirksam
            F_ZU = zu.x + p["rueckfeuchtzahl"] / 100.0 * (ab.x - zu.x) * anteil_zu * wirksam
            T_FO = ab.T - p["rueckwaermzahl"] / 100.0 * (ab.T - zu.T) * anteil_ab * wirksam
            F_FO = ab.x - p["rueckfeuchtzahl"] / 100.0 * (ab.x - zu.x) * anteil_ab * wirksam

        Q_WRG = zu.V / 3600.0 * 1.2 * 1.007 * (T_ZU - zu.T)

        dp_ZU = dp_AB = 0.0
        if p["V_nenn"]:
            offen = (100.0 - byp) / 100.0
            zu_byp = byp / 100.0
            dp_ZU = (zu.V / p["V_nenn"]) ** 2 * (
                p["dp_WRG_nenn"] * offen + p["dp_Bypass_nenn"] * zu_byp
            )
            # Anlage!J43 klammert auf der Abluftseite anders - bewusst uebernommen
            dp_AB = (ab.V / p["V_nenn"]) ** 2 * p["dp_WRG_nenn"] * offen + (
                p["dp_Bypass_nenn"] * zu_byp
            )

        return (
            {
                "zuluft_aus": Luft(V=zu.V, T=T_ZU, x=F_ZU, dp=dp_ZU),
                "abluft_aus": Luft(V=ab.V, T=T_FO, x=F_FO, dp=dp_AB),
                "Q_WRG": Q_WRG,
                "T_ZU": T_ZU, "F_ZU": F_ZU, "T_FO": T_FO, "F_FO": F_FO,
                "dp_ZU": dp_ZU, "dp_AB": dp_AB,
            },
            zustand,
        )

    def bedarf(self, aus_bedarf, p):
        return {
            "zuluft_ein": aus_bedarf.get("zuluft_aus", 0.0),
            "abluft_ein": aus_bedarf.get("abluft_aus", 0.0),
        }
