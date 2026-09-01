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

NAME = "AX_SIM 2.1"
BESCHREIBUNG = "Zwei Lüftungsgeräte an gemeinsamer WRG, ein Raum (aus der Excel)"


def baue(projekt_id, name="AX_SIM 2.1"):
    anlage = anlagen.anlage_anlegen(
        projekt_id, name, notiz="Nachbau der Excel-Mappe AX_SIM 2.1"
    )

    def karte(typ, x, y, bezeichnung, **parameter):
        karte_id = anlagen.karte_anlegen(anlage, typ, x, y, parameter, bezeichnung)
        return karte_id

    def verbinde(von_karte_id, von_schluessel, nach_karte_id, nach_schluessel):
        anlagen.verbindung_anlegen(
            anlage,
            anlagen.port_id(von_karte_id, von_schluessel),
            anlagen.port_id(nach_karte_id, nach_schluessel),
        )

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
    #
    # Die Mappe stellt ihre Ventile nicht mit je einem Regler. Der Kuehler folgt
    # Anlage!S16 = MAX(100-S61; S72) aus einem Entfeuchtungs- und einem
    # Kuehlregler, und der Erhitzer folgt V16 = MAX(IF(Waescher=100;50;0); V72),
    # oeffnet also mindestens halb, sobald der Luftwaescher laeuft.
    #
    # WICHTIG: Entfeuchtungs-, Kuehl- und Erhitzerregler sind in der Mappe KEINE
    # Regler je Geraet, sondern je EINER fuer beide Straenge (Halle + Umkleide).
    # Anlage!S38 (Kuehler Umkleide) rechnet =MAX(100-S61;S72) - dieselben Zellen
    # wie S16 (Kuehler Halle). Ebenso teilen sich V16 und V38 dieselbe Zelle V72.
    # Nur der Waescherregler bleibt je Geraet eigenstaendig (AB57 fuer Halle,
    # AB68 fuer Umkleide), weil jeder Waescher seine eigene Verriegelung
    # (Anlage!V16 bzw. V38 ueber AB16/AB38) hat.

    regler_vor = karte(
        "p_regler", 440, 400, "Regler Vorerhitzer",
        xp_1=5.0, xp_2=10.0, sollwert_2=19.0,          # Anlage!N52, N54, M59
    )

    # Entfeuchtungsregler (Anlage!S61, Kette T53=S61-((S60-S59)/T54)): S60=AH46,
    # der Istwert ist also die Raumfeuchte; S59 ist ein fester Sollwert. EIN
    # Regler fuer beide Geraete. Sein Ausgang geht umgekehrt in beide
    # Kuehlerstellungen ein (Anlage!S16=MAX(100-S61;S72)) - die Umkehrung steht
    # als eigene Karte davor, nicht als Parameter am Maximalglied: das
    # Maximalglied bleibt so symmetrisch und laesst sich im Editor frei
    # verdrahten, ohne die Portnummern zu kennen, die die automatische
    # Verdrahtung vergibt (siehe core/bausteine/maximalwert.py). Ein
    # gemeinsames Umkehrglied genuegt, weil auch der Regler dahinter gemeinsam
    # ist - ein Signalausgang darf beliebig viele Verbraucher speisen.
    entfeuchtungsregler = karte(
        "p_regler", 780, 20, "Entfeuchtungsregler",
        xp_1=5.0, xp_2=10.0, sollwert_2=9.0,           # Anlage!S59
    )
    entfeuchter_umkehr = karte(
        "umkehrglied", 780, 100, "Umkehrung Entfeuchter",   # Anlage!S16: 100-S61
    )
    # Kuehlregler (Anlage!S72, Kette T64=S72-((S71-S70)/T65)): S70=AH45, der
    # Sollwert ist also die Raumtemperatur, S71 ein fester Istwert - dieselbe
    # Vertauschung wie beim Waescherregler. EIN Regler fuer beide Geraete.
    kuehlregler = karte(
        "p_regler", 780, 180, "Kühlregler",
        xp_1=5.0, xp_2=10.0, istwert_2=22.0,           # Anlage!S71
    )
    kuehlerstellung_1 = karte(
        "maximalwert", 780, 260, "Stellung Kühler Halle",   # Anlage!S16
    )
    kuehlerstellung_2 = karte(
        "maximalwert", 780, 340, "Stellung Kühler Umkleide",   # Anlage!S38
    )

    # Erhitzerregler (Anlage!V72, Kette W64=V72-((V71-V70)/W65)): V71=V39, der
    # Istwert ist also die Austrittstemperatur des ERHITZERS UMKLEIDE (nicht des
    # eigenen Geraets!); V70 ist ein fester Sollwert. EIN Regler fuer beide
    # Geraete - das ist die echte Kopplung ueber die Straenge hinweg: die Halle
    # reagiert in der Mappe auf den Austritt der Umkleide.
    erhitzerregler = karte(
        "p_regler", 960, 20, "Regler Erhitzer",
        xp_1=5.0, xp_2=10.0, sollwert_2=20.0,          # Anlage!V70
    )
    nachwaermen_1 = karte(
        "faktor", 960, 100, "Nachwärmen Halle", faktor=0.5,   # Anlage!V16
    )
    nachwaermen_2 = karte(
        "faktor", 960, 180, "Nachwärmen Umkleide", faktor=0.5,   # Anlage!V38
    )
    erhitzerstellung_1 = karte(
        "maximalwert", 960, 260, "Stellung Erhitzer Halle",
    )
    erhitzerstellung_2 = karte(
        "maximalwert", 960, 340, "Stellung Erhitzer Umkleide",
    )

    # Waescherregler bleiben je Geraet eigenstaendig (Anlage!AB57, AB68).
    waescherregler_1 = karte(
        "hysterese_regler", 1320, 20, "Regler Luftwäscher Halle",
        hysterese=0.1, istwert=5.0,                    # Anlage!AB54, AB56
    )
    waescherregler_2 = karte(
        "hysterese_regler", 1320, 100, "Regler Luftwäscher Umkleide",
        hysterese=0.1, istwert=6.0,                    # Anlage!AB65, AB67
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

        # Entfeuchtungs- und Kuehlregler sind gemeinsame Regler fuer beide
        # Geraete (siehe Kommentar oben). Das Maximalglied ist symmetrisch -
        # welcher der beiden Pfeile zuerst ankommt, ist ohne Belang, siehe
        # core/bausteine/maximalwert.py.
        (entfeuchtungsregler, entfeuchter_umkehr),
        (entfeuchter_umkehr, kuehlerstellung_1),
        (kuehlregler, kuehlerstellung_1),
        (kuehlerstellung_1, kuehler_1),
        (entfeuchter_umkehr, kuehlerstellung_2),
        (kuehlregler, kuehlerstellung_2),
        (kuehlerstellung_2, kuehler_2),

        # Der Erhitzerregler ist ebenfalls gemeinsam, gespeist vom eigenen
        # Austritt des Erhitzers UMKLEIDE (Anlage!V71=V39) - die echte Kopplung
        # der Mappe ueber die Straenge hinweg (siehe Kommentar oben).
        (erhitzer_2, erhitzerregler),

        # Je Geraet: eigener Regler oder Nachwaermen nach dem eigenen Waescher,
        # groesseres gewinnt. Der Pfeil vom Waescherregler zum Waescher selbst
        # fehlt hier bewusst - er wird weiter unten von Hand gesetzt (siehe
        # Kommentar dort).
        (erhitzerregler, erhitzerstellung_1),
        (nachwaermen_1, erhitzerstellung_1),
        (erhitzerstellung_1, erhitzer_1),
        (waescherregler_1, nachwaermen_1),

        (erhitzerregler, erhitzerstellung_2),
        (nachwaermen_2, erhitzerstellung_2),
        (erhitzerstellung_2, erhitzer_2),
        (waescherregler_2, nachwaermen_2),
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

    # Der Raum bietet mehrere Messwerte an (T_Raum, F_Raum, QH_stat) - ein
    # namenloser Sollwert- oder Istwert-Anschluss bleibt nach der Regel aus
    # Task 26 deshalb frei. Diese vier Verbindungen werden darum ausdruecklich
    # gesetzt statt automatisch geraten.
    verbinde(raum, "F_Raum", entfeuchtungsregler, "istwert_2")  # Anlage!S60
    verbinde(raum, "T_Raum", kuehlregler, "sollwert_2")         # Anlage!S70
    verbinde(raum, "F_Raum", waescherregler_1, "sollwert")      # Anlage!AB55
    verbinde(raum, "F_Raum", waescherregler_2, "sollwert")      # Anlage!AB66

    # Der Waescherregler speist den Waescher selbst ebenfalls ausdruecklich statt
    # ueber pfeil_anlegen: ein gewoehnlicher Pfeil haette dabei die automatische
    # Rueckverdrahtung ausgeloest, die zu jeder Stellgroesse den passenden
    # Istwert vom Ziel zurueckholt - und den freien "istwert"-Anschluss des
    # Reglers mit der Waescher-Austrittstemperatur belegt. Genau das war der
    # urspruengliche Fehler (der Regler haengt am eigenen Austritt); der feste
    # Istwert-Parameter aus Schritt 5 wuerde dadurch wieder unwirksam.
    verbinde(waescherregler_1, "ausgang", waescher_1, "stellgroesse")
    verbinde(waescherregler_2, "ausgang", waescher_2, "stellgroesse")

    return anlage
