import pytest

from core import graph
from core.bausteine import basis, lade_alle

lade_alle()


def karte(karte_id, typ, parameter=None):
    klasse = basis.hole(typ)
    p = klasse.vorgabeparameter()
    p.update(parameter or {})
    ports = graph.erzeuge_ports(klasse, p, karte_id, ab_id=karte_id * 100)
    return graph.KarteInstanz(
        id=karte_id, typ=typ, name=klasse.NAME, parameter=p,
        baustein=klasse(), ports=ports,
    )


# --------------------------------------------------------------- Portanlage

def test_feste_ports_behalten_ihren_schluessel():
    k = karte(1, "erhitzer")
    schluessel = {p.schluessel for p in k.ports}
    assert "luft_ein" in schluessel
    assert "stellgroesse" in schluessel


def test_dynamische_ports_werden_nummeriert():
    k = karte(1, "sammler")
    eingaenge = [p for p in k.ports if p.richtung == basis.EINGANG]
    assert [p.schluessel for p in eingaenge] == ["luft_ein_1"]
    assert eingaenge[0].basis == "luft_ein"


def test_ventilator_bekommt_abluftrollen_nach_parameter():
    k = karte(1, "ventilator", {"rolle": "abluft"})
    rollen = {p.schluessel: p.rolle for p in k.ports}
    assert rollen["luft_ein"] == basis.ABLUFT


# ---------------------------------------------------- automatische Verdrahtung

def test_ein_pfeil_verdrahtet_den_luftweg():
    a, b = karte(1, "erhitzer"), karte(2, "kuehler")
    paare = graph.verdrahte(a, b, belegt=set())
    assert len(paare) == 1
    von, nach = paare[0]
    assert von.schluessel == "luft_aus"
    assert nach.schluessel == "luft_ein"


def test_pfeil_vom_raum_zur_wrg_trifft_den_abluftweg():
    raum, wrg = karte(1, "einfacher_raum"), karte(2, "wrg")
    paare = graph.verdrahte(raum, wrg, belegt=set())
    assert [(v.basis, n.schluessel) for v, n in paare] == [
        ("abluft_aus", "abluft_ein")
    ]


def test_pfeil_vom_regler_verdrahtet_stellgroesse_und_istwert():
    regler, erhitzer = karte(1, "p_regler"), karte(2, "erhitzer")
    paare = graph.verdrahte(regler, erhitzer, belegt=set())
    richtungen = {(v.schluessel, n.schluessel) for v, n in paare}
    assert ("ausgang_1", "stellgroesse") in richtungen or (
        "ausgang_2", "stellgroesse"
    ) in richtungen
    # Rueckrichtung: der Messwert des Erhitzers geht auf den Istwert des Reglers
    assert any(v.karte_id == 2 and n.karte_id == 1 for v, n in paare)


def test_gleiche_schluessel_werden_bevorzugt_gepaart():
    """Die Wetterkarte am Raum verdrahtet T_AU auf T_AU, QH_S auf QH_S und so fort."""
    wetter, raum = karte(1, "wetter"), karte(2, "raum")
    paare = graph.verdrahte(wetter, raum, belegt=set())
    zuordnung = {v.schluessel: n.schluessel for v, n in paare}
    assert zuordnung["T_AU"] == "T_AU"
    assert zuordnung["QH_S"] == "QH_S"
    assert zuordnung["QH_H"] == "QH_H"
    assert len(paare) == 7


def test_wrg_zur_fortluft_nimmt_den_abluftweg():
    """Der Zuluftausgang darf niemals auf einen Fortluftanschluss laufen."""
    wrg, fortluft = karte(1, "wrg"), karte(2, "fortluft")
    paare = graph.verdrahte(wrg, fortluft, belegt=set())
    assert [v.schluessel for v, _ in paare] == ["abluft_aus"]


def test_aussenluft_geht_auf_den_zuluftweg():
    aussenluft, wrg = karte(1, "aussenluft"), karte(2, "wrg")
    paare = graph.verdrahte(aussenluft, wrg, belegt=set())
    assert [n.schluessel for _, n in paare] == ["zuluft_ein"]


def test_sammler_nimmt_abluft_an():
    """Verteiler und Sammler haben eine neutrale Luftrolle."""
    raum, sammler = karte(1, "einfacher_raum"), karte(2, "sammler")
    paare = graph.verdrahte(raum, sammler, belegt=set())
    assert [(v.basis, n.schluessel) for v, n in paare] == [
        ("abluft_aus", "luft_ein_1")
    ]


def test_raum_geht_nicht_auf_den_zuluftweg_einer_wrg():
    raum, wrg = karte(1, "einfacher_raum"), karte(2, "wrg")
    paare = graph.verdrahte(raum, wrg, belegt=set())
    assert all(n.schluessel != "zuluft_ein" for _, n in paare)


def test_leistungen_treffen_die_richtige_bilanzspalte():
    """Ohne eigene Energierollen liefe die Ventilatorleistung auf 'Wärme'."""
    ventilator, bilanz = karte(1, "ventilator"), karte(2, "bilanz")
    paare = graph.verdrahte(ventilator, bilanz, belegt=set())
    zuordnung = {v.schluessel: n.schluessel for v, n in paare}
    assert zuordnung["PE"] == "strom_1"
    assert "waerme_1" not in zuordnung.values()


def test_erhitzer_speist_die_waermespalte():
    erhitzer, bilanz = karte(1, "erhitzer"), karte(2, "bilanz")
    zuordnung = {
        v.schluessel: n.schluessel
        for v, n in graph.verdrahte(erhitzer, bilanz, belegt=set())
    }
    assert zuordnung["QH"] == "waerme_1"


def test_luftwaescher_speist_strom_und_wasser():
    waescher, bilanz = karte(1, "luftwaescher"), karte(2, "bilanz")
    zuordnung = {
        v.schluessel: n.schluessel
        for v, n in graph.verdrahte(waescher, bilanz, belegt=set())
    }
    assert zuordnung["PE_Pumpe"] == "strom_1"
    assert zuordnung["wasser"] == "wasser_1"


def test_datenlogger_belegt_die_spalten_der_reihe_nach():
    """Ein Textvergleich wuerde hier 'wert_10' vor 'wert_2' einsortieren."""
    raum, logger = karte(1, "einfacher_raum"), karte(2, "datenlogger")
    paare = graph.verdrahte(raum, logger, belegt=set())
    ziele = [n.schluessel for _, n in paare]
    assert ziele[:2] == ["wert_1", "wert_2"]


def test_zuluft_darf_nicht_in_den_umlufteingang():
    """Umluft ist zurueckgefuehrte Abluft, nicht Zuluft.

    Der einzige Umluftanschluss im Programm ist mischkammer.umluft_ein. Ein
    Erhitzer, der auf eine Mischkammer gezogen wird, gehoert an den
    Aussenlufteingang - etwa als Vorerhitzer im Aussenluftweg.
    """
    erhitzer, mischkammer = karte(1, "erhitzer"), karte(2, "mischkammer")
    zuordnung = {
        v.schluessel: n.schluessel
        for v, n in graph.verdrahte(erhitzer, mischkammer, belegt=set())
    }
    assert zuordnung.get("luft_aus") == "aussenluft_ein"


def test_abluft_darf_in_den_umlufteingang():
    raum, mischkammer = karte(1, "einfacher_raum"), karte(2, "mischkammer")
    zuordnung = {
        v.basis: n.schluessel
        for v, n in graph.verdrahte(raum, mischkammer, belegt=set())
    }
    assert zuordnung.get("abluft_aus") == "umluft_ein"


def test_mehrdeutige_zuordnung_wird_gemeldet():
    """Die WRG ist die einzige Karte mit zwei Luftrollen am Ausgang.

    An einem neutralen Sammler ist damit nicht entscheidbar, ob der Zuluft- oder
    der Abluftstrang gemeint ist. Die Wahl faellt wiederholbar nach der
    Portreihenfolge; die verworfene Moeglichkeit muss aber benennbar bleiben,
    damit der Editor den Pfeil als mehrdeutig kennzeichnen kann.
    """
    wrg, sammler = karte(1, "wrg"), karte(2, "sammler")
    gewaehlt = graph.verdrahte(wrg, sammler, belegt=set())
    verworfen = graph.alternativen(wrg, sammler, belegt=set())

    assert [v.schluessel for v, _ in gewaehlt] == ["zuluft_aus"]
    assert [v.schluessel for v, _ in verworfen] == ["abluft_aus"]


def test_eindeutige_zuordnung_meldet_keine_alternative():
    erhitzer, kuehler = karte(1, "erhitzer"), karte(2, "kuehler")
    assert graph.alternativen(erhitzer, kuehler, belegt=set()) == []


def test_belegte_ports_werden_uebersprungen():
    a, b = karte(1, "erhitzer"), karte(2, "kuehler")
    belegt = {p.id for p in a.ports if p.schluessel == "luft_aus"}
    assert graph.verdrahte(a, b, belegt=belegt) == []


def test_dynamischer_port_waechst_nach_dem_verbinden_nach():
    verteiler, erhitzer = karte(1, "verteiler"), karte(2, "erhitzer")
    paare = graph.verdrahte(verteiler, erhitzer, belegt=set())
    belegt = {v.id for v, _ in paare}
    neue = graph.fehlende_ports(verteiler, belegt)
    assert [p.schluessel for p in neue] == ["luft_aus_2"]


def test_kein_nachwachsen_solange_ein_port_frei_ist():
    verteiler = karte(1, "verteiler")
    assert graph.fehlende_ports(verteiler, belegt=set()) == []


def test_zwei_raeume_belegen_nacheinander_die_verteilerabgaenge():
    verteiler = karte(1, "verteiler")
    raum_a, raum_b = karte(2, "einfacher_raum"), karte(3, "einfacher_raum")

    paare_a = graph.verdrahte(verteiler, raum_a, belegt=set())
    belegt = {v.id for v, _ in paare_a} | {n.id for _, n in paare_a}
    verteiler.ports += graph.fehlende_ports(verteiler, belegt)

    paare_b = graph.verdrahte(verteiler, raum_b, belegt=belegt)
    assert paare_a[0][0].schluessel == "luft_aus_1"
    assert paare_b[0][0].schluessel == "luft_aus_2"


# ------------------------------------------------------------------ Sortierung

def baue_graph(karten, kanten):
    verbindungen = []
    for von_id, von_port, nach_id, nach_port in kanten:
        v = next(p for p in karten[von_id].ports if p.schluessel == von_port)
        n = next(p for p in karten[nach_id].ports if p.schluessel == nach_port)
        verbindungen.append(graph.VerbindungInstanz(von_port=v, nach_port=n))
    return graph.Anlagengraph(karten=karten, verbindungen=verbindungen)


def test_reihenfolge_ist_topologisch():
    karten = {i: karte(i, t) for i, t in [(1, "erhitzer"), (2, "kuehler"), (3, "luftwaescher")]}
    g = baue_graph(
        karten,
        [(1, "luft_aus", 2, "luft_ein"), (2, "luft_aus", 3, "luft_ein")],
    )
    assert g.reihenfolge() == [1, 2, 3]


def test_zyklus_wird_aufgebrochen_und_gemeldet():
    karten = {i: karte(i, t) for i, t in [(1, "erhitzer"), (2, "kuehler")]}
    g = baue_graph(
        karten,
        [(1, "luft_aus", 2, "luft_ein"), (2, "QK", 1, "stellgroesse")],
    )
    reihenfolge = g.reihenfolge()
    assert sorted(reihenfolge) == [1, 2]
    assert g.rueckkanten() == {(2, 1)}


def test_ventilator_belegt_nicht_die_aussentemperatur_des_raums():
    """Der Austritt eines Ventilators ist nicht die Aussentemperatur.

    Vor der Verschaerfung der Signalrollen verband ein Pfeil vom Ventilator zum
    Raum ausser dem Luftweg auch T_aus mit T_AU - beide trugen die Rolle Messwert.
    Danach fand die Wetterkarte den Eingang belegt und verteilte ihre Strahlung auf
    Feuchte und innere Last.
    """
    ventilator, raum = karte(1, "ventilator"), karte(2, "einfacher_raum")
    paare = graph.verdrahte(ventilator, raum, belegt=set())
    assert [(v.schluessel, n.basis) for v, n in paare] == [("luft_aus", "zuluft_ein")]


def test_wetterkarte_trifft_die_gleichnamigen_eingaenge_des_raums():
    wetter, raum = karte(1, "wetter"), karte(2, "raum")
    zuordnung = {v.schluessel: n.schluessel for v, n in graph.verdrahte(wetter, raum, set())}
    assert zuordnung == {
        "T_AU": "T_AU", "F_AU": "F_AU", "QH_S": "QH_S", "QH_O": "QH_O",
        "QH_W": "QH_W", "QH_N": "QH_N", "QH_H": "QH_H",
    }


def test_zeitplan_findet_den_anlagenbetrieb():
    zeitplan, betrieb = karte(1, "wochenzeitplan"), karte(2, "anlagenbetrieb")
    paare = graph.verdrahte(zeitplan, betrieb, belegt=set())
    assert [(v.schluessel, n.basis) for v, n in paare] == [("betrieb", "zeitplan")]


def test_ferien_und_lastgang_finden_ihre_eigenen_eingaenge():
    betrieb = karte(9, "anlagenbetrieb")
    belegt = set()
    for typ, erwartet in (("ferien", "ferien"), ("tageslastprofil", "tagesprofil")):
        paare = graph.verdrahte(karte(1, typ), betrieb, belegt)
        assert [n.basis for _, n in paare] == [erwartet], typ
        belegt |= {n.id for _, n in paare}


def test_anlagenbetrieb_erreicht_die_verbraucher():
    betrieb, licht = karte(1, "anlagenbetrieb"), karte(2, "beleuchtung")
    zuordnung = {v.schluessel: n.schluessel for v, n in graph.verdrahte(betrieb, licht, set())}
    assert zuordnung.get("betrieb") == "betrieb"


def test_messwerte_landen_im_datenlogger():
    wrg, logger = karte(1, "wrg"), karte(2, "datenlogger")
    paare = graph.verdrahte(wrg, logger, belegt=set())
    assert [(v.schluessel, n.schluessel) for v, n in paare] == [("Q_WRG", "wert_1")]


def test_raum_meldet_seinen_heizbedarf_an_die_statische_heizung():
    raum, heizung = karte(1, "einfacher_raum"), karte(2, "statische_heizung")
    zuordnung = {v.schluessel: n.schluessel for v, n in graph.verdrahte(raum, heizung, set())}
    assert zuordnung.get("QH_stat") == "QH_stat"


def test_regler_greift_auf_die_traege_stufe():
    """In der Excel traegt nur Regler 2 einen Sollwert; Regler 1 steht auf '???'.

    Ein Pfeil vom Regler auf einen Erhitzer muss deshalb die traege Stufe nehmen,
    sonst regelt die Anlage gegen einen Sollwert von null.
    """
    regler, erhitzer = karte(1, "p_regler"), karte(2, "erhitzer")
    paare = graph.verdrahte(regler, erhitzer, belegt=set())
    hin = [(v.schluessel, n.schluessel) for v, n in paare if v.karte_id == 1]
    zurueck = [(v.schluessel, n.schluessel) for v, n in paare if v.karte_id == 2]
    assert hin == [("ausgang_2", "stellgroesse")]
    assert zurueck == [("T_aus", "istwert_2")]


def test_signalausgang_speist_mehrere_verbraucher():
    """Eine Wetterkarte versorgt Aussenluft, Raum und Regler zugleich."""
    wetter = karte(1, "wetter")
    belegt = set()
    getroffen = []
    for nummer, typ in enumerate(("aussenluft", "einfacher_raum", "kaskade"), start=2):
        paare = graph.verdrahte(wetter, karte(nummer, typ), belegt)
        belegt |= {n.id for _, n in paare}
        getroffen.append([v.schluessel for v, _ in paare])
    assert getroffen[0] == ["T_AU", "F_AU"]
    assert getroffen[1] == ["T_AU", "F_AU"]
    assert getroffen[2] == ["T_AU"]


def test_luftausgang_bleibt_einem_strang_vorbehalten():
    erhitzer = karte(1, "erhitzer")
    erster = graph.verdrahte(erhitzer, karte(2, "kuehler"), set())
    belegt = {v.id for v, _ in erster} | {n.id for _, n in erster}
    assert graph.verdrahte(erhitzer, karte(3, "kuehler"), belegt) == []


def test_namenloser_istwert_bleibt_bei_mehrdeutigkeit_frei():
    """Der Raum bietet mehrere Messwerte an - welcher gemeint ist, ist offen."""
    raum, feuchteregler = karte(1, "einfacher_raum"), karte(2, "hysterese_regler")
    assert graph.verdrahte(raum, feuchteregler, belegt=set()) == []


def test_namenloser_istwert_wird_bei_eindeutigkeit_belegt():
    erhitzer, regler = karte(1, "erhitzer"), karte(2, "p_regler")
    paare = graph.verdrahte(erhitzer, regler, belegt=set())
    assert [(v.schluessel, n.schluessel) for v, n in paare] == [("T_aus", "istwert_2")]
