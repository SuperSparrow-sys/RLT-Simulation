"""Ventilator mit Frequenzumrichter, Drallregler oder ungeregelt.

Formeln aus Anlage!Z121, Z122, Y131 bis Y135. Der Ventilator ist der einzige
Baustein, der den Volumenstrom selbst festlegt; im Rueckwaertslauf ist er daher
der Ausgangspunkt.
"""

from core.bausteine.basis import (
    ABLUFT, AUSGANG, AUSWAHL, EINGANG, LUFT, MESSWERT, PROZENT, SIGNAL,
    STELLGROESSE, STROM, ZAHL, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)


@registriere
class Ventilator(Baustein):
    KENNUNG = "ventilator"
    NAME = "Ventilator"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "ventilator.svg"

    PARAMETER = [
        Param("rolle", "Zuluft/Abluft", "-", "zuluft", auswahl=("zuluft", "abluft"), darstellung=AUSWAHL),
        Param("V_max", "V_max", "m³/h", 8200.0, darstellung=ZAHL, dezimalstellen=0),
        Param("dp_max", "dp_max", "Pa", 1400.0, darstellung=ZAHL, dezimalstellen=0),
        Param("dp_konst", "dp_konst", "Pa", 1400.0, darstellung=ZAHL, dezimalstellen=0),
        Param("PE_max", "PE_max", "kW", 4.9, darstellung=ZAHL, dezimalstellen=1),
        Param("regelart", "FU/DD/-", "-", "F", auswahl=("F", "D", "-"), darstellung=AUSWAHL),
        # Wirkt nur, solange der Anschluss 'stellgroesse' unverbunden ist - das
        # Parameterfenster zeigt das anhand der Verbindungsauskunft aus
        # core.anlagen.als_json() an (siehe dortiges 'ueberschrieben_von').
        Param("stellgroesse", "Stellgröße (fest)", "%", 100.0, darstellung=PROZENT, dezimalstellen=1),
    ]

    PORTS = [
        Port("luft_ein", LUFT, EINGANG, ZULUFT),
        Port("luft_aus", LUFT, AUSGANG, ZULUFT),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
        Port("PE", SIGNAL, AUSGANG, STROM),
    ]

    AUSGABEN = ["T_aus", "F_aus", "PE", "dp", "V"]
    AUSGABE_LABEL = {"T_aus": "Austrittstemperatur"}

    @classmethod
    def ports_fuer(cls, p):
        """Die Luftports tragen je nach Rolle Zuluft oder Abluft."""
        rolle = ABLUFT if p.get("rolle") == "abluft" else ZULUFT
        return [
            Port("luft_ein", LUFT, EINGANG, rolle),
            Port("luft_aus", LUFT, AUSGANG, rolle),
            Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
            Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
            Port("PE", SIGNAL, AUSGANG, STROM),
        ]

    def wirkungsgrad(self, p):
        if not p["PE_max"]:
            return 0.0
        return p["V_max"] * p["dp_max"] / 3600000.0 / p["PE_max"]

    def volumenstrom(self, u, p):
        if str(p["regelart"]) in ("", "-"):
            return p["V_max"]
        return u / 100.0 * p["V_max"]

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        # Ist der Stellgroessen-Port nicht belegt, gilt der eingestellte Wert. In der
        # Excel steht die Stellgroesse des Ventilators ebenfalls als feste Zelle
        # (Anlage!Y16 = 100 %), sie wird dort nicht vom Zeitplan gestellt.
        u = float(ein.get("stellgroesse", p["stellgroesse"]))

        V = self.volumenstrom(u, p)
        dp = 0.0
        if p["V_max"]:
            dp = (p["dp_max"] - p["dp_konst"]) * (u / 100.0) ** 2 + p["dp_konst"]

        eta = self.wirkungsgrad(p)
        eta_teil = eta * (u / 100.0) ** 0.8

        art = str(p["regelart"]).upper()
        PE = 0.0
        if p["V_max"] and u and p["PE_max"] and p["dp_max"] and eta_teil:
            if art == "F":
                PE = u / 100.0 * p["V_max"] / 3600000.0 * dp / eta_teil
            elif art == "D":
                PE = 0.32 * p["PE_max"] + 0.68 * (
                    u / 100.0 * p["V_max"] * dp
                ) / 3600000.0 / eta_teil
            else:
                PE = p["PE_max"]
        elif art not in ("F", "D") and p["V_max"]:
            PE = p["PE_max"]

        T_aus = luft.T
        if V > 0:
            T_aus = luft.T + 3600.0 * PE / (1.2 * 1.007 * V)

        return (
            {
                "luft_aus": Luft(V=V, T=T_aus, x=luft.x, dp=dp),
                "PE": PE, "T_aus": T_aus, "F_aus": luft.x, "dp": dp, "V": V,
            },
            zustand,
        )

    def bedarf(self, aus_bedarf, p):
        return {"luft_ein": p["V_max"]}
