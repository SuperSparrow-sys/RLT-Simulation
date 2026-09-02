"""Raum-/Zuluft-Kaskade mit aussentemperaturgefuehrtem Sollwert.

Formeln aus Anlage!P143 (gleitender Raumsollwert), Q140 (Regelabweichung mit
Vorrang der Zuluftbegrenzung) und Q138/P153 bis P157 (Sequenzausgaenge).
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, ISTWERT, MESSWERT, SIGNAL, STELLGROESSE, ZAHL,
    Baustein, Param, Port, registriere,
)
from core.bausteine.sequenzregler import STUFEN


@registriere
class RaumZuluftKaskade(Baustein):
    # Der Ausgang bezieht sich auf seinen eigenen Vorwert - er baut sich ueber
    # die Iterationen des Vorwaertslaufs auf, genau wie in der Excel.
    ZUSTAND_UEBER_ITERATION = True

    KENNUNG = "kaskade"
    NAME = "Raum-/Zuluft-Kaskade"
    GRUPPE = "Regelung"
    SYMBOL = "kaskade.svg"

    PARAMETER = [
        # "bei T_AU" stand zweimal wortgleich an zwei verschiedenen Parametern -
        # im Parameterfenster waren die beiden Zeilen nicht zu unterscheiden.
        Param("T_Raum_min", "Unterer Raumsollwert", "°C", 22.0,
              darstellung=ZAHL, dezimalstellen=1,
              hinweis="Gilt an kalten Tagen. Zwischen den beiden Außentemperaturen "
                      "unten wandert der Raumsollwert geradlinig vom unteren zum "
                      "oberen Wert - im Sommer darf es drinnen wärmer sein."),
        Param("T_AU_min", "Unterer Raumsollwert gilt bis Außentemperatur", "°C", 20.0,
              darstellung=ZAHL, dezimalstellen=1),
        Param("T_Raum_max", "Oberer Raumsollwert", "°C", 28.0,
              darstellung=ZAHL, dezimalstellen=1),
        Param("T_AU_max", "Oberer Raumsollwert gilt ab Außentemperatur", "°C", 32.0,
              darstellung=ZAHL, dezimalstellen=1),
        Param("T_ZU_min", "Tiefste erlaubte Zulufttemperatur", "°C", 16.0,
              darstellung=ZAHL, dezimalstellen=1,
              hinweis="Zuluftbegrenzung mit Vorrang: Verlässt die Zuluft dieses "
                      "Fenster, regelt die Kaskade zuerst sie zurück und lässt den "
                      "Raumsollwert so lange außer Acht - sonst zöge es im Raum."),
        Param("T_ZU_max", "Höchste erlaubte Zulufttemperatur", "°C", 25.0,
              darstellung=ZAHL, dezimalstellen=1),
        # Anlage!Q140 teilt fest durch 3 - wie beim Sequenzregler geht die
        # Xp-Zelle des Blocks in die Formel nicht ein.
        Param("xp", "Proportionalbereich (Xp)", "K", 5.0,
              darstellung=ZAHL, dezimalstellen=1,
              hinweis="Wird nicht gerechnet: Die Karte bildet die Regelabweichung wie "
                      "die Excel-Vorlage mit einem festen Teiler (Abweichung ÷ 3 K je "
                      "Durchgang). Ein anderer Wert ändert das Ergebnis nicht.", ohne_wirkung=True),
    ]

    PORTS = [
        Port("T_AU", SIGNAL, EINGANG, MESSWERT),
        Port("T_Raum", SIGNAL, EINGANG, ISTWERT),
        Port("T_ZU", SIGNAL, EINGANG, ISTWERT),
        Port("sollwert", SIGNAL, AUSGANG, MESSWERT),
        Port("waermer_3", SIGNAL, AUSGANG, STELLGROESSE),
        Port("waermer_2", SIGNAL, AUSGANG, STELLGROESSE),
        Port("waermer_1", SIGNAL, AUSGANG, STELLGROESSE),
        Port("kaelter_1", SIGNAL, AUSGANG, STELLGROESSE),
        Port("kaelter_2", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = [
        "sollwert", "waermer_3", "waermer_2", "waermer_1",
        "kaelter_1", "kaelter_2", "e",
    ]
    AUSGABE_LABEL = {
        "sollwert": "gleitender Raumsollwert (°C)",
        "waermer_1": "Heizen Stufe 1 - öffnet zuerst (0–100 %)",
        "waermer_2": "Heizen Stufe 2 (0–100 %)",
        "waermer_3": "Heizen Stufe 3 - öffnet zuletzt (0–100 %)",
        "kaelter_1": "Kühlen Stufe 1 - öffnet zuerst (0–100 %)",
        "kaelter_2": "Kühlen Stufe 2 - öffnet zuletzt (0–100 %)",
        "e": "Regelabweichung (−300 bis +200)",
    }
    PORT_LABEL = {
        "T_AU": "Außentemperatur (°C)",
        "T_Raum": "Raumtemperatur (°C)",
        "T_ZU": "Zulufttemperatur (°C)",
    }

    def gleitender_sollwert(self, T_AU, p):
        if T_AU < p["T_AU_min"]:
            return p["T_Raum_min"]
        spanne = p["T_AU_max"] - p["T_AU_min"]
        if spanne == 0:
            return p["T_Raum_max"]
        gleitend = p["T_Raum_min"] + (T_AU - p["T_AU_min"]) * (
            p["T_Raum_max"] - p["T_Raum_min"]
        ) / spanne
        return min(gleitend, p["T_Raum_max"])

    def berechne(self, ein, p, zustand):
        T_AU = float(ein.get("T_AU", 0.0))
        T_Raum = float(ein.get("T_Raum", 0.0))
        T_ZU = float(ein.get("T_ZU", 0.0))
        e_alt = float(zustand.get("e", 0.0))

        soll = self.gleitender_sollwert(T_AU, p)

        if T_ZU > p["T_ZU_max"]:
            delta = (T_ZU - p["T_ZU_max"]) / 3.0
        elif T_ZU < p["T_ZU_min"]:
            delta = (T_ZU - p["T_ZU_min"]) / 3.0
        else:
            delta = (T_Raum - soll) / 3.0

        e = max(-300.0, min(200.0, e_alt + delta))

        aus = {"sollwert": soll, "e": e}
        for name, versatz, vorzeichen in STUFEN:
            aus[name] = max(0.0, min(vorzeichen * (e + versatz), 100.0))
        return aus, {"e": e}

    def anfangszustand(self, p):
        return {"e": 0.0}
