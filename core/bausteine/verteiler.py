"""Verteiler: ein Luftstrang auf mehrere Gaenge.

In der Excel gibt es diesen Baustein nur als Formel - S9 = V9 reicht den
Volumenstrom weiter, M9 = S9 + S31 summiert zwei Geraete. Hier wird daraus eine
eigene Karte mit dynamischen Ausgaengen.

Der Volumenstrom je Gang ergibt sich aus dem, was stromabwaerts gefordert wird.
Meldet ein Gang keinen Bedarf, greift der Parameter 'anteile'.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, LUFT, LUFTWEG, Baustein, Luft, Param, Port, registriere,
)


@registriere
class Verteiler(Baustein):
    KENNUNG = "verteiler"
    NAME = "Verteiler"
    GRUPPE = "Verteilung"
    SYMBOL = "verteiler.svg"

    PARAMETER = [Param("anteile", "Anteile je Gang", "%", {})]

    PORTS = [
        Port("luft_ein", LUFT, EINGANG, LUFTWEG),
        Port("luft_aus", LUFT, AUSGANG, LUFTWEG, dynamisch=True),
    ]

    AUSGABEN = ["warnung"]

    def __init__(self):
        # Vertrag mit dem Solver: Diese beiden Felder gehoeren NICHT zum
        # Stundenzustand, sondern zur Topologie. Der Solver fuellt sie einmal je
        # Lauf im Rueckwaertslauf (core/solver.py, _volumenstroeme) und laesst sie
        # danach unveraendert - 'abgaenge' sind die Schluessel der angelegten
        # Luftausgaenge, 'bedarf_je_abgang' der Volumenstrom, den jeder Gang
        # stromabwaerts anfordert. Deshalb stehen sie hier und nicht im
        # 'zustand'-Woerterbuch, das je Stunde neu gesetzt und fortgeschrieben
        # wird. Ohne Solver - etwa im Test - sind beide von Hand zu setzen.
        self.abgaenge = []
        self.bedarf_je_abgang = {}

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        abgaenge = self.abgaenge or ["luft_aus"]

        gefordert = {a: self.bedarf_je_abgang.get(a, 0.0) for a in abgaenge}
        summe = sum(gefordert.values())

        warnung = ""
        if summe <= 0:
            anteile = p.get("anteile") or {}
            rest = [a for a in abgaenge]
            gesamt_anteil = sum(anteile.get(a, 0.0) for a in rest)
            if gesamt_anteil > 0:
                verteilt = {
                    a: luft.V * anteile.get(a, 0.0) / gesamt_anteil for a in rest
                }
            else:
                verteilt = {a: luft.V / len(rest) for a in rest}
        elif summe > luft.V:
            faktor = luft.V / summe   # summe > luft.V >= 0, also nie null
            verteilt = {a: v * faktor for a, v in gefordert.items()}
            warnung = "Volumenstrom reicht nicht fuer alle Gaenge"
        else:
            verteilt = gefordert

        aus = {
            a: Luft(V=v, T=luft.T, x=luft.x, dp=luft.dp) for a, v in verteilt.items()
        }
        aus["warnung"] = warnung
        return aus, zustand

    def bedarf(self, aus_bedarf, p):
        return {"luft_ein": sum(aus_bedarf.values())}
