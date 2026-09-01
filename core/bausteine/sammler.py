"""Sammler: mehrere Gaenge auf einen Luftstrang.

Die Mischung folgt derselben Regel wie die Mischkammer (Anlage!M132/M133),
nur ueber beliebig viele Straenge und massenstromgewichtet.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, LUFT, LUFTWEG, Baustein, Luft, Port, registriere,
)


@registriere
class Sammler(Baustein):
    KENNUNG = "sammler"
    NAME = "Sammler"
    GRUPPE = "Verteilung"
    SYMBOL = "sammler.svg"

    PARAMETER = []

    PORTS = [
        Port("luft_ein", LUFT, EINGANG, LUFTWEG, dynamisch=True),
        Port("luft_aus", LUFT, AUSGANG, LUFTWEG),
    ]

    AUSGABEN = ["T_aus", "F_aus", "V"]

    def berechne(self, ein, p, zustand):
        # Nur ueber die eigenen Eingaenge sammeln. Der Solver legt auch die
        # Abnahme des Luftausgangs in 'ein' ab; wuerde die mitgemischt, zaehlte
        # der Sammler seinen eigenen Ausgang als weiteren Strang mit.
        straenge = [
            w for s, w in ein.items()
            if s.startswith("luft_ein") and isinstance(w, Luft)
        ]
        gesamt = sum(s.V for s in straenge)

        if gesamt <= 0:
            leer = Luft()
            return {"luft_aus": leer, "T_aus": 0.0, "F_aus": 0.0, "V": 0.0}, zustand

        T = sum(s.V * s.T for s in straenge) / gesamt
        x = sum(s.V * s.x for s in straenge) / gesamt
        dp = max((s.dp for s in straenge), default=0.0)

        return (
            {"luft_aus": Luft(V=gesamt, T=T, x=x, dp=dp), "T_aus": T, "F_aus": x, "V": gesamt},
            zustand,
        )

    def bedarf(self, aus_bedarf, p):
        """Der geforderte Volumenstrom wird gleichmaessig auf die Straenge verteilt.

        Die tatsaechliche Aufteilung ergibt sich im Vorwaertslauf aus den
        Ventilatoren der einzelnen Straenge; dieser Wert ist nur der Startwert
        der Iteration.
        """
        return {"luft_ein": sum(aus_bedarf.values())}
