"""Produktionshalle - adiabate Kuehlung und zwei Zonen.

Die einzige Anlage mit einem Luftwaescher und die einzige mit einem geteilten
Luftweg: Ein Geraet versorgt zwei Hallenteile, ein Verteiler teilt die Zuluft
auf, ein Sammler fuehrt die Abluft wieder zusammen. Gekuehlt wird nicht mit
einer Kaeltemaschine, sondern adiabat - der Luftwaescher verdunstet Wasser in
die Abluft und kuehlt damit ueber die Waermerueckgewinnung die Zuluft. Das
kostet Wasser statt Strom.

Der Fall prueft zweierlei, was sonst keiner prueft: ob die Luftmengen ueber
Verteiler und Sammler aufgehen, und ob der Luftwaescher in der Wasserbilanz
ankommt.

AUSLEGUNG

    Geometrie      3000 m2, 6,0 m hoch -> 18 000 m3, zwei Zonen zu je 1500 m2
    Luftmenge      20 000 m3/h -> 1,11 facher Luftwechsel. Bei einer Halle
                   zaehlt die Waermeabfuhr, nicht der Luftwechsel.
    Transmission   grosse, maessig gedaemmte Huelle -> rund 2,5 kW/K
    Heizlast       2,5 x 32 K                                        = 80,0 kW
                   Lueftung nach WRG (75 %)
                       20000 x 0,34 x 32 x 0,25                      = 54,4 kW
                                                                       -------
                                                                      134,4 kW
                   -> Erhitzer 160 kW
    Innere Last    Maschinen und Beleuchtung 18 W/m2 x 3000 m2     = 54 kW
                   40 Beschaeftigte x 150 W (koerperliche Arbeit)  =  6 kW
                                                                     -------
                                                                     60 kW
                   Die 20 W/m2 der Auslegung stehen also weiter, nur getrennt
                   nach Maschinen und Menschen. Deren Feuchteabgabe von je
                   150 g/h ergibt 6,0 kg/h, die vorher fehlte.
                   Die Luftmenge folgt der Last, nicht der Flaeche. Abfuehrbar
                   sind bei 30 GradC Hallentemperatur und 14 GradC erreichbarer
                   Zuluft (mehr gibt ein Kuehler mit 6 GradC Kaltwasser nicht
                   her):
                       20000/3600 x 1,2 x 1,007 x 16 K               = 107 kW
                   Mit 20 W/m2 bleibt Luft nach oben; mit den zunaechst
                   angesetzten 33 W/m2 (99 kW) lag die Last so dicht an dieser
                   Grenze, dass die Halle im Sommer auf 41 GradC lief
                   (nachgemessen). 20 W/m2 ist fuer eine Montage- und
                   Fertigungshalle die uebliche Groessenordnung.
    Kuehlung       adiabat ueber den Luftwaescher in der Abluft. Er kuehlt die
                   Abluft um bis zu 8 K herunter, die WRG traegt davon 75 %
                   auf die Zuluft: rund 6 K bei 20 000 m3/h
                       20000/3600 x 1,2 x 1,007 x 6                  = 40,3 kW
                   kostenlose Kuehlleistung. Ein Kuehler steht zusaetzlich
                   fuer die heissesten Stunden bereit -> 100 kW.
    Ventilator     20 000 m3/h, 1100 Pa, Wirkungsgrad 0,65           = 9,40 kW
                   -> SFP 0,47 W/(m3/h) - der lange Kanalweg einer Halle
                      kostet mehr Druck als ein Bueroteil.
"""

from core.vorlagen.bauhilfe import (
    Bauplatz, auswertung_verdrahten, betrieb_verdrahten,
    lasten_verdrahten,
)
from core.vorlagen.anlagen._geraet import WERKTAGE, betriebszeiten, tagesgang

NAME = "Produktionshalle"
#: Wohin die Anlage im Katalog gehoert (siehe core/vorlagen/__init__.py,
#: alle()). Drei Gruppen statt zehn Einzelbezeichnungen: Zwoelf Karten in
#: einer Reihe sind kein Katalog, und eine Gruppe je Anlage waere keine
#: Gliederung, sondern dieselbe Reihe mit Ueberschriften.
GRUPPE = "Technik und Industrie"
BESCHREIBUNG = (
    "3000 m² Halle in zwei Zonen, adiabate Kühlung über einen Luftwäscher "
    "in der Abluft, Verteiler und Sammler im Luftweg"
)

FLAECHE_M2 = 3000.0
LUFTMENGE_M3H = 20000.0
#: Lichte Raumhöhe - der Prüfstand rechnet daraus den Luftwechsel.
HOEHE_M = 6.0

ERWARTUNG = {
    "heizwaerme_kwh_m2a": (20.0, 140.0),
    # Wenig, weil adiabat gekuehlt wird - genau das soll die Anlage zeigen.
    "kaelte_kwh_m2a": (0.0, 40.0),
    "sfp_w_m3h": (0.30, 1.10),
    "luftwechsel_1h": (0.9, 1.4),
}


def baue(projekt_id, name=NAME):
    with Bauplatz(projekt_id, name, notiz=BESCHREIBUNG) as b:
        wetter = b.karte("wetter", 40, 20, "Wetterdaten")
        aussenluft = b.karte("aussenluft", 40, 200, "Außenluft")
        wrg = b.karte("wrg", 260, 200, "Wärmerückgewinnung",
                      V_nenn=LUFTMENGE_M3H, dp_WRG_nenn=180.0, dp_Bypass_nenn=45.0,
                      rueckwaermzahl=75.0, rueckfeuchtzahl=0.0)
        erhitzer = b.karte("erhitzer", 480, 200, "Erhitzer",
                           V_nenn=LUFTMENGE_M3H, dp_nenn=160.0, QH_max=160.0)
        kuehler = b.karte("kuehler", 700, 200, "Kühler",
                          V_nenn=LUFTMENGE_M3H, dp_nenn=200.0, QK_nenn=100.0,
                          T_KW_mittel=6.0, kontaktfaktor=0.5)
        zuluft = b.karte("ventilator", 920, 200, "Zuluftventilator",
                         rolle="zuluft", V_max=LUFTMENGE_M3H, dp_max=1100.0,
                         dp_konst=1100.0, PE_max=9.4, regelart="F")
        # Zwei Zonen zu gleichen Teilen.
        zonenverteiler = b.karte("verteiler", 1140, 200, "Zonenverteiler",
                                 anteile={"luft_aus_1": 50.0, "luft_aus_2": 50.0})
        zone_a = b.karte("einfacher_raum", 1360, 120, "Fertigung",
                         spez_transmission=1.25, sollwert_stat=17.0)
        zone_b = b.karte("einfacher_raum", 1360, 300, "Montage",
                         spez_transmission=1.25, sollwert_stat=17.0)
        # Die Gebaeudeheizung je Zone. Ohne sie meldet der Raum seine
        # Unterdeckung (QH_stat) und niemand nimmt sie entgegen: Er bleibt
        # trotzdem auf seinem Sollwert, und die Waerme dafuer taucht in keiner
        # Bilanz auf. Auslegung je Zone: 1,25 kW/K x 27 K (15 GradC innen)
        # = 34 kW.
        heizung_a = b.karte("statische_heizung", 1140, 620, "Gebäudeheizung Fertigung",
                            QH_nenn=40.0)
        heizung_b = b.karte("statische_heizung", 1360, 620, "Gebäudeheizung Montage",
                            QH_nenn=40.0)
        zonensammler = b.karte("sammler", 1580, 200, "Zonensammler")
        abluft = b.karte("ventilator", 1800, 200, "Abluftventilator",
                         rolle="abluft", V_max=LUFTMENGE_M3H, dp_max=800.0,
                         dp_konst=800.0, PE_max=6.8, regelart="F")
        # Der Waescher sitzt in der ABLUFT, nicht in der Zuluft: Er kuehlt sie
        # durch Verdunstung herunter, und die Waermerueckgewinnung traegt die
        # Kaelte auf die Zuluft. So wird die Zuluft nicht befeuchtet.
        waescher = b.karte("luftwaescher", 2020, 200, "Luftwäscher (adiabat)",
                           V_nenn=LUFTMENGE_M3H, dp_nenn=60.0,
                           absalzverlust=10.0, pumpenart="H")
        fortluft = b.karte("fortluft", 260, 420, "Fortluft")

        kaskade = b.karte("kaskade", 480, 20, "Raum-/Zuluft-Kaskade",
                          T_Raum_min=17.0, T_AU_min=15.0, T_Raum_max=30.0,
                          T_AU_max=30.0, T_ZU_min=16.0, T_ZU_max=30.0, xp=5.0,
                          # Register wärmt, Wäscher und Kühler kühlen.
                          waermestufen=2, kaeltestufen=2)

        zeitplan = b.karte("wochenzeitplan", 920, 620, "Schichtbetrieb",
                           **betriebszeiten(WERKTAGE, 6.0, 22.0))
        tagesprofil = b.karte("tageslastprofil", 1140, 620, "Tageslastprofil",
                              lastgang_1=tagesgang(0.2, 1.0, 0.4, tagstunden=(6, 22)))
        betrieb = b.karte("anlagenbetrieb", 1360, 620, "Anlagenbetrieb")
        grundlast = b.karte("faktor", 1580, 620, "Nachtluft-Grundlast", faktor=100.0)
        ventilatorstellung = b.karte("maximalwert", 1800, 620, "Ventilatorstellung")

        maschinen = b.karte("beleuchtung", 1580, 420, "Maschinen und Beleuchtung",
                            spez_leistung=18.0, grundflaeche=FLAECHE_M2,
                            nennbeleuchtung=500.0)
        bilanz = b.karte("bilanz", 2240, 200, "Jahresbilanz",
                         preis_strom=280.0, preis_waerme=95.0, preis_kaelte=95.0,
                         preis_wasser=4.2, ht_von=6.0 / 24.0, ht_bis=19.0 / 24.0)
        logger = b.karte("datenlogger", 2240, 20, "Datenlogger",
                         namen=["T Fertigung", "F Fertigung", "Sollwert",
                                "T Zuluft", "Wärme WRG"] + [""] * 5,
                         einheiten=["°C", "g/kg", "°C", "°C", "kW"] + [""] * 5)

        # Luftweg mit Verzweigung und Zusammenfuehrung
        b.pfeil(wetter, aussenluft)
        b.pfeil(wetter, zone_a)
        b.pfeil(wetter, zone_b)
        b.verbinde(aussenluft, "luft_aus", wrg, "zuluft_ein")
        b.pfeil(wrg, erhitzer)
        b.pfeil(erhitzer, kuehler)
        b.pfeil(kuehler, zuluft)
        b.pfeil(zuluft, zonenverteiler)
        b.verbinde(zonenverteiler, "luft_aus_1", zone_a, "zuluft_ein_1")
        b.verbinde(zonenverteiler, "luft_aus_2", zone_b, "zuluft_ein_1")
        b.verbinde(zone_a, "abluft_aus_1", zonensammler, "luft_ein_1")
        b.verbinde(zone_b, "abluft_aus_1", zonensammler, "luft_ein_2")
        b.pfeil(zonensammler, abluft)
        b.verbinde(abluft, "luft_aus", waescher, "luft_ein")
        b.verbinde(waescher, "luft_aus", wrg, "abluft_ein")
        b.verbinde(wrg, "abluft_aus", fortluft, "luft_ein")

        b.verbinde(wetter, "T_AU", kaskade, "T_AU")
        b.verbinde(zone_a, "T_Raum", kaskade, "T_Raum")
        b.verbinde(zuluft, "T_aus", kaskade, "T_ZU")
        # Die Waermerueckgewinnung laeuft hier DURCHGEHEND, nicht geregelt.
        #
        # Mit dem Luftwaescher in der Abluft nuetzt sie in beide Richtungen:
        # im Winter traegt sie Waerme von der Abluft auf die Zuluft, im Sommer
        # die Kaelte, die der Waescher durch Verdunstung erzeugt. Es gibt also
        # keine Stunde, in der man sie abschalten wollte.
        #
        # Zwei Zwischenschritte waren falsch und stehen hier als Warnung:
        # Haengt sie allein an der Waermesequenz ('waermer_1'), schaltet sie
        # genau dann ab, wenn gekuehlt werden soll - die adiabate Kuehlung kam
        # nie an, die Halle lief im Januar auf 34,7 GradC. Haengt sie ueber ein
        # Maximalglied an beiden Sequenzen, kehrt sie ihre Wirkung dort um, wo
        # die Kaskade zwischen Heizen und Kuehlen wechselt; die Rechnung
        # pendelte an dieser Stelle, statt einzuschwingen.
        #
        # Der Faktor 5 auf die Ventilatorstellung (20 bis 100 %) ergibt nach
        # der Begrenzung der Karte auf 100 % genau das: volle Rueckgewinnung,
        # solange Luft stroemt.
        wrg_stellung = b.karte("faktor", 700, 20, "WRG dauernd an", faktor=5.0)
        b.verbinde(kaskade, "waermer_2", erhitzer, "stellgroesse")
        b.verbinde(kaskade, "kaelter_1", waescher, "stellgroesse")
        b.verbinde(kaskade, "kaelter_2", kuehler, "stellgroesse")

        betrieb_verdrahten(b, (zeitplan, tagesprofil), betrieb, tagesprofil,
                           grundlast, ventilatorstellung, (zuluft, abluft))
        b.verbinde(ventilatorstellung, "ausgang", wrg_stellung, "ein")
        b.verbinde(wrg_stellung, "ausgang", wrg, "stellgroesse")
        b.pfeil(betrieb, maschinen)
        # Die Maschinenlast verteilt sich auf beide Zonen; jede sieht die
        # Haelfte. Dasselbe gilt fuer die Belegschaft: 40 Beschaeftigte, je
        # zwanzig in einer Zone. Koerperliche Arbeit gibt 150 W Waerme und
        # 150 g/h Feuchte je Person ab - die Feuchte wurde vorher gar nicht
        # gerechnet, obwohl eine Montagehalle im Winter davon beschlaegt.
        halbe_last = b.karte("faktor", 1800, 420, "Last je Zone", faktor=0.5)
        b.verbinde(maschinen, "Q_Bel", halbe_last, "ein")
        for zone, heizung, versatz in ((zone_a, heizung_a, 0),
                                       (zone_b, heizung_b, 180)):
            lasten = b.karte(
                "innere_lasten", 1580, 420 + versatz, "Innere Lasten",
                personen=20.0, waerme_je_person=150.0, feuchte_je_person=150.0,
                grundflaeche=FLAECHE_M2 / 2.0,
            )
            b.verbinde(halbe_last, "ausgang", lasten, "weitere_waerme")
            lasten_verdrahten(b, tagesprofil, None, lasten, zone,
                              gebaeudeheizung=heizung)

        auswertung_verdrahten(
            b, (zuluft, abluft, erhitzer, kuehler, waescher, maschinen,
                heizung_a, heizung_b),
            bilanz, logger,
            protokoll=((wrg, "Q_WRG", "wert_5"),),
            pfeile=(zone_a, kaskade),
        )

    return b.anlage
