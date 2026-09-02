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
        Param("max_umluft", "Höchster Umluftanteil", "%", 80.0,
              darstellung=PROZENT, dezimalstellen=1, minimum=0.0, maximum=100.0,
              hinweis="Obergrenze für die Stellgröße: Auch wenn der Regler mehr "
                      "fordert, wird nie mehr Umluft beigemischt. Der Rest bleibt "
                      "Außenluft - das sichert die Frischluftmenge im Raum.")
    ]

    PORTS = [
        Port("aussenluft_ein", LUFT, EINGANG, AUSSENLUFT),
        Port("umluft_ein", LUFT, EINGANG, UMLUFT),
        Port("luft_aus", LUFT, AUSGANG, ZULUFT),
        Port("umluftanteil", SIGNAL, EINGANG, STELLGROESSE),
    ]

    AUSGABEN = ["T_MI", "F_MI", "umluftanteil"]
    AUSGABE_LABEL = {
        "T_MI": "Mischtemperatur (°C)",
        "F_MI": "Mischfeuchte, absolut (g/kg)",
        "umluftanteil": "wirksamer Umluftanteil (%)",
    }
    # Der gleichnamige Eingang traegt den GEFORDERTEN Anteil; wirksam wird er
    # erst nach der Begrenzung auf max_umluft - deshalb hier ein eigener Name
    # statt der Beschriftung des Ausgabewerts.
    PORT_LABEL = {"umluftanteil": "geforderter Umluftanteil (0–100 %)"}

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
