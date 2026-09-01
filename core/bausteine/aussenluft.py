"""Anschlusspunkt Aussenluft. Wandelt die Wettersignale in einen Luftzustand."""

from core.bausteine.basis import (
    AUSGANG, AUSSENLUFT, EINGANG, LUFT, MESSWERT, SIGNAL,
    Baustein, Luft, Port, registriere,
)


@registriere
class Aussenluft(Baustein):
    KENNUNG = "aussenluft"
    NAME = "Außenluft"
    GRUPPE = "Quellen und Senken"
    SYMBOL = "aussenluft.svg"

    PARAMETER = []

    PORTS = [
        Port("T_AU", SIGNAL, EINGANG, MESSWERT),
        Port("F_AU", SIGNAL, EINGANG, MESSWERT),
        Port("luft_aus", LUFT, AUSGANG, AUSSENLUFT),
    ]

    AUSGABEN = ["T_AU", "F_AU", "V"]

    def berechne(self, ein, p, zustand):
        T = float(ein.get("T_AU", 0.0))
        x = float(ein.get("F_AU", 0.0))
        V = float(zustand.get("bedarf", 0.0))
        return (
            {"luft_aus": Luft(V=V, T=T, x=x, dp=0.0), "T_AU": T, "F_AU": x, "V": V},
            zustand,
        )

    def bedarf(self, aus_bedarf, p):
        return {}
