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

from core.vorlagen.bauhilfe import (
    Bauplatz, auswertung_verdrahten, betrieb_verdrahten,
    kaskade_verdrahten, lasten_verdrahten, luftweg_verdrahten,
)

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
    lasten: int
    kuehlflaeche: int
    statische_heizung: int


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
    sollwert_stat=None, raumname="Raum",
    zeitplan_tage=WERKTAGE, zeitplan_von=7.0, zeitplan_bis=18.0,
    lastgang=None, beleuchtung_w_m2=8.0, beleuchtung_lux=500.0,
    personen=0.0, waerme_je_person=75.0, feuchte_je_person=50.0,
    geraete_w_m2=0.0, grundlast_w_m2=0.0,
    sollwert_kuehl=0.0, QK_flaeche=0.0, QH_statisch=0.0,
):
    """Baut das Geruest und liefert seine Karten zurueck.

    Der Bauplatz bleibt OFFEN - der Aufrufer ergaenzt und schliesst ihn selbst
    (with-Block um standardgeraet herum).

    PE_zuluft/PE_abluft duerfen fehlen; dann wird die Wellenleistung aus
    Luftmenge, Druck und einem Wirkungsgrad von 0,65 gerechnet - dieselbe
    Rechnung, die in den Kopfkommentaren der Anlagen steht.
    """
    # Der Sollwert der Gebaeudeheizung ist derselbe wie der untere
    # Raumsollwert der Kaskade. Liegt er darunter, entsteht ein Band, in dem
    # die Heizkoerper den Raum festhalten (T_Raum = max(T_frei, Sollwert)) und
    # die Kaskade gegen eine Abweichung integriert, die sie nicht wegregeln
    # kann - die Produktionshalle verlor so drei Stunden je Woche, bis ihre
    # beiden Sollwerte zusammengelegt wurden. Er steht deshalb nicht als
    # eigene Zahl da, sondern folgt T_Raum_min; wer ihn ausdruecklich anders
    # will, gibt ihn an. tests/test_sollwerte_passen_zusammen.py haelt die
    # Regel fuer alle Vorlagen fest.
    if sollwert_stat is None:
        sollwert_stat = T_Raum_min

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
                   spez_transmission=transmission, sollwert_stat=sollwert_stat,
                   sollwert_kuehl=sollwert_kuehl)
    # Eine Kuehlflaeche im Raum, wo die Luftmenge nach Hygiene bemessen ist und
    # die innere Last mehr hergibt, als sie abfuehren kann (siehe
    # core/bausteine/statische_kuehlung.py). QK_flaeche = 0 heisst: keine.
    kuehlflaeche = b.karte("statische_kuehlung", 1140, 420, "Kühlfläche",
                           QK_nenn=QK_flaeche)
    # Die Gebaeudeheizung. Ohne sie meldet der Raum seine Unterdeckung
    # (QH_stat) und niemand nimmt sie entgegen: Er bleibt trotzdem auf seinem
    # Sollwert, und die Waerme dafuer taucht in keiner Bilanz auf - das
    # Gebaeude heizte sich umsonst. Der Lueftungserhitzer allein deckt das
    # nicht; er waermt die Zuluft, nicht die Huelle.
    statische_heizung = b.karte("statische_heizung", 1140, 620, "Gebäudeheizung",
                                QH_nenn=QH_statisch)
    abluft = b.karte("ventilator", 1360, 200, "Abluftventilator",
                     rolle="abluft", V_max=luftmenge, dp_max=dp_abluft,
                     dp_konst=dp_abluft, regelart="F",
                     PE_max=PE_abluft if PE_abluft is not None
                     else round(leistung(luftmenge, dp_abluft), 2))
    fortluft = b.karte("fortluft", 260, 420, "Fortluft")

    kaskade = b.karte("kaskade", 480, 20, "Raum-/Zuluft-Kaskade",
                      T_Raum_min=T_Raum_min, T_AU_min=15.0,
                      T_Raum_max=T_Raum_max, T_AU_max=30.0,
                      T_ZU_min=T_ZU_min, T_ZU_max=T_ZU_max, xp=5.0,
                      # Verdrahtet sind waermer_1 (Rueckgewinnung),
                      # waermer_2 (Register) und kaelter_1 (Kuehler). Weiter
                      # darf die Regelabweichung nicht laufen, sonst laedt sie
                      # sich wirkungslos auf.
                      waermestufen=2, kaeltestufen=1)

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
    lasten = b.karte("innere_lasten", 1360, 420, "Innere Lasten",
                     personen=personen, waerme_je_person=waerme_je_person,
                     feuchte_je_person=feuchte_je_person, grundflaeche=flaeche,
                     geraete=geraete_w_m2, grundlast=grundlast_w_m2)
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
    b.pfeil(betrieb, beleuchtung)

    luftweg_verdrahten(b, aussenluft, wrg, (erhitzer, kuehler), zuluft, raum,
                       abluft, fortluft)
    kaskade_verdrahten(b, wetter, raum, zuluft, kaskade, {
        "waermer_1": wrg, "waermer_2": erhitzer, "kaelter_1": kuehler,
    })
    betrieb_verdrahten(b, (zeitplan, tagesprofil), betrieb, tagesprofil,
                       grundlast, ventilatorstellung, (zuluft, abluft))
    lasten_verdrahten(b, tagesprofil, beleuchtung, lasten, raum,
                      gebaeudeheizung=statische_heizung,
                      kuehlflaeche=kuehlflaeche)
    auswertung_verdrahten(
        b,
        (zuluft, abluft, erhitzer, kuehler, beleuchtung, kuehlflaeche,
         statische_heizung),
        bilanz, logger,
        protokoll=((wrg, "Q_WRG", "wert_5"),),
        pfeile=(raum, kaskade),
    )

    return Geraet(
        bauplatz=b, wetter=wetter, aussenluft=aussenluft, wrg=wrg,
        erhitzer=erhitzer, kuehler=kuehler, zuluft=zuluft, raum=raum,
        abluft=abluft, fortluft=fortluft, kaskade=kaskade, zeitplan=zeitplan,
        lasten=lasten, kuehlflaeche=kuehlflaeche,
        statische_heizung=statische_heizung,
        tagesprofil=tagesprofil, betrieb=betrieb, grundlast=grundlast,
        ventilatorstellung=ventilatorstellung, bilanz=bilanz, logger=logger,
    )
