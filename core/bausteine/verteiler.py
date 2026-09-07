"""Verteiler: ein Luftstrang auf mehrere Gaenge.

In der Excel gibt es diesen Baustein nur als Formel - S9 = V9 reicht den
Volumenstrom weiter, M9 = S9 + S31 summiert zwei Geraete. Hier wird daraus eine
eigene Karte mit dynamischen Ausgaengen.

Der Volumenstrom je Gang ergibt sich aus dem, was stromabwaerts gefordert wird.
Meldet ein Gang keinen Bedarf, greift der Parameter 'anteile'.
"""

from core.bausteine.basis import (
    ANTEILE, AUSGANG, EINGANG, LUFT, LUFTWEG,
    Baustein, Luft, Param, Port, registriere,
)


@registriere
class Verteiler(Baustein):
    KENNUNG = "verteiler"
    NAME = "Verteiler"
    GRUPPE = "Verteilung"
    SYMBOL = "verteiler.svg"

    PARAMETER = [
        Param("anteile", "Anteile je Gang", "%", {}, darstellung=ANTEILE,
              hinweis="Notaufteilung: Sie greift nur, wenn hinter keinem Gang ein "
                      "Ventilator steht, der die Luftmenge selbst bestimmt. "
                      "Normalerweise fordert jeder Gang seinen Bedarf an.")
    ]

    PORTS = [
        Port("luft_ein", LUFT, EINGANG, LUFTWEG),
        Port("luft_aus", LUFT, AUSGANG, LUFTWEG, dynamisch=True),
    ]

    AUSGABEN = ["warnung"]
    AUSGABE_LABEL = {"warnung": "Warnung"}

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

        # None heisst "hinter diesem Gang hat niemand etwas gefordert" - das
        # ist eine Senke wie die Fortluft. Eine ausdrueckliche Null heisst
        # "dieser Gang will nichts", und dann bekommt er auch nichts.
        #
        # Beides an derselben Zahl festzumachen, kostete das Rechenzentrum eine
        # Stunde im Jahr: Seine freie Kuehlung faehrt die Umluftklappe zu, die
        # Forderung der Mischkammer laeuft sauber gegen null - und in dem
        # Durchgang, in dem sie null erreichte, schob der Verteiler ihr nach
        # seinem festen Schluessel 80 Prozent der Abluft zu, 26 400 m3/h in
        # einen Strang, den niemand haben wollte. Im naechsten Durchgang
        # forderte sie wieder null, und das Spiel begann von vorn.
        gemeldet = {a: self.bedarf_je_abgang.get(a) for a in abgaenge}
        gefordert = {a: (0.0 if v is None else v) for a, v in gemeldet.items()}
        summe = sum(gefordert.values())

        warnung = ""
        if summe > luft.V:
            # Mehr gefordert als da ist: alle Gaenge anteilig kuerzen.
            faktor = luft.V / summe   # summe > luft.V >= 0, also nie null
            verteilt = {a: v * faktor for a, v in gefordert.items()}
            warnung = "Volumenstrom reicht nicht für alle Gänge"
        else:
            # Jeder fordernde Gang bekommt seinen Bedarf. Was uebrig bleibt,
            # geht an die Gaenge, die nichts fordern - typisch die Fortluft,
            # die als Senke nie etwas anfordert. Ohne diesen Rest verschwaende
            # ein Verteiler Luft: In core/vorlagen/testanlage.py forderte die
            # Mischkammer 3000 von 5000 m³/h als Umluft an, und die restlichen
            # 2000 loesten sich auf, statt ins Freie zu gehen.
            verteilt = dict(gefordert)
            rest = luft.V - summe
            ohne_bedarf = [a for a in abgaenge if gemeldet.get(a) is None]
            if rest > 0 and ohne_bedarf:
                verteilt.update(self._nach_anteilen(rest, ohne_bedarf, p))
            elif rest > 0 and summe <= 0:
                # Jeder Gang sagt ausdruecklich null, und es ist trotzdem Luft
                # da - sie muss irgendwohin. Nach dem festen Schluessel, wie im
                # ersten Rueckwaertsdurchlauf, in dem noch niemand etwas
                # gefordert hat.
                verteilt = self._nach_anteilen(rest, abgaenge, p)
            elif rest > 0:
                # Alle Gaenge fordern etwas, und es bleibt trotzdem Luft
                # uebrig: Sie anteilig auf die Forderungen aufschlagen, statt
                # sie verschwinden zu lassen.
                verteilt = {a: v + rest * v / summe for a, v in gefordert.items()}

        aus = {
            a: Luft(V=v, T=luft.T, x=luft.x, dp=luft.dp) for a, v in verteilt.items()
        }
        aus["warnung"] = warnung
        return aus, zustand

    def _nach_anteilen(self, menge, abgaenge, p):
        """Verteilt 'menge' auf 'abgaenge' nach dem Parameter 'anteile'.

        Ohne gesetzte Anteile gleichmaessig - das ist die Notaufteilung fuer
        Gaenge, hinter denen kein Ventilator steht, der die Luftmenge selbst
        bestimmt.
        """
        anteile = p.get("anteile") or {}
        gesamt = sum(anteile.get(a, 0.0) for a in abgaenge)
        if gesamt > 0:
            return {a: menge * anteile.get(a, 0.0) / gesamt for a in abgaenge}
        return {a: menge / len(abgaenge) for a in abgaenge}

    def bedarf(self, aus_bedarf, p):
        return {"luft_ein": sum(aus_bedarf.values())}
