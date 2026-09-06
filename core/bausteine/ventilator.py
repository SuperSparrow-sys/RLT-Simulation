"""Ventilator mit Frequenzumrichter, Drallregler oder ungeregelt.

Formeln aus Anlage!Z121, Z122, Y131 bis Y135. Der Ventilator ist der einzige
Baustein, der den Volumenstrom selbst festlegt; im Rueckwaertslauf ist er daher
der Ausgangspunkt.
"""

from core.bausteine.basis import (
    ABLUFT, AUSGANG, AUSWAHL, EINGANG, LUFT, MESSWERT, PROZENT, SIGNAL,
    STELLGROESSE, STROM, ZAHL, ZULUFT,
    Baustein, Luft, Param, Port, registriere, wahl,
    strangparameter, strangrolle,
)


# Untere Drehzahl, bis zu der die Teillastformel des Wirkungsgrads gilt
# (siehe berechne()). Darunter bleibt der Wirkungsgrad auf seinem Wert bei
# dieser Drehzahl stehen.
TEILLAST_MIN = 30.0


def _ports(rolle):
    """Die Anschluesse des Ventilators. Die Luftrolle haengt am Einbauort -
    siehe core/bausteine/basis.py, strangparameter().
    """
    return [
        Port("luft_ein", LUFT, EINGANG, rolle),
        Port("luft_aus", LUFT, AUSGANG, rolle),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
        Port("PE", SIGNAL, AUSGANG, STROM),
    ]


@registriere
class Ventilator(Baustein):
    KENNUNG = "ventilator"
    NAME = "Ventilator"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "ventilator.svg"

    PARAMETER = strangparameter() + [
        Param("V_max", "Volumenstrom bei 100 % (V_max)", "m³/h", 8200.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0,
              hinweis="Der Ventilator bestimmt als einzige Karte die Luftmenge der "
                      "ganzen Anlage. Bei 60 % Stellgröße fördert er 60 % davon."),
        Param("dp_max", "Druckerhöhung bei 100 % (dp_max)", "Pa", 1400.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0),
        Param("dp_konst", "Gleichbleibender Druckanteil (dp_konst)", "Pa", 1400.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0,
              hinweis="Der Teil der Druckerhöhung, der bei jeder Drehzahl anliegt "
                      "(Druckregelung im Kanal). Gleich dp_max heißt: konstanter "
                      "Druck; 0 heißt: der Druck fällt im Quadrat mit der Drehzahl."),
        Param("PE_max", "Elektrische Leistung bei 100 % (PE_max)", "kW", 4.9,
              darstellung=ZAHL, dezimalstellen=1, minimum=0.0,
              hinweis="Aus V_max, dp_max und diesem Wert bildet die Karte den "
                      "Wirkungsgrad des Ventilators."),
        Param(
            "regelart", "Art der Drehzahlregelung", "-", "F",
            auswahl=(
                wahl("F", "Frequenzumrichter (F)"),
                wahl("D", "Drallregler (D)"),
                wahl("-", "ungeregelt (-)"),
            ),
            darstellung=AUSWAHL,
            hinweis="Ungeregelt fördert der Ventilator immer die volle Luftmenge und "
                    "nimmt immer die volle Leistung auf - die Stellgröße wirkt dann "
                    "nicht.",
        ),
        # Wirkt nur, solange der Anschluss 'stellgroesse' unverbunden ist - das
        # Parameterfenster zeigt das anhand der Verbindungsauskunft aus
        # core.anlagen.als_json() an (siehe dortiges 'ueberschrieben_von').
        Param("stellgroesse", "Stellgröße (fest)", "%", 100.0,
              darstellung=PROZENT, dezimalstellen=1, minimum=0.0, maximum=100.0,
              hinweis="Gilt nur, solange am Anschluss „Stellgröße“ kein Pfeil hängt. "
                      "Sobald einer ankommt, zählt dessen Wert."),
    ]

    PORTS = _ports(ZULUFT)

    @classmethod
    def ports_fuer(cls, p):
        return _ports(strangrolle(p))

    AUSGABEN = ["T_aus", "F_aus", "PE", "dp", "V"]
    # Ohne diesen Eintrag heisst der Anschluss wie sein gleichnamiger
    # Parameter ("Stellgröße (fest)") - der Zusatz gilt aber dem Feld im
    # Fenster, nicht dem Anschluss.
    PORT_LABEL = {"stellgroesse": "Stellgröße (0–100 %)"}
    AUSGABE_LABEL = {
        "T_aus": "Austrittstemperatur (°C)",
        "F_aus": "Austrittsfeuchte, absolut (g/kg)",
        "PE": "elektrische Leistung (kW)",
        "dp": "Druckerhöhung (Pa)",
        "V": "geförderter Volumenstrom (m³/h)",
    }

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
        # Teillastwirkungsgrad nach der Excel-Vorlage, aber mit einer unteren
        # Schranke fuer die Drehzahl.
        #
        # Warum die Schranke: Der Druck faellt nur zum Teil mit dem Quadrat der
        # Drehzahl (dp_konst bleibt stehen), waehrend der Wirkungsgrad mit
        # u^0,8 faellt. Zusammengesetzt zieht die Formel PE ~ u^0,2 nach sich -
        # ein Ventilator bei 5 Prozent Drehzahl braeuchte danach noch rund
        # 42 Prozent seiner Nennleistung und heizte die Luft um 11 K auf
        # (nachgemessen in core/vorlagen/testanlage.py). Das ist keine Physik
        # mehr, sondern eine Formel ausserhalb ihres Gueltigkeitsbereichs: Sie
        # beschreibt einen Ventilator im ueblichen Regelbereich, nicht einen
        # im Kriechgang.
        #
        # Unterhalb von TEILLAST_MIN gilt deshalb der Wirkungsgrad, den die
        # Formel dort noch hergibt. Die Leistung faellt dann weiter mit der
        # Drehzahl (linear ueber u/100 * V_max), statt in einen unsinnigen
        # Wirkungsgrad zu laufen. Anlagen, deren Ventilatoren im ueblichen
        # Bereich fahren, sind davon nicht betroffen - in der Excel-Vorlage
        # steht die Stellgroesse fest auf 100 Prozent (Anlage!Y16).
        eta_teil = eta * (max(u, TEILLAST_MIN) / 100.0) ** 0.8

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
        """Nennbedarf fuer alles, was VOR dem Ventilator liegt.

        Die Mappe legt Kuehler, Erhitzer und Luftwaescher auf den Nennstrom aus
        (S13 = S9 = V9 = Y9, AB13 = AB9 = Y9). Dass die Luftmenge am Ventilator
        auf den gestellten Strom springt, ist ihr getreu und bleibt so.
        """
        return {"luft_ein": p["V_max"]}

    #: Der gestellte Bedarf liest genau dies aus den eigenen Ausgaben.
    BEDARF_HAENGT_AN = ("V",)

    def bedarf_gestellt(self, aus_bedarf, p, werte):
        """Gestellter Bedarf - Anlage!Y20, Y42 und M42.

        Y20 = IF(Y12=""; Y9; Y16/100*Y9), also genau das, was volumenstrom()
        rechnet und berechne() als "V" ausgibt. Wer den Ventilator entgegen der
        Luftrichtung abliest - der Raum liest ueber AH33 = M42/2 seine
        Abluftmenge beim Abluftventilator ab -, muss diesen Wert sehen und nicht
        den Nennstrom. Der Solver ruft das im Vorwaertslauf; vor dem ersten
        Durchgang steht noch kein "V" bereit, dann gilt der Nennstrom als
        Startwert der Iteration.
        """
        V = werte.get("V")
        if V is None:
            return {"luft_ein": p["V_max"]}
        return {"luft_ein": float(V)}
