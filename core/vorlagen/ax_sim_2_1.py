"""Die Anlage aus RLTSimulation_Vorlage_AX_SIM_2.1 als Vorlage.

Aufbau (Anlage!I2:AC43):

    Wetter -> Aussenluft -> Waermerueckgewinnung -> Vorerhitzer -> Verteiler
        Gang 1 "Halle":  Kuehler -> Erhitzer -> Zuluftventilator -> Luftwaescher
        Gang 2 "Umkl.":  Kuehler -> Erhitzer -> Zuluftventilator -> Luftwaescher
    beide Gaenge -> Raum -> Sammler -> Abluftventilator -> Waermerueckgewinnung
                                                        -> Fortluft

Die Waermerueckgewinnung regelt ihre eigene Zulufttemperatur (Anlage!J59: 18 °C)
ueber einen P-Regler; der Bypass ist die Umkehrung seiner Stellgroesse.

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
    wetter = karte("wetter", 40, 320, "Wetterdaten")
    aussenluft = karte("aussenluft", 40, 460, "Außenluft")

    # -- Gemeinsame Vorbehandlung, Anlage!I9:N21 ----------------------
    wrg = karte(
        "wrg", 250, 460, "Wärmerückgewinnung",
        V_nenn=12200.0,        # Anlage!J9
        dp_WRG_nenn=170.0,     # Anlage!J10
        dp_Bypass_nenn=50.0,   # Anlage!J11
        rueckwaermzahl=81.0,   # Anlage!J12
        rueckfeuchtzahl=0.0,   # Anlage!J13
    )
    vorerhitzer = karte(
        "erhitzer", 460, 460, "Vorerhitzer",
        V_nenn=12200.0, dp_nenn=30.0, QH_max=27.0,   # Anlage!M9, M10, M11
    )
    verteiler = karte("verteiler", 670, 460, "Verteiler")

    # -- Gang 1 "Halle", Anlage!R9:AC21 -------------------------------
    kuehler_1 = karte(
        "kuehler", 880, 180, "Kühler Halle",
        V_nenn=8200.0, dp_nenn=240.0, QK_nenn=63.0, T_KW_mittel=6.0,
    )
    erhitzer_1 = karte(
        "erhitzer", 1090, 180, "Erhitzer Halle",
        V_nenn=8200.0, dp_nenn=147.0, QH_max=101.0,
    )
    zuluft_1 = karte(
        "ventilator", 1300, 180, "Zuluftventilator Halle",
        rolle="zuluft", V_max=8200.0, dp_max=1400.0, dp_konst=1400.0,
        PE_max=4.9, regelart="F", stellgroesse=100.0,   # Anlage!Y16
    )
    waescher_1 = karte(
        "luftwaescher", 1510, 180, "Luftwäscher Halle",
        V_nenn=8200.0, dp_nenn=50.0, absalzverlust=10.0, pumpenart="H",
    )

    # -- Gang 2 "Umkleide", Anlage!R31:AC43 ---------------------------
    kuehler_2 = karte(
        "kuehler", 880, 740, "Kühler Umkleide",
        V_nenn=4000.0, dp_nenn=150.0, QK_nenn=250.0, T_KW_mittel=9.0,
    )
    erhitzer_2 = karte(
        "erhitzer", 1090, 740, "Erhitzer Umkleide",
        V_nenn=4000.0, dp_nenn=62.0, QH_max=47.0,
    )
    zuluft_2 = karte(
        "ventilator", 1300, 740, "Zuluftventilator Umkleide",
        rolle="zuluft", V_max=4000.0, dp_max=1190.0, dp_konst=4000.0,
        PE_max=1.7, regelart="F", stellgroesse=100.0,   # Anlage!Y38
    )
    waescher_2 = karte(
        "luftwaescher", 1510, 740, "Luftwäscher Umkleide",
        V_nenn=4000.0, dp_nenn=50.0, absalzverlust=10.0, pumpenart="H",
    )

    # -- Raum und Abluft, Anlage!AG31:AI50 und L31:N43 ----------------
    raum = karte(
        "einfacher_raum", 1720, 460, "Einfacher Raum",
        spez_transmission=0.5,   # Anlage!AH31
        sollwert_stat=15.0,      # Anlage!AH44
    )
    sammler = karte("sammler", 1720, 600, "Sammler Abluft")
    abluft = karte(
        "ventilator", 1720, 740, "Abluftventilator",
        rolle="abluft", V_max=10000.0, dp_max=750.0, dp_konst=600.0,
        PE_max=3.3, regelart="F", stellgroesse=90.0,    # Anlage!M38
    )
    fortluft = karte("fortluft", 250, 600, "Fortluft")

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
        "p_regler", 460, 320, "Regler Vorerhitzer",
        xp_1=5.0, xp_2=10.0, sollwert_2=19.0,          # Anlage!N52, N54, M59
    )

    # WRG-Regler (Anlage!K53, Kette K53=J61-((J60-J59)/K54)): J60=J38, der
    # Istwert ist also die Zulufttemperatur der WRG SELBST - sie regelt ihre
    # eigene Austrittstemperatur auf 18 °C. Der Ausgang J61 setzt die
    # Stellgroesse J20; der Bypass ist dessen Umkehrung (J21 = 100 - J20) und
    # steht deshalb, wie beim Entfeuchter, als eigenes Umkehrglied davor.
    #
    # J38 haengt selbst von J20 ab und J20 vom Regler, dessen Istwert J38 ist -
    # ein Zirkelbezug, den die Mappe ueber Application.Iteration aufloest. Hier
    # loest ihn ZUSTAND_UEBER_ITERATION des P-Reglers (siehe
    # core/bausteine/p_regler.py): der Ausgang baut sich ueber die Durchgaenge
    # des Vorwaertslaufs auf, statt in einem Durchgang zu springen.
    regler_wrg = karte(
        "p_regler", 250, 320, "Regler Wärmerückgewinnung",
        xp_1=5.0, xp_2=10.0, sollwert_2=18.0,          # Anlage!K52, K54, J59
    )
    wrg_umkehr = karte(
        "umkehrglied", 250, 180, "Umkehrung WRG-Bypass",   # Anlage!J21: 100-J20
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
        "p_regler", 670, 320, "Entfeuchtungsregler",
        xp_1=5.0, xp_2=10.0, sollwert_2=9.0,           # Anlage!S59
    )
    entfeuchter_umkehr = karte(
        "umkehrglied", 880, 320, "Umkehrung Entfeuchter",   # Anlage!S16: 100-S61
    )
    # Kuehlregler (Anlage!S72, Kette T64=S72-((S71-S70)/T65)): S70=AH45, der
    # Sollwert ist also die Raumtemperatur, S71 ein fester Istwert - dieselbe
    # Vertauschung wie beim Waescherregler. EIN Regler fuer beide Geraete.
    kuehlregler = karte(
        "p_regler", 880, 600, "Kühlregler",
        xp_1=5.0, xp_2=10.0, istwert_2=22.0,           # Anlage!S71
    )
    kuehlerstellung_1 = karte(
        "maximalwert", 880, 40, "Stellung Kühler Halle",   # Anlage!S16
    )
    kuehlerstellung_2 = karte(
        "maximalwert", 880, 880, "Stellung Kühler Umkleide",   # Anlage!S38
    )

    # Erhitzerregler (Anlage!V72, Kette W64=V72-((V71-V70)/W65)): V71=V39, der
    # Istwert ist also die Austrittstemperatur des ERHITZERS UMKLEIDE (nicht des
    # eigenen Geraets!); V70 ist ein fester Sollwert. EIN Regler fuer beide
    # Geraete - das ist die echte Kopplung ueber die Straenge hinweg: die Halle
    # reagiert in der Mappe auf den Austritt der Umkleide.
    erhitzerregler = karte(
        "p_regler", 1090, 460, "Regler Erhitzer",
        xp_1=5.0, xp_2=10.0, sollwert_2=20.0,          # Anlage!V70
    )
    nachwaermen_1 = karte(
        "faktor", 1300, 40, "Nachwärmen Halle", faktor=0.5,   # Anlage!V16
    )
    nachwaermen_2 = karte(
        "faktor", 1300, 880, "Nachwärmen Umkleide", faktor=0.5,   # Anlage!V38
    )
    erhitzerstellung_1 = karte(
        "maximalwert", 1090, 40, "Stellung Erhitzer Halle",
    )
    erhitzerstellung_2 = karte(
        "maximalwert", 1090, 880, "Stellung Erhitzer Umkleide",
    )

    # Waescherregler bleiben je Geraet eigenstaendig (Anlage!AB57, AB68).
    waescherregler_1 = karte(
        "hysterese_regler", 1510, 40, "Regler Luftwäscher Halle",
        hysterese=0.1, istwert=5.0,                    # Anlage!AB54, AB56
    )
    waescherregler_2 = karte(
        "hysterese_regler", 1510, 880, "Regler Luftwäscher Umkleide",
        hysterese=0.1, istwert=6.0,                    # Anlage!AB65, AB67
    )

    # -- Zeit und Betrieb, Anlage!AK4:AV32 ----------------------------
    zeitplan = karte("wochenzeitplan", 40, 1020, "Wochenzeitplan")
    ferien = karte(
        "ferien", 250, 1020, "Ferien",
        zeitraeume=[
            {"name": "Weihnachten", "von": "22.12.", "bis": "06.01."},
            {"name": "Ostern", "von": "22.03.", "bis": "06.04."},
            {"name": "Pfingsten", "von": "17.05.", "bis": "01.06."},
            {"name": "Sommer", "von": "24.07.", "bis": "07.09."},
            {"name": "Herbst", "von": "25.10.", "bis": "02.11."},
        ],
    )
    tagesprofil = karte(
        "tageslastprofil", 460, 1020, "Tageslastprofil",
        lastgang_1=[0.4] * 7 + [1.0] * 13 + [0.4] * 4,   # Anlage!AT7:AT30
    )
    betrieb = karte("anlagenbetrieb", 670, 1020, "Anlagenbetrieb")

    # -- Bilanz und Protokoll, Anlage!AO30:AR42 und B26:D46 -----------
    bilanz = karte(
        "bilanz", 1930, 740, "Energiepreise und Bilanz",
        preis_strom_ht=150.0, preis_strom_nt=150.0, preis_strom_leistung=0.0,
        preis_waerme=50.0, preis_kaelte=50.0, preis_wasser=4.0,
        ht_von=7.0 / 24.0, ht_bis=20.0 / 24.0,
    )
    # Die WRG gibt seit dem T_ZU-Anschluss zwei Messwerte ab; der Pfeil zum
    # Datenlogger verdrahtet beide, T_ZU landet in der zweiten Spalte. Sie ist
    # hier ausdruecklich benannt, damit die Spalten des Protokolls weiter zu
    # dem passen, was tatsaechlich an ihnen haengt (Anlage!I38 heisst "T_ZU").
    logger = karte(
        "datenlogger", 1930, 460, "Datenlogger",
        namen=["WRG", "T_ZU WRG", "T Raum", "F Raum"] + [""] * 6,
        einheiten=["kW", "°C", "°C", "g/kg"] + [""] * 6,
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
    # Auch die WRG bietet inzwischen mehrere Messwerte an (Q_WRG und T_ZU) -
    # derselbe Fall wie beim Raum, also wieder von Hand. Und in der
    # Gegenrichtung braucht der Regler beide Stellsignale an der richtigen
    # Stelle: ein gewoehnlicher Pfeil legte den ungenutzten schnellen Ausgang
    # (Anlage!J57) auf den Bypass, weil beide Anschluesse dieselbe Rolle tragen
    # und dann die Portreihenfolge entscheidet.
    verbinde(wrg, "T_ZU", regler_wrg, "istwert_2")             # Anlage!J60 = J38
    verbinde(regler_wrg, "ausgang_2", wrg, "stellgroesse")     # Anlage!J20 = J61
    verbinde(regler_wrg, "ausgang_2", wrg_umkehr, "ein")
    verbinde(wrg_umkehr, "ausgang", wrg, "stellgroesse_bypass")  # Anlage!J21

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
