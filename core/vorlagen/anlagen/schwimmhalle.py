"""Schwimmhalle - der feuchtekritische Fall.

Eine Wasserflaeche von 500 m2 verdunstet staendig. Die Anlage muss die Feuchte
abfuehren, ohne die Halle auszukuehlen: Im Winter geschieht das ueber die
kalte, trockene Aussenluft, im Sommer reicht deren Feuchte dafuer nicht mehr
aus und der Kuehler muss entfeuchten. Zugleich soll moeglichst viel Luft im
Umlauf bleiben, weil jeder Kubikmeter Aussenluft auf 30 GradC erwaermt werden
muss.

Das ist der Fall, in dem sich eine Rechenkette am ehesten verheddert: Feuchte
und Temperatur haengen ueber die Mischkammer, die Rueckgewinnung und den
Kuehler aneinander, und alle drei wirken auf denselben Raum zurueck.

AUSLEGUNG

    Geometrie      500 m2 Wasserflaeche, Halle 6,0 m hoch -> 3000 m3
    Luftmenge      15 000 m3/h -> 5-facher Luftwechsel. Fuer eine Schwimmhalle
                   ueblich (Richtwert 4 bis 6), weil die Luft die Feuchte
                   forttragen muss, nicht nur den Sauerstoff bringen.
    Verdunstung    Bei 30 GradC Wasser und ruhendem Betrieb rund
                   0,15 kg/(h*m2) -> 500 m2 x 0,15 = 75 kg/h.
                   Die Feuchtelast steht als fester Wert am Raum, gefuehrt
                   ueber den Anlagenbetrieb: nachts mit abgedeckter
                   Wasserflaeche verdunstet weniger.
    Raumtemperatur 30 GradC - in einer Schwimmhalle liegt die Lufttemperatur
                   ueber der Wassertemperatur, sonst verdunstet es staerker.
    Transmission   Halle mit viel Glas -> rund 1,4 kW/K
    Heizlast       Transmission 1,4 x (30 - (-12)) = 42 K            = 58,8 kW
                   Aussenluftanteil 30 % von 15 000 = 4500 m3/h,
                   nach WRG (70 %):
                       4500 x 0,34 x 42 x 0,30                       = 19,3 kW
                   Verdunstungswaerme 75 kg/h x 0,7 kWh/kg           = 52,5 kW
                                                                       -------
                                                                      130,6 kW
                   -> Erhitzer 160 kW
    Kuehllast      Entfeuchtung im Sommer: 15 000 m3/h ueber 4 g/kg
                   herunterkuehlen entspricht rund
                       15000/3600 x 1,2 x 4 g/kg x 2,5 kJ/g          = 50 kW
                   dazu die sensible Last -> Kuehler 90 kW
    Ventilator     15 000 m3/h, 1000 Pa, Wirkungsgrad 0,65           = 6,4 kW
                   -> SFP 0,43 W/(m3/h)
"""

from core.vorlagen.bauhilfe import (
    Bauplatz, auswertung_verdrahten, betrieb_verdrahten,
    kaskade_verdrahten, lasten_verdrahten,
)

NAME = "Schwimmhalle"
#: Wohin die Anlage im Katalog gehoert (siehe core/vorlagen/__init__.py,
#: alle()). Drei Gruppen statt zehn Einzelbezeichnungen: Zwoelf Karten in
#: einer Reihe sind kein Katalog, und eine Gruppe je Anlage waere keine
#: Gliederung, sondern dieselbe Reihe mit Ueberschriften.
GRUPPE = "Sonderbau"
BESCHREIBUNG = (
    "500 m² Wasserfläche, hohe Verdunstungslast, Umluft über Mischkammer, "
    "Entfeuchtung über den Kühler, Raumtemperatur 30 °C"
)

FLAECHE_M2 = 500.0
LUFTMENGE_M3H = 15000.0
#: Lichte Raumhöhe - der Prüfstand rechnet daraus den Luftwechsel.
HOEHE_M = 6.0
VERDUNSTUNG_KG_H = 75.0

ERWARTUNG = {
    # Die Halle laeuft rund um die Uhr und muss 42 K Temperaturhub gegen
    # die Aussenluft halten. Der Verbrauch je Quadratmeter ist deshalb um ein
    # Vielfaches hoeher als im Buero - das ist der Kern dieser Vorlage.
    "heizwaerme_kwh_m2a": (200.0, 900.0),
    # Kaelte dagegen fast nie. Das ist kein Versehen, sondern die Bauart: Eine
    # Schwimmhalle steht auf 30 GradC, und die Aussenluft ist in Mitteleuropa
    # in weniger als hundert Stunden im Jahr waermer. Entfeuchtet wird ueber
    # die Aussenluftklappe, nicht ueber ein Kaelteregister - der Kuehler steht
    # nur fuer die wenigen schwuelen Sommerstunden da, in denen die Aussenluft
    # feuchter ist als die Hallenluft. Gemessen ueber das Testreferenzjahr
    # bleiben davon 0,3 kWh/(m2 a).
    #
    # Das Band stand vorher bei 5 bis 150 und war schlicht falsch hergeleitet:
    # Es uebertrug die Groessenordnung eines Bueros auf eine Anlage, die aus
    # ganz anderen Gruenden kuehlt. Die Obergrenze bleibt, damit ein Kuehler,
    # der gegen die Heizung arbeitet, weiterhin auffaellt.
    "kaelte_kwh_m2a": (0.0, 20.0),
    "sfp_w_m3h": (0.25, 0.95),
    "luftwechsel_1h": (4.0, 6.0),
}

WOCHENTAGE = ("montag", "dienstag", "mittwoch", "donnerstag", "freitag",
              "samstag", "sonntag")


def baue(projekt_id, name=NAME):
    with Bauplatz(projekt_id, name, notiz=BESCHREIBUNG) as b:
        wetter = b.karte("wetter", 40, 20, "Wetterdaten")
        aussenluft = b.karte("aussenluft", 40, 200, "Außenluft")
        wrg = b.karte("wrg", 260, 200, "Wärmerückgewinnung",
                      V_nenn=LUFTMENGE_M3H, dp_WRG_nenn=170.0, dp_Bypass_nenn=45.0,
                      rueckwaermzahl=70.0, rueckfeuchtzahl=0.0)
        # Bis 70 % Umluft: der Rest ist Aussenluft, die die Feuchte forttraegt.
        mischkammer = b.karte("mischkammer", 480, 200, "Mischkammer",
                              max_umluft=70.0)
        erhitzer = b.karte("erhitzer", 700, 200, "Erhitzer",
                           V_nenn=LUFTMENGE_M3H, dp_nenn=170.0, QH_max=160.0)
        kuehler = b.karte("kuehler", 920, 200, "Kühler (Entfeuchtung)",
                          V_nenn=LUFTMENGE_M3H, dp_nenn=200.0, QK_nenn=90.0,
                          T_KW_mittel=6.0, kontaktfaktor=0.6)
        zuluft = b.karte("ventilator", 1140, 200, "Zuluftventilator",
                         rolle="zuluft", V_max=LUFTMENGE_M3H, dp_max=1000.0,
                         dp_konst=1000.0, PE_max=6.4, regelart="F")
        halle = b.karte("einfacher_raum", 1360, 200, "Schwimmhalle",
                        spez_transmission=1.4, sollwert_stat=30.0)
        # Die Gebaeudeheizung. Ohne sie meldet der Raum seine
        # Unterdeckung (QH_stat) und niemand nimmt sie entgegen: Er bleibt
        # trotzdem auf seinem Sollwert, und die Waerme dafuer taucht in
        # keiner Bilanz auf - das Gebaeude heizte sich umsonst. Der
        # Lueftungserhitzer deckt das nicht; er waermt die Zuluft, nicht
        # die Huelle. Auslegung: 1,4 kW/K x 40 K (28 GradC innen) = 56 kW
        gebaeudeheizung = b.karte("statische_heizung", 1360, 620,
                                  "Gebäudeheizung", QH_nenn=60.0)
        abluft = b.karte("ventilator", 1580, 200, "Abluftventilator",
                         rolle="abluft", V_max=LUFTMENGE_M3H, dp_max=800.0,
                         dp_konst=800.0, PE_max=5.1, regelart="F")
        verteiler = b.karte("verteiler", 1800, 200, "Umluft/Fortluft",
                            anteile={"luft_aus_1": 70.0, "luft_aus_2": 30.0})
        fortluft = b.karte("fortluft", 260, 420, "Fortluft")

        # Feuchteregelung ueber den Aussenluftanteil - das ist der Regelkreis,
        # der eine Schwimmhalle ausmacht. Steigt die Hallenfeuchte ueber den
        # Sollwert, faehrt der Regler seine Stellgroesse zurueck, die
        # Umluftklappe schliesst, und mehr trockene Aussenluft kommt herein.
        # Die Richtung stimmt ohne Umkehrglied: p_regler.berechne rechnet
        # y_neu = y_alt - (istwert - sollwert) / Xp, ein zu feuchter Raum senkt
        # die Stellgroesse also von selbst.
        #
        # Sollwert 14,3 g/kg entspricht bei 30 GradC rund 55 % relativer
        # Feuchte - der uebliche Bereich fuer eine Schwimmhalle liegt bei 50
        # bis 60 %. Xp 3,0 g/kg ist breit genug, dass die Klappe nicht
        # zwischen ihren Anschlaegen springt (dieselbe Ueberlegung wie bei der
        # Kaskade, siehe tests/test_testanlage_regelkreise.py).
        feuchteregler = b.karte("p_regler", 480, 20, "Feuchteregelung",
                                xp_1=5.0, xp_2=3.0, sollwert_2=14.3)

        # Temperaturregelung auf 30 GradC Hallentemperatur.
        kaskade = b.karte("kaskade", 700, 20, "Raum-/Zuluft-Kaskade",
                          T_Raum_min=30.0, T_AU_min=15.0, T_Raum_max=32.0,
                          T_AU_max=30.0, T_ZU_min=26.0, T_ZU_max=38.0, xp=5.0,
                          # WRG und Register wärmen, ein Kühler kühlt.
                          waermestufen=2, kaeltestufen=1)

        zeitplan = b.karte(
            "wochenzeitplan", 1140, 620, "Badezeiten",
            **{f"von_{tag}": 6.0 / 24.0 for tag in WOCHENTAGE},
            **{f"bis_{tag}": 22.0 / 24.0 for tag in WOCHENTAGE},
        )
        # Nachts liegt die Abdeckung auf dem Becken: weniger Verdunstung,
        # aber die Halle laeuft weiter (30 GradC halten).
        tagesprofil = b.karte("tageslastprofil", 1360, 620, "Tageslastprofil",
                              lastgang_1=[0.4] * 6 + [1.0] * 16 + [0.4] * 2)
        betrieb = b.karte("anlagenbetrieb", 1580, 620, "Anlagenbetrieb")
        grundlast = b.karte("faktor", 1800, 620, "Nachtluft-Grundlast", faktor=100.0)
        ventilatorstellung = b.karte("maximalwert", 2020, 620, "Ventilatorstellung")
        # 75 kg/h bei vollem Betrieb, nachts entsprechend dem Tagesprofil
        # weniger. Der Lastgang des Tagesprofils laeuft von 0 bis 1 (NICHT von
        # 0 bis 100), der Faktor ist deshalb die Verdunstung selbst.
        verdunstung = b.karte("faktor", 1360, 760, "Verdunstung Becken",
                              faktor=VERDUNSTUNG_KG_H)

        lasten = b.karte("innere_lasten", 1580, 420, "Innere Lasten",
                         personen=60.0, waerme_je_person=60.0,
                         feuchte_je_person=100.0, grundflaeche=FLAECHE_M2)
        beleuchtung = b.karte("beleuchtung", 1800, 420, "Beleuchtung",
                              spez_leistung=15.0, grundflaeche=FLAECHE_M2,
                              nennbeleuchtung=300.0)
        bilanz = b.karte("bilanz", 2240, 200, "Jahresbilanz",
                         preis_strom=280.0, preis_waerme=95.0, preis_kaelte=95.0,
                         preis_wasser=4.2, ht_von=6.0 / 24.0, ht_bis=19.0 / 24.0)
        logger = b.karte("datenlogger", 2240, 20, "Datenlogger",
                         namen=["T Halle", "F Halle", "Sollwert", "T Zuluft",
                                "Wärme WRG"] + [""] * 5,
                         einheiten=["°C", "g/kg", "°C", "°C", "kW"] + [""] * 5)

        # Luftweg. Die Reihenfolge an der Mischkammer ist verbindlich - erst
        # die Aussenluftseite, sonst landet die Umluft am Aussenluft-Eingang.
        b.pfeil(wetter, aussenluft)
        b.pfeil(wetter, halle)
        b.verbinde(aussenluft, "luft_aus", wrg, "zuluft_ein")
        b.verbinde(wrg, "zuluft_aus", mischkammer, "aussenluft_ein")
        b.pfeil(mischkammer, erhitzer)
        b.pfeil(erhitzer, kuehler)
        b.pfeil(kuehler, zuluft)
        b.pfeil(zuluft, halle)
        b.pfeil(halle, abluft)
        b.pfeil(abluft, verteiler)
        b.verbinde(verteiler, "luft_aus_1", mischkammer, "umluft_ein")
        b.verbinde(verteiler, "luft_aus_2", wrg, "abluft_ein")
        b.verbinde(wrg, "abluft_aus", fortluft, "luft_ein")

        # Der Luftweg oben bleibt ausdruecklich: Diese Anlage fuehrt einen Teil
        # der Abluft ueber einen Verteiler in die Mischkammer zurueck, statt
        # geradeaus durch die Rueckgewinnung zu laufen.
        kaskade_verdrahten(b, wetter, halle, zuluft, kaskade, {
            "waermer_1": wrg, "waermer_2": erhitzer, "kaelter_1": kuehler,
        })
        # Bypass gegenlaeufig zur Rueckgewinnung: Fordert die Kaskade keine
        # Waerme mehr, soll die Abluft am Waermetauscher vorbei - sonst heizt
        # er die Zuluft weiter auf, obwohl niemand das will. Das Umkehrglied
        # macht aus "0 % Waermeanforderung" ein "100 % Bypass".
        bypass = b.karte("umkehrglied", 920, 20, "Bypass-Klappe", bezug=100.0)
        b.verbinde(kaskade, "waermer_1", bypass, "ein")
        b.verbinde(bypass, "ausgang", wrg, "stellgroesse_bypass")

        betrieb_verdrahten(b, (zeitplan, tagesprofil), betrieb, tagesprofil,
                           grundlast, ventilatorstellung, (zuluft, abluft))
        # Die Beckenverdunstung ist die grosse Feuchtequelle, aber nicht die
        # einzige: 60 Badegaeste geben 100 g/h ab, zusammen 6 kg/h neben den
        # 75 kg/h aus dem Becken. Beides laeuft ueber die Lastenkarte in den
        # einen Feuchteeingang der Halle.
        b.verbinde(tagesprofil, "lastgang_1", verdunstung, "ein")
        b.verbinde(verdunstung, "ausgang", lasten, "weitere_feuchte")
        b.verbinde(halle, "F_Raum", feuchteregler, "istwert_2")
        b.verbinde(feuchteregler, "ausgang_2", mischkammer, "umluftanteil")
        b.pfeil(betrieb, beleuchtung)
        lasten_verdrahten(b, tagesprofil, beleuchtung, lasten, halle,
                          gebaeudeheizung=gebaeudeheizung)
        auswertung_verdrahten(
            b, (zuluft, abluft, erhitzer, kuehler, beleuchtung, gebaeudeheizung),
            bilanz, logger,
            protokoll=((wrg, "Q_WRG", "wert_5"),),
            pfeile=(halle, kaskade),
        )

    return b.anlage
