"""Krankenhaus, OP-Bereich - 100 Prozent Aussenluft ohne jede Umluft.

Der Gegenpol zur Schwimmhalle: Dort wird moeglichst viel Luft im Umlauf
gehalten, hier gar keine. Umluft ist im OP nicht zulaessig, jeder Kubikmeter
muss von aussen kommen und vollstaendig aufbereitet werden. Dazu ein
Luftwechsel, der das Vier- bis Fuenffache eines Bueros betraegt. Rund um die
Uhr.

Diese Anlage prueft den Fall ohne Mischkammer bei hohem Luftwechsel - genau
die Kombination, bei der ein Fehler in der Luftmengenkette am teuersten ist.

AUSLEGUNG

    Geometrie      300 m2 OP und Nebenraeume, 3,0 m hoch -> 900 m3
    Luftmenge      6 000 m3/h -> 6,7 facher Luftwechsel. Fuer einen OP der
                   unteren Richtwert (Raumklasse Ib), Reinraum-OPs liegen hoeher.
    Transmission   Innenliegend, wenig Aussenflaeche -> rund 0,3 kW/K
    Heizlast       Transmission 0,3 x 32 K                     =  9,6 kW
                   Lueftung nach WRG (75 %)
                       6000 x 0,34 x 32 x 0,25                 = 16,3 kW
                                                                 -------
                                                                  25,9 kW
                   -> Erhitzer 35 kW
    Innere Last    OP-Leuchten, Geraetetuerme, Monitore     54 W/m2 = 16,2 kW
                   OP-Team 12 Personen x 150 W (stehende Arbeit) =  1,8 kW
                                                                   --------
                                                                    18,0 kW
                   Die 60 W/m2 der Auslegung stehen also weiter, nur getrennt
                   nach dem, was Geraete abgeben, und dem, was Menschen
                   abgeben - Letztere geben auch Feuchte ab: 12 x 70 g/h unter
                   OP-Kleidung ergibt 0,84 kg/h.
    Kuehllast      18 kW innere Last, dazu Aussenluft im Sommer
                   -> Kuehler 45 kW
    Befeuchtung    OP-Bereiche werden befeuchtet (30 bis 50 % rF):
                       6000/3600 x 1,2 x 5,0 g/kg              = 10,0 kg/h
                   -> Dampfbefeuchter 14 kg/h
    Ventilator     6000 m3/h, 1100 Pa (Filterstufen!), Wirkungsgrad 0,65
                                                                = 2,82 kW
                   -> SFP 0,47 W/(m3/h) - hoeher als im Buero, weil mehrere
                      Filterstufen Druck kosten.
"""

from core.vorlagen.bauhilfe import Bauplatz

WOCHENTAGE = ("montag", "dienstag", "mittwoch", "donnerstag", "freitag",
              "samstag", "sonntag")
WERKTAGE = WOCHENTAGE[:5]

NAME = "Krankenhaus, OP-Bereich"
BESCHREIBUNG = (
    "300 m² OP und Nebenräume, 100 % Außenluft ohne Umluft, "
    "6,7-facher Luftwechsel, Befeuchtung, Dauerbetrieb"
)

FLAECHE_M2 = 300.0
LUFTMENGE_M3H = 6000.0
#: Lichte Raumhöhe - der Prüfstand rechnet daraus den Luftwechsel.
HOEHE_M = 3.0

ERWARTUNG = {
    # Dauerbetrieb, hoher Luftwechsel, kleine Flaeche - der spezifische
    # Verbrauch je Quadratmeter ist deshalb sehr hoch.
    "heizwaerme_kwh_m2a": (100.0, 500.0),
    "kaelte_kwh_m2a": (10.0, 200.0),
    "sfp_w_m3h": (0.30, 1.10),
    "luftwechsel_1h": (6.0, 7.5),
}


def baue(projekt_id, name=NAME):
    with Bauplatz(projekt_id, name, notiz=BESCHREIBUNG) as b:
        wetter = b.karte("wetter", 40, 20, "Wetterdaten")
        aussenluft = b.karte("aussenluft", 40, 200, "Außenluft")
        wrg = b.karte("wrg", 260, 200, "Wärmerückgewinnung",
                      V_nenn=LUFTMENGE_M3H, dp_WRG_nenn=180.0, dp_Bypass_nenn=45.0,
                      rueckwaermzahl=75.0, rueckfeuchtzahl=0.0)
        erhitzer = b.karte("erhitzer", 480, 200, "Erhitzer",
                           V_nenn=LUFTMENGE_M3H, dp_nenn=160.0, QH_max=35.0)
        kuehler = b.karte("kuehler", 700, 200, "Kühler",
                          V_nenn=LUFTMENGE_M3H, dp_nenn=200.0, QK_nenn=45.0,
                          T_KW_mittel=6.0, kontaktfaktor=0.6)
        befeuchter = b.karte("dampfbefeuchter", 920, 200, "Dampfbefeuchter",
                             dampftemperatur=180.0, absalzverlust=10.0,
                             max_leistung=14.0, dampfart="E")
        zuluft = b.karte("ventilator", 1140, 200, "Zuluftventilator",
                         rolle="zuluft", V_max=LUFTMENGE_M3H, dp_max=1100.0,
                         dp_konst=1100.0, PE_max=2.8, regelart="F")
        raum = b.karte("einfacher_raum", 1360, 200, "OP und Nebenräume",
                       spez_transmission=0.3, sollwert_stat=22.0)
        # Die Gebaeudeheizung. Ohne sie meldet der Raum seine
        # Unterdeckung (QH_stat) und niemand nimmt sie entgegen: Er bleibt
        # trotzdem auf seinem Sollwert, und die Waerme dafuer taucht in
        # keiner Bilanz auf - das Gebaeude heizte sich umsonst. Der
        # Lueftungserhitzer deckt das nicht; er waermt die Zuluft, nicht
        # die Huelle. Auslegung: 0,3 kW/K x 32 K = 9,6 kW
        gebaeudeheizung = b.karte("statische_heizung", 1360, 620,
                                  "Gebäudeheizung", QH_nenn=12.0)
        abluft = b.karte("ventilator", 1580, 200, "Abluftventilator",
                         rolle="abluft", V_max=LUFTMENGE_M3H, dp_max=700.0,
                         dp_konst=700.0, PE_max=1.8, regelart="F")
        fortluft = b.karte("fortluft", 260, 420, "Fortluft")

        kaskade = b.karte("kaskade", 480, 20, "Raum-/Zuluft-Kaskade",
                          T_Raum_min=22.0, T_AU_min=15.0, T_Raum_max=24.0,
                          T_AU_max=30.0, T_ZU_min=18.0, T_ZU_max=28.0, xp=5.0,
                          # WRG und Register wärmen, ein Kühler kühlt.
                          waermestufen=2, kaeltestufen=1)
        feuchteregler = b.karte("p_regler", 700, 20, "Feuchteregelung",
                                xp_1=5.0, xp_2=2.0, sollwert_2=7.0)
        # Frostschutz: Bei 100 % Aussenluft ohne Umluft steht der Erhitzer
        # unmittelbar hinter der Waermerueckgewinnung. Faellt die Luft dort
        # unter den Gefrierpunkt, friert das Register ein. Der Sequenzregler
        # ueberwacht die Temperatur nach der WRG und fordert Waerme an, sobald
        # sie unter 5 GradC faellt - unabhaengig davon, was die Raumkaskade
        # gerade will. Beide fordern ueber ein Maximalglied denselben Erhitzer.
        frostschutz = b.karte("sequenzregler", 920, 20, "Frostschutz",
                              unterer_sw=5.0, oberer_sw=8.0, xp=3.0,
                              # Nur waermer_1 ist verdrahtet.
                              waermestufen=1, kaeltestufen=1)
        erhitzerstellung = b.karte("maximalwert", 1140, 20, "Erhitzeranforderung")

        zeitplan = b.karte(
            "wochenzeitplan", 1140, 620, "Dauerbetrieb",
            **{f"von_{tag}": 0.0 for tag in WOCHENTAGE},
            **{f"bis_{tag}": 1.0 for tag in WOCHENTAGE},
        )
        # Nachts Reduzierung auf 50 % - im OP-Bereich uebliche Absenkung
        # ausserhalb des Betriebs, aber nie Stillstand.
        tagesprofil = b.karte("tageslastprofil", 1360, 620, "Tageslastprofil",
                              lastgang_1=[0.5] * 6 + [1.0] * 12 + [0.5] * 6)
        betrieb = b.karte("anlagenbetrieb", 1580, 620, "Anlagenbetrieb")
        grundlast = b.karte("faktor", 1800, 620, "Grundlast", faktor=100.0)
        ventilatorstellung = b.karte("maximalwert", 2020, 620, "Ventilatorstellung")

        beleuchtung = b.karte("beleuchtung", 1800, 420, "OP-Beleuchtung und Geräte",
                              spez_leistung=54.0, grundflaeche=FLAECHE_M2,
                              nennbeleuchtung=1000.0)
        bilanz = b.karte("bilanz", 2240, 200, "Jahresbilanz",
                         preis_strom=280.0, preis_waerme=95.0, preis_kaelte=95.0,
                         preis_wasser=4.2, ht_von=6.0 / 24.0, ht_bis=19.0 / 24.0)
        logger = b.karte("datenlogger", 2240, 20, "Datenlogger",
                         namen=["T Raum", "F Raum", "Sollwert", "T Zuluft",
                                "Wärme WRG"] + [""] * 5,
                         einheiten=["°C", "g/kg", "°C", "°C", "kW"] + [""] * 5)

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
        b.verbinde(kaskade, "waermer_2", erhitzerstellung, "ein_1")
        b.verbinde(wrg, "T_ZU", frostschutz, "istwert")
        b.verbinde(frostschutz, "waermer_1", erhitzerstellung, "ein_2")
        b.verbinde(erhitzerstellung, "ausgang", erhitzer, "stellgroesse")
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
                         personen=12.0, waerme_je_person=150.0, feuchte_je_person=70.0,
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
        # Erst die benannten Groessen auf ihre Steckplaetze, dann den Pfeil: Ein
        # Pfeil auf den Datenlogger belegt die freien Plaetze der Reihe nach, und
        # zwar so viele, wie die Gegenkarte Messwerte anbietet. Stand er zuerst,
        # verschob ein neuer Ausgang an einer Karte alle folgenden Nummern - das
        # Anlegen der Kuehlflaeche liess so jede Vorlage mit "Der Anschluss
        # 'wert_5' ist schon belegt" scheitern.
        b.verbinde(wrg, "Q_WRG", logger, "wert_5")
        b.pfeil(raum, logger)
        b.pfeil(kaskade, logger)

    return b.anlage
