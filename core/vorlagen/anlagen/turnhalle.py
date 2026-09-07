"""Turnhalle - stossweise Belegung, traeger Baukoerper, Zweipunktheizung.

Eine Halle steht die meiste Zeit leer und ist dann fuer zwei Stunden voll
besetzt. Das Tageslastprofil faehrt die Lueftung mehrmals am Tag hoch und
wieder herunter, waehrend die grosse Speichermasse der Halle traege nachzieht.

Als einzige der zehn Anlagen benutzt sie die ausfuehrliche Raumkarte mit ihrer
Bauphysik statt des einfachen Raums - bei einer Halle mit 7 m Hoehe und
massiven Waenden ist die Speichermasse gerade das, worauf es ankommt. Und als
einzige heizt sie statisch ueber Heizkoerper, geschaltet von einem
Zweipunktregler: Die Traegheit der Halle ist genau der Fall, in dem eine
Zweipunktregelung richtig ist - sie schaltet ein paarmal am Tag, nicht ein
paarmal in der Stunde.

AUSLEGUNG

    Geometrie      30 x 30 m, 7,0 m hoch -> 900 m2, 6300 m3
    Luftmenge      9 000 m3/h -> 1,43 facher Luftwechsel. Bei 60 Sportlern und
                   30 m3/(h*Person) sind 1800 m3/h Mindestaussenluft noetig;
                   die uebrige Menge dient der Waermeverteilung.
    Heizlast       Die Raumkarte rechnet die Transmission aus der Geometrie
                   und den U-Werten selbst. Ueberschlagen:
                       Waende 4 x 30 x 7 = 840 m2 x 0,45 W/(m2K)     = 378 W/K
                       Dach   900 m2 x 0,30                          = 270 W/K
                       Boden  900 m2 x 0,35                          = 315 W/K
                       Fenster 120 m2 x 1,60                         = 192 W/K
                                                                       -------
                                                                      1155 W/K
                   bei 32 K also 37 kW Transmission, dazu die Lueftung nach
                   WRG (75 %): 9000 x 0,34 x 32 x 0,25                = 24,5 kW
                   -> Erhitzer 60 kW in der Luft, Heizkoerper 40 kW statisch
    Kuehllast      Personen 60 x 120 W = 7,2 kW, Beleuchtung 12 W/m2 = 10,8 kW
                   Sport treibende Menschen geben viel Feuchte ab: 200 g/h je
                   Person, zusammen 12,0 kg/h. Das ist der Grund, warum eine
                   Turnhalle ohne Lueftung binnen einer Stunde beschlaegt - und
                   es wurde vorher gar nicht gerechnet.
                   -> Kuehler 40 kW
    Zweipunkt      Schaltdifferenz 2,0 K. Sie muss BREITER sein als der Sprung,
                   den ein Schaltvorgang in der Halle bewirkt - sonst schaltet
                   der Regler sofort wieder zurueck und taktet (derselbe Fehler
                   wie im Hysterese-Beispiel, siehe Commit 8022f7e). 40 kW auf
                   6300 m3 Luft und die Speichermasse der Waende heben die
                   Temperatur um weniger als 1 K je Stunde - 2,0 K sind
                   reichlich Abstand.
    Ventilator     9000 m3/h, 800 Pa, Wirkungsgrad 0,65               = 3,08 kW
                   -> SFP 0,34 W/(m3/h)
"""

from core.vorlagen.bauhilfe import (
    Bauplatz, auswertung_verdrahten, betrieb_verdrahten,
    kaskade_verdrahten, lasten_verdrahten,
)
from core.vorlagen.anlagen._geraet import WOCHENTAGE, betriebszeiten

NAME = "Turnhalle"
#: Wohin die Anlage im Katalog gehoert (siehe core/vorlagen/__init__.py,
#: alle()). Drei Gruppen statt zehn Einzelbezeichnungen: Zwoelf Karten in
#: einer Reihe sind kein Katalog, und eine Gruppe je Anlage waere keine
#: Gliederung, sondern dieselbe Reihe mit Ueberschriften.
GRUPPE = "Sonderbau"
BESCHREIBUNG = (
    "900 m² Halle mit 7 m Höhe, bauphysikalischer Raum mit Speichermasse, "
    "Heizkörper über Zweipunktregler, stoßweise Belegung 8–22 Uhr"
)

FLAECHE_M2 = 900.0
LUFTMENGE_M3H = 9000.0
#: Lichte Raumhöhe - der Prüfstand rechnet daraus den Luftwechsel.
HOEHE_M = 7.0

ERWARTUNG = {
    "heizwaerme_kwh_m2a": (20.0, 160.0),
    "kaelte_kwh_m2a": (0.0, 60.0),
    "sfp_w_m3h": (0.25, 0.95),
    "luftwechsel_1h": (1.2, 1.8),
}

# Schulsport vormittags, Pause ueber Mittag, Vereinsbetrieb abends - der
# Lastgang springt mehrmals, statt einem glatten Tagesbogen zu folgen.
LASTGANG = [0.2] * 8 + [1.0, 1.0, 1.0, 1.0] + [0.3, 0.3] + [1.0] * 8 + [0.2] * 2


def baue(projekt_id, name=NAME):
    with Bauplatz(projekt_id, name, notiz=BESCHREIBUNG) as b:
        wetter = b.karte("wetter", 40, 20, "Wetterdaten")
        aussenluft = b.karte("aussenluft", 40, 200, "Außenluft")
        wrg = b.karte("wrg", 260, 200, "Wärmerückgewinnung",
                      V_nenn=LUFTMENGE_M3H, dp_WRG_nenn=160.0, dp_Bypass_nenn=40.0,
                      rueckwaermzahl=75.0, rueckfeuchtzahl=0.0)
        erhitzer = b.karte("erhitzer", 480, 200, "Erhitzer",
                           V_nenn=LUFTMENGE_M3H, dp_nenn=150.0, QH_max=60.0)
        kuehler = b.karte("kuehler", 700, 200, "Kühler",
                          V_nenn=LUFTMENGE_M3H, dp_nenn=190.0, QK_nenn=40.0,
                          T_KW_mittel=6.0, kontaktfaktor=0.55)
        zuluft = b.karte("ventilator", 920, 200, "Zuluftventilator",
                         rolle="zuluft", V_max=LUFTMENGE_M3H, dp_max=800.0,
                         dp_konst=800.0, PE_max=3.08, regelart="F")
        halle = b.karte(
            "raum", 1140, 200, "Hallenfläche",
            laenge_a=30.0, laenge_b=30.0, laenge_c=30.0, laenge_d=30.0,
            aw_anteil_a=1.0, aw_anteil_b=1.0, aw_anteil_c=1.0, aw_anteil_d=1.0,
            u_wand_a=0.45, u_wand_b=0.45, u_wand_c=0.45, u_wand_d=0.45,
            fenster_a=60.0, fenster_b=0.0, fenster_c=60.0, fenster_d=0.0,
            u_dach=0.30, u_boden=0.35, hoehe=HOEHE_M, geschosse=1.0,
            # Massive Waende und ein Estrichboden - die Halle traegt viel
            # Speichermasse, und genau darum geht es bei dieser Vorlage.
            bauart=130.0, ausrichtung=0.0, start_temperatur=18.0,
            spez_beleuchtung=0.0,
        )
        abluft = b.karte("ventilator", 1360, 200, "Abluftventilator",
                         rolle="abluft", V_max=LUFTMENGE_M3H, dp_max=600.0,
                         dp_konst=600.0, PE_max=2.31, regelart="F")
        fortluft = b.karte("fortluft", 260, 420, "Fortluft")

        kaskade = b.karte("kaskade", 480, 20, "Raum-/Zuluft-Kaskade",
                          T_Raum_min=18.0, T_AU_min=15.0, T_Raum_max=24.0,
                          T_AU_max=30.0, T_ZU_min=16.0, T_ZU_max=28.0, xp=5.0,
                          # WRG und Register wärmen, ein Kühler kühlt.
                          waermestufen=2, kaeltestufen=1)
        # Heizkoerper, geschaltet mit 2,0 K Schaltdifferenz - siehe Kopf.
        raumthermostat = b.karte("hysterese_regler", 480, 20, "Raumthermostat",
                                 sollwert=18.0, hysterese=2.0)
        # Der Hysterese-Regler schaltet EIN, wenn der Istwert ueber dem
        # Sollwert liegt - richtig fuer eine Kuehlung, verkehrt fuer eine
        # Heizung. Ohne diese Umkehr heizte der Heizkoerper genau dann, wenn
        # die Halle ohnehin zu warm war: ueber das Testreferenzjahr 88 MWh
        # allein von Juni bis August, mehr als doppelt so viel wie im ganzen
        # Winterhalbjahr.
        thermostat_umkehr = b.karte("umkehrglied", 700, 20, "Heizen statt kühlen")
        # Und der Anschluss QH_stat des Heizkoerpers nimmt KILOWATT entgegen,
        # nicht Prozent. Aus dem Schaltausgang 0/100 wird deshalb 0/40 kW -
        # die Nennleistung des Heizkoerpers. Bisher standen dort 100 kW, die
        # der Heizkoerper stillschweigend auf seine 40 kW kappte; die Anlage
        # rechnete richtig und log ueber ihre eigene Anforderung.
        heizanforderung = b.karte("faktor", 810, 20, "Heizanforderung in kW",
                                  faktor=0.4)
        heizkoerper = b.karte("statische_heizung", 920, 20, "Heizkörper",
                              QH_nenn=40.0)

        zeitplan = b.karte("wochenzeitplan", 920, 620, "Hallenbelegung",
                           **betriebszeiten(WOCHENTAGE, 8.0, 22.0))
        tagesprofil = b.karte("tageslastprofil", 1140, 620, "Tageslastprofil",
                              lastgang_1=LASTGANG)
        betrieb = b.karte("anlagenbetrieb", 1360, 620, "Anlagenbetrieb")
        grundlast = b.karte("faktor", 1580, 620, "Nachtluft-Grundlast", faktor=100.0)
        ventilatorstellung = b.karte("maximalwert", 1800, 620, "Ventilatorstellung")

        beleuchtung = b.karte("beleuchtung", 1580, 420, "Hallenbeleuchtung",
                              spez_leistung=12.0, grundflaeche=FLAECHE_M2,
                              nennbeleuchtung=400.0)
        bilanz = b.karte("bilanz", 2020, 200, "Jahresbilanz",
                         preis_strom=280.0, preis_waerme=95.0, preis_kaelte=95.0,
                         preis_wasser=4.2, ht_von=6.0 / 24.0, ht_bis=19.0 / 24.0)
        logger = b.karte("datenlogger", 2020, 20, "Datenlogger",
                         namen=["T Halle", "F Halle", "Sollwert", "T Zuluft",
                                "Wärme WRG", "Heizkörper"] + [""] * 4,
                         einheiten=["°C", "g/kg", "°C", "°C", "kW", "kW"] + [""] * 4)

        b.pfeil(wetter, aussenluft)
        # Die ausfuehrliche Raumkarte braucht neben T_AU und F_AU auch die
        # Strahlung auf ihre vier Fassaden und die Waagerechte.
        b.pfeil(wetter, halle)
        b.verbinde(aussenluft, "luft_aus", wrg, "zuluft_ein")
        b.pfeil(wrg, erhitzer)
        b.pfeil(erhitzer, kuehler)
        b.pfeil(kuehler, zuluft)
        b.verbinde(zuluft, "luft_aus", halle, "zuluft_ein_1")
        b.verbinde(halle, "abluft_aus_1", abluft, "luft_ein")
        b.verbinde(abluft, "luft_aus", wrg, "abluft_ein")
        b.verbinde(wrg, "abluft_aus", fortluft, "luft_ein")

        # Der Luftweg oben bleibt ausdruecklich: Die ausfuehrliche Raumkarte
        # traegt nummerierte Zu- und Abluftanschluesse, und welcher gemeint
        # ist, soll hier stehen und nicht geraten werden.
        kaskade_verdrahten(b, wetter, halle, zuluft, kaskade, {
            "waermer_1": wrg, "waermer_2": erhitzer, "kaelter_1": kuehler,
        })
        b.verbinde(halle, "T_Raum", raumthermostat, "istwert")
        b.verbinde(raumthermostat, "ausgang", thermostat_umkehr, "ein")
        b.verbinde(thermostat_umkehr, "ausgang", heizanforderung, "ein")
        b.verbinde(heizanforderung, "ausgang", heizkoerper, "QH_stat")
        b.verbinde(heizkoerper, "QH", halle, "QH_stat")

        betrieb_verdrahten(b, (zeitplan, tagesprofil), betrieb, tagesprofil,
                           grundlast, ventilatorstellung, (zuluft, abluft))
        b.pfeil(betrieb, beleuchtung)
        lasten = b.karte("innere_lasten", 1360, 420, "Innere Lasten",
                         personen=60.0, waerme_je_person=120.0, feuchte_je_person=200.0,
                         grundflaeche=FLAECHE_M2)
        # Die ausfuehrliche Raumkarte nimmt QH_stat als EINGANG entgegen (der
        # Heizkoerper speist ihn oben), nicht als Forderung - deshalb hier ohne
        # gebaeudeheizung.
        lasten_verdrahten(b, tagesprofil, beleuchtung, lasten, halle)
        auswertung_verdrahten(
            b, (zuluft, abluft, erhitzer, kuehler, beleuchtung, heizkoerper),
            bilanz, logger,
            protokoll=((wrg, "Q_WRG", "wert_5"), (heizkoerper, "QH", "wert_6")),
            pfeile=(halle, kaskade),
        )

    return b.anlage
