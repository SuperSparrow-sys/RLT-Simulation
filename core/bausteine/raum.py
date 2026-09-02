"""Raum mit Bauphysik, Solargewinnen und Wandspeicher.

Formeln aus Anlage!AG70:AL134. Kern ist die exponentielle Loesung der
Waermebilanz ueber eine Stunde (Anlage!AJ89):

    T_neu = (T_alt + B/A) * exp(A/C) - B/A

A ist die Summe aller Waermeabfluesse je Kelvin, B die Summe aller Zufluesse,
C die Waermekapazitaet der Raumluft. Die Wandtemperatur wird ueber die
Speicherfaehigkeit der Innenwaende fortgeschrieben (Anlage!AK127/AK128).
"""

import math

from core.bausteine.basis import (
    ABLUFT, AUSGANG, EINGANG, LUFT, MESSWERT, SIGNAL, ZAHL, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)

LUFT_C = 1.005 * 1000.0 / 3600.0 * 1.2  # W/(K) je m³/h, wie in Anlage!AJ85
ERDREICH = 10.0  # °C hinter der Bodenplatte, Anlage!AH125


@registriere
class Raum(Baustein):
    KENNUNG = "raum"
    NAME = "Raum"
    GRUPPE = "Räume"
    SYMBOL = "raum.svg"

    PARAMETER = [
        # Die vier Seiten a bis d bilden den Grundriss (im Uhrzeigersinn); ihre
        # Himmelsrichtung ergibt sich aus 'ausrichtung' weiter unten.
        Param("laenge_a", "Länge Seite a", "m", 22.0, darstellung=ZAHL, dezimalstellen=1, minimum=0.0,
              hinweis="Die vier Seiten a bis d bilden den Grundriss; die Grundfläche "
                      "wird aus den Mittelwerten (a+c)/2 mal (b+d)/2 gebildet."),
        Param("laenge_b", "Länge Seite b", "m", 33.0, darstellung=ZAHL, dezimalstellen=1, minimum=0.0),
        Param("laenge_c", "Länge Seite c", "m", 22.0, darstellung=ZAHL, dezimalstellen=1, minimum=0.0),
        Param("laenge_d", "Länge Seite d", "m", 33.0, darstellung=ZAHL, dezimalstellen=1, minimum=0.0),
        # laenge_e geht nur in den Umfang ein (dort zweifach) und damit in die
        # Innenwandflaeche - Transmission und Fenster kennen keine Seite e.
        Param("laenge_e", "Länge zusätzlicher Innenwände (Seite e)", "m", 0.0,
              darstellung=ZAHL, dezimalstellen=1, minimum=0.0,
              hinweis="Zählt nur bei der speicherwirksamen Innenwandfläche mit, und "
                      "zwar doppelt (beide Seiten). Sie hat keinen U-Wert, kein "
                      "Fenster und keine Wärmeverluste nach außen."),
        # aw_anteil_*/dach_anteil/boden_anteil sind Anteile einer Flaeche (siehe
        # geometrie() unten, l * a) - wie ein Prozentwert nicht ueber 1 (=100 %).
        Param("aw_anteil_a", "Außenwandanteil Seite a", "Anteil 0–1", 1.0,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0, maximum=1.0,
              hinweis="Welcher Teil dieser Seite an die Außenluft grenzt: 1,0 = ganz "
                      "außen, 0,5 = zur Hälfte an einen Nachbarraum, 0 = ganz innen."),
        Param("aw_anteil_b", "Außenwandanteil Seite b", "Anteil 0–1", 0.5,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0, maximum=1.0),
        Param("aw_anteil_c", "Außenwandanteil Seite c", "Anteil 0–1", 0.35,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0, maximum=1.0),
        Param("aw_anteil_d", "Außenwandanteil Seite d", "Anteil 0–1", 1.0,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0, maximum=1.0),
        # geometrie() nimmt nur die Anteile a bis d entgegen - aw_anteil_e wird
        # nirgends gelesen, so wie es auch die Excel-Vorlage nicht tut.
        Param("aw_anteil_e", "Außenwandanteil Seite e - ohne Wirkung", "Anteil 0–1", 0.0,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0, maximum=1.0,
              hinweis="Wird nicht gerechnet: Seite e geht nur über ihre Länge in die "
                      "Innenwandfläche ein. Wärmeverluste bilden allein die Seiten "
                      "a bis d - so wie in der Excel-Vorlage."),
        Param("u_wand_a", "U-Wert Wand a", "W/(m²·K)", 1.62, darstellung=ZAHL, dezimalstellen=2, minimum=0.0,
              hinweis="Wärmedurchgang der Wand: je kleiner, desto besser gedämmt. "
                      "Altbau ohne Dämmung rund 1,5; heutiger Neubau unter 0,3."),
        Param("u_wand_b", "U-Wert Wand b", "W/(m²·K)", 1.9, darstellung=ZAHL, dezimalstellen=2, minimum=0.0),
        Param("u_wand_c", "U-Wert Wand c", "W/(m²·K)", 1.9, darstellung=ZAHL, dezimalstellen=2, minimum=0.0),
        Param("u_wand_d", "U-Wert Wand d", "W/(m²·K)", 1.9, darstellung=ZAHL, dezimalstellen=2, minimum=0.0),
        Param("fenster_a", "Fensterfläche Seite a", "m²", 0.0, darstellung=ZAHL, dezimalstellen=1, minimum=0.0),
        Param("fenster_b", "Fensterfläche Seite b", "m²", 72.6, darstellung=ZAHL, dezimalstellen=1, minimum=0.0),
        Param("fenster_c", "Fensterfläche Seite c", "m²", 0.0, darstellung=ZAHL, dezimalstellen=1, minimum=0.0),
        Param("fenster_d", "Fensterfläche Seite d", "m²", 123.8, darstellung=ZAHL, dezimalstellen=1, minimum=0.0),
        Param("u_fenster_a", "U-Wert Fenster a", "W/(m²·K)", 2.5, darstellung=ZAHL, dezimalstellen=2, minimum=0.0),
        Param("u_fenster_b", "U-Wert Fenster b", "W/(m²·K)", 2.5, darstellung=ZAHL, dezimalstellen=2, minimum=0.0),
        Param("u_fenster_c", "U-Wert Fenster c", "W/(m²·K)", 2.5, darstellung=ZAHL, dezimalstellen=2, minimum=0.0),
        Param("u_fenster_d", "U-Wert Fenster d", "W/(m²·K)", 2.5, darstellung=ZAHL, dezimalstellen=2, minimum=0.0),
        # War als "Dachanteil"/"m" beschriftet, wird aber als Winkel gerechnet
        # (math.radians() in geometrie() unten) - das war eine falsche Einheit.
        Param("dach_laenge", "Dachneigung", "Grad", 0.0, darstellung=ZAHL, dezimalstellen=1,
              hinweis="0° ist ein Flachdach. Mit der Neigung wächst die Dachfläche: "
                      "bei 30° sind es rund 15 % mehr als der Grundriss."),
        Param("dach_anteil", "Anteil des Dachs nach außen", "Anteil 0–1", 1.0,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0, maximum=1.0),
        Param("u_dach", "U-Wert Dach", "W/(m²·K)", 0.91, darstellung=ZAHL, dezimalstellen=2, minimum=0.0),
        Param("fenster_dach", "Fläche der Dachfenster", "m²", 0.0, darstellung=ZAHL, dezimalstellen=1, minimum=0.0),
        Param("u_fenster_dach", "U-Wert Dachfenster", "W/(m²·K)", 2.5, darstellung=ZAHL, dezimalstellen=2, minimum=0.0),
        Param("boden_anteil", "Anteil der Bodenplatte zum Erdreich", "Anteil 0–1", 1.0,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0, maximum=1.0),
        Param("u_boden", "U-Wert Bodenplatte", "W/(m²·K)", 0.16, darstellung=ZAHL, dezimalstellen=2, minimum=0.0,
              hinweis="Hinter der Bodenplatte wird ganzjährig mit fest 10 °C "
                      "Erdreich gerechnet, nicht mit der Außentemperatur."),
        Param("geschosse", "Geschosse", "Anzahl", 1.0, darstellung=ZAHL, dezimalstellen=0, minimum=0.0,
              hinweis="Wirkt allein auf die speicherwirksame Innenfläche: Jedes "
                      "Geschoss bringt eine weitere Decke ein. Grundfläche, Volumen "
                      "und Wärmeverluste ändern sich dadurch nicht."),
        Param("hoehe", "Raumhöhe", "m", 6.15, darstellung=ZAHL, dezimalstellen=2, minimum=0.0),
        Param("bauart", "Speicherfähigkeit der Innenbauteile (Bauart)", "Wh/(m²·K)", 90.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0,
              hinweis="Wie viel Wärme Wände und Decken je m² und Kelvin aufnehmen: "
                      "rund 90 für schwere Massivbauweise, rund 30 für leichte. Je "
                      "größer, desto langsamer wird der Raum warm - und desto länger "
                      "hält er die Wärme."),
        Param("ausrichtung", "Ausrichtung des Gebäudes", "Grad", 65.0, darstellung=ZAHL, dezimalstellen=1,
              hinweis="Drehung gegen die Himmelsrichtungen: 0° heißt Seite a nach "
                      "Norden, b nach Osten, c nach Süden, d nach Westen. 90° dreht "
                      "jede Seite um eine Himmelsrichtung weiter; dazwischen wird die "
                      "Einstrahlung anteilig auf beide Nachbarrichtungen verteilt."),
        Param("waermebruecke", "Zuschlag für Wärmebrücken", "W/(m²·K)", 0.1,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0,
              hinweis="Pauschaler Aufschlag auf die gesamte Hüllfläche für "
                      "Anschlüsse, Stützen und Durchdringungen."),
        Param("waermeuebergang", "Wärmeübergang Raumluft an Innenbauteile", "W/(m²·K)", 7.7,
              darstellung=ZAHL, dezimalstellen=1, minimum=0.0),
        # g-Faktor und Verschattung sind Anteile durchgelassener Strahlung - wie
        # ein Prozentwert nicht ueber 1 (=100 %), siehe solargewinn() unten.
        Param("g_faktor", "Energiedurchlass der Verglasung (g-Wert)", "Anteil 0–1", 0.8,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0, maximum=1.0,
              hinweis="Welcher Teil der auftreffenden Sonnenenergie durchs Glas in "
                      "den Raum kommt: 0,8 = 80 % bei Einfachglas, 0,5 bis 0,6 bei "
                      "Sonnenschutzverglasung."),
        # verschattung_1/2 wirken auf alle Fenster, verschattung_3 nur auf die
        # Fassade, verschattung_4 wieder auf alle (siehe solargewinn(): die
        # Fassade bekommt v1*v2*v3*v4, das Dachfenster v1*v2*v4).
        Param("verschattung_1", "Verschattung 1 (alle Fenster)", "Anteil 0–1", 0.7,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0, maximum=1.0,
              hinweis="Durchlassanteil einer Verschattung: 1,0 verschattet nicht, 0,7 "
                      "lässt 70 % der Strahlung durch. Die vier Werte werden "
                      "miteinander malgenommen - für Umgebung, Rahmen, Jalousie und "
                      "Ähnliches."),
        Param("verschattung_2", "Verschattung 2 (alle Fenster)", "Anteil 0–1", 0.9,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0, maximum=1.0),
        Param("verschattung_3", "Verschattung 3 (nur Fassadenfenster)", "Anteil 0–1", 0.9,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0, maximum=1.0,
              hinweis="Wirkt als einzige nicht auf die Dachfenster - dort steht "
                      "stattdessen nur Verschattung 1, 2 und 4."),
        Param("verschattung_4", "Verschattung 4 (alle Fenster)", "Anteil 0–1", 1.0,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0, maximum=1.0),
        Param("spez_beleuchtung", "Spezifische Beleuchtungsleistung", "W/m²", 2.0,
              darstellung=ZAHL, dezimalstellen=1, minimum=0.0,
              hinweis="Wird rund um die Uhr als Wärme angesetzt, ohne Zeitplan. Wer "
                      "die Beleuchtung nur im Betrieb rechnen will, setzt diesen Wert "
                      "auf 0 und hängt die eigene Karte „Beleuchtung“ an die "
                      "Wärmelast."),
        Param("start_temperatur", "Starttemperatur von Raum und Wänden", "°C", 20.0,
              darstellung=ZAHL, dezimalstellen=1,
              hinweis="Nur der Anfangswert der ersten gerechneten Stunde; nach ein "
                      "paar Tagen Simulation ist sein Einfluss verschwunden."),
    ]

    PORTS = [
        Port("zuluft_ein", LUFT, EINGANG, ZULUFT, dynamisch=True),
        Port("abluft_aus", LUFT, AUSGANG, ABLUFT, dynamisch=True),
        Port("T_AU", SIGNAL, EINGANG, MESSWERT),
        Port("F_AU", SIGNAL, EINGANG, MESSWERT),
        Port("QH_S", SIGNAL, EINGANG, MESSWERT),
        Port("QH_O", SIGNAL, EINGANG, MESSWERT),
        Port("QH_W", SIGNAL, EINGANG, MESSWERT),
        Port("QH_N", SIGNAL, EINGANG, MESSWERT),
        Port("QH_H", SIGNAL, EINGANG, MESSWERT),
        Port("waermelast", SIGNAL, EINGANG, MESSWERT),
        Port("feuchtelast", SIGNAL, EINGANG, MESSWERT),
        Port("QH_stat", SIGNAL, EINGANG, MESSWERT),
        Port("T_Raum", SIGNAL, AUSGANG, MESSWERT),
        Port("F_Raum", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["T_Raum", "F_Raum", "T_Wand", "QH_Solar", "Q_Bel", "Q_Raum"]
    AUSGABE_LABEL = {
        "T_Raum": "Raumtemperatur (°C)",
        "F_Raum": "Raumfeuchte, absolut (g/kg)",
        "T_Wand": "Temperatur der Innenbauteile (°C)",
        "QH_Solar": "Sonneneintrag durch die Fenster (kW)",
        "Q_Bel": "Beleuchtungswärme (kW)",
        "Q_Raum": "Wärmeinhalt der Raumluft (kWh)",
    }
    # Zehn Signaleingaenge, alle mit der Rolle "Messwert": ohne eigene
    # Beschriftung stuenden im Parameterfenster zehn Zeilen "Messwert".
    PORT_LABEL = {
        "T_AU": "Außentemperatur (°C)",
        "F_AU": "Außenfeuchte, absolut (g/kg)",
        "QH_S": "Sonneneinstrahlung Süd (W/m²)",
        "QH_O": "Sonneneinstrahlung Ost (W/m²)",
        "QH_W": "Sonneneinstrahlung West (W/m²)",
        "QH_N": "Sonneneinstrahlung Nord (W/m²)",
        "QH_H": "Sonneneinstrahlung waagerecht (W/m²)",
        "waermelast": "innere Wärmelast (kW)",
        "feuchtelast": "innere Feuchtelast (kg/h)",
        "QH_stat": "Leistung der statischen Heizung (kW)",
    }

    # -- Geometrie -------------------------------------------------------

    def geometrie(self, p):
        h = p["hoehe"]
        laengen = [p["laenge_a"], p["laenge_b"], p["laenge_c"], p["laenge_d"]]
        anteile = [p["aw_anteil_a"], p["aw_anteil_b"], p["aw_anteil_c"], p["aw_anteil_d"]]
        u_wand = [p["u_wand_a"], p["u_wand_b"], p["u_wand_c"], p["u_wand_d"]]
        fenster = [p["fenster_a"], p["fenster_b"], p["fenster_c"], p["fenster_d"]]
        u_fenster = [
            p["u_fenster_a"], p["u_fenster_b"], p["u_fenster_c"], p["u_fenster_d"]
        ]

        grundflaeche = (p["laenge_a"] + p["laenge_c"]) / 2.0 * (
            (p["laenge_b"] + p["laenge_d"]) / 2.0
        )
        volumen = grundflaeche * h
        dachflaeche = (
            (p["laenge_b"] / 2.0) / math.cos(math.radians(p["dach_laenge"]))
        ) * p["laenge_a"] * 2.0
        fensterflaeche = sum(fenster) + p["fenster_dach"]

        umfang = sum(laengen) + p["laenge_e"] * 2.0
        innenwand = (
            umfang * h + p["geschosse"] * grundflaeche + dachflaeche - fensterflaeche
        )
        aussenwand = sum(l * a for l, a in zip(laengen, anteile)) * h - fensterflaeche

        trans_aw = sum(
            (l * h - f) * a * u
            for l, a, u, f in zip(laengen, anteile, u_wand, fenster)
        )
        trans_fe = sum(f * u for f, u in zip(fenster, u_fenster)) + (
            p["fenster_dach"] * p["u_fenster_dach"]
        )
        trans_fb = p["u_boden"] * grundflaeche * p["boden_anteil"]
        trans_da = p["u_dach"] * dachflaeche * p["dach_anteil"]

        luftwechsel = (
            1.135 * (aussenwand + dachflaeche + fensterflaeche) / volumen
            if volumen else 0.0
        )
        spez_verlust = 0.34 * luftwechsel * volumen

        return {
            "grundflaeche": grundflaeche,
            "volumen": volumen,
            "dachflaeche": dachflaeche,
            "fensterflaeche": fensterflaeche,
            "innenwand": innenwand,
            "aussenwand": aussenwand,
            "trans_aw": trans_aw,
            "trans_fe": trans_fe,
            "trans_fb": trans_fb,
            "trans_da": trans_da,
            "luftwechsel": luftwechsel,
            "spez_verlust": spez_verlust,
        }

    def beleuchtungswaerme(self, p):
        return p["spez_beleuchtung"] * self.geometrie(p)["grundflaeche"] / 1000.0

    def solargewinn(self, p, strahlung, T_AU):
        """Anlage!AK122 - Fenster nach Ausrichtung gewichtet.

        Die Abminderung auf ein Fuenftel haengt an der AUSSENtemperatur, nicht an
        der Raumtemperatur: AK122 prueft AJ75, und AI75 beschriftet diese Zelle
        als T_AU. Gemeint ist offenbar, dass ab 22 °C draussen die Verschattung
        gefahren wird. Die Raumtemperatur steht in AJ87 und wird hier nicht
        verwendet.
        """
        a = p["ausrichtung"] / 90.0
        b = 1.0 - a
        g = p["g_faktor"]
        v = p["verschattung_1"] * p["verschattung_2"] * p["verschattung_3"]
        v_dach = p["verschattung_1"] * p["verschattung_2"] * p["verschattung_4"]

        S = strahlung.get("QH_S", 0.0)
        O = strahlung.get("QH_O", 0.0)
        W = strahlung.get("QH_W", 0.0)
        N = strahlung.get("QH_N", 0.0)
        H = strahlung.get("QH_H", 0.0)

        summe = (
            p["fenster_a"] * (b * N + a * O)
            + p["fenster_b"] * (b * O + a * S)
            + p["fenster_c"] * (b * S + a * W)
            + p["fenster_d"] * (b * W + a * N)
        ) * g * v * p["verschattung_4"]
        summe += p["fenster_dach"] * H * g * v_dach
        summe /= 1000.0

        return 0.2 * summe if T_AU > 22.0 else summe

    # -- Bilanz ----------------------------------------------------------

    def berechne(self, ein, p, zustand):
        g = self.geometrie(p)

        T_Raum_alt = float(zustand.get("T_Raum", p["start_temperatur"]))
        T_Wand = float(zustand.get("T_Wand", p["start_temperatur"]))

        zuluft = [
            w for s, w in ein.items()
            if s.startswith("zuluft_ein") and isinstance(w, Luft)
        ]
        abluft = [
            (s, w) for s, w in ein.items()
            if s.startswith("abluft_aus") and isinstance(w, Luft)
        ]

        V_zu = sum(w.V for w in zuluft)
        T_zu = sum(w.V * w.T for w in zuluft) / V_zu if V_zu else 0.0
        x_zu = sum(w.V * w.x for w in zuluft) / V_zu if V_zu else 0.0

        T_AU = float(ein.get("T_AU", 0.0))
        F_AU = float(ein.get("F_AU", 0.0))
        Q_i = float(ein.get("waermelast", 0.0))
        M_i = float(ein.get("feuchtelast", 0.0))
        QH_stat = float(ein.get("QH_stat", 0.0))

        strahlung = {
            k: float(ein.get(k, 0.0))
            for k in ("QH_S", "QH_O", "QH_W", "QH_N", "QH_H")
        }
        QH_Solar = self.solargewinn(p, strahlung, T_AU)
        Q_Bel = self.beleuchtungswaerme(p)

        huelle = g["aussenwand"] + g["dachflaeche"] + g["grundflaeche"] + g["fensterflaeche"]
        trans_summe = g["trans_aw"] + g["trans_fe"] + g["trans_fb"] + g["trans_da"]
        wand_kopplung = g["innenwand"] * p["waermeuebergang"]

        # Anlage!AH85 - alle Abfluesse je Kelvin, negativ
        A = -(
            wand_kopplung
            + trans_summe
            + p["waermebruecke"] * huelle
            + g["spez_verlust"]
            + V_zu * LUFT_C
        )
        # Anlage!AI85 - alle Zufluesse in Watt
        B = (
            Q_Bel * 1000.0
            + QH_Solar * 1000.0
            + wand_kopplung * T_Wand
            + g["trans_fb"] * ERDREICH
            + (g["trans_da"] + g["trans_aw"] + g["trans_fe"]) * T_AU
            + p["waermebruecke"] * huelle * T_AU
            + g["spez_verlust"] * T_AU
            + V_zu * LUFT_C * T_zu
            + QH_stat * 1000.0
            + Q_i * 1000.0
        )
        C = LUFT_C * g["volumen"]  # Anlage!AJ85

        if A == 0 or C == 0:
            T_Raum = T_Raum_alt
        else:
            beharrung = B / A
            T_Raum = (T_Raum_alt + beharrung) * math.exp(A / C) - beharrung

        # Wandspeicher, Anlage!AK127/AK128.
        #
        # Achtung, hier steckt eine Ungereimtheit der Vorlage: 'bauart' ist mit
        # Wh/(m² K) beschriftet, sodass innenwand * bauart eine Kapazitaet in Wh/K
        # ergaebe - zu QH_Wand in kW gehoerte dann der Teiler 1000. Die Excel teilt
        # aber durch 3600, wodurch sich die Wand rund 3,6-mal so schnell an den Raum
        # angleicht. Uebernommen wird die Excel, weil der Nachbau ihre Ergebnisse
        # reproduzieren soll; der Test unten haelt den Wert aus AK127 fest, damit
        # das eine bewusste Entscheidung bleibt und kein Zahlendreher.
        QH_Wand = (T_Wand - T_Raum) * p["waermeuebergang"] * g["innenwand"] / 1000.0
        C_Wand = g["innenwand"] * p["bauart"] / 3600.0
        T_Wand_neu = T_Wand - QH_Wand / C_Wand if C_Wand else T_Wand

        # Feuchtebilanz, Anlage!AJ90
        if V_zu > 0:
            F_Raum = (V_zu * x_zu * 1.2 + M_i * 1000.0) / (V_zu * 1.2)
        else:
            F_Raum = F_AU + (M_i * 1000.0 / g["volumen"] if g["volumen"] else 0.0)

        Q_Raum = T_Raum * (1.005 * 1.2 * g["volumen"] / 3600.0)

        aus = {
            "T_Raum": T_Raum,
            "F_Raum": F_Raum,
            "T_Wand": T_Wand_neu,
            "QH_Solar": QH_Solar,
            "Q_Bel": Q_Bel,
            "Q_Raum": Q_Raum,
        }
        for schluessel, w in abluft:
            aus[schluessel] = Luft(V=w.V, T=T_Raum, x=F_Raum, dp=0.0)

        return aus, {"T_Raum": T_Raum, "T_Wand": T_Wand_neu}

    def anfangszustand(self, p):
        return {
            "T_Raum": p["start_temperatur"],
            "T_Wand": p["start_temperatur"],
        }

    def bedarf(self, aus_bedarf, p):
        return {}
