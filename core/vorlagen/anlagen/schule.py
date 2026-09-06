"""Schule mit Waermerueckgewinnung, Ferien und Monatsprofil.

Ein Klassentrakt von 1500 m2. Der Luftwechsel ist mehr als doppelt so hoch wie
im Buero, weil die Belegungsdichte im Klassenraum um ein Vielfaches groesser
ist. Die Anlage steht in den Ferien still - das ist der Unterschied, den diese
Vorlage gegenueber dem Buero pruefen soll: Ferienkarte und Monatsprofil greifen
in den Betrieb ein, und der Verbrauch muss darauf antworten.

AUSLEGUNG

    Geometrie      1500 m2, 3,0 m lichte Hoehe -> 4500 m3
    Luftmenge      12 000 m3/h -> 2,67 facher Luftwechsel.
                   Bei 25 Schuelern je 60 m2 Klassenraum und 25 m3/(h*Person)
                   sind rund 10 m3/(h*m2) noetig; 12 000 / 1500 = 8 m3/(h*m2)
                   trifft die Groessenordnung.
    Transmission   1500 m2 Huelle mit Fenstern, Dach, Boden -> rund 1,0 kW/K
    Heizlast       Transmission 1,0 x 32 K                  = 32,0 kW
                   Lueftung nach WRG (75 %)
                       12000 x 0,34 x 32 x 0,25             = 32,6 kW
                                                              -------
                                                               64,6 kW
                   -> Erhitzer 80 kW
    Kuehllast      Personen und Geraete rund 30 W/m2         = 45 kW
                   -> Kuehler 60 kW
    Ventilator     12000 m3/h, 850 Pa, Wirkungsgrad 0,65     = 4,36 kW
                   -> SFP 0,36 W/(m3/h)
    Nachtluft      20 % von 12 000 = 2400 m3/h. Autoritaet des Erhitzers
                   3600 x 80 / (1,2 x 1,007 x 2400) = 0,99 K/%,
                   bei Xp 5 K also Kreisverstaerkung 0,20 - stabil.
"""

from core.vorlagen.bauhilfe import Bauplatz

NAME = "Schule mit WRG und Ferien"
BESCHREIBUNG = (
    "1500 m² Klassentrakt, hoher Luftwechsel wegen Belegung, "
    "Plattenwärmetauscher, Betrieb Mo–Fr 7–16 Uhr, Anlage steht in den Ferien"
)

FLAECHE_M2 = 1500.0
LUFTMENGE_M3H = 12000.0
#: Lichte Raumhöhe - der Prüfstand rechnet daraus den Luftwechsel.
HOEHE_M = 3.0

ERWARTUNG = {
    # Wie beim Buero ueber die Gradtagszahl abgeschaetzt, aber mit deutlich
    # weniger Betriebsstunden (Ferien!) und hoeherem Luftwechsel.
    "heizwaerme_kwh_m2a": (10.0, 70.0),
    "kaelte_kwh_m2a": (0.0, 30.0),
    "sfp_w_m3h": (0.25, 0.95),
    "luftwechsel_1h": (2.2, 3.2),
}

WOCHENTAGE = ("montag", "dienstag", "mittwoch", "donnerstag", "freitag")

# Schulferien Sachsen, als Beispiel - Winter, Ostern, Sommer, Herbst, Weihnachten.
FERIEN = [
    {"name": "Winterferien", "von": "12.02.", "bis": "26.02."},
    {"name": "Osterferien", "von": "15.04.", "bis": "23.04."},
    {"name": "Sommerferien", "von": "15.07.", "bis": "23.08."},
    {"name": "Herbstferien", "von": "07.10.", "bis": "15.10."},
    {"name": "Weihnachtsferien", "von": "23.12.", "bis": "02.01."},
]


def baue(projekt_id, name=NAME):
    with Bauplatz(projekt_id, name, notiz=BESCHREIBUNG) as b:
        wetter = b.karte("wetter", 40, 20, "Wetterdaten")
        aussenluft = b.karte("aussenluft", 40, 200, "Außenluft")
        wrg = b.karte("wrg", 260, 200, "Plattenwärmetauscher",
                      V_nenn=LUFTMENGE_M3H, dp_WRG_nenn=160.0, dp_Bypass_nenn=40.0,
                      rueckwaermzahl=75.0, rueckfeuchtzahl=0.0)
        erhitzer = b.karte("erhitzer", 480, 200, "Erhitzer",
                           V_nenn=LUFTMENGE_M3H, dp_nenn=150.0, QH_max=80.0)
        kuehler = b.karte("kuehler", 700, 200, "Kühler",
                          V_nenn=LUFTMENGE_M3H, dp_nenn=180.0, QK_nenn=60.0,
                          T_KW_mittel=6.0, kontaktfaktor=0.5)
        zuluft = b.karte("ventilator", 920, 200, "Zuluftventilator",
                         rolle="zuluft", V_max=LUFTMENGE_M3H, dp_max=850.0,
                         dp_konst=850.0, PE_max=4.4, regelart="F")
        raum = b.karte("einfacher_raum", 1140, 200, "Klassenräume",
                       spez_transmission=1.0, sollwert_stat=16.0)
        abluft = b.karte("ventilator", 1360, 200, "Abluftventilator",
                         rolle="abluft", V_max=LUFTMENGE_M3H, dp_max=650.0,
                         dp_konst=650.0, PE_max=3.3, regelart="F")
        fortluft = b.karte("fortluft", 260, 380, "Fortluft")

        kaskade = b.karte("kaskade", 480, 20, "Raum-/Zuluft-Kaskade",
                          T_Raum_min=20.0, T_AU_min=15.0, T_Raum_max=26.0,
                          T_AU_max=30.0, T_ZU_min=16.0, T_ZU_max=28.0, xp=5.0,
                          # WRG und Register wärmen, ein Kühler kühlt.
                          waermestufen=2, kaeltestufen=1)

        zeitplan = b.karte(
            "wochenzeitplan", 920, 560, "Schulzeiten",
            **{f"von_{tag}": 7.0 / 24.0 for tag in WOCHENTAGE},
            **{f"bis_{tag}": 16.0 / 24.0 for tag in WOCHENTAGE},
            von_samstag=0.0, bis_samstag=0.0, von_sonntag=0.0, bis_sonntag=0.0,
        )
        ferien = b.karte("ferien", 920, 700, "Schulferien", zeitraeume=FERIEN)
        # Der August liegt ganz in den Sommerferien - das Monatsprofil legt
        # die Anlage dort zusaetzlich still. Ferienkarte und Monatsprofil
        # wirken hintereinander wie zwei Schalter (core/bausteine/
        # anlagenbetrieb.py), die Ueberschneidung schadet nicht.
        monate = b.karte("monatsprofil", 1140, 700, "Sommerferien August",
                         monate=[True] * 7 + [False] + [True] * 4)
        tagesprofil = b.karte("tageslastprofil", 1140, 560, "Tageslastprofil",
                              lastgang_1=[0.2] * 6 + [1.0] * 11 + [0.3] * 7)
        betrieb = b.karte("anlagenbetrieb", 1360, 560, "Anlagenbetrieb")
        grundlast = b.karte("faktor", 1580, 560, "Nachtluft-Grundlast", faktor=100.0)
        ventilatorstellung = b.karte("maximalwert", 1800, 560, "Ventilatorstellung")

        beleuchtung = b.karte("beleuchtung", 1580, 380, "Beleuchtung",
                              spez_leistung=10.0, grundflaeche=FLAECHE_M2,
                              nennbeleuchtung=500.0)
        bilanz = b.karte("bilanz", 2020, 200, "Jahresbilanz",
                         preis_strom=280.0, preis_waerme=95.0, preis_kaelte=95.0,
                         preis_wasser=4.2, ht_von=6.0 / 24.0, ht_bis=19.0 / 24.0)
        logger = b.karte("datenlogger", 2020, 20, "Datenlogger",
                         namen=["T Raum", "F Raum", "Sollwert Raum", "T Zuluft",
                                "Wärme WRG"] + [""] * 5,
                         einheiten=["°C", "g/kg", "°C", "°C", "kW"] + [""] * 5)

        b.pfeil(wetter, aussenluft)
        b.pfeil(wetter, raum)
        b.verbinde(aussenluft, "luft_aus", wrg, "zuluft_ein")
        b.pfeil(wrg, erhitzer)
        b.pfeil(erhitzer, kuehler)
        b.pfeil(kuehler, zuluft)
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

        b.pfeil(zeitplan, betrieb)
        b.pfeil(ferien, betrieb)
        b.pfeil(monate, betrieb)
        b.pfeil(tagesprofil, betrieb)
        b.verbinde(tagesprofil, "lastgang_1", grundlast, "ein")
        b.verbinde(betrieb, "stellgrad", ventilatorstellung, "ein_1")
        b.verbinde(grundlast, "ausgang", ventilatorstellung, "ein_2")
        b.verbinde(ventilatorstellung, "ausgang", zuluft, "stellgroesse")
        b.verbinde(ventilatorstellung, "ausgang", abluft, "stellgroesse")
        b.pfeil(betrieb, beleuchtung)
        b.verbinde(beleuchtung, "Q_Bel", raum, "waermelast")

        for karte in (zuluft, abluft, erhitzer, kuehler, beleuchtung):
            b.pfeil(karte, bilanz)
        b.pfeil(raum, logger)
        b.pfeil(kaskade, logger)
        b.verbinde(wrg, "Q_WRG", logger, "wert_5")

    return b.anlage
