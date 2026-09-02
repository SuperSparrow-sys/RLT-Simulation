"""Mischkammer aus Aussenluft und Umluft. Formeln aus Anlage!M132 bis M134."""

from core.bausteine.basis import (
    AUSGANG, AUSSENLUFT, EINGANG, LUFT, PROZENT, SIGNAL, STELLGROESSE, UMLUFT,
    ZULUFT, Baustein, Luft, Param, Port, registriere,
)


@registriere
class Mischkammer(Baustein):
    KENNUNG = "mischkammer"
    NAME = "Mischkammer"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "mischkammer.svg"

    PARAMETER = [
        Param("max_umluft", "max. Umluft", "%", 80.0, darstellung=PROZENT, dezimalstellen=1, minimum=0.0, maximum=100.0)
    ]

    PORTS = [
        Port("aussenluft_ein", LUFT, EINGANG, AUSSENLUFT),
        Port("umluft_ein", LUFT, EINGANG, UMLUFT),
        Port("luft_aus", LUFT, AUSGANG, ZULUFT),
        Port("umluftanteil", SIGNAL, EINGANG, STELLGROESSE),
    ]

    AUSGABEN = ["T_MI", "F_MI", "umluftanteil"]

    def berechne(self, ein, p, zustand):
        au = ein.get("aussenluft_ein", Luft())
        um = ein.get("umluft_ein", Luft())
        anteil = min(float(ein.get("umluftanteil", 0.0)), p["max_umluft"])

        T = ((100.0 - anteil) * au.T + anteil * um.T) / 100.0
        x = ((100.0 - anteil) * au.x + anteil * um.x) / 100.0
        V = au.V + um.V

        return (
            {
                "luft_aus": Luft(V=V, T=T, x=x, dp=0.0),
                "T_MI": T, "F_MI": x, "umluftanteil": anteil,
            },
            zustand,
        )

    def bedarf(self, aus_bedarf, p):
        gesamt = sum(aus_bedarf.values())
        return {"aussenluft_ein": gesamt, "umluft_ein": 0.0}
