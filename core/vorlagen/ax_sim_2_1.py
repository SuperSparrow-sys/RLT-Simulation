"""Die Anlage aus RLTSimulation_Vorlage_AX_SIM_2.1 als Vorlage.

Aufbau (Anlage!I2:AC43):

    Wetter -> Aussenluft -> Waermerueckgewinnung -> Vorerhitzer -> Verteiler
        Gang 1 "Halle":  Kuehler -> Erhitzer -> Zuluftventilator -> Luftwaescher
        Gang 2 "Umkl.":  Kuehler -> Erhitzer -> Zuluftventilator -> Luftwaescher
    beide Gaenge -> Raum -> Sammler -> Abluftventilator -> Waermerueckgewinnung
                                                        -> Fortluft

Alle Nennwerte sind aus dem Blatt 'Anlage' uebernommen; die Zellbezuege stehen
jeweils als Kommentar daneben.
"""

from core import anlagen

BESCHREIBUNG = "Zwei Lüftungsgeräte an gemeinsamer WRG, ein Raum (aus der Excel)"


def baue(projekt_id, name="AX_SIM 2.1"):
    anlage = anlagen.anlage_anlegen(
        projekt_id, name, notiz="Nachbau der Excel-Mappe AX_SIM 2.1"
    )

    def karte(typ, x, y, bezeichnung, **parameter):
        karte_id = anlagen.karte_anlegen(anlage, typ, x, y, parameter, bezeichnung)
        return karte_id

    # -- Quellen ------------------------------------------------------
    wetter = karte("wetter", 40, 40, "Wetterdaten")
    aussenluft = karte("aussenluft", 40, 200, "Außenluft")

    # -- Gemeinsame Vorbehandlung, Anlage!I9:N21 ----------------------
    wrg = karte(
        "wrg", 240, 200, "Wärmerückgewinnung",
        V_nenn=12200.0,        # Anlage!J9
        dp_WRG_nenn=170.0,     # Anlage!J10
        dp_Bypass_nenn=50.0,   # Anlage!J11
        rueckwaermzahl=81.0,   # Anlage!J12
        rueckfeuchtzahl=0.0,   # Anlage!J13
    )
    vorerhitzer = karte(
        "erhitzer", 440, 200, "Vorerhitzer",
        V_nenn=12200.0, dp_nenn=30.0, QH_max=27.0,   # Anlage!M9, M10, M11
    )
    verteiler = karte("verteiler", 620, 200, "Verteiler")

    # -- Gang 1 "Halle", Anlage!R9:AC21 -------------------------------
    kuehler_1 = karte(
        "kuehler", 780, 120, "Kühler Halle",
        V_nenn=8200.0, dp_nenn=240.0, QK_nenn=63.0, T_KW_mittel=6.0,
    )
    erhitzer_1 = karte(
        "erhitzer", 960, 120, "Erhitzer Halle",
        V_nenn=8200.0, dp_nenn=147.0, QH_max=101.0,
    )
    zuluft_1 = karte(
        "ventilator", 1140, 120, "Zuluftventilator Halle",
        rolle="zuluft", V_max=8200.0, dp_max=1400.0, dp_konst=1400.0,
        PE_max=4.9, regelart="F", stellgroesse=100.0,   # Anlage!Y16
    )
    waescher_1 = karte(
        "luftwaescher", 1320, 120, "Luftwäscher Halle",
        V_nenn=8200.0, dp_nenn=50.0, absalzverlust=10.0, pumpenart="H",
    )

    # -- Gang 2 "Umkleide", Anlage!R31:AC43 ---------------------------
    kuehler_2 = karte(
        "kuehler", 780, 320, "Kühler Umkleide",
        V_nenn=4000.0, dp_nenn=150.0, QK_nenn=250.0, T_KW_mittel=9.0,
    )
    erhitzer_2 = karte(
        "erhitzer", 960, 320, "Erhitzer Umkleide",
        V_nenn=4000.0, dp_nenn=62.0, QH_max=47.0,
    )
    zuluft_2 = karte(
        "ventilator", 1140, 320, "Zuluftventilator Umkleide",
        rolle="zuluft", V_max=4000.0, dp_max=1190.0, dp_konst=4000.0,
        PE_max=1.7, regelart="F", stellgroesse=100.0,   # Anlage!Y38
    )
    waescher_2 = karte(
        "luftwaescher", 1320, 320, "Luftwäscher Umkleide",
        V_nenn=4000.0, dp_nenn=50.0, absalzverlust=10.0, pumpenart="H",
    )

    # -- Raum und Abluft, Anlage!AG31:AI50 und L31:N43 ----------------
    raum = karte(
        "einfacher_raum", 1520, 220, "Einfacher Raum",
        spez_transmission=0.5,   # Anlage!AH31
        sollwert_stat=15.0,      # Anlage!AH44
    )
    sammler = karte("sammler", 1520, 420, "Sammler Abluft")
    abluft = karte(
        "ventilator", 1320, 480, "Abluftventilator",
        rolle="abluft", V_max=10000.0, dp_max=750.0, dp_konst=600.0,
        PE_max=3.3, regelart="F", stellgroesse=90.0,    # Anlage!M38
    )
    fortluft = karte("fortluft", 40, 420, "Fortluft")

    # -- Regelung, Anlage!I52:W72 -------------------------------------
    regler_vor = karte(
        "p_regler", 440, 400, "Regler Vorerhitzer",
        xp_1=10.0, xp_2=5.0, sollwert_2=19.0,   # Anlage!N52, N54, M59
    )
    regler_erhitzer_1 = karte(
        "p_regler", 960, 20, "Regler Erhitzer Halle",
        xp_1=10.0, xp_2=5.0, sollwert_2=20.0,   # Anlage!W52, W54, V59
    )
    regler_kuehler_1 = karte(
        "p_regler", 780, 20, "Regler Kühler Halle",
        xp_1=10.0, xp_2=5.0, sollwert_2=15.0,   # Anlage!T52, T54, S70
    )
    regler_erhitzer_2 = karte(
        "p_regler", 960, 440, "Regler Erhitzer Umkleide",
        xp_1=10.0, xp_2=5.0, sollwert_2=20.0,
    )
    regler_kuehler_2 = karte(
        "p_regler", 780, 440, "Regler Kühler Umkleide",
        xp_1=10.0, xp_2=5.0, sollwert_2=15.0,
    )
    regler_waescher_1 = karte(
        "hysterese_regler", 1320, 20, "Regler Luftwäscher Halle",
        hysterese=0.1, sollwert=2.885138971629036,   # Anlage!AB54, AB55
    )
    regler_waescher_2 = karte(
        "hysterese_regler", 1320, 440, "Regler Luftwäscher Umkleide",
        hysterese=0.1, sollwert=2.885138971629036,
    )

    # -- Zeit und Betrieb, Anlage!AK4:AV32 ----------------------------
    zeitplan = karte("wochenzeitplan", 40, 560, "Wochenzeitplan")
    ferien = karte(
        "ferien", 240, 560, "Ferien",
        zeitraeume=[
            {"name": "Weihnachten", "von": "22.12.", "bis": "06.01."},
            {"name": "Ostern", "von": "22.03.", "bis": "06.04."},
            {"name": "Pfingsten", "von": "17.05.", "bis": "01.06."},
            {"name": "Sommer", "von": "24.07.", "bis": "07.09."},
            {"name": "Herbst", "von": "25.10.", "bis": "02.11."},
        ],
    )
    tagesprofil = karte(
        "tageslastprofil", 440, 560, "Tageslastprofil",
        lastgang_1=[0.4] * 7 + [1.0] * 13 + [0.4] * 4,   # Anlage!AT7:AT30
    )
    betrieb = karte("anlagenbetrieb", 640, 560, "Anlagenbetrieb")

    # -- Bilanz und Protokoll, Anlage!AO30:AR42 und B26:D46 -----------
    bilanz = karte(
        "bilanz", 1720, 560, "Energiepreise und Bilanz",
        preis_strom_ht=150.0, preis_strom_nt=150.0, preis_strom_leistung=0.0,
        preis_waerme=50.0, preis_kaelte=50.0, preis_wasser=4.0,
        ht_von=7.0 / 24.0, ht_bis=20.0 / 24.0,
    )
    logger = karte(
        "datenlogger", 1720, 220, "Datenlogger",
        namen=["WRG", "T Raum", "F Raum"] + [""] * 7,
        einheiten=["kW", "°C", "g/kg"] + [""] * 7,
    )

    # -- Verdrahtung --------------------------------------------------
    for von, nach in [
        (wetter, aussenluft),
        (aussenluft, wrg),
        (wrg, vorerhitzer),
        (vorerhitzer, verteiler),
        (verteiler, kuehler_1),
        (kuehler_1, erhitzer_1),
        (erhitzer_1, zuluft_1),
        (zuluft_1, waescher_1),
        (waescher_1, raum),
        (verteiler, kuehler_2),
        (kuehler_2, erhitzer_2),
        (erhitzer_2, zuluft_2),
        (zuluft_2, waescher_2),
        (waescher_2, raum),
        (raum, sammler),
        (sammler, abluft),
        (abluft, wrg),
        (wrg, fortluft),
        (wetter, raum),
        (regler_vor, vorerhitzer),
        (regler_kuehler_1, kuehler_1),
        (regler_erhitzer_1, erhitzer_1),
        (regler_kuehler_2, kuehler_2),
        (regler_erhitzer_2, erhitzer_2),
        (regler_waescher_1, waescher_1),
        (regler_waescher_2, waescher_2),
        (zeitplan, betrieb),
        (ferien, betrieb),
        (tagesprofil, betrieb),
        (zuluft_1, bilanz),
        (zuluft_2, bilanz),
        (abluft, bilanz),
        (waescher_1, bilanz),
        (waescher_2, bilanz),
        (vorerhitzer, bilanz),
        (erhitzer_1, bilanz),
        (erhitzer_2, bilanz),
        (kuehler_1, bilanz),
        (kuehler_2, bilanz),
        (wrg, logger),
        (raum, logger),
    ]:
        anlagen.pfeil_anlegen(anlage, von, nach)

    return anlage
