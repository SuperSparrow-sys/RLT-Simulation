"""Verkaufsraum - hohe Beleuchtungslast, lange Oeffnungszeiten.

Der Fall, in dem die inneren Lasten den Verbrauch bestimmen. Ein Supermarkt
beleuchtet mit 25 W/m2 und laeuft montags bis samstags von 7 bis 21 Uhr; die
Beleuchtung allein erzeugt so viel Waerme, dass die Anlage einen grossen Teil
des Jahres kuehlt statt heizt - auch im Winter. Genau das soll diese Vorlage
zeigen.

AUSLEGUNG

    Geometrie      1200 m2, 4,0 m hoch -> 4800 m3
    Luftmenge      7 000 m3/h -> 1,46 facher Luftwechsel
    Transmission   viel Glasfront -> rund 1,5 kW/K
    Heizlast       1,5 x 32 K + 7000 x 0,34 x 32 x 0,25 = 48,0 + 19,0 = 67,0 kW
                   -> Erhitzer 80 kW
    Innere Last    Beleuchtung 25 W/m2 x 1200 m2                     = 30 kW
                   -> Kuehler 70 kW (Beleuchtung, Personen, Sonne)
    Ventilator     7000 m3/h, 850 Pa, Wirkungsgrad 0,65              = 2,54 kW
                   -> SFP 0,36 W/(m3/h)
"""

from core.vorlagen.anlagen._geraet import WOCHENTAGE, standardgeraet, tagesgang

NAME = "Verkaufsraum"
BESCHREIBUNG = (
    "1200 m² Verkaufsfläche, 25 W/m² Beleuchtung, Mo–Sa 7–21 Uhr - "
    "die inneren Lasten bestimmen den Verbrauch"
)

FLAECHE_M2 = 1200.0
LUFTMENGE_M3H = 7000.0
#: Lichte Raumhöhe - der Prüfstand rechnet daraus den Luftwechsel.
HOEHE_M = 4.0

ERWARTUNG = {
    # Die Beleuchtung deckt einen Teil der Heizlast; der Heizbedarf liegt
    # deshalb unter dem eines Bueros gleicher Groesse, der Kuehlbedarf darueber.
    "heizwaerme_kwh_m2a": (5.0, 60.0),
    "kaelte_kwh_m2a": (5.0, 80.0),
    "sfp_w_m3h": (0.25, 0.95),
    "luftwechsel_1h": (1.2, 1.8),
}


def baue(projekt_id, name=NAME):
    g = standardgeraet(
        projekt_id, name, BESCHREIBUNG,
        luftmenge=LUFTMENGE_M3H, flaeche=FLAECHE_M2, transmission=1.5,
        QH_max=80.0, QK_nenn=70.0, dp_zuluft=850.0, dp_abluft=650.0,
        raumname="Verkaufsfläche", sollwert_stat=12.0,
        zeitplan_tage=WOCHENTAGE[:6], zeitplan_von=7.0, zeitplan_bis=21.0,
        lastgang=tagesgang(0.2, 1.0, 0.3, tagstunden=(6, 21)),
        beleuchtung_w_m2=25.0, beleuchtung_lux=750.0,
    )
    g.bauplatz.__exit__(None, None, None)
    return g.bauplatz.anlage
