"""Rechenzentrum - nur Kuehlung, freie Kuehlung ueber die Mischkammer.

Der einzige Fall ohne Heizbedarf: 100 kW Abwaerme fallen rund um die Uhr an,
das ganze Jahr. Geheizt wird nie, gekuehlt immer. Solange die Aussenluft kalt
genug ist, uebernimmt sie die Kuehlung allein (freie Kuehlung) und die
Kaeltemaschine bleibt aus; erst im Sommer muss der Kuehler ran.

Die Anlage prueft damit zwei Dinge, die sonst keine prueft: einen Raum, dessen
Bilanz von der inneren Last beherrscht wird, und eine Mischkammer, die im
Winter auf 100 Prozent Aussenluft faehrt statt auf Umluft.

AUSLEGUNG

    Geometrie      400 m2 Serverflaeche, 3,0 m hoch -> 1200 m3
    Innere Last    250 W/m2 x 400 m2                                 = 100 kW
    Luftmenge      Aus der Last hergeleitet, nicht geschaetzt - und aus dem,
                   was das Kuehlregister wirklich hergibt. Es hat einen
                   Kontaktfaktor von 0,5 bei 6 GradC Kaltwasser; aus 30 GradC
                   Rueckluft macht es damit
                       30 - 0,5 x (30 - 6) = 18 GradC
                   und ueber das Jahr, mit kuehlerer Mischluft, weniger. Bei einem Raumsollwert von
                   27 GradC bleibt also ein Hub von rund 9 K:
                       V = 100 kW x 3600 / (1,2 x 1,007 x 9 K)
                         = 33 100 m3/h
                   -> 33 000 m3/h, also 27,5 facher Luftwechsel. Das ist fuer
                   ein luftgekuehltes Rechenzentrum normal; die Luft traegt
                   hier die Waerme fort, sie versorgt keine Personen.

                   Zwei fruehere Ansaetze waren zu klein. Mit 10 000 m3/h
                   waere der noetige Hub 29,8 K gewesen und der Raum auf ueber
                   42 GradC gelaufen. Mit 25 000 m3/h unterstellte die
                   Herleitung 14 GradC Zuluft - eine Temperatur, die dieses
                   Register nie erreicht; der Raum lief auf 28 bis 33 GradC.
                   Beides nachgerechnet. Die Luftmenge folgt der Last UND dem
                   Register, nicht der Flaeche.
    Transmission   innenliegend, gedaemmt -> rund 0,4 kW/K
    Kaltwasser     6 GradC. Mit 10 GradC erreichte das Register im Sommer
                   nur 21 GradC Zuluft, der Raum lief auf 30,4 GradC, und in
                   einer Stunde des Jahres blieb die Rechnung mit mehr als
                   zwei Einheiten Restabweichung stehen: Der Kuehler stand am
                   Anschlag, und die Regelung sprang zwischen ihm und der
                   Zuluftbegrenzung. Mit 6 GradC bleibt der Raum bei 24,0 bis
                   28,5 GradC, und jede Stunde schwingt ein (nachgemessen).
                   6 GradC ist die uebliche Kaltwassertemperatur einer
                   Kaeltemaschine.
    Freie Kuehlung Die Klappe regelt die MISCHTEMPERATUR auf 18 GradC, also
                   VOR dem Kuehler. Zusammen mit dem festen Raumsollwert von
                   27 GradC traegt sie damit den groessten Teil der
                   Jahresarbeit: 370 statt 2190 kWh/(m2 a) gehen ueber die
                   Kaeltemaschine (nachgemessen), also ein Sechstel. Gegenprobe:
                   Ueber 18 GradC Aussenluft, wo die Mischung 18 GradC nicht
                   mehr erreicht, liegen im Testreferenzjahr rund 1200 Stunden;
                   1200 h x 100 kW / 400 m2 = 300 kWh/(m2 a) - dieselbe
                   Groessenordnung.

                   Zwei Fehler steckten hier, beide gefunden, weil eine Stunde
                   des Jahres nicht einschwang (der 10. Juni um 17 Uhr, mit
                   18,1 GradC Aussenluft genau auf dem Sollwert der Klappe):

                   Erstens verwechselte der Verteiler "fordert null an" mit
                   "fordert nichts an". Sobald die Klappe zufuhr, zaehlte er
                   den Umluftgang zu den Gaengen ohne Bedarf und schob ihm nach
                   seinem festen Schluessel 80 Prozent der Abluft zu - 26 400
                   m3/h in einen Strang, den niemand haben wollte. Behoben in
                   core/bausteine/verteiler.py.

                   Zweitens verdeckte dieses Rauschen einen Auslegungsfehler:
                   den gleitenden Raumsollwert, siehe bei der Kaskade unten.
    Kuehllast      100 kW innere Last + Transmission im Sommer
                   -> Kuehler 120 kW
                   Gegenprobe an der Jahresarbeit: Alles, was die Server an
                   Strom aufnehmen, muss als Waerme wieder heraus. 100 kW x
                   8760 h = 876 MWh; gerechnet werden 887 MWh Kaelte.
    Erhitzer       Keiner. Ein Rechenzentrum heizt nicht.
    Ventilator     33 000 m3/h, 900 Pa, Wirkungsgrad 0,65           = 12,69 kW
                   Abluft 33 000 m3/h, 600 Pa                        =  8,46 kW
                   -> SFP 0,64 W/(m3/h) fuer beide zusammen
"""

from core.vorlagen.bauhilfe import (
    Bauplatz, auswertung_verdrahten, betrieb_verdrahten,
    lasten_verdrahten,
)
from core.vorlagen.anlagen._geraet import WOCHENTAGE, betriebszeiten

NAME = "Rechenzentrum"
#: Wohin die Anlage im Katalog gehoert (siehe core/vorlagen/__init__.py,
#: alle()). Drei Gruppen statt zehn Einzelbezeichnungen: Zwoelf Karten in
#: einer Reihe sind kein Katalog, und eine Gruppe je Anlage waere keine
#: Gliederung, sondern dieselbe Reihe mit Ueberschriften.
GRUPPE = "Technik und Industrie"
BESCHREIBUNG = (
    "400 m² Serverfläche, 100 kW Abwärme rund um die Uhr, keine Heizung, "
    "freie Kühlung über die Mischkammer, Kühler nur im Sommer"
)

FLAECHE_M2 = 400.0
LUFTMENGE_M3H = 33000.0
#: Lichte Raumhöhe - der Prüfstand rechnet daraus den Luftwechsel.
HOEHE_M = 3.0
INNERE_LAST_W_M2 = 250.0

ERWARTUNG = {
    # Kein Heizbedarf - das ist die Aussage dieser Anlage.
    "heizwaerme_kwh_m2a": (0.0, 5.0),
    # 100 kW ueber 8760 h sind 876 MWh = 2190 kWh/(m2*a) - so viel Waerme
    # muss heraus, denn alles, was die Server an Strom aufnehmen, wird Waerme.
    # Was davon die Kaeltemaschine traegt und was die freie Kuehlung, ist
    # gerade die Frage an die Rechnung; gemessen sind es 370 kWh/(m2*a), also
    # ein Sechstel. Die Obergrenze liegt weit darueber und faengt den Fall,
    # dass die freie Kuehlung gar nicht arbeitet; die Untergrenze faengt den
    # umgekehrten: Weniger als 200 kWh/(m2*a) hiesse, dass die Waerme der
    # Server irgendwo verschwindet, statt abgefuehrt zu werden.
    "kaelte_kwh_m2a": (200.0, 1800.0),
    "sfp_w_m3h": (0.25, 0.95),
    # 33 000 m3/h auf 1200 m3 Raum sind 27,5 Luftwechsel je Stunde. Fuer ein
    # luftgekuehltes Rechenzentrum ist das normal - die Luft traegt hier die
    # Waerme fort, sie versorgt keine Personen. Das Band stand auf 19 bis 23
    # und gehoerte zur frueheren Luftmenge von 25 000 m3/h.
    "luftwechsel_1h": (24.0, 32.0),
}


def baue(projekt_id, name=NAME):
    with Bauplatz(projekt_id, name, notiz=BESCHREIBUNG) as b:
        wetter = b.karte("wetter", 40, 20, "Wetterdaten")
        aussenluft = b.karte("aussenluft", 40, 200, "Außenluft")
        # Keine Waermerueckgewinnung: sie wuerde die warme Abluft nutzen, um
        # die Zuluft zu erwaermen - genau das Gegenteil dessen, was hier
        # gebraucht wird.
        mischkammer = b.karte("mischkammer", 260, 200, "Mischkammer (freie Kühlung)",
                              max_umluft=90.0)
        kuehler = b.karte("kuehler", 480, 200, "Kühler",
                          V_nenn=LUFTMENGE_M3H, dp_nenn=200.0, QK_nenn=120.0,
                          T_KW_mittel=6.0, kontaktfaktor=0.5)
        zuluft = b.karte("ventilator", 700, 200, "Zuluftventilator",
                         rolle="zuluft", V_max=LUFTMENGE_M3H, dp_max=900.0,
                         dp_konst=900.0, PE_max=12.69, regelart="F")
        raum = b.karte("einfacher_raum", 920, 200, "Serverfläche",
                       # Keine Gebaeudeheizung: 100 kW Serverlast heizen den
                       # Raum von innen, und niemand haelt sich darin auf. Der
                       # Sollwert steht deshalb auf null - der Raum klemmt seine
                       # Temperatur sonst auf einen Wert, den niemand bezahlt
                       # (core/pruefung.py meldet genau das).
                       spez_transmission=0.4, sollwert_stat=0.0)
        abluft = b.karte("ventilator", 1140, 200, "Abluftventilator",
                         rolle="abluft", V_max=LUFTMENGE_M3H, dp_max=600.0,
                         dp_konst=600.0, PE_max=8.46, regelart="F")
        verteiler = b.karte("verteiler", 1360, 200, "Umluft/Fortluft",
                            anteile={"luft_aus_1": 80.0, "luft_aus_2": 20.0})
        fortluft = b.karte("fortluft", 260, 420, "Fortluft")

        # Nur die Kuehlseite der Kaskade wird gebraucht.
        kaskade = b.karte("kaskade", 480, 20, "Raumtemperaturregelung",
                          # KEIN gleitender Raumsollwert: 27 GradC das ganze
                          # Jahr. Ein gleitender Sollwert folgt der
                          # Behaglichkeit - Menschen nehmen im Sommer einen
                          # waermeren Raum an -, und hier sitzt niemand. Fuer
                          # ein Rechenzentrum ist er sogar verkehrt herum:
                          # Faellt er bei kaltem Wetter auf 24 GradC, muss die
                          # Zuluft auf 15,1 GradC, und die Kaeltemaschine
                          # kuehlt die 18 GradC, die die freie Kuehlung gerade
                          # umsonst geliefert hat, noch einmal um drei Kelvin
                          # herunter. Nachgemessen ueber das Testreferenzjahr:
                          #     24 bis 27 GradC  1111 kWh/(m2 a) Kaelte
                          #     26 bis 27 GradC   623 kWh/(m2 a)
                          #     fest auf 27       376 kWh/(m2 a)
                          # Ein Drittel der Kaeltearbeit, und die
                          # Gebaeudeheizung faellt ganz weg. 27 GradC ist der
                          # obere Wert des Bandes, das ASHRAE TC9.9 fuer den
                          # Lufteintritt in die Technik empfiehlt (18 bis 27);
                          # der Kaltgang liegt hier bei der Zuluft von 18 GradC.
                          T_Raum_min=27.0, T_AU_min=15.0, T_Raum_max=27.0,
                          T_AU_max=30.0, T_ZU_min=15.0, T_ZU_max=26.0, xp=5.0,
                          # Ein Kuehler, keine Heizung. Ohne diese Angabe
                          # lief die Regelabweichung bis 200, wirksam waren
                          # 100 - hundert Einheiten Leerweg, die der Regler
                          # nach jedem warmen Tag zurueckwandern musste.
                          waermestufen=1, kaeltestufen=1)
        # Freie Kuehlung: je kaelter es draussen ist, desto weniger Umluft.
        # Der Regler haelt die MISCHTEMPERATUR bei 18 GradC, indem er den
        # Umluftanteil nachfuehrt - ist die Aussenluft kalt, mischt er warme
        # Abluft dazu, ist sie warm, faehrt er auf Umluft und laesst den
        # Kuehler arbeiten.
        #
        # Gemessen wird VOR dem Kuehler, nicht hinter ihm. Frueher hing der
        # Istwert am Zuluftventilator, also hinter dem Kuehler - damit regelten
        # Klappe und Kuehler dieselbe Groesse. Der Kuehler ist der schnellere
        # von beiden: Er kuehlte die Mischluft auf 14 GradC herunter, die
        # Klappe sah 14 statt 18 GradC und fuhr auf ihre maximalen 90 Prozent
        # Umluft, um wieder aufzuwaermen. Bei 3,7 GradC Aussenluft lief die
        # Kaeltemaschine dadurch mit 94 kW, obwohl draussen die Kaelte umsonst
        # zu haben war - die freie Kuehlung sparte ueber das Jahr nichts. Vor
        # dem Kuehler gemessen greift sie zuerst, und der Kuehler nimmt nur
        # noch, was sie uebriglaesst.
        freikuehlung = b.karte("p_regler", 700, 20, "Freie Kühlung",
                               xp_1=5.0, xp_2=4.0, sollwert_2=18.0)

        zeitplan = b.karte("wochenzeitplan", 920, 620, "Dauerbetrieb",
                           **betriebszeiten(WOCHENTAGE, 0.0, 24.0))
        tagesprofil = b.karte("tageslastprofil", 1140, 620, "Tageslastprofil",
                              lastgang_1=[1.0] * 24)
        betrieb = b.karte("anlagenbetrieb", 1360, 620, "Anlagenbetrieb")
        grundlast = b.karte("faktor", 1580, 620, "Grundlast", faktor=100.0)
        ventilatorstellung = b.karte("maximalwert", 1800, 620, "Ventilatorstellung")
        server = b.karte("beleuchtung", 1580, 420, "Serverabwärme",
                         spez_leistung=INNERE_LAST_W_M2, grundflaeche=FLAECHE_M2,
                         nennbeleuchtung=1.0)

        bilanz = b.karte("bilanz", 2020, 200, "Jahresbilanz",
                         preis_strom=280.0, preis_waerme=95.0, preis_kaelte=95.0,
                         preis_wasser=4.2, ht_von=6.0 / 24.0, ht_bis=19.0 / 24.0)
        logger = b.karte("datenlogger", 2020, 20, "Datenlogger",
                         namen=["T Raum", "F Raum", "Sollwert", "T Zuluft",
                                "Umluftanteil"] + [""] * 5,
                         einheiten=["°C", "g/kg", "°C", "°C", "%"] + [""] * 5)

        b.pfeil(wetter, aussenluft)
        b.pfeil(wetter, raum)
        b.verbinde(aussenluft, "luft_aus", mischkammer, "aussenluft_ein")
        b.pfeil(mischkammer, kuehler)
        b.pfeil(kuehler, zuluft)
        b.pfeil(zuluft, raum)
        b.pfeil(raum, abluft)
        b.pfeil(abluft, verteiler)
        b.verbinde(verteiler, "luft_aus_1", mischkammer, "umluft_ein")
        b.verbinde(verteiler, "luft_aus_2", fortluft, "luft_ein")

        b.verbinde(wetter, "T_AU", kaskade, "T_AU")
        b.verbinde(raum, "T_Raum", kaskade, "T_Raum")
        b.verbinde(zuluft, "T_aus", kaskade, "T_ZU")
        b.verbinde(kaskade, "kaelter_1", kuehler, "stellgroesse")
        b.verbinde(mischkammer, "T_MI", freikuehlung, "istwert_2")
        b.verbinde(freikuehlung, "ausgang_2", mischkammer, "umluftanteil")

        betrieb_verdrahten(b, (zeitplan, tagesprofil), betrieb, tagesprofil,
                           grundlast, ventilatorstellung, (zuluft, abluft))
        b.pfeil(betrieb, server)
        lasten = b.karte("innere_lasten", 1360, 380, "Innere Lasten",
                         personen=0.0, grundflaeche=FLAECHE_M2)
        # Die Serverabwaerme kommt ueber 'weitere_waerme' herein; Personen gibt
        # es hier keine - ein Rechenzentrum versorgt keine.
        lasten_verdrahten(b, tagesprofil, server, lasten, raum)
        auswertung_verdrahten(
            b, (zuluft, abluft, kuehler, server),
            bilanz, logger,
            protokoll=((mischkammer, "umluftanteil_ist", "wert_5"),),
            pfeile=(raum, kaskade),
        )

    return b.anlage
