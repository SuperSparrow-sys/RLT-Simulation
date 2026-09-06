"""Luftkuehler mit Taupunktentfeuchtung.

Formeln aus Anlage!AC117, AB131 bis AB135 sowie der Warnung in AA136.
Die Oberflaechentemperatur wird wie in der Excel als Kaltwassertemperatur plus
15 Prozent der Spreizung zur Eintrittsluft angesetzt.
"""

from core.bausteine import stoffdaten as st
from core.bausteine.basis import (
    AUSGANG, EINGANG, KAELTE, LUFT, MESSWERT, SIGNAL, STELLGROESSE, ZAHL, ZULUFT,
    Baustein, Luft, Param, Port, bypassfaktor, druckverlust, registriere,
    strangparameter, strangrolle,
)


def _ports(rolle):
    """Die Anschluesse des Kuehlers. Die Luftrolle haengt am Einbauort -
    siehe core/bausteine/basis.py, strangparameter().
    """
    return [
        Port("luft_ein", LUFT, EINGANG, rolle),
        Port("luft_aus", LUFT, AUSGANG, rolle),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
        Port("QK", SIGNAL, AUSGANG, KAELTE),
    ]


@registriere
class Kuehler(Baustein):
    KENNUNG = "kuehler"
    NAME = "Kühler"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "kuehler.svg"

    PARAMETER = strangparameter() + [
        Param("V_nenn", "Nennvolumenstrom (V_nenn)", "m³/h", 8200.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0),
        Param("dp_nenn", "Druckverlust bei Nennvolumenstrom (dp_nenn)", "Pa", 240.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0),
        Param("QK_nenn", "Nennkälteleistung (QK_nenn)", "kW", 63.0,
              darstellung=ZAHL, dezimalstellen=1, minimum=0.0,
              hinweis="Dient nur als Warngrenze: Braucht der Kühler mehr, meldet die "
                      "Karte „Kühlleistung zu niedrig“. Begrenzt wird die gerechnete "
                      "Leistung dadurch nicht."),
        Param("T_KW_mittel", "Mittlere Kaltwassertemperatur (T_KW_mittel)", "°C", 6.0,
              darstellung=ZAHL, dezimalstellen=1,
              hinweis="Bestimmt, wie kalt die Luft überhaupt werden kann. Die "
                      "Oberfläche des Kühlers liegt zwischen dieser Temperatur und "
                      "der eintretenden Luft (siehe Kontaktfaktor); unter ihrem "
                      "Taupunkt fällt Wasser aus und die Luft wird entfeuchtet."),
        # Bisher stand die 0,15 unbenannt in oberflaechentemperatur(). Sie ist
        # aber keine Naturkonstante, sondern beschreibt, wie gut ein bestimmter
        # Kuehler seine Luft an das Kaltwasser heranfuehrt - genau die Groesse,
        # an der man in einer Uebung dreht. Der Vorgabewert ist der der
        # Excel-Mappe (Anlage!T3), die Rechnung bleibt damit unveraendert.
        Param("kontaktfaktor", "Kontaktfaktor der Kühlfläche", "Anteil 0–1", 0.15,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0, maximum=1.0,
              hinweis="Wie weit die Oberflächentemperatur vom Kaltwasser zur "
                      "eintretenden Luft hin abweicht: 0 hieße, die Oberfläche wäre "
                      "so kalt wie das Wasser, 1 hieße, sie wäre so warm wie die "
                      "Luft und der Kühler wirkungslos. Kleiner heißt tiefere "
                      "Lufttemperatur und mehr Entfeuchtung."),
    ]

    PORTS = _ports(ZULUFT)

    @classmethod
    def ports_fuer(cls, p):
        return _ports(strangrolle(p))

    AUSGABEN = ["T_aus", "F_aus", "QK", "dp", "warnung"]
    AUSGABE_LABEL = {
        "T_aus": "Austrittstemperatur (°C)",
        "F_aus": "Austrittsfeuchte, absolut (g/kg)",
        "QK": "Kälteleistung (kW)",
        "dp": "Druckverlust (Pa)",
        "warnung": "Warnung",
    }

    def oberflaechentemperatur(self, T_ein, p, V=None):
        """Anlage!T3 - die Temperatur, an die der Kuehler die Luft heranfuehrt.

        Sie liegt zwischen Kaltwasser und Eintrittsluft; wo genau, sagt der
        Kontaktfaktor. Ist die Eintrittsluft KAELTER als das Kaltwasser, liegt
        sie darueber - dann waermt der Kuehler, statt zu kuehlen. berechne()
        warnt in diesem Fall (siehe dort).

        Der Kontaktfaktor ist der Bypassfaktor des Registers und keine
        Konstante des Bauteils: Stroemt weniger Luft, bleibt sie laenger an
        der Flaeche und kommt dem Kaltwasser naeher. Wird V uebergeben, gilt
        der eingestellte Wert als AUSLEGUNGSwert bei V_nenn und wird auf die
        aktuelle Luftmenge umgerechnet (basis.bypassfaktor). Ohne V - etwa aus
        einer Auswertung heraus - bleibt es beim eingestellten Wert.
        """
        faktor = p["kontaktfaktor"]
        if V is not None:
            faktor = bypassfaktor(faktor, V, p["V_nenn"])
        return p["T_KW_mittel"] + faktor * (T_ein - p["T_KW_mittel"])

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        u = float(ein.get("stellgroesse", 0.0))

        T_O = self.oberflaechentemperatur(luft.T, p, luft.V)
        x_O = st.x_saett(T_O)

        T_aus = luft.T - u / 100.0 * (luft.T - T_O)
        x_aus = luft.x
        if x_O < luft.x:
            x_aus = luft.x - u / 100.0 * (luft.x - x_O)

        # Hinter einem Kuehlregister kann keine uebersaettigte Luft austreten:
        # Was mehr Wasser traegt, als bei dieser Temperatur in der Luft bleiben
        # kann, schlaegt sich am Register nieder und laeuft in die Wanne.
        #
        # Ohne diese Zeile entstand Uebersaettigung aus zwei harmlosen Anlaessen
        # zugleich. Erstens enthaelt das Testreferenzjahr Nebelstunden, deren
        # Feuchte knapp ueber der Saettigung liegt (13,60 GradC mit 9,900 g/kg
        # bei 9,833 moeglich) - Messwerte bei 100 % relativer Feuchte, kein
        # Fehler. Zweitens ist die Saettigungskurve gekruemmt: Die Formeln oben
        # mischen den Eintrittszustand geradlinig mit dem Zustand an der
        # Registeroberflaeche, und eine Gerade zwischen zwei Punkten auf oder
        # dicht ueber einer nach oben gekruemmten Kurve verlaeuft dazwischen
        # weiter darueber. Aus 0,067 g/kg Ueberschuss am Eintritt wurden so
        # 0,118 g/kg am Austritt - die Anlage machte aus einer Nebelstunde
        # einen physikalisch unmoeglichen Zustand und reichte ihn weiter.
        x_aus = min(x_aus, st.x_saett(T_aus))

        # Erst danach die Leistung: Was hier niederschlaegt, ist Kondensat, und
        # seine Verdampfungswaerme gehoert zur Kuehlleistung. Die Enthalpie
        # rechnet sie ueber x_aus mit.
        QK = 0.0
        if luft.V > 0:
            QK = luft.V / 3600.0 * 1.2 * (
                st.enthalpie(luft.T, luft.x) - st.enthalpie(T_aus, x_aus)
            )

        dp = druckverlust(luft.V, p["V_nenn"], p["dp_nenn"])

        warnung = "Kühlleistung zu niedrig" if QK > p["QK_nenn"] else ""
        # Die Oberflaechentemperatur T_O liegt WAERMER als die Eintrittsluft,
        # wenn diese schon kaelter ist als das Kaltwasser selbst (T_ein <
        # T_KW_mittel) - derselbe Grenzfall wie in der Excel (Anlage!T3),
        # dort ebenfalls ungesichert. Der Kuehler waermt die Luft dann
        # tatsaechlich, statt sie zu kuehlen, sobald er trotzdem angesteuert
        # wird (u > 0): QK wird negativ. Das ist keine neue Bedingung, nur
        # eine zweite Meldung fuer denselben Zustand, den die Formel oben
        # unveraendert durchrechnet - eine Anlage sollte den Kuehler in
        # diesem Betriebszustand gar nicht erst ansteuern.
        if u > 0.0 and luft.T < p["T_KW_mittel"]:
            zusatz = (
                "Kühler außerhalb seines Einsatzbereichs angesteuert: "
                "Eintrittsluft ist kälter als das Kaltwasser – er wärmt "
                "statt zu kühlen"
            )
            warnung = f"{warnung}; {zusatz}" if warnung else zusatz

        aus = Luft(V=luft.V, T=T_aus, x=x_aus, dp=dp)
        return (
            {
                "luft_aus": aus, "QK": QK, "warnung": warnung,
                "T_aus": T_aus, "F_aus": x_aus, "dp": dp,
            },
            zustand,
        )
