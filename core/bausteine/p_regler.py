"""Zweistufiger P-Regler.

Formeln aus Anlage!K51/J57 (schnelle Stufe) und K53/J61 (traege Stufe). Der
Ausgang bezieht sich auf seinen eigenen Vorwert; ueber die Iterationen des
Vorwaertslaufs wirkt der Regler dadurch integrierend. Das ist in der Excel so
gewollt und wird bewusst uebernommen.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, ISTWERT, SIGNAL, SOLLWERT, STELLGROESSE, ZAHL,
    Baustein, Param, Port, registriere,
)


def klemme(wert, unten=0.0, oben=100.0):
    return max(unten, min(oben, wert))


@registriere
class PRegler(Baustein):
    # Der Ausgang bezieht sich auf seinen eigenen Vorwert - er baut sich ueber
    # die Iterationen des Vorwaertslaufs auf, genau wie in der Excel.
    ZUSTAND_UEBER_ITERATION = True

    KENNUNG = "p_regler"
    NAME = "P-Regler"
    GRUPPE = "Regelung"
    SYMBOL = "p_regler.svg"

    PARAMETER = [
        # Anlage!K52 speist Ausgang 1, K54 speist Ausgang 2 - der "schnelle"
        # Regler hat die kleinere Bandbreite, weil die einen kraeftigeren
        # Eingriff je Durchgang bedeutet.
        # Der Regler wird fuer ganz verschiedene Groessen eingesetzt - Temperatur
        # beim Vor-/Nacherhitzer, Feuchte beim Entfeuchtungsregler (siehe
        # core/vorlagen/ax_sim_2_1.py: sollwert_2=9.0 fuer den Entfeuchtungsregler
        # ist ein Feuchtewert, keine Temperatur). Deshalb steht als Einheit
        # durchgehend "Einheit des Istwerts" statt eines nichtssagenden "-";
        # welche Groesse gemeint ist, sagt der Anschluss, der hier haengt.
        #
        # Der Anfang "Xp " der beiden Bandbreiten-Labels ist zugleich die
        # Ueberschrift der Regelkreise im Parameterfenster (static/js/panel.js,
        # ermittleRegelkreise schneidet ihn samt Klammerzusatz ab und zeigt den
        # Rest als "Regler 1 (schnell)").
        Param("xp_1", "Xp (Proportionalbereich) Regler 1 (schnell)",
              "Einheit des Istwerts", 5.0, darstellung=ZAHL, dezimalstellen=1,
              hinweis="Um wie viel der Istwert vom Sollwert abweichen muss, damit der "
                      "Ausgang je Rechendurchgang um volle 100 % nachgeführt wird. "
                      "Kleiner Wert = kräftigere, schnellere Regelung."),
        Param("xp_2", "Xp (Proportionalbereich) Regler 2 (träge)",
              "Einheit des Istwerts", 10.0, darstellung=ZAHL, dezimalstellen=1,
              hinweis="Wie Regler 1, nur mit größerer Bandbreite und damit ruhigerem "
                      "Verhalten."),
        Param("sollwert_1", "Sollwert 1", "Einheit des Istwerts", 0.0,
              darstellung=ZAHL, dezimalstellen=1),
        Param("sollwert_2", "Sollwert 2", "Einheit des Istwerts", 20.0,
              darstellung=ZAHL, dezimalstellen=1),
        # Anlage!S71 usw.: Bei manchen Reglern steht der Istwert als feste Zahl
        # daneben, waehrend der Sollwert von aussen kommt (umgekehrte Zuordnung).
        Param("istwert_1", "Istwert 1 (fest)", "Einheit des Istwerts", 0.0,
              darstellung=ZAHL, dezimalstellen=1),
        Param("istwert_2", "Istwert 2 (fest)", "Einheit des Istwerts", 0.0,
              darstellung=ZAHL, dezimalstellen=1),
    ]

    PORTS = [
        # Stufe 2 steht bewusst zuerst: In der Excel traegt nur der traege Regler
        # einen Sollwert (Anlage!M59), waehrend der schnelle auf '???' steht. Bei
        # gleicher Bewertung entscheidet die Reihenfolge, und ein Pfeil soll die
        # Stufe treffen, die tatsaechlich regelt.
        Port("sollwert_2", SIGNAL, EINGANG, SOLLWERT),
        Port("istwert_2", SIGNAL, EINGANG, ISTWERT),
        Port("ausgang_2", SIGNAL, AUSGANG, STELLGROESSE),
        Port("sollwert_1", SIGNAL, EINGANG, SOLLWERT),
        Port("istwert_1", SIGNAL, EINGANG, ISTWERT),
        Port("ausgang_1", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["ausgang_1", "ausgang_2"]
    AUSGABE_LABEL = {
        "ausgang_1": "Stellgröße Regler 1 (0–100 %)",
        "ausgang_2": "Stellgröße Regler 2 (0–100 %)",
    }

    def _stufe(self, y_alt, sollwert, istwert, xp):
        """Ein Schritt der Stellgroesse, begrenzt auf 0 bis 100 Prozent.

        Der Regler verschiebt seine Stellgroesse je Rechendurchgang um
        Abweichung/Xp und faengt beim Wert des vorigen Durchgangs an. Ueber die
        Durchgaenge einer Stunde laeuft er damit so lange nach, bis die
        Abweichung null ist - er verhaelt sich also integrierend und
        hinterlaesst KEINE bleibende Regelabweichung, anders als ein reiner
        P-Regler im Lehrbuch. Xp bestimmt, wie schnell er ankommt, nicht wie
        weit er daneben liegt. Der Name stammt aus der Excel-Mappe
        (Anlage!S140 und Nachbarn), und mit ihr steht und faellt der Vergleich;
        deshalb bleibt er - die Erklaerung in core/lehrinhalte/ sagt es dazu.
        """
        if not xp:
            return y_alt
        return klemme(y_alt - (istwert - sollwert) / xp)

    def berechne(self, ein, p, zustand):
        # Ist der Sollwert-Port nicht belegt, gilt der eingestellte Parameter -
        # in der Excel steht der Sollwert ebenfalls als feste Zelle (Anlage!M59).
        # p traegt, aus vorgabeparameter() kommend, immer alle deklarierten
        # Parameter; ein fehlender Sollwert soll deshalb laut mit KeyError
        # zuschlagen statt still zu 0 zu werden.
        y1 = self._stufe(
            float(zustand.get("y1", 0.0)),
            float(ein.get("sollwert_1", p["sollwert_1"])),
            float(ein.get("istwert_1", p["istwert_1"])),
            p["xp_1"],
        )
        y2 = self._stufe(
            float(zustand.get("y2", 0.0)),
            float(ein.get("sollwert_2", p["sollwert_2"])),
            float(ein.get("istwert_2", p["istwert_2"])),
            p["xp_2"],
        )
        return {"ausgang_1": y1, "ausgang_2": y2}, {"y1": y1, "y2": y2}

    def anfangszustand(self, p):
        return {"y1": 0.0, "y2": 0.0}
