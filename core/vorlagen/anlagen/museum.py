"""Museum und Archiv - enges Feuchteband in beide Richtungen.

Der Fall, den keine andere Anlage zeigt: Die Luft muss BEIDES koennen -
befeuchten, wenn die kalte Winterluft die Raeume austrocknet, und entfeuchten,
wenn im Sommer die feuchte Aussenluft hereinkommt. Dampfbefeuchter und Kuehler
arbeiten dabei gegen denselben Raum, und beide haengen an derselben
Raumfeuchte. Rund um die Uhr, das ganze Jahr - Exponate kennen keine
Betriebszeit.

AUSLEGUNG

    Geometrie      800 m2 Ausstellung und Depot, 4,0 m hoch -> 3200 m3
    Luftmenge      4 000 m3/h -> 1,25 facher Luftwechsel. Bewusst niedrig:
                   je weniger Aussenluft, desto weniger Feuchteschwankung.
    Sollwerte      20 GradC und 50 % relative Feuchte -> 7,3 g/kg.
                   Der uebliche Bereich fuer gemischte Sammlungen liegt bei
                   45 bis 55 % - die Schwankung zaehlt mehr als der Absolutwert.
    Transmission   massiver Bau, gut gedaemmt -> rund 0,5 kW/K
    Heizlast       Transmission 0,5 x 32 K                     = 16,0 kW
                   Lueftung nach WRG (75 %)
                       4000 x 0,34 x 32 x 0,25                 = 10,9 kW
                                                                 -------
                                                                  26,9 kW
                   -> Erhitzer 35 kW
    Befeuchtung    Von 1,5 g/kg Aussenluft im Winter auf 7,3 g/kg:
                       4000/3600 x 1,2 x 5,8 g/kg              = 7,7 kg/h
                   mit 10 % Absalzverlust 8,5 kg/h -> Dampfbefeuchter 16 kg/h
    Innere Last    Ausstellungsbeleuchtung 12 W/m2 x 800 m2      = 9,6 kW
                   60 Besucher x 75 W                            = 4,5 kW
                   Ihre Feuchteabgabe von 60 x 50 g/h = 3,0 kg/h ist fuer ein
                   Museum die wichtigere Zahl: Sie laeuft der Feuchteregelung
                   entgegen, die das Haus auf 50 % relative Feuchte haelt.
    Kuehllast      Entfeuchtung im Sommer und innere Lasten    -> Kuehler 30 kW
    Ventilator     4000 m3/h, 800 Pa, Wirkungsgrad 0,65        = 1,37 kW
                   -> SFP 0,34 W/(m3/h)
"""

from core.vorlagen.bauhilfe import Bauplatz

NAME = "Museum und Archiv"
BESCHREIBUNG = (
    "800 m² Ausstellung und Depot, enges Feuchteband in beide Richtungen: "
    "Dampfbefeuchter im Winter, Entfeuchtung über den Kühler im Sommer, 24/7"
)

FLAECHE_M2 = 800.0
LUFTMENGE_M3H = 4000.0
#: Lichte Raumhöhe - der Prüfstand rechnet daraus den Luftwechsel.
HOEHE_M = 4.0
SOLL_FEUCHTE_G_KG = 7.3

ERWARTUNG = {
    # Durchlaufbetrieb bei niedrigem Luftwechsel und gut gedaemmter Huelle.
    "heizwaerme_kwh_m2a": (20.0, 120.0),
    "kaelte_kwh_m2a": (2.0, 60.0),
    "sfp_w_m3h": (0.25, 0.95),
    "luftwechsel_1h": (1.0, 1.5),
}

WOCHENTAGE = ("montag", "dienstag", "mittwoch", "donnerstag", "freitag",
              "samstag", "sonntag")


def baue(projekt_id, name=NAME):
    with Bauplatz(projekt_id, name, notiz=BESCHREIBUNG) as b:
        wetter = b.karte("wetter", 40, 20, "Wetterdaten")
        aussenluft = b.karte("aussenluft", 40, 200, "Außenluft")
        wrg = b.karte("wrg", 260, 200, "Wärmerückgewinnung",
                      V_nenn=LUFTMENGE_M3H, dp_WRG_nenn=140.0, dp_Bypass_nenn=35.0,
                      rueckwaermzahl=75.0, rueckfeuchtzahl=0.0)
        erhitzer = b.karte("erhitzer", 480, 200, "Erhitzer",
                           V_nenn=LUFTMENGE_M3H, dp_nenn=140.0, QH_max=35.0)
        kuehler = b.karte("kuehler", 700, 200, "Kühler (Entfeuchtung)",
                          V_nenn=LUFTMENGE_M3H, dp_nenn=180.0, QK_nenn=30.0,
                          T_KW_mittel=6.0, kontaktfaktor=0.6)
        befeuchter = b.karte("dampfbefeuchter", 920, 200, "Dampfbefeuchter",
                             dampftemperatur=180.0, absalzverlust=10.0,
                             max_leistung=16.0, dampfart="E")
        zuluft = b.karte("ventilator", 1140, 200, "Zuluftventilator",
                         rolle="zuluft", V_max=LUFTMENGE_M3H, dp_max=800.0,
                         dp_konst=800.0, PE_max=1.4, regelart="F")
        raum = b.karte("einfacher_raum", 1360, 200, "Ausstellung und Depot",
                       spez_transmission=0.5, sollwert_stat=20.0)
        # Die Gebaeudeheizung. Ohne sie meldet der Raum seine
        # Unterdeckung (QH_stat) und niemand nimmt sie entgegen: Er bleibt
        # trotzdem auf seinem Sollwert, und die Waerme dafuer taucht in
        # keiner Bilanz auf - das Gebaeude heizte sich umsonst. Der
        # Lueftungserhitzer deckt das nicht; er waermt die Zuluft, nicht
        # die Huelle. Auslegung: 0,5 kW/K x 32 K = 16 kW
        gebaeudeheizung = b.karte("statische_heizung", 1360, 620,
                                  "Gebäudeheizung", QH_nenn=20.0)
        abluft = b.karte("ventilator", 1580, 200, "Abluftventilator",
                         rolle="abluft", V_max=LUFTMENGE_M3H, dp_max=600.0,
                         dp_konst=600.0, PE_max=1.0, regelart="F")
        fortluft = b.karte("fortluft", 260, 420, "Fortluft")

        kaskade = b.karte("kaskade", 480, 20, "Raum-/Zuluft-Kaskade",
                          T_Raum_min=20.0, T_AU_min=15.0, T_Raum_max=22.0,
                          T_AU_max=30.0, T_ZU_min=16.0, T_ZU_max=26.0, xp=5.0,
                          # WRG und Register wärmen, ein Kühler kühlt.
                          waermestufen=2, kaeltestufen=1)
        # Ein Regler fuer beide Richtungen: Stufe 2 (traege) befeuchtet, wenn
        # es zu trocken ist. Zum Entfeuchten dient der Kuehler, den die Kaskade
        # ohnehin fuehrt - er kuehlt die Luft unter den Taupunkt.
        feuchteregler = b.karte("p_regler", 700, 20, "Feuchteregelung",
                                xp_1=5.0, xp_2=2.0, sollwert_2=SOLL_FEUCHTE_G_KG)
        # Kein Umkehrglied: p_regler.berechne rechnet
        # y_neu = y_alt - (istwert - sollwert) / Xp. Ist die Raumluft zu
        # trocken, ist (istwert - sollwert) negativ, die Stellgroesse steigt,
        # und der Befeuchter geht auf - genau die gewuenschte Richtung. Ein
        # Umkehrglied dazwischen kehrte sie um und liesse den Befeuchter
        # gerade dann schliessen, wenn er gebraucht wird (nachgemessen:
        # 3 kWh in einer Januarwoche statt der noetigen Hunderte, Raumfeuchte
        # 22 % statt 45 bis 55 %).

        zeitplan = b.karte(
            "wochenzeitplan", 1140, 620, "Dauerbetrieb",
            **{f"von_{tag}": 0.0 for tag in WOCHENTAGE},
            **{f"bis_{tag}": 1.0 for tag in WOCHENTAGE},
        )
        # Kein Nachtabsenken: die Sammlung braucht auch nachts ihr Klima.
        tagesprofil = b.karte("tageslastprofil", 1360, 620, "Tageslastprofil",
                              lastgang_1=[1.0] * 24)
        betrieb = b.karte("anlagenbetrieb", 1580, 620, "Anlagenbetrieb")
        grundlast = b.karte("faktor", 1800, 620, "Grundlast", faktor=100.0)
        ventilatorstellung = b.karte("maximalwert", 2020, 620, "Ventilatorstellung")

        beleuchtung = b.karte("beleuchtung", 1800, 420, "Ausstellungsbeleuchtung",
                              spez_leistung=12.0, grundflaeche=FLAECHE_M2,
                              nennbeleuchtung=200.0)
        # Ein Museum wird nach RELATIVER Feuchte gefuehrt, geregelt wird aber
        # auf die absolute (in g/kg fuehrt auch die Bilanz). Der
        # Enthalpierechner macht aus Raumtemperatur und absoluter Feuchte die
        # relative, damit im Datenlogger die Groesse steht, ueber die ein
        # Konservator spricht.
        enthalpie = b.karte("enthalpierechner", 1800, 20, "Raumluftzustand")

        bilanz = b.karte("bilanz", 2240, 200, "Jahresbilanz",
                         preis_strom=280.0, preis_waerme=95.0, preis_kaelte=95.0,
                         preis_wasser=4.2, ht_von=6.0 / 24.0, ht_bis=19.0 / 24.0)
        logger = b.karte("datenlogger", 2240, 20, "Datenlogger",
                         namen=["T Raum", "F Raum", "Sollwert", "T Zuluft",
                                "Wärme WRG", "rel. Feuchte", "Enthalpie"] + [""] * 3,
                         einheiten=["°C", "g/kg", "°C", "°C", "kW",
                                    "%", "kJ/kg"] + [""] * 3)

        b.pfeil(wetter, aussenluft)
        b.pfeil(wetter, raum)
        b.verbinde(aussenluft, "luft_aus", wrg, "zuluft_ein")
        b.pfeil(wrg, erhitzer)
        b.pfeil(erhitzer, kuehler)
        b.pfeil(kuehler, befeuchter)
        b.pfeil(befeuchter, zuluft)
        b.pfeil(zuluft, raum)
        b.pfeil(raum, abluft)
        b.verbinde(abluft, "luft_aus", wrg, "abluft_ein")
        b.verbinde(wrg, "abluft_aus", fortluft, "luft_ein")

        b.verbinde(wetter, "T_AU", kaskade, "T_AU")
        b.verbinde(raum, "T_Raum", kaskade, "T_Raum")
        b.verbinde(zuluft, "T_aus", kaskade, "T_ZU")
        b.verbinde(kaskade, "waermer_1", wrg, "stellgroesse")
        b.verbinde(kaskade, "waermer_2", erhitzer, "stellgroesse")
        b.verbinde(kaskade, "kaelter_1", kuehler, "stellgroesse")

        b.verbinde(raum, "F_Raum", feuchteregler, "istwert_2")
        b.verbinde(feuchteregler, "ausgang_2", befeuchter, "stellgroesse")

        b.pfeil(zeitplan, betrieb)
        b.pfeil(tagesprofil, betrieb)
        b.verbinde(tagesprofil, "lastgang_1", grundlast, "ein")
        b.verbinde(betrieb, "stellgrad", ventilatorstellung, "ein_1")
        b.verbinde(grundlast, "ausgang", ventilatorstellung, "ein_2")
        b.verbinde(ventilatorstellung, "ausgang", zuluft, "stellgroesse")
        b.verbinde(ventilatorstellung, "ausgang", abluft, "stellgroesse")
        b.pfeil(betrieb, beleuchtung)
        lasten = b.karte("innere_lasten", 1580, 420, "Innere Lasten",
                         personen=60.0, waerme_je_person=75.0, feuchte_je_person=50.0,
                         grundflaeche=FLAECHE_M2)
        # Der Raum hat je EINEN Eingang fuer Waerme- und Feuchtelast; die
        # Lastenkarte zaehlt zusammen, was hineingeht. Bisher lief nur die
        # Waerme dorthin, und die Feuchteabgabe der Menschen fehlte ganz.
        b.verbinde(tagesprofil, "lastgang_1", lasten, "belegung")
        b.verbinde(beleuchtung, "Q_Bel", lasten, "weitere_waerme")
        b.verbinde(lasten, "waermelast", raum, "waermelast")
        b.verbinde(lasten, "feuchtelast", raum, "feuchtelast")

        b.verbinde(raum, "QH_stat", gebaeudeheizung, "QH_stat")
        for karte in (zuluft, abluft, erhitzer, kuehler, befeuchter, beleuchtung, gebaeudeheizung):
            b.pfeil(karte, bilanz)
        b.verbinde(raum, "T_Raum", enthalpie, "t")
        b.verbinde(raum, "F_Raum", enthalpie, "x")
        # Erst die benannten Groessen auf ihre Steckplaetze, dann den Pfeil:
        # Ein Pfeil auf den Datenlogger belegt die freien Plaetze der Reihe
        # nach, und zwar so viele, wie die Gegenkarte Messwerte anbietet. Stand
        # er zuerst, verschob ein neuer Ausgang an einer Karte alle folgenden
        # Nummern.
        b.verbinde(wrg, "Q_WRG", logger, "wert_5")
        b.verbinde(enthalpie, "rF", logger, "wert_6")
        b.verbinde(enthalpie, "h", logger, "wert_7")
        b.pfeil(raum, logger)
        b.pfeil(kaskade, logger)

    return b.anlage
