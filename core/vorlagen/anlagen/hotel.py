"""Hotel - die Anlage mit der Wasserseite.

Lueftungstechnisch unauffaellig, dafuer der einzige Fall mit einem
nennenswerten Warmwasserbedarf: Warmwasserbereitung, Zirkulation und
Heizungspumpen laufen rund um die Uhr und stehen in der Bilanz neben der
Luftbehandlung. Diese Vorlage prueft, ob die Verbraucherkarten richtig in die
Jahresbilanz eingehen - der haeufigste stille Fehler ist ein Verbraucher, der
nirgends ankommt.

AUSLEGUNG

    Geometrie      4000 m2 auf mehreren Geschossen, 2,6 m -> 10 400 m3
    Luftmenge      6 000 m3/h -> 0,58 facher Luftwechsel. Hotelzimmer werden
                   nur mit Aussenluft versorgt, nicht temperiert belueftet;
                   die Raumtemperatur haelt die statische Heizung.
    Transmission   grosse Huelle, gedaemmt -> rund 2,0 kW/K
    Heizlast       2,0 x 32 K + 6000 x 0,34 x 32 x 0,25 = 64,0 + 16,3 = 80,3 kW
                   -> Erhitzer 100 kW
    Kuehllast      Personen und Geraete -> Kuehler 60 kW
    Warmwasser     150 Zimmer bei 60 % Belegung und 50 l je Gast und Tag:
                       150 x 0,6 x 50 l x 365 = 1642 m3/a
    Zirkulation    grosses Leitungsnetz: 3,0 m3/h bei 5 K Abkuehlung
                       3,0 x 1,163 x 5 = 17,4 kW Dauerverlust
    Ventilator     6000 m3/h, 750 Pa, Wirkungsgrad 0,65             = 1,92 kW
                   -> SFP 0,32 W/(m3/h)
"""

from core.vorlagen.anlagen._geraet import WOCHENTAGE, standardgeraet

NAME = "Hotel"
BESCHREIBUNG = (
    "4000 m² Hotel, Lüftung der Zimmer, dazu Warmwasserbereitung, "
    "Zirkulation und Heizungspumpen in der Jahresbilanz"
)

FLAECHE_M2 = 4000.0
LUFTMENGE_M3H = 6000.0
#: Lichte Raumhöhe - der Prüfstand rechnet daraus den Luftwechsel.
HOEHE_M = 2.6

ERWARTUNG = {
    # Enthaelt Warmwasser und Zirkulation - deshalb deutlich mehr Waerme je
    # Quadratmeter, als die Lueftung allein braeuchte.
    "heizwaerme_kwh_m2a": (30.0, 150.0),
    "kaelte_kwh_m2a": (0.0, 30.0),
    "sfp_w_m3h": (0.20, 0.90),
    "luftwechsel_1h": (0.4, 0.8),
}


def baue(projekt_id, name=NAME):
    g = standardgeraet(
        projekt_id, name, BESCHREIBUNG,
        luftmenge=LUFTMENGE_M3H, flaeche=FLAECHE_M2, transmission=2.0,
        QH_max=100.0, QK_nenn=60.0, dp_zuluft=750.0, dp_abluft=600.0,
        raumname="Zimmer und Flure", sollwert_stat=20.0,
        zeitplan_tage=WOCHENTAGE, zeitplan_von=0.0, zeitplan_bis=24.0,
        lastgang=[0.6] * 6 + [1.0] * 4 + [0.5] * 8 + [1.0] * 4 + [0.8] * 2,
        beleuchtung_w_m2=6.0, beleuchtung_lux=200.0,
    )
    b = g.bauplatz

    # -- Wasserseite --------------------------------------------------
    warmwasser = b.karte("warmwasser", 1580, 760, "Warmwasserbereitung",
                         speichervolumen=3000.0, verbrauch=1642.0, sollwert=60.0)
    zirkulation = b.karte("zirkulation", 1800, 760, "Zirkulation",
                          volumenstrom=3.0, spreizung=5.0, P_pumpe=0.12)
    pumpen = b.karte("heizungspumpen", 2020, 760, "Heizungspumpen",
                     P_allgemein=1.2, P_wwb=0.4, P_kessel=0.8)

    b.pfeil(g.betrieb, zirkulation)
    b.pfeil(g.betrieb, pumpen)
    for karte in (warmwasser, zirkulation, pumpen):
        b.pfeil(karte, g.bilanz)

    b.__exit__(None, None, None)
    return b.anlage
