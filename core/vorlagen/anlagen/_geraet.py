"""Der Grundaufbau, den fast jedes Luftgeraet teilt.

Aussenluft, Waermerueckgewinnung, Erhitzer, Kuehler, Zuluftventilator, Raum,
Abluftventilator, Fortluft - dazu Kaskade, Zeitsteuerung und Bilanz. Zehn
Anlagen unterscheiden sich in ihren Zahlen und in dem, was sie darueber hinaus
brauchen, nicht in diesem Geruest.

Wer eine Anlage baut, ruft standardgeraet() und ergaenzt danach, was seine
Bauart ausmacht - eine Mischkammer, einen Befeuchter, einen zweiten Raum. Die
Rueckgabe nennt alle angelegten Karten, damit sich daran weiterbauen laesst.

Zwei Dinge sind hier fest verdrahtet und sollen es bleiben:

- Die Waermerueckgewinnung haengt an 'waermer_1' der Kaskade, das Register an
  'waermer_2'. Die Kaskade staffelt ihre Ausgaenge; so zieht die kostenlose
  Waerme zuerst an und das Register erst, wenn sie nicht mehr reicht.
- Die Nachtluft faellt nie unter 20 Prozent der Nennmenge. Bei kleiner
  Luftmenge waechst die Autoritaet des Registers je Prozent Ventilstellung so
  stark, dass die Regelung zwischen ihren Anschlaegen kippt - siehe
  tests/test_testanlage_regelkreise.py.
"""

from dataclasses import dataclass

from core.vorlagen.bauhilfe import Bauplatz

WOCHENTAGE = ("montag", "dienstag", "mittwoch", "donnerstag", "freitag",
              "samstag", "sonntag")
WERKTAGE = WOCHENTAGE[:5]

#: Kleinster Anteil der Nennluftmenge ausserhalb der Betriebszeit.
NACHTLUFT_ANTEIL = 0.2


@dataclass
class Geraet:
    """Die Karten des Grundaufbaus, zum Weiterbauen."""
    bauplatz: object
    wetter: int
    aussenluft: int
    wrg: int
    erhitzer: int
    kuehler: int
    zuluft: int
    raum: int
    abluft: int
    fortluft: int
    kaskade: int
    zeitplan: int
    tagesprofil: int
    betrieb: int
    grundlast: int
    ventilatorstellung: int
    bilanz: int
    logger: int


def betriebszeiten(tage, von_stunde, bis_stunde):
    """Wochenzeitplan-Parameter aus Stunden statt Tagesbruchteilen."""
    werte = {f"von_{tag}": 0.0 for tag in WOCHENTAGE}
    werte.update({f"bis_{tag}": 0.0 for tag in WOCHENTAGE})
    for tag in tage:
        werte[f"von_{tag}"] = von_stunde / 24.0
        werte[f"bis_{tag}"] = bis_stunde / 24.0
    return werte


def tagesgang(nacht, tag, abend, tagstunden=(6, 18)):
    """Lastgang ueber 24 Stunden - nachts, tagsueber, abends."""
    beginn, ende = tagstunden
    return [nacht] * beginn + [tag] * (ende - beginn) + [abend] * (24 - ende)


def standardgeraet(
    projekt_id, name, notiz, *, luftmenge, flaeche, transmission,
    QH_max, QK_nenn, rueckwaermzahl=75.0,
    dp_zuluft=900.0, PE_zuluft=None, dp_abluft=700.0, PE_abluft=None,
    T_Raum_min=20.0, T_Raum_max=26.0, T_ZU_min=16.0, T_ZU_max=28.0,
    sollwert_stat=16.0, raumname="Raum",
    zeitplan_tage=WERKTAGE, zeitplan_von=7.0, zeitplan_bis=18.0,
    lastgang=None, beleuchtung_w_m2=8.0, beleuchtung_lux=500.0,
):
    """Baut das Geruest und liefert seine Karten zurueck.

    Der Bauplatz bleibt OFFEN - der Aufrufer ergaenzt und schliesst ihn selbst
    (with-Block um standardgeraet herum).

    PE_zuluft/PE_abluft duerfen fehlen; dann wird die Wellenleistung aus
    Luftmenge, Druck und einem Wirkungsgrad von 0,65 gerechnet - dieselbe
    Rechnung, die in den Kopfkommentaren der Anlagen steht.
    """
    def leistung(volumenstrom, druck):
        return volumenstrom / 3600.0 * druck / 0.65 / 1000.0

    b = Bauplatz(projekt_id, name, notiz=notiz)
    b.__enter__()

    wetter = b.karte("wetter", 40, 20, "Wetterdaten")
    aussenluft = b.karte("aussenluft", 40, 200, "Außenluft")
    wrg = b.karte("wrg", 260, 200, "Wärmerückgewinnung",
                  V_nenn=luftmenge, dp_WRG_nenn=160.0, dp_Bypass_nenn=40.0,
                  rueckwaermzahl=rueckwaermzahl, rueckfeuchtzahl=0.0)
    erhitzer = b.karte("erhitzer", 480, 200, "Erhitzer",
                       V_nenn=luftmenge, dp_nenn=150.0, QH_max=QH_max)
    kuehler = b.karte("kuehler", 700, 200, "Kühler",
                      V_nenn=luftmenge, dp_nenn=190.0, QK_nenn=QK_nenn,
                      T_KW_mittel=6.0, kontaktfaktor=0.55)
    zuluft = b.karte("ventilator", 920, 200, "Zuluftventilator",
                     rolle="zuluft", V_max=luftmenge, dp_max=dp_zuluft,
                     dp_konst=dp_zuluft, regelart="F",
                     PE_max=PE_zuluft if PE_zuluft is not None
                     else round(leistung(luftmenge, dp_zuluft), 2))
    raum = b.karte("einfacher_raum", 1140, 200, raumname,
                   spez_transmission=transmission, sollwert_stat=sollwert_stat)
    abluft = b.karte("ventilator", 1360, 200, "Abluftventilator",
                     rolle="abluft", V_max=luftmenge, dp_max=dp_abluft,
                     dp_konst=dp_abluft, regelart="F",
                     PE_max=PE_abluft if PE_abluft is not None
                     else round(leistung(luftmenge, dp_abluft), 2))
    fortluft = b.karte("fortluft", 260, 420, "Fortluft")

    kaskade = b.karte("kaskade", 480, 20, "Raum-/Zuluft-Kaskade",
                      T_Raum_min=T_Raum_min, T_AU_min=15.0,
                      T_Raum_max=T_Raum_max, T_AU_max=30.0,
                      T_ZU_min=T_ZU_min, T_ZU_max=T_ZU_max, xp=5.0)

    zeitplan = b.karte("wochenzeitplan", 920, 620, "Betriebszeiten",
                       **betriebszeiten(zeitplan_tage, zeitplan_von, zeitplan_bis))
    tagesprofil = b.karte(
        "tageslastprofil", 1140, 620, "Tageslastprofil",
        lastgang_1=lastgang or tagesgang(NACHTLUFT_ANTEIL, 1.0, 0.3),
    )
    betrieb = b.karte("anlagenbetrieb", 1360, 620, "Anlagenbetrieb")
    grundlast = b.karte("faktor", 1580, 620, "Nachtluft-Grundlast", faktor=100.0)
    ventilatorstellung = b.karte("maximalwert", 1800, 620, "Ventilatorstellung")

    beleuchtung = b.karte("beleuchtung", 1580, 420, "Beleuchtung",
                          spez_leistung=beleuchtung_w_m2, grundflaeche=flaeche,
                          nennbeleuchtung=beleuchtung_lux)
    bilanz = b.karte("bilanz", 2020, 200, "Jahresbilanz",
                     preis_strom=280.0, preis_waerme=95.0, preis_kaelte=95.0,
                     preis_wasser=4.2, ht_von=6.0 / 24.0, ht_bis=19.0 / 24.0)
    logger = b.karte("datenlogger", 2020, 20, "Datenlogger",
                     namen=["T Raum", "F Raum", "Sollwert", "T Zuluft",
                            "Wärme WRG"] + [""] * 5,
                     einheiten=["°C", "g/kg", "°C", "°C", "kW"] + [""] * 5)

    # Luftweg
    b.pfeil(wetter, aussenluft)
    b.pfeil(wetter, raum)
    b.verbinde(aussenluft, "luft_aus", wrg, "zuluft_ein")
    b.pfeil(wrg, erhitzer)
    b.pfeil(erhitzer, kuehler)
    b.pfeil(kuehler, zuluft)
    b.pfeil(zuluft, raum)
    b.pfeil(raum, abluft)
    b.verbinde(abluft, "luft_aus", wrg, "abluft_ein")
    b.verbinde(wrg, "abluft_aus", fortluft, "luft_ein")

    # Regelung - erst die zurueckgewonnene Waerme, dann das Register
    b.verbinde(wetter, "T_AU", kaskade, "T_AU")
    b.verbinde(raum, "T_Raum", kaskade, "T_Raum")
    b.verbinde(zuluft, "T_aus", kaskade, "T_ZU")
    b.verbinde(kaskade, "waermer_1", wrg, "stellgroesse")
    b.verbinde(kaskade, "waermer_2", erhitzer, "stellgroesse")
    b.verbinde(kaskade, "kaelter_1", kuehler, "stellgroesse")

    # Betrieb
    b.pfeil(zeitplan, betrieb)
    b.pfeil(tagesprofil, betrieb)
    b.verbinde(tagesprofil, "lastgang_1", grundlast, "ein")
    b.verbinde(betrieb, "stellgrad", ventilatorstellung, "ein_1")
    b.verbinde(grundlast, "ausgang", ventilatorstellung, "ein_2")
    b.verbinde(ventilatorstellung, "ausgang", zuluft, "stellgroesse")
    b.verbinde(ventilatorstellung, "ausgang", abluft, "stellgroesse")
    b.pfeil(betrieb, beleuchtung)
    b.verbinde(beleuchtung, "Q_Bel", raum, "waermelast")

    for karte in (zuluft, abluft, erhitzer, kuehler, beleuchtung):
        b.pfeil(karte, bilanz)
    b.pfeil(raum, logger)
    b.pfeil(kaskade, logger)
    b.verbinde(wrg, "Q_WRG", logger, "wert_5")

    return Geraet(
        bauplatz=b, wetter=wetter, aussenluft=aussenluft, wrg=wrg,
        erhitzer=erhitzer, kuehler=kuehler, zuluft=zuluft, raum=raum,
        abluft=abluft, fortluft=fortluft, kaskade=kaskade, zeitplan=zeitplan,
        tagesprofil=tagesprofil, betrieb=betrieb, grundlast=grundlast,
        ventilatorstellung=ventilatorstellung, bilanz=bilanz, logger=logger,
    )
