"""Sequenzregler: eine Regelabweichung auf fuenf Stufen.

Formeln aus Anlage!T138 bis S148. Die Regelabweichung laeuft zwischen -300 und
+200; daraus werden drei Waerme- und zwei Kaeltestufen abgeleitet.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, ISTWERT, SIGNAL, STELLGROESSE, ZAHL,
    Baustein, Param, Port, registriere,
)

# Ausgang = klemme(vorzeichen * (e + versatz), 0, 100). Die Versaetze stehen so,
# dass jede Zeile ihre Excel-Formel wiedergibt:
#   waermer_3  Anlage!S144 = MAX(0;MIN(-(e+200);100))
#   waermer_2  Anlage!S145 = MAX(0;MIN(-(e+100);100))
#   waermer_1  Anlage!S146 = MAX(0;MIN(-e;100))
#   kaelter_1  Anlage!S147 = MAX(0;MIN(e;100))
#   kaelter_2  Anlage!S148 = MAX(0;MIN(e-100;100))
STUFEN = (
    ("waermer_3", 200.0, -1.0),
    ("waermer_2", 100.0, -1.0),
    ("waermer_1", 0.0, -1.0),
    ("kaelter_1", 0.0, 1.0),
    ("kaelter_2", -100.0, 1.0),
)

#: Wieviel Regelabweichung eine Stufe abdeckt.
STUFENBREITE = 100.0

#: Vorgabe: alle Stufen stehen zur Verfuegung - so rechnete es bisher.
WAERMESTUFEN_VORGABE = 3
KAELTESTUFEN_VORGABE = 2


def stufenparameter():
    """Die beiden Parameter, mit denen eine Anlage ihre Stufenzahl angibt.

    Kaskade und Sequenzregler teilen sie sich; die Regel gehoert an eine
    Stelle, nicht an zwei.
    """
    return [
        Param("waermestufen", "Genutzte Wärmestufen", "Anzahl",
              float(WAERMESTUFEN_VORGABE), darstellung=ZAHL, dezimalstellen=0,
              minimum=1.0, maximum=3.0,
              hinweis="Wie viele der Ausgänge wärmer_1 bis wärmer_3 die Anlage "
                      "wirklich verdrahtet. Die Regelabweichung läuft nur so "
                      "weit, wie diese Stufen reichen - sonst lädt sie sich in "
                      "einen Bereich auf, den niemand hört, und muss ihn "
                      "später zurückwandern."),
        Param("kaeltestufen", "Genutzte Kältestufen", "Anzahl",
              float(KAELTESTUFEN_VORGABE), darstellung=ZAHL, dezimalstellen=0,
              minimum=1.0, maximum=2.0,
              hinweis="Wie viele der Ausgänge kälter_1 und kälter_2 die Anlage "
                      "wirklich verdrahtet - siehe Wärmestufen."),
    ]


def stufengrenzen(p):
    """Der Bereich, in dem die Regelabweichung noch etwas bewirkt."""
    waerme = int(p.get("waermestufen", WAERMESTUFEN_VORGABE) or WAERMESTUFEN_VORGABE)
    kaelte = int(p.get("kaeltestufen", KAELTESTUFEN_VORGABE) or KAELTESTUFEN_VORGABE)
    waerme = max(1, min(waerme, WAERMESTUFEN_VORGABE))
    kaelte = max(1, min(kaelte, KAELTESTUFEN_VORGABE))
    return -waerme * STUFENBREITE, kaelte * STUFENBREITE


def stufenausgaenge(e, p):
    """Die fuenf Stufenausgaenge - nicht gefahrene bleiben auf null.

    Stuende an einer nicht verdrahteten Stufe eine Anforderung, zeigte die
    Karte Leistung an, die die Anlage gar nicht abrufen kann.
    """
    waerme = int(p.get("waermestufen", WAERMESTUFEN_VORGABE) or WAERMESTUFEN_VORGABE)
    kaelte = int(p.get("kaeltestufen", KAELTESTUFEN_VORGABE) or KAELTESTUFEN_VORGABE)
    genutzt = set()
    for nummer in range(1, min(waerme, WAERMESTUFEN_VORGABE) + 1):
        genutzt.add(f"waermer_{nummer}")
    for nummer in range(1, min(kaelte, KAELTESTUFEN_VORGABE) + 1):
        genutzt.add(f"kaelter_{nummer}")

    aus = {}
    for name, versatz, vorzeichen in STUFEN:
        if name not in genutzt:
            aus[name] = 0.0
            continue
        aus[name] = max(0.0, min(vorzeichen * (e + versatz), 100.0))
    return aus


@registriere
class Sequenzregler(Baustein):
    # Der Ausgang bezieht sich auf seinen eigenen Vorwert - er baut sich ueber
    # die Iterationen des Vorwaertslaufs auf, genau wie in der Excel.
    ZUSTAND_UEBER_ITERATION = True

    KENNUNG = "sequenzregler"
    NAME = "Sequenzregler"
    GRUPPE = "Regelung"
    SYMBOL = "sequenzregler.svg"

    PARAMETER = stufenparameter() + [
        Param("oberer_sw", "Oberer Sollwert - darüber wird gekühlt", "°C", 24.0,
              darstellung=ZAHL, dezimalstellen=1),
        Param("unterer_sw", "Unterer Sollwert - darunter wird geheizt", "°C", 20.0,
              darstellung=ZAHL, dezimalstellen=1,
              hinweis="Zwischen unterem und oberem Sollwert liegt die Totzone: Dort "
                      "bleibt die Regelabweichung 0 und alle fünf Stufen sind zu."),
        # Anlage!T140 teilt fest durch 10 - die Xp-Zelle des Blocks geht in die
        # Formel gar nicht ein. Der Wert bleibt als Parameter stehen (er steht so
        # in der Mappe und in gespeicherten Anlagen), aber die Beschriftung muss
        # sagen, dass an ihm zu drehen nichts bewirkt.
        Param("xp", "Proportionalbereich (Xp)", "K", 5.0,
              darstellung=ZAHL, dezimalstellen=1,
              hinweis="Wird nicht gerechnet: Die Karte bildet die Regelabweichung wie "
                      "die Excel-Vorlage mit einem festen Teiler (Abweichung ÷ 10 K "
                      "je Durchgang). Ein anderer Wert ändert das Ergebnis nicht.", ohne_wirkung=True),
    ]

    PORTS = [
        Port("istwert", SIGNAL, EINGANG, ISTWERT),
        Port("waermer_3", SIGNAL, AUSGANG, STELLGROESSE),
        Port("waermer_2", SIGNAL, AUSGANG, STELLGROESSE),
        Port("waermer_1", SIGNAL, AUSGANG, STELLGROESSE),
        Port("kaelter_1", SIGNAL, AUSGANG, STELLGROESSE),
        Port("kaelter_2", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["waermer_3", "waermer_2", "waermer_1", "kaelter_1", "kaelter_2", "e"]
    # Die Nummern sind die Reihenfolge des Aufziehens, nicht die Groesse der
    # Stufe: waermer_1 oeffnet als erstes (e < 0), waermer_3 erst ganz zuletzt
    # (e < -200). Ohne diese Beschriftung stuenden im Parameterfenster fuenf
    # Zeilen "Stellgröße", nur durch eine laufende Nummer unterschieden.
    AUSGABE_LABEL = {
        "waermer_1": "Heizen Stufe 1 - öffnet zuerst (0–100 %)",
        "waermer_2": "Heizen Stufe 2 (0–100 %)",
        "waermer_3": "Heizen Stufe 3 - öffnet zuletzt (0–100 %)",
        "kaelter_1": "Kühlen Stufe 1 - öffnet zuerst (0–100 %)",
        "kaelter_2": "Kühlen Stufe 2 - öffnet zuletzt (0–100 %)",
        "e": "Regelabweichung (−300 bis +200)",
    }

    def berechne(self, ein, p, zustand):
        istwert = float(ein.get("istwert", 0.0))
        e_alt = float(zustand.get("e", 0.0))

        if p["unterer_sw"] < istwert < p["oberer_sw"]:
            e = 0.0
        else:
            if istwert < p["unterer_sw"]:
                delta = (istwert - p["unterer_sw"]) / 10.0
            else:
                delta = (istwert - p["oberer_sw"]) / 10.0
            unten, oben = stufengrenzen(p)
            e = max(unten, min(oben, e_alt + delta))

        aus = stufenausgaenge(e, p)
        aus["e"] = e
        return aus, {"e": e}

    def anfangszustand(self, p):
        return {"e": 0.0}
