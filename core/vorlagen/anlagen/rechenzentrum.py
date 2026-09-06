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
    Luftmenge      Aus der Last hergeleitet, nicht geschaetzt. Zulaessig ist
                   ein Temperaturhub von rund 12 K zwischen Zuluft (etwa
                   14 GradC hinter dem Kuehler) und Abluft; daraus folgt
                       V = 100 kW x 3600 / (1,2 x 1,007 x 12 K)
                         = 24 800 m3/h
                   -> 25 000 m3/h, also 20,8 facher Luftwechsel. Das ist fuer
                   ein luftgekuehltes Rechenzentrum normal; die Luft traegt
                   hier die Waerme fort, sie versorgt keine Personen.

                   Mit 10 000 m3/h - dem ersten Ansatz - waere der noetige Hub
                   29,8 K gewesen und der Raum auf ueber 42 GradC gelaufen
                   (nachgerechnet). Die Luftmenge folgt der Last, nicht der
                   Flaeche.
    Transmission   innenliegend, gedaemmt -> rund 0,4 kW/K
    Kuehllast      100 kW innere Last + Transmission im Sommer
                   -> Kuehler 120 kW
    Erhitzer       Keiner. Ein Rechenzentrum heizt nicht.
    Ventilator     25 000 m3/h, 900 Pa, Wirkungsgrad 0,65            = 9,62 kW
                   -> SFP 0,38 W/(m3/h)
"""

from core.vorlagen.bauhilfe import Bauplatz
from core.vorlagen.anlagen._geraet import WOCHENTAGE, betriebszeiten

NAME = "Rechenzentrum"
BESCHREIBUNG = (
    "400 m² Serverfläche, 100 kW Abwärme rund um die Uhr, keine Heizung, "
    "freie Kühlung über die Mischkammer, Kühler nur im Sommer"
)

FLAECHE_M2 = 400.0
LUFTMENGE_M3H = 25000.0
#: Lichte Raumhöhe - der Prüfstand rechnet daraus den Luftwechsel.
HOEHE_M = 3.0
INNERE_LAST_W_M2 = 250.0

ERWARTUNG = {
    # Kein Heizbedarf - das ist die Aussage dieser Anlage.
    "heizwaerme_kwh_m2a": (0.0, 5.0),
    # 100 kW ueber 8760 h waeren 876 MWh = 2190 kWh/(m2*a), wenn alles ueber
    # die Kaeltemaschine ginge. Die freie Kuehlung nimmt den groessten Teil
    # davon ab; wieviel genau, ist gerade die Frage an die Rechnung.
    "kaelte_kwh_m2a": (50.0, 1500.0),
    "sfp_w_m3h": (0.25, 0.95),
    "luftwechsel_1h": (19.0, 23.0),
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
                          T_KW_mittel=10.0, kontaktfaktor=0.5)
        zuluft = b.karte("ventilator", 700, 200, "Zuluftventilator",
                         rolle="zuluft", V_max=LUFTMENGE_M3H, dp_max=900.0,
                         dp_konst=900.0, PE_max=9.62, regelart="F")
        raum = b.karte("einfacher_raum", 920, 200, "Serverfläche",
                       spez_transmission=0.4, sollwert_stat=15.0)
        abluft = b.karte("ventilator", 1140, 200, "Abluftventilator",
                         rolle="abluft", V_max=LUFTMENGE_M3H, dp_max=600.0,
                         dp_konst=600.0, PE_max=6.41, regelart="F")
        verteiler = b.karte("verteiler", 1360, 200, "Umluft/Fortluft",
                            anteile={"luft_aus_1": 80.0, "luft_aus_2": 20.0})
        fortluft = b.karte("fortluft", 260, 420, "Fortluft")

        # Nur die Kuehlseite der Kaskade wird gebraucht.
        kaskade = b.karte("kaskade", 480, 20, "Raumtemperaturregelung",
                          T_Raum_min=24.0, T_AU_min=15.0, T_Raum_max=27.0,
                          T_AU_max=30.0, T_ZU_min=15.0, T_ZU_max=26.0, xp=5.0)
        # Freie Kuehlung: je kaelter es draussen ist, desto weniger Umluft.
        # Der Regler haelt die Zulufttemperatur bei 18 GradC, indem er den
        # Umluftanteil nachfuehrt - ist die Aussenluft kalt, mischt er warme
        # Abluft dazu, ist sie warm, faehrt er auf Umluft und laesst den
        # Kuehler arbeiten.
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
        b.verbinde(zuluft, "T_aus", freikuehlung, "istwert_2")
        b.verbinde(freikuehlung, "ausgang_2", mischkammer, "umluftanteil")

        b.pfeil(zeitplan, betrieb)
        b.pfeil(tagesprofil, betrieb)
        b.verbinde(tagesprofil, "lastgang_1", grundlast, "ein")
        b.verbinde(betrieb, "stellgrad", ventilatorstellung, "ein_1")
        b.verbinde(grundlast, "ausgang", ventilatorstellung, "ein_2")
        b.verbinde(ventilatorstellung, "ausgang", zuluft, "stellgroesse")
        b.verbinde(ventilatorstellung, "ausgang", abluft, "stellgroesse")
        b.pfeil(betrieb, server)
        b.verbinde(server, "Q_Bel", raum, "waermelast")

        for karte in (zuluft, abluft, kuehler, server):
            b.pfeil(karte, bilanz)
        b.pfeil(raum, logger)
        b.pfeil(kaskade, logger)
        b.verbinde(mischkammer, "umluftanteil_ist", logger, "wert_5")

    return b.anlage
