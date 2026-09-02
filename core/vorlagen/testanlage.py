"""Testanlage Technikhalle - gebaut zum Pruefen, nicht aus der Excel uebernommen.

Task 20 weist nach, dass der Nachbau der Excel-Mappe AX_SIM 2.1 deren Zahlen
reproduziert. Das sagt nichts darueber, ob ein Baustein, den AX_SIM 2.1 gar nicht
benutzt, physikalisch vernuenftig rechnet. Diese Vorlage setzt deshalb bewusst
eine ANDERE Bauart, andere Bauteile und eine andere Regelung ein, damit die
zweite grosse Vorlage gerade das abdeckt, was die erste auslaesst:

    AX_SIM 2.1                              Testanlage Technikhalle
    -----------------------------------     -----------------------------------
    Waermerueckgewinnung (Platten-WT)        Mischkammer mit Umluftbeimischung
    Luftwaescher (adiabate Befeuchtung)      Dampfbefeuchter (Elektrodampf)
    einfacher_raum (ein Verlustkoeffizient)  raum (Bauphysik + Wandspeicher)
    p_regler + Umkehr-/Maximalglied           kaskade (Raum-/Zuluft-Kaskade)
    hysterese_regler (Zweipunkt)             sequenzregler (stetig, Frostschutz)
                                              statische_heizung (Frostschutz)
                                              enthalpierechner, monatsprofil,
                                              beleuchtung, heizungspumpen,
                                              warmwasser, zirkulation

Aufbau:

    Wetter -> Aussenluft -----\\
                                Mischkammer -> Erhitzer -> Kuehler
                                            -> Dampfbefeuchter -> Zuluftventilator
                                            -> Raum
    Raum -> Abluftventilator -> Verteiler -+-> Fortluft
                                           +-> Mischkammer (Umluft)

    Kaskade (T_AU, T_Raum, T_ZU nach dem Zuluftventilator) stellt ueber je einen
        einzelnen Sequenzausgang Erhitzer UND Kuehler (stetig, kein Zweipunkt).
    Sequenzregler (Frostschutz, misst Raumtemperatur) speist ueber die statische
        Heizung eine von der Lueftung unabhaengige Grundheizung des Raums - siehe
        "Zur Konvergenz" unten, warum das die Aufgabe der Aussentemperatur
        uebernimmt, die urspruenglich einen Economizer stellen sollte.
    P-Regler (Feuchte, misst Raumfeuchte) stellt den Dampfbefeuchter - STETIG,
        nicht als Zweipunktregler.
    Der Umluftanteil der Mischkammer folgt DIREKT dem Anlagenbetrieb
        (Auslastung 0-100 %) statt einem eigenen Regler - ebenfalls ein Ergebnis
        von "Zur Konvergenz" unten.
    Beide Ventilatoren fahren ausserhalb der Betriebszeit auf eine reduzierte
        Nachtluftmenge zurueck statt ganz abzuschalten (Maximalglied aus
        Anlagenbetrieb.stellgrad und einer festen, nie verschwindenden
        Grundlast aus dem Tageslastprofil - siehe "Zur Konvergenz" unten,
        Fund 2). Beleuchtung, Heizungspumpen, Zirkulation und der
        Umluftanteil folgen direkt dem Anlagenbetrieb (Wochenzeitplan +
        Ferien + Monatsprofil [Betriebsferien im August] + Tageslastprofil).
    Beleuchtung speist ihre Waerme EXPLIZIT in die Raumbilanz (raum.waermelast);
        der interne Beleuchtungsparameter des Raums bleibt deshalb auf 0, sonst
        zaehlte die Beleuchtungswaerme doppelt.
    Enthalpierechner wandelt die geregelte Groesse (Raumfeuchte in g/kg) in eine
        anschauliche relative Feuchte fuer den Datenlogger um - die Regelung
        selbst bleibt auf der absoluten Feuchte, weil das die Groesse ist, die
        auch die Bilanz fuehrt (genau wie beim Entfeuchtungsregler in AX_SIM 2.1).

Zur Konvergenz - zwei Funde, keine Vermutungen:

    Der Solver iteriert je Stunde bis zu 100 Mal. AX_SIM 2.1 konvergiert dabei in
    fast keiner Stunde: ihre Luftwaescher haengen an Zweipunktreglern, die
    zwischen 0 und 100 % kippen und dabei ihre EIGENE Messgroesse (Raumfeuchte)
    innerhalb derselben Stunde so stark verschieben, dass ein echter Grenzzyklus
    entsteht (siehe werkzeuge/abgleich.py, rechne_referenzjahr).

    Diese Vorlage verzichtet deshalb ganz auf hysterese_regler (der Kartentyp
    ist ueber AX_SIM 2.1 trotzdem abgedeckt) und regelt ausschliesslich mit
    stetigen Reglern (p_regler, kaskade, sequenzregler). Das allein reichte
    NICHT: zwei eigene Entwurfsfehler erzeugten dieselbe Art Nichtkonvergenz,
    aus einer anderen Ursache als beim Zweipunktregler - beide wurden mit dem
    Solver selbst aufgespuert (siehe Bericht) und sind hier absichtlich als
    Erkenntnis stehen geblieben, nicht nur als Zahl im Ergebnis:

    1. p_regler/kaskade/sequenzregler tragen ihren Fehler 'e' als Speicher
       ueber die Iterationen fort (ZUSTAND_UEBER_ITERATION) und aendern ihn pro
       Durchgang um einen FESTEN Betrag, solange der Istwert ausserhalb des
       Sollbands liegt. Reagiert der Istwert NICHT auf die eigene Stellgroesse
       (kein Regelkreis, sondern eine offene Kette), bleibt dieser Betrag
       konstant, und 'e' braucht bis zu Hunderte Durchgaenge, um seine Grenze
       (-300/+200 bei kaskade/sequenzregler) zu erreichen - weit mehr als die
       100 erlaubten. Ein ursprünglich geplanter Economizer-Sequenzregler auf
       die AUSSENTEMPERATUR (eine reine Wettergroesse, von keiner Stellgroesse
       dieser Anlage beeinflusst) tat genau das - deshalb hier ersetzt: der
       Sequenzregler regelt jetzt die statische Heizung ueber die
       Raumtemperatur - eine Groesse, die auf ihre eigene Stellgroesse (QH_stat
       geht direkt in raum.berechne() ein) reagiert, unabhaengig vom
       Luftvolumenstrom. Der Umluftanteil der Mischkammer folgt seitdem
       schlicht dem Anlagenbetrieb statt einem eigenen Regler.

    2. Sogar ein GESCHLOSSENER Regelkreis bricht auf, wenn die Strecke
       zeitweise abgeschaltet ist: raum.berechne() setzt bei Volumenstrom null
       die Feuchtebilanz auf F_Raum = F_AU - unabhaengig davon, was der
       Dampfbefeuchter liefert. Das ist kein Fehler, sondern der Mappe treu
       nachgebaut (Anlage!AH49 = IF(AH32>0;AH32;0,001) - bei null Volumenstrom
       setzt die Excel selbst einen Ersatzwert ein, wodurch die Raumfeuchte
       praktisch der Aussenluft folgt). Ein Feuchteregler auf F_Raum haengt
       dann waehrend jeder Betriebspause komplett in der Luft und rammt seine
       Stellgroesse fest gegen 100, ohne dass sich die gemessene Groesse je
       bewegt - derselbe Fehlertyp wie oben, nur durch den Zeitplan statt
       durch eine Wettergroesse ausgeloest.

       Daraus folgt NICHT, dass die Ventilatoren durchlaufen muessen - nur,
       dass sie nicht auf null fallen duerfen. Beide Ventilatoren fahren
       deshalb ausserhalb der Betriebszeit auf eine REDUZIERTE Luftmenge
       zurueck (Maximalglied aus Anlagenbetrieb.stellgrad und einer festen
       Grundlast, abgeleitet aus dem - von Wochenzeitplan/Ferien/Monatsprofil
       unabhaengigen, darum nie verschwindenden - Tageslastprofil): der
       Feuchteregelkreis bleibt dadurch zu jeder Stunde tatsaechlich
       geschlossen, UND die Anlage heizt nicht mehr rund um die Uhr auf
       volle Luftmenge - eine Nachtluftabsenkung ist ohnehin der Normalfall,
       keine Ausnahme. Kaskade bleibt von alldem unberuehrt: ihr T_ZU ist
       eine reine Lufttemperatur (T), die auch bei kleinem Volumenstrom aus
       der Kette durchgereicht wird, waehrend F_Raum bei Volumenstrom null
       einer VOELLIG ANDEREN Formel folgt (siehe core/bausteine/raum.py) -
       bei reduziertem, aber nie null werdendem Volumenstrom bleibt sie in
       ihrer normalen (gekoppelten) Formel.

    Beide Funde beseitigt, bleibt trotzdem ein Rest an Stunden, die innerhalb
    von 100 Durchgaengen NICHT vollstaendig einschwingen - vor allem, wenn die
    Kaskade in ihrem normalen Regelfall gegen die (durch die Speichermasse des
    Raums gedaempfte) Raumtemperatur arbeitet statt gegen die viel staerker
    rueckgekoppelte Zulufttemperatur. Das ist kein neuer Grenzzyklus, sondern
    genau das langsame, aber echte Konvergieren, das
    werkzeuge/abgleich.py._ohne_befeuchtungsregelung() schon fuer AX_SIM 2.1
    (ohne ihre Zweipunktregler) beschreibt und tests/test_abgleich.py,
    test_ohne_den_befeuchtungskreis_schwingt_nichts_mehr, ausdruecklich zulaesst
    (Restabweichungen bis 0,44) - der Unterschied zu einem Grenzzyklus ist eine
    KLEINE, nicht 100,0 grosse Restabweichung. werkzeuge/plausibilitaet.py
    prueft genau darauf, nicht auf "keine einzige Warnung".

    Eine Testanlage, die als Plausibilitaetsmassstab dienen soll, darf ihre
    Ergebnisse trotzdem nicht aus einem echten Grenzzyklus beziehen - der waere
    hier kein Lehrbeispiel, sondern wuerde die Pruefungen unbrauchbar machen.

    3. Kein Konvergenzfund, sondern ein Betriebszustand: Die Kaskade kann -
       unabhaengig von den beiden obigen Funden - Kuehlung anfordern
       (kaelter_1 > 0), waehrend die Luft, die beim Kuehler ankommt, bereits
       kaelter ist als dessen Kaltwasser (T_KW_mittel). core/bausteine/
       kuehler.py rechnet diesen Grenzfall unveraendert durch der Excel
       getreu (Anlage!T3 hat dieselbe ungesicherte Formel) und der Kuehler
       waermt die Luft dann statt sie zu kuehlen - QK wird negativ, meldet
       sich aber jetzt auch als eigene Warnung. Diese Anlage soll diesen
       Betriebszustand gar nicht erst anfahren: eine Kuehlerschutz-
       Vorwaermung (P-Regler auf erhitzer.T_aus, ueber ein Maximalglied
       gemeinsam mit kaskade.waermer_1 auf den Erhitzer) haelt die
       Kuehler-Eintrittsluft unabhaengig von der Kaskade ueber einem
       Sollwert knapp oberhalb T_KW_mittel - ein Vorwaerm-/Frostschutz-
       register vor dem Kuehler, wie es in echten RLT-Anlagen an dieser
       Stelle steht, keine Verlegenheitsloesung. Details und Zahlen im
       Bericht.

Zur Wahl der Verdrahtung - ein Befund ueber Task 14:

    Bieten zwei Karten mehrere gleichrangige Anschluesse fuer dieselbe Rolle an
    (z. B. die fuenf STELLGROESSE-Ausgaenge von kaskade/sequenzregler gegen
    einen einzelnen Reglereingang, oder mehrere ISTWERT-Eingaenge gegen eine
    einzelne MESSWERT-Quelle), entscheidet core/graph.py._paare() rein nach der
    Reihenfolge, in der die Ports angelegt wurden - NICHT danach, welcher
    Anschluss fachlich gemeint ist. Bei kaskade/sequenzregler traf das
    zuverlaessig den falschen Ausgang (den seltensten Extremfall "waermer_3"
    statt des normalen Regelausgangs "waermer_1"); bei mehreren ISTWERT-Zielen
    haengt das Ergebnis von der Aufrufreihenfolge ab. Diese Vorlage umgeht das
    durchgaengig mit expliziten verbindung_anlegen()-Aufrufen statt der
    automatischen pfeil_anlegen()-Zuordnung, wo mehr als ein gleichrangiger
    Kandidat besteht. core/graph.py liegt ausserhalb des Dateibereichs dieser
    Aufgabe (core/vorlagen/, werkzeuge/plausibilitaet.py, tests/) und wird darum
    nicht angefasst; der Befund gehoert nach Task 14.
"""

from core import anlagen

NAME = "Testanlage Technikhalle"
BESCHREIBUNG = (
    "Ein Luftgerät mit Umluft-Mischkammer statt WRG, Dampfbefeuchtung, "
    "bauphysikalischem Raum mit Wandspeicher, Kaskaden-/Sequenzregelung und "
    "eigenständiger Verbraucherbilanz – deckt ab, was AX_SIM 2.1 auslässt"
)


def baue(projekt_id, name=NAME):
    anlage = anlagen.anlage_anlegen(
        projekt_id, name,
        notiz="Zum Pruefen gebaut, nicht aus der Excel uebernommen (Task 25)",
    )

    def karte(typ, x, y, bezeichnung, **parameter):
        return anlagen.karte_anlegen(anlage, typ, x, y, parameter, bezeichnung)

    def pfeil(von_karte_id, nach_karte_id):
        return anlagen.pfeil_anlegen(anlage, von_karte_id, nach_karte_id)

    def verbinde(von_karte_id, von_schluessel, nach_karte_id, nach_schluessel):
        anlagen.verbindung_anlegen(
            anlage,
            anlagen.port_id(von_karte_id, von_schluessel),
            anlagen.port_id(nach_karte_id, nach_schluessel),
        )

    # -- Quellen ----------------------------------------------------------
    wetter = karte("wetter", 40, 20, "Wetterdaten")
    aussenluft = karte("aussenluft", 40, 170, "Außenluft")

    # -- Luftbehandlung -----------------------------------------------------
    mischkammer = karte(
        "mischkammer", 260, 170, "Mischkammer",
        max_umluft=60.0,
    )
    erhitzer = karte(
        "erhitzer", 480, 170, "Erhitzer",
        V_nenn=5000.0, dp_nenn=150.0, QH_max=90.0,
    )
    kuehler = karte(
        "kuehler", 920, 170, "Kühler",
        V_nenn=5000.0, dp_nenn=180.0, QK_nenn=70.0, T_KW_mittel=7.0,
    )
    befeuchter = karte(
        "dampfbefeuchter", 1140, 170, "Dampfbefeuchter",
        dampftemperatur=180.0, absalzverlust=10.0, max_leistung=45.0, dampfart="E",
    )
    zuluft = karte(
        "ventilator", 1360, 170, "Zuluftventilator",
        rolle="zuluft", V_max=5000.0, dp_max=850.0, dp_konst=650.0,
        PE_max=2.2, regelart="F", stellgroesse=100.0,
    )

    raum = karte(
        "raum", 1580, 170, "Technikhalle",
        laenge_a=25.0, laenge_b=20.0, laenge_c=25.0, laenge_d=20.0, laenge_e=0.0,
        aw_anteil_a=1.0, aw_anteil_b=1.0, aw_anteil_c=1.0, aw_anteil_d=1.0,
        u_wand_a=0.24, u_wand_b=0.24, u_wand_c=0.24, u_wand_d=0.24,
        fenster_a=20.0, fenster_b=15.0, fenster_c=20.0, fenster_d=15.0,
        u_fenster_a=1.1, u_fenster_b=1.1, u_fenster_c=1.1, u_fenster_d=1.1,
        dach_laenge=0.0, dach_anteil=1.0, u_dach=0.22,
        fenster_dach=0.0, u_fenster_dach=1.3,
        boden_anteil=1.0, u_boden=0.28,
        geschosse=1.0, hoehe=4.0, bauart=100.0, ausrichtung=45.0,
        waermebruecke=0.05, waermeuebergang=7.7,
        g_faktor=0.5, verschattung_1=0.8, verschattung_2=0.9,
        verschattung_3=0.9, verschattung_4=1.0,
        # Die Beleuchtung haengt als eigene Karte am Raum (waermelast) - der
        # interne Beleuchtungsparameter bleibt aus, sonst zaehlte sie doppelt.
        spez_beleuchtung=0.0,
        start_temperatur=20.0,
    )

    abluft = karte(
        "ventilator", 1580, 470, "Abluftventilator",
        rolle="abluft", V_max=5000.0, dp_max=650.0, dp_konst=450.0,
        PE_max=1.8, regelart="F", stellgroesse=100.0,
    )
    verteiler = karte(
        "verteiler", 1360, 620, "Verteiler Abluft",
        anteile={"luft_aus_1": 60.0, "luft_aus_2": 40.0},
    )
    fortluft = karte("fortluft", 40, 620, "Fortluft")

    # Nachtluftabsenkung statt Abschalten (siehe Docstring, "Zur Konvergenz",
    # Fund 2): tageslastprofil.lastgang_1 (0,2 nachts / 1,0 tags / 0,3 abends)
    # ist von Wochenzeitplan/Ferien/Monatsprofil UNABHAENGIG und daher nie
    # null - skaliert auf 5-25 % ergibt eine Luftmenge, die auch ausserhalb
    # der Betriebszeit nie auf null faellt. Der Anlagenbetrieb (bis 100 %)
    # gewinnt ueber das Maximalglied, sobald er hoeher liegt.
    #
    # Der Grund, warum die Luftmenge NIE null werden darf, steht in raum.py
    # und stammt so aus der Excel: raum.berechne() koppelt die Raumfeuchte nur
    # bei Volumenstrom groesser null an die Zuluft; bei Volumenstrom null
    # springt sie auf die Aussenfeuchte (Anlage!AH49 = IF(AH32>0; AH32; 0,001) -
    # die Mappe setzt dort selbst einen Ersatzwert ein, kein Nachbaufehler).
    #
    # 25 (-> 5-25 % Luftmenge) ist dabei eine bewusst gewaehlte, plausible
    # GROESSENORDNUNG fuer eine reduzierte Nachtlueftung - kein Wert aus einer
    # Norm (z. B. DIN EN 16798-1) und nicht gegen einen Mindestwert geprueft.
    # Fuer die Kopplung selbst waere jeder Wert > 0 gleich gut geeignet:
    # raum.berechne() prueft nur "Volumenstrom > 0", nicht seine Hoehe.
    nachtluft = karte(
        "faktor", 1360, 320, "Nachtluft-Grundlast", faktor=25.0,
    )
    ventilatorstellung = karte(
        "maximalwert", 1360, 470, "Ventilatorstellung",
    )

    # -- Regelung -------------------------------------------------------
    kaskade = karte(
        "kaskade", 480, 20, "Raum-/Zuluft-Kaskade",
        T_Raum_min=20.0, T_AU_min=15.0, T_Raum_max=26.0, T_AU_max=30.0,
        T_ZU_min=15.0, T_ZU_max=26.0, xp=5.0,
    )
    # Sequenzregler auf die Raumtemperatur statt auf die Aussentemperatur - ein
    # urspruenglich geplanter Economizer-Regler auf T_AU (eine reine Wettergroesse
    # ohne Rueckwirkung der eigenen Stellgroesse) konvergierte nicht (siehe
    # Docstring, "Zur Konvergenz", Fund 1). T_Raum wirkt dagegen ueber
    # statische_heizung.QH_stat unmittelbar auf sich selbst zurueck.
    frostregler = karte(
        "sequenzregler", 1580, 20, "Frostschutzregler",
        oberer_sw=50.0, unterer_sw=17.0, xp=5.0,
    )
    # xp_2 klein und der Befeuchter kraeftig genug ausgelegt, damit der
    # Regelkreis Raumfeuchte -> Dampfbefeuchter.stellgroesse -> x_zu -> F_Raum
    # (F_Raum folgt x_zu 1:1, siehe raum.berechne) innerhalb der 100 erlaubten
    # Durchgaenge tatsaechlich einschwingt statt nur langsam heranzukriechen
    # (siehe Docstring, "Zur Konvergenz").
    feuchteregler = karte(
        "p_regler", 1140, 20, "Feuchteregler",
        xp_1=5.0, xp_2=0.7, sollwert_2=6.0,
    )
    # Kuehlerschutz (Vorwaermung): verhindert, dass der Kuehler Luft
    # ansteuert bekommt, die schon kaelter ist als sein Kaltwasser (siehe
    # Bericht und core/bausteine/kuehler.py - dort wird das jetzt nur
    # gemeldet, hier soll es gar nicht erst vorkommen). Misst
    # erhitzer.T_aus - genau die Luft, die als naechstes in den Kuehler
    # laeuft - und haelt sie mit derselben Kaskade-Erhitzer-Strecke ueber
    # einem Sollwert oberhalb T_KW_mittel (7,0 °C, siehe Kuehlerkarte unten),
    # unabhaengig davon, ob die Kaskade selbst gerade heizen oder kuehlen
    # will. xp_2 klein: derselbe starke, unmittelbare Regelkreis wie bei der
    # Kaskade selbst (Erhitzer -> eigener Austritt), siehe Docstring,
    # "Zur Konvergenz".
    #
    # Die 2 K Abstand zwischen sollwert_2 (9,0) und T_KW_mittel (7,0) sind -
    # genau wie die 25 % Nachtluft weiter unten - ein bewusst gewaehlter,
    # plausibler Sicherheitsabstand (Regelabweichung/Ueberschwingen sollen
    # den Sollwert nicht bis unter T_KW_mittel durchsacken lassen), KEIN
    # berechneter oder aus einer Norm entnommener Wert. Ungeprueft blieb, wie
    # gross der Abstand tatsaechlich sein muesste (z. B. aus xp_2 und der
    # Regelguete hergeleitet) - siehe Bericht.
    kuehlerschutz = karte(
        "p_regler", 920, 20, "Kühlerschutz (Vorwärmung)",
        xp_1=5.0, xp_2=1.0, sollwert_2=9.0,
    )
    erhitzerstellung = karte(
        "maximalwert", 700, 20, "Erhitzerstellung",
    )
    statische_heizung = karte(
        "statische_heizung", 1800, 20, "Statische Heizung (Frostschutz)",
        QH_nenn=8.0,
    )
    enthalpie = karte("enthalpierechner", 1800, 170, "Raumluftzustand")

    # -- Zeit und Betrieb -------------------------------------------------
    zeitplan = karte(
        "wochenzeitplan", 40, 770, "Wochenzeitplan",
        von_montag=6.0 / 24.0, bis_montag=20.0 / 24.0,
        von_dienstag=6.0 / 24.0, bis_dienstag=20.0 / 24.0,
        von_mittwoch=6.0 / 24.0, bis_mittwoch=20.0 / 24.0,
        von_donnerstag=6.0 / 24.0, bis_donnerstag=20.0 / 24.0,
        von_freitag=6.0 / 24.0, bis_freitag=20.0 / 24.0,
        von_samstag=8.0 / 24.0, bis_samstag=13.0 / 24.0,
        von_sonntag=0.0, bis_sonntag=0.0,
    )
    ferien = karte(
        "ferien", 260, 770, "Betriebsferien",
        zeitraeume=[
            {"name": "Weihnachten", "von": "23.12.", "bis": "02.01."},
            {"name": "Ostern", "von": "29.03.", "bis": "02.04."},
        ],
    )
    monate = karte(
        "monatsprofil", 480, 770, "Werksferien August",
        monate=[True, True, True, True, True, True, True, False, True, True, True, True],
    )
    tagesprofil = karte(
        "tageslastprofil", 920, 770, "Tageslastprofil",
        lastgang_1=[0.2] * 6 + [1.0] * 10 + [0.3] * 8,
    )
    betrieb = karte("anlagenbetrieb", 1140, 770, "Anlagenbetrieb")

    # -- Verbraucher --------------------------------------------------------
    beleuchtung = karte(
        "beleuchtung", 2020, 470, "Beleuchtung",
        spez_leistung=10.0, grundflaeche=500.0, nennbeleuchtung=300.0,
    )
    pumpen = karte(
        "heizungspumpen", 2020, 620, "Heizungspumpen",
        P_allgemein=0.25, P_wwb=0.15, P_kessel=0.35,
    )
    warmwasser = karte(
        "warmwasser", 2020, 770, "Warmwasserbereitung",
        speichervolumen=300.0, verbrauch=120.0, sollwert=55.0,
    )
    zirkulation = karte(
        "zirkulation", 2020, 920, "Zirkulation",
        volumenstrom=0.6, spreizung=5.0, P_pumpe=0.025,
    )

    bilanz = karte(
        "bilanz", 2240, 320, "Energiepreise und Bilanz",
        preis_strom_ht=260.0, preis_strom_nt=200.0, preis_strom_leistung=0.0,
        preis_waerme=85.0, preis_kaelte=85.0, preis_wasser=4.2,
        ht_von=6.0 / 24.0, ht_bis=19.0 / 24.0,
    )
    logger = karte(
        "datenlogger", 2240, 20, "Datenlogger",
        namen=[
            "T Raum", "F Raum", "Sollwert Raum", "T Zuluft",
            "Enthalpie Raum", "rel. Feuchte Raum",
        ] + [""] * 4,
        einheiten=["°C", "g/kg", "°C", "°C", "kJ/kg", "%"] + [""] * 4,
    )

    # -- Automatische Verdrahtung -----------------------------------------
    #
    # Reihenfolge bewusst gewaehlt: 'aussenluft' MUSS vor 'verteiler' an die
    # Mischkammer angeschlossen werden. Beide Quellen passen wegen der
    # neutralen LUFTWEG-Rolle des Verteilers gleich gut (Punktzahl 2) auf
    # BEIDE Mischkammer-Eingaenge; erst wenn 'aussenluft_ein' schon belegt
    # ist, bleibt fuer den Verteiler nur noch 'umluft_ein' frei. Vertauscht
    # man die Reihenfolge, verbindet sich Fortluft/Umluft versehentlich mit
    # dem Aussenluft-Eingang - derselbe Befund wie oben zu kaskade/sequenzregler.
    for von, nach in [
        (wetter, aussenluft),
        (wetter, raum),
        (aussenluft, mischkammer),
        (mischkammer, erhitzer),
        (erhitzer, kuehler),
        (kuehler, befeuchter),
        (befeuchter, zuluft),
        (zuluft, raum),
        (raum, abluft),
        (abluft, verteiler),
        (verteiler, fortluft),
        (verteiler, mischkammer),
        (raum, kaskade),
        (zeitplan, betrieb),
        (ferien, betrieb),
        (monate, betrieb),
        (tagesprofil, betrieb),
        # Beide Ventilatoren fahren nachts/ausserhalb der Betriebszeit auf eine
        # REDUZIERTE, nie auf null fallende Luftmenge zurueck statt ganz
        # abzuschalten - siehe Docstring, "Zur Konvergenz", Fund 2: bei
        # Volumenstrom null entkoppelt raum.berechne() die Feuchtebilanz vom
        # Zuluftzustand voellig (der Mappe getreu nachgebaut, Anlage!AH49),
        # der Feuchteregelkreis braeuchte dann in jeder Betriebspause einen
        # tatsaechlichen, aber nicht vorhandenen Volumenstrom.
        (betrieb, ventilatorstellung),
        (nachtluft, ventilatorstellung),
        (ventilatorstellung, zuluft),
        (ventilatorstellung, abluft),
        (betrieb, mischkammer),
        (betrieb, beleuchtung),
        (betrieb, pumpen),
        (betrieb, zirkulation),
        (zuluft, bilanz),
        (abluft, bilanz),
        (erhitzer, bilanz),
        (kuehler, bilanz),
        (befeuchter, bilanz),
        (beleuchtung, bilanz),
        (pumpen, bilanz),
        (warmwasser, bilanz),
        (zirkulation, bilanz),
        (statische_heizung, bilanz),
        (raum, logger),
        (kaskade, logger),
        (befeuchter, logger),
        # Kuehlerschutz: erhitzer bietet genau einen Messwert (T_aus) an, das
        # macht die automatische Zuordnung auf istwert_2 hier eindeutig (siehe
        # core/graph.py._paare - "eindeutig").
        (erhitzer, kuehlerschutz),
        # Kuehlerschutz UND Kaskade konkurrieren beide um die Erhitzerstellung
        # - deshalb ueber ein Maximalglied statt direkt. kuehlerschutz hat nur
        # eine Stufe (ausgang_2) wirklich verdrahtet, die automatische
        # Zuordnung waehlt sie hier eindeutig (niedrigste Portnummer, siehe
        # Docstring oben); "ein_1" wird dabei angelegt, "ein_2" waechst erst
        # danach nach - deshalb muss dieser Pfeil vor der expliziten
        # Verdrahtung von kaskade.waermer_1 unten stehen.
        (kuehlerschutz, erhitzerstellung),
        (erhitzerstellung, erhitzer),
    ]:
        pfeil(von, nach)

    # -- Explizite Verdrahtung ----------------------------------------------
    #
    # Jede dieser Verbindungen faellt aus einem von zwei Gruenden aus der
    # automatischen Zuordnung heraus: entweder bietet die Quelle mehrere
    # MESSWERTE an (Wetter, Raum), sodass die automatische Zuordnung einen
    # namenlosen ISTWERT-/SOLLWERT-Anschluss bewusst frei laesst, oder Rolle
    # und Name der beiden Enden passen nicht zusammen (Stellgroesse -> Messwert
    # am Frostschutzpfad), oder mehrere gleichrangige Ausgaenge (kaskade,
    # sequenzregler) konkurrieren um einen einzelnen Eingang (siehe Docstring).
    # tageslastprofil.lastgang_1 traegt die Rolle LASTGANG, faktor.ein
    # erwartet STELLGROESSE - deshalb explizit statt automatisch (die Karte
    # bietet ausserdem drei Lastgaenge an, siehe Docstring oben).
    verbinde(tagesprofil, "lastgang_1", nachtluft, "ein")

    verbinde(wetter, "T_AU", kaskade, "T_AU")
    verbinde(zuluft, "T_aus", kaskade, "T_ZU")
    # "ein_2" existiert erst, nachdem oben (kuehlerschutz, erhitzerstellung)
    # gelaufen ist und den zweiten dynamischen Anschluss nachwachsen liess.
    verbinde(kaskade, "waermer_1", erhitzerstellung, "ein_2")
    verbinde(kaskade, "kaelter_1", kuehler, "stellgroesse")

    verbinde(raum, "F_Raum", feuchteregler, "istwert_2")
    verbinde(feuchteregler, "ausgang_2", befeuchter, "stellgroesse")

    verbinde(raum, "T_Raum", frostregler, "istwert")
    verbinde(frostregler, "waermer_1", statische_heizung, "QH_stat")
    verbinde(statische_heizung, "QH", raum, "QH_stat")

    verbinde(beleuchtung, "Q_Bel", raum, "waermelast")

    verbinde(raum, "T_Raum", enthalpie, "t")
    verbinde(raum, "F_Raum", enthalpie, "x")
    verbinde(enthalpie, "h", logger, "wert_5")
    verbinde(enthalpie, "rF", logger, "wert_6")

    return anlage
