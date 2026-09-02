"""Anschlusspunkt Fortluft. Endpunkt eines Abluftwegs."""

from core.bausteine.basis import (
    EINGANG, FORTLUFT, LUFT, Baustein, Luft, Port, registriere,
)


@registriere
class Fortluft(Baustein):
    KENNUNG = "fortluft"
    NAME = "Fortluft"
    GRUPPE = "Quellen und Senken"
    SYMBOL = "fortluft.svg"

    PARAMETER = []

    PORTS = [Port("luft_ein", LUFT, EINGANG, FORTLUFT)]

    AUSGABEN = ["T_FO", "F_FO", "V"]
    AUSGABE_LABEL = {
        "T_FO": "Fortlufttemperatur (°C)",
        "F_FO": "Fortluftfeuchte, absolut (g/kg)",
        "V": "ausgeblasener Volumenstrom (m³/h)",
    }

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        return {"T_FO": luft.T, "F_FO": luft.x, "V": luft.V}, zustand

    def bedarf(self, aus_bedarf, p):
        return {}
