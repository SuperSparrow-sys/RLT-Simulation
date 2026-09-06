"""Waermerueckgewinnung mit Bypass.

Formeln aus Anlage!J152 bis J157 (Zuluft, Fortluft, Q_WRG, Druckverluste).
Der Wirkungsgrad wird mit dem Verhaeltnis des kleineren zum jeweiligen
Volumenstrom gewichtet, genau wie in der Excel.
"""

from core.bausteine import stoffdaten as st
from core.bausteine.basis import (
    ABLUFT, AUSGANG, EINGANG, LUFT, MESSWERT, PROZENT, SIGNAL, STELLGROESSE,
    ZAHL, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)


@registriere
class Waermerueckgewinnung(Baustein):
    KENNUNG = "wrg"
    NAME = "Wärmerückgewinnung"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "wrg.svg"

    PARAMETER = [
        Param("V_nenn", "Nennvolumenstrom (V_nenn)", "m³/h", 12200.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0),
        Param("dp_WRG_nenn", "Nenndruckverlust Wärmetauscher (dp_WRG_nenn)", "Pa", 170.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0),
        Param("dp_Bypass_nenn", "Nenndruckverlust Bypass (dp_Byp_nenn)", "Pa", 50.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0,
              hinweis="Gilt für den Weg an der Wärmerückgewinnung vorbei; er ist "
                      "meist deutlich kleiner als der durch den Tauscher."),
        Param("rueckwaermzahl", "Rückwärmzahl (Temperatur-Wirkungsgrad)", "%", 81.0,
              darstellung=PROZENT, dezimalstellen=1, minimum=0.0, maximum=100.0,
              hinweis="Wie viel des Temperaturunterschieds zwischen Abluft und "
                      "Außenluft auf die Zuluft übergeht. Beispiel: bei 80 %, 22 °C "
                      "Abluft und 0 °C Außenluft kommt die Zuluft mit rund 18 °C an."),
        Param("rueckfeuchtzahl", "Rückfeuchtzahl (Feuchte-Wirkungsgrad)", "%", 0.0,
              darstellung=PROZENT, dezimalstellen=1, minimum=0.0, maximum=100.0,
              hinweis="Nur Bauarten mit Feuchteübertragung (z. B. Rotationstauscher) "
                      "haben hier einen Wert; Plattentauscher und Kreislaufverbund "
                      "bleiben bei 0."),
    ]

    PORTS = [
        Port("zuluft_ein", LUFT, EINGANG, ZULUFT),
        Port("zuluft_aus", LUFT, AUSGANG, ZULUFT),
        Port("abluft_ein", LUFT, EINGANG, ABLUFT),
        Port("abluft_aus", LUFT, AUSGANG, ABLUFT),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("stellgroesse_bypass", SIGNAL, EINGANG, STELLGROESSE),
        Port("Q_WRG", SIGNAL, AUSGANG, MESSWERT),
        # Anlage!J38 = T_ZU. Der Wert wird ohnehin gerechnet; er braucht einen
        # Anschluss, weil die Mappe genau daran regelt: J60 = J38 ist der Istwert
        # des WRG-Reglers, dessen Ausgang J61 wiederum die Stellgroesse J20
        # setzt. Steht bewusst NACH Q_WRG - bei gleicher Bewertung entscheidet
        # die Reihenfolge der Ports, und die vorhandene Verdrahtung soll
        # unveraendert bleiben (Q_WRG behaelt die erste Protokollspalte).
        Port("T_ZU", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["T_ZU", "F_ZU", "T_FO", "F_FO", "Q_WRG", "kondensat",
                "dp_ZU", "dp_AB"]
    AUSGABE_LABEL = {
        "Q_WRG": "rückgewonnene Wärmeleistung, sensibel (kW)",
        "kondensat": "Kondensat auf der Abluftseite (kg/h)",
        "T_ZU": "Zulufttemperatur nach WRG (°C)",
        "F_ZU": "Zuluftfeuchte, absolut (g/kg)",
        "T_FO": "Fortlufttemperatur (°C)",
        "F_FO": "Fortluftfeuchte, absolut (g/kg)",
        "dp_ZU": "Druckverlust Zuluftseite (Pa)",
        "dp_AB": "Druckverlust Abluftseite (Pa)",
    }
    # Zwei Stellgroessen an einer Karte: ohne eigene Beschriftung stuende im
    # Parameterfenster zweimal "Stellgröße", auseinandergehalten nur durch eine
    # laufende Nummer.
    PORT_LABEL = {
        "stellgroesse": "Stellgröße Wärmerückgewinnung (0–100 %)",
        "stellgroesse_bypass": "Stellgröße Bypass (0–100 %)",
    }

    def berechne(self, ein, p, zustand):
        zu = ein.get("zuluft_ein", Luft())
        ab = ein.get("abluft_ein", Luft())
        u = float(ein.get("stellgroesse", 0.0))
        byp = float(ein.get("stellgroesse_bypass", 0.0))

        wirksam = 0.0
        if zu.V > 0 and ab.V > 0:
            wirksam = u / 100.0 * (100.0 - byp) / 100.0

        kleiner = min(zu.V, ab.V) if (zu.V > 0 and ab.V > 0) else 0.0

        T_ZU, F_ZU, T_FO, F_FO = zu.T, zu.x, ab.T, ab.x
        if wirksam > 0:
            anteil_zu = kleiner / zu.V
            anteil_ab = kleiner / ab.V
            T_ZU = zu.T + p["rueckwaermzahl"] / 100.0 * (ab.T - zu.T) * anteil_zu * wirksam
            F_ZU = zu.x + p["rueckfeuchtzahl"] / 100.0 * (ab.x - zu.x) * anteil_zu * wirksam
            T_FO = ab.T - p["rueckwaermzahl"] / 100.0 * (ab.T - zu.T) * anteil_ab * wirksam
            F_FO = ab.x - p["rueckfeuchtzahl"] / 100.0 * (ab.x - zu.x) * anteil_ab * wirksam

            # Die Zuluft kann nicht mehr Wasser aufnehmen, als sie bei ihrer
            # Temperatur traegt. Ein Rotationstauscher, der im Winter feuchte
            # Abluft an sehr kalte Aussenluft gibt, laeuft genau in diese
            # Grenze - ungebremst verliess die Zuluft ihn mit 12,0 g/kg bei
            # 15,5 GradC, moeglich sind dort 11,0. Was nicht uebergehen kann,
            # bleibt in der Abluft; die Mengenbilanz muss aufgehen.
            grenze_zu = st.x_saett(T_ZU)
            if F_ZU > grenze_zu:
                nicht_uebergegangen = F_ZU - grenze_zu
                F_ZU = grenze_zu
                if ab.V > 0:
                    F_FO += nicht_uebergegangen * zu.V / ab.V

        # Nur der SENSIBLE Anteil: die Temperaturerhoehung der Zuluft. Wird
        # ueber die Rueckfeuchtzahl auch Feuchte uebertragen, steckt darin
        # zusaetzlich latente Waerme, die diese Zahl nicht enthaelt - die Excel
        # rechnet sie an dieser Stelle ebenfalls nicht mit (Anlage!J38).
        # Deshalb heisst die Ausgabe "sensibel"; wer die gesamte
        # zurueckgewonnene Enthalpie will, bildet sie aus T_ZU und F_ZU.
        Q_WRG = zu.V / 3600.0 * 1.2 * 1.007 * (T_ZU - zu.T)

        # Kondensation auf der Abluftseite. Kuehlt der Tauscher die Abluft
        # unter ihren Taupunkt, faellt Wasser aus - jeder Plattentauscher hat
        # dafuer einen Kondensatablauf. Ohne diese Rechnung verliess die
        # Fortluft den Tauscher uebersaettigt (gemessen an der Vorlage
        # "Schwimmhalle": 14,3 g/kg bei 10,8 GradC, moeglich sind 8,1 - in 274
        # von 504 Stunden).
        T_FO, F_FO, kondensat = self._kondensation(T_FO, F_FO, ab.V)

        dp_ZU = dp_AB = 0.0
        if p["V_nenn"]:
            offen = (100.0 - byp) / 100.0
            zu_byp = byp / 100.0
            dp_ZU = (zu.V / p["V_nenn"]) ** 2 * (
                p["dp_WRG_nenn"] * offen + p["dp_Bypass_nenn"] * zu_byp
            )
            # Anlage!J43 klammert auf der Abluftseite anders - bewusst uebernommen
            dp_AB = (ab.V / p["V_nenn"]) ** 2 * p["dp_WRG_nenn"] * offen + (
                p["dp_Bypass_nenn"] * zu_byp
            )

        return (
            {
                "zuluft_aus": Luft(V=zu.V, T=T_ZU, x=F_ZU, dp=dp_ZU),
                "abluft_aus": Luft(V=ab.V, T=T_FO, x=F_FO, dp=dp_AB),
                "Q_WRG": Q_WRG,
                "kondensat": kondensat,
                "T_ZU": T_ZU, "F_ZU": F_ZU, "T_FO": T_FO, "F_FO": F_FO,
                "dp_ZU": dp_ZU, "dp_AB": dp_AB,
            },
            zustand,
        )

    #: Verdampfungswaerme von Wasser bei Umgebungsbedingungen, kJ/kg.
    VERDAMPFUNGSWAERME = 2500.0
    #: Spezifische Waermekapazitaet der feuchten Luft, kJ/(kg*K).
    WAERMEKAPAZITAET = 1.007

    def _kondensation(self, T_FO, F_FO, V_ab):
        """Faellt Wasser aus der abgekuehlten Fortluft aus?

        Liegt der Wassergehalt ueber der Saettigung bei der erreichten
        Temperatur, kondensiert die Differenz. Die dabei frei werdende Waerme
        erwaermt die Fortluft wieder - rund 2,5 K je Gramm je Kilogramm -,
        wodurch sie mehr Wasser tragen kann; der Zustand stellt sich in
        wenigen Schritten ein.

        Die Kondensationswaerme wird der ZULUFT bewusst NICHT gutgeschrieben.
        Die Rueckwaermzahl ist ein eingestellter Auslegungswert, der den
        ueblichen Betrieb bereits abbildet; sie zusaetzlich zu erhoehen hiesse,
        dieselbe Waerme zweimal zu zaehlen. Die Rechnung bleibt damit auf der
        sicheren Seite - sie gewinnt eher zu wenig zurueck als zu viel.

        Rueckgabe: (Temperatur, Wassergehalt, Kondensat in kg/h).
        """
        grenze = st.x_saett(T_FO)
        if F_FO <= grenze or V_ab <= 0:
            return T_FO, F_FO, 0.0

        T_trocken = T_FO
        for _ in range(8):
            grenze = st.x_saett(T_FO)
            if F_FO <= grenze:
                break
            ausgefallen = F_FO - grenze
            T_neu = T_trocken + ausgefallen / 1000.0 * (
                self.VERDAMPFUNGSWAERME / self.WAERMEKAPAZITAET
            )
            if abs(T_neu - T_FO) < 1e-4:
                T_FO = T_neu
                break
            T_FO = T_neu

        grenze = st.x_saett(T_FO)
        kondensat_je_kg = max(0.0, F_FO - grenze)
        # g/kg auf kg/h: Volumenstrom mal Dichte mal Gehalt
        kondensat = V_ab * 1.2 * kondensat_je_kg / 1000.0
        return T_FO, min(F_FO, grenze), kondensat

    def bedarf(self, aus_bedarf, p):
        return {
            "zuluft_ein": aus_bedarf.get("zuluft_aus", 0.0),
            "abluft_ein": aus_bedarf.get("abluft_aus", 0.0),
        }
