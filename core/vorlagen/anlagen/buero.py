"""Buerogebaeude mit Waermerueckgewinnung - der Regelfall.

Zwei Geschosse zu je 1000 m2, belegt Montag bis Freitag von 7 bis 18 Uhr. Ein
Zentralgeraet mit Plattenwaermetauscher, Erhitzer und Kuehler; die Zuluft wird
ueber eine Raum-/Zuluft-Kaskade gefuehrt. Keine Befeuchtung - in einem
gewoehnlichen Buero wird nicht befeuchtet.

Diese Anlage ist der einfachste der zehn Faelle und dient als Bezugspunkt: Was
hier nicht auffaellt, faellt auch sonst nirgends an der Grundkette auf.

AUSLEGUNG (nachrechenbar, nicht aus dem Gedaechtnis)

    Geometrie      40 x 25 m, 2 Geschosse, 3,0 m lichte Hoehe
                   -> 2000 m2 Flaeche, 6000 m3 Volumen

    Luftmenge      8000 m3/h -> 8000 / 6000 = 1,33 facher Luftwechsel.
                   Fuer ein Buero ueblich (Richtwert 1 bis 2 je Stunde).

    Transmission   Waende  780 m2, davon 25 % Fenster
                       585 m2 x 0,35 W/(m2K) =  205 W/K
                       195 m2 x 1,30 W/(m2K) =  254 W/K
                   Dach   1000 m2 x 0,25     =  250 W/K
                   Boden  1000 m2 x 0,30     =  300 W/K
                   Waermebruecken +10 %      =  101 W/K
                                              ----------
                                             1110 W/K -> spez_transmission 1,11 kW/K

    Heizlast       bei -12 GradC aussen und 20 GradC innen, also 32 K:
                   Transmission   1,11 kW/K x 32 K              = 35,5 kW
                   Lueftung nach WRG (75 % rueckgewonnen):
                       8000 m3/h x 0,34 Wh/(m3K) x 32 K x 0,25  = 21,8 kW
                                                                 --------
                                                                  57,3 kW
                   -> Erhitzer 70 kW (rund 20 % Zuschlag)

    Kuehllast      innere Lasten 25 W/m2 x 2000 m2              = 50 kW
                   davon Personen  160 Pers. x 75 W  = 12,0 kW =  6 W/m2
                         Geraete   11 W/m2           = 22,0 kW = 11 W/m2
                         Beleucht.  8 W/m2           = 16,0 kW =  8 W/m2
                   160 Personen sind 12,5 m2 je Person - der uebliche Ansatz
                   fuer ein Grossraumbuero. Ihre Feuchteabgabe von je 50 g/h
                   ergibt bei voller Belegung 8,0 kg/h.
                   Aussenluft im Sommer (32 GradC, nach WRG)    = 10 kW
                   -> Kuehler 80 kW

    Ventilator     8000 m3/h, 900 Pa, Wirkungsgrad 0,65:
                   8000/3600 x 900 / 0,65 / 1000                = 3,08 kW
                   -> SFP 3080 W / 8000 m3/h = 0,39 W/(m3/h),
                      im ueblichen Bereich 0,3 bis 0,5.
"""

from core.vorlagen.bauhilfe import (
    Bauplatz, auswertung_verdrahten, betrieb_verdrahten,
    kaskade_verdrahten, lasten_verdrahten, luftweg_verdrahten,
)

NAME = "Bürogebäude mit WRG"
#: Wohin die Anlage im Katalog gehoert (siehe core/vorlagen/__init__.py,
#: alle()). Drei Gruppen statt zehn Einzelbezeichnungen: Zwoelf Karten in
#: einer Reihe sind kein Katalog, und eine Gruppe je Anlage waere keine
#: Gliederung, sondern dieselbe Reihe mit Ueberschriften.
GRUPPE = "Komfortlüftung"
BESCHREIBUNG = (
    "2000 m² Büro auf zwei Geschossen, Zentralgerät mit Plattenwärmetauscher, "
    "Erhitzer und Kühler, Raum-/Zuluft-Kaskade, Betrieb Mo–Fr 7–18 Uhr"
)

FLAECHE_M2 = 2000.0
LUFTMENGE_M3H = 8000.0
#: Lichte Raumhöhe - der Prüfstand rechnet daraus den Luftwechsel.
HOEHE_M = 3.0
VOLUMEN_M3 = 6000.0

#: Erwartungsbänder, hergeleitet oben im Kopf dieser Datei.
ERWARTUNG = {
    # Gradtagszahl Dresden (20/15) rund 3300 Kd/a. Transmission über das Jahr:
    # 1,11 kW/K x 3300 Kd x 24 h = 87 900 kWh/a = 44 kWh/(m²·a). Davon deckt
    # ein Teil die inneren Lasten und die Sonne ab; die Lüftung kommt in den
    # Betriebsstunden hinzu. Das Band ist bewusst weit: Es soll grobe Fehler
    # (Faktor zwei und mehr) fangen, nicht eine Auslegung nachrechnen.
    "heizwaerme_kwh_m2a": (15.0, 70.0),
    # Innere Lasten 25 W/m² über rund 2800 Betriebsstunden ergäben 70 kWh/(m²·a),
    # wenn alles weggekühlt werden müsste. Ein großer Teil geht über die
    # Abluft und die Hülle ab, und im Winter wird gar nicht gekühlt.
    "kaelte_kwh_m2a": (2.0, 40.0),
    # SFP beider Ventilatoren zusammen, siehe Auslegung oben.
    "sfp_w_m3h": (0.25, 0.95),
    "luftwechsel_1h": (1.0, 1.7),
}


def baue(projekt_id, name=NAME):
    with Bauplatz(projekt_id, name, notiz=BESCHREIBUNG) as b:
        # -- Quellen -----------------------------------------------------
        wetter = b.karte("wetter", 40, 20, "Wetterdaten")
        aussenluft = b.karte("aussenluft", 40, 200, "Außenluft")

        # -- Luftbehandlung ----------------------------------------------
        wrg = b.karte(
            "wrg", 260, 200, "Plattenwärmetauscher",
            V_nenn=LUFTMENGE_M3H, dp_WRG_nenn=150.0, dp_Bypass_nenn=40.0,
            # 75 % ist für einen Plattentauscher realistisch (Kreuz-Gegenstrom).
            # Keine Feuchteübertragung - ein Plattentauscher überträgt sie nicht.
            rueckwaermzahl=75.0, rueckfeuchtzahl=0.0,
        )
        erhitzer = b.karte(
            "erhitzer", 480, 200, "Erhitzer",
            V_nenn=LUFTMENGE_M3H, dp_nenn=150.0, QH_max=70.0,
        )
        kuehler = b.karte(
            "kuehler", 700, 200, "Kühler",
            V_nenn=LUFTMENGE_M3H, dp_nenn=180.0, QK_nenn=80.0,
            T_KW_mittel=6.0, kontaktfaktor=0.5,
        )
        zuluft = b.karte(
            "ventilator", 920, 200, "Zuluftventilator",
            rolle="zuluft", V_max=LUFTMENGE_M3H,
            dp_max=900.0, dp_konst=900.0, PE_max=3.1, regelart="F",
        )
        raum = b.karte(
            "einfacher_raum", 1140, 200, "Büroflächen",
            spez_transmission=1.11, sollwert_stat=20.0, sollwert_kuehl=26.0,
        )
        # Die Luftmenge ist nach Hygiene bemessen (50 m3/h je Person) und
        # traegt bei 8 K Untertemperatur rund 22 kW - weniger als die halbe
        # innere Last. Den Rest nimmt eine Kuehldecke auf, wie in jedem so
        # gebauten Buero. Auslegung bei 32 GradC aussen und 26 GradC im Raum:
        #     innere Last                                    50,0 kW
        #     Transmission 1,11 kW/K x 6 K                  + 6,7 kW
        #     Zuluft 8000 m3/h x 0,34 Wh/(m3K) x 10 K       - 27,2 kW
        #                                                    -------
        #                                                    29,5 kW
        # -> 35 kW, also 18 W/m2. Eine Kuehldecke leistet 40 bis 70 W/m2.
        kuehlflaeche = b.karte(
            "statische_kuehlung", 1140, 380, "Kühldecke", QK_nenn=35.0,
        )
        # Und die Gebaeudeheizung. Ohne sie meldet der Raum seine Unterdeckung
        # (QH_stat) und niemand nimmt sie entgegen: Er bleibt trotzdem auf
        # seinem Sollwert, und die Waerme dafuer taucht in keiner Bilanz auf -
        # das Gebaeude heizte sich umsonst. Der Lueftungserhitzer deckt das
        # nicht; er waermt die Zuluft, nicht die Huelle.
        # Auslegung: 1,11 kW/K x 32 K = 35,5 kW -> 40 kW.
        gebaeudeheizung = b.karte(
            "statische_heizung", 1140, 620, "Gebäudeheizung", QH_nenn=40.0,
        )
        abluft = b.karte(
            "ventilator", 1360, 200, "Abluftventilator",
            rolle="abluft", V_max=LUFTMENGE_M3H,
            dp_max=700.0, dp_konst=700.0, PE_max=2.4, regelart="F",
        )
        fortluft = b.karte("fortluft", 260, 380, "Fortluft")

        # -- Regelung ----------------------------------------------------
        # Sollwert gleitend: 20 GradC bei kalter, 26 bei warmer Witterung.
        kaskade = b.karte(
            "kaskade", 480, 20, "Raum-/Zuluft-Kaskade",
            T_Raum_min=20.0, T_AU_min=15.0, T_Raum_max=26.0, T_AU_max=30.0,
            T_ZU_min=16.0, T_ZU_max=28.0, xp=5.0,
            # Verdrahtet sind waermer_1 (Rueckgewinnung), waermer_2 (Register)
            # und kaelter_1 (Kuehler) - weiter darf die Regelabweichung
            # nicht laufen, sonst laedt sie sich wirkungslos auf.
            waermestufen=2, kaeltestufen=1,
        )

        # -- Zeit und Betrieb --------------------------------------------
        zeitplan = b.karte(
            "wochenzeitplan", 920, 560, "Bürozeiten",
            **{f"von_{tag}": 7.0 / 24.0 for tag in
               ("montag", "dienstag", "mittwoch", "donnerstag", "freitag")},
            **{f"bis_{tag}": 18.0 / 24.0 for tag in
               ("montag", "dienstag", "mittwoch", "donnerstag", "freitag")},
            von_samstag=0.0, bis_samstag=0.0, von_sonntag=0.0, bis_sonntag=0.0,
        )
        tagesprofil = b.karte(
            "tageslastprofil", 1140, 560, "Tageslastprofil",
            # Nachts 20 %, tags voll, abends 30 %. Der Anteil darf NICHT
            # kleiner werden: bei kleiner Luftmenge waechst die Autoritaet des
            # Erhitzers je Prozent Ventilstellung so stark, dass die Regelung
            # zwischen ihren Anschlaegen kippt (siehe Commit 055f86a und
            # tests/test_testanlage_regelkreise.py).
            #     3600 x 70 kW / (1,2 x 1,007 x 1600 m3/h) = 1,30 K/%
            #     bei Xp = 5 K also Kreisverstaerkung 0,26 - stabil.
            lastgang_1=[0.2] * 6 + [1.0] * 12 + [0.3] * 6,
        )
        betrieb = b.karte("anlagenbetrieb", 1360, 560, "Anlagenbetrieb")
        grundlast = b.karte(
            "faktor", 1580, 560, "Nachtluft-Grundlast", faktor=100.0,
        )
        ventilatorstellung = b.karte(
            "maximalwert", 1800, 560, "Ventilatorstellung",
        )

        # -- Verbraucher und Auswertung ----------------------------------
        lasten = b.karte(
            "innere_lasten", 1360, 380, "Innere Lasten",
            personen=160.0, waerme_je_person=75.0, feuchte_je_person=50.0,
            grundflaeche=FLAECHE_M2, geraete=11.0, grundlast=0.0,
        )
        beleuchtung = b.karte(
            "beleuchtung", 1580, 380, "Beleuchtung",
            spez_leistung=8.0, grundflaeche=FLAECHE_M2, nennbeleuchtung=500.0,
        )
        bilanz = b.karte(
            "bilanz", 2020, 200, "Jahresbilanz",
            preis_strom=280.0, preis_waerme=95.0, preis_kaelte=95.0,
            preis_wasser=4.2, ht_von=6.0 / 24.0, ht_bis=19.0 / 24.0,
        )
        logger = b.karte(
            "datenlogger", 2020, 20, "Datenlogger",
            namen=["T Raum", "F Raum", "Sollwert Raum", "T Zuluft",
                   "Wärme WRG"] + [""] * 5,
            einheiten=["°C", "g/kg", "°C", "°C", "kW"] + [""] * 5,
        )

        # -- Luftweg -----------------------------------------------------
        b.pfeil(wetter, aussenluft)
        b.pfeil(wetter, raum)
        b.pfeil(betrieb, beleuchtung)

        luftweg_verdrahten(b, aussenluft, wrg, (erhitzer, kuehler), zuluft,
                           raum, abluft, fortluft)
        kaskade_verdrahten(b, wetter, raum, zuluft, kaskade, {
            "waermer_1": wrg, "waermer_2": erhitzer, "kaelter_1": kuehler,
        })
        betrieb_verdrahten(b, (zeitplan, tagesprofil), betrieb, tagesprofil,
                           grundlast, ventilatorstellung, (zuluft, abluft))
        lasten_verdrahten(b, tagesprofil, beleuchtung, lasten, raum,
                          gebaeudeheizung=gebaeudeheizung,
                          kuehlflaeche=kuehlflaeche)
        auswertung_verdrahten(
            b,
            (zuluft, abluft, erhitzer, kuehler, beleuchtung, kuehlflaeche,
             gebaeudeheizung),
            bilanz, logger,
            protokoll=((wrg, "Q_WRG", "wert_5"),),
            pfeile=(raum, kaskade),
        )

    return b.anlage
