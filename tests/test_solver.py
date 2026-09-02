from datetime import datetime, timedelta

import pytest

from core import config, graph, solver
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


def verbinde(karten, kanten):
    verbindungen = []
    for von_id, von_port, nach_id, nach_port in kanten:
        verbindungen.append(
            graph.VerbindungInstanz(
                von_port=karten[von_id].port(von_port),
                nach_port=karten[nach_id].port(nach_port),
            )
        )
    return graph.Anlagengraph(karten=karten, verbindungen=verbindungen)


def wetterstunden(anzahl, t_au=0.0, x_au=0.0):
    start = datetime(2024, 1, 1, 0)
    return [
        {
            "zeitpunkt": start + timedelta(hours=i),
            "t_au": t_au, "x_au": x_au,
            "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
        }
        for i in range(anzahl)
    ]


def einfache_anlage():
    """Wetter -> Aussenluft -> Erhitzer -> Ventilator -> Fortluft."""
    karten = {
        1: karte(1, "wetter"),
        2: karte(2, "aussenluft"),
        3: karte(3, "erhitzer", {"V_nenn": 8200.0, "QH_max": 100.0, "dp_nenn": 100.0}),
        4: karte(4, "ventilator", {"V_max": 8200.0, "PE_max": 4.9, "regelart": "F"}),
        5: karte(5, "fortluft"),
    }
    return karten, verbinde(
        karten,
        [
            (1, "T_AU", 2, "T_AU"),
            (1, "F_AU", 2, "F_AU"),
            (2, "luft_aus", 3, "luft_ein"),
            (3, "luft_aus", 4, "luft_ein"),
            (4, "luft_aus", 5, "luft_ein"),
        ],
    )


def test_volumenstrom_wird_vom_ventilator_rueckwaerts_gesetzt():
    karten, g = einfache_anlage()
    lauf = solver.Solver(g).starte(wetterstunden(1, t_au=5.0))
    assert lauf.stunden[0][3]["V_ein"] == pytest.approx(8200.0)


def test_wetterwerte_erreichen_die_aussenluft():
    karten, g = einfache_anlage()
    lauf = solver.Solver(g).starte(wetterstunden(1, t_au=5.0, x_au=3.0))
    assert lauf.stunden[0][2]["T_AU"] == pytest.approx(5.0)
    assert lauf.stunden[0][2]["F_AU"] == pytest.approx(3.0)


def test_ohne_stellgroesse_heizt_der_erhitzer_nicht():
    karten, g = einfache_anlage()
    lauf = solver.Solver(g).starte(wetterstunden(1, t_au=5.0))
    assert lauf.stunden[0][3]["QH"] == pytest.approx(0.0)


def test_geschlossener_regelkreis_konvergiert():
    """Regler haelt die Temperatur nach dem Erhitzer auf dem Sollwert."""
    karten = {
        1: karte(1, "wetter"),
        2: karte(2, "aussenluft"),
        3: karte(3, "erhitzer", {"V_nenn": 8200.0, "QH_max": 200.0, "dp_nenn": 0.0}),
        4: karte(4, "ventilator", {"V_max": 8200.0, "PE_max": 0.001, "regelart": "-"}),
        5: karte(5, "fortluft"),
        6: karte(6, "p_regler",
                 {"xp_1": 10.0, "xp_2": 5.0, "sollwert_2": 20.0}),
    }
    g = verbinde(
        karten,
        [
            (1, "T_AU", 2, "T_AU"),
            (1, "F_AU", 2, "F_AU"),
            (2, "luft_aus", 3, "luft_ein"),
            (3, "luft_aus", 4, "luft_ein"),
            (4, "luft_aus", 5, "luft_ein"),
            (6, "ausgang_2", 3, "stellgroesse"),
            (3, "QH", 6, "istwert_2"),
        ],
    )
    lauf = solver.Solver(g).starte(wetterstunden(1, t_au=0.0))
    assert lauf.warnungen == []
    # Der Regler faehrt auf, weil der Istwert (QH) unter dem Sollwert liegt.
    assert lauf.stunden[0][3]["QH"] > 0.0


def test_regler_erreicht_den_sollwert_innerhalb_einer_stunde():
    """Der Regler integriert ueber die Iterationen - wie Application.Iteration."""
    karten = {
        1: karte(1, "wetter"),
        2: karte(2, "aussenluft"),
        3: karte(3, "erhitzer", {"V_nenn": 8200.0, "QH_max": 200.0, "dp_nenn": 0.0}),
        4: karte(4, "ventilator", {"V_max": 8200.0, "PE_max": 0.001, "regelart": "-"}),
        5: karte(5, "fortluft"),
        6: karte(6, "p_regler",
                 {"xp_1": 10.0, "xp_2": 5.0, "sollwert_2": 18.0}),
    }
    g = verbinde(
        karten,
        [
            (1, "T_AU", 2, "T_AU"),
            (1, "F_AU", 2, "F_AU"),
            (2, "luft_aus", 3, "luft_ein"),
            (3, "luft_aus", 4, "luft_ein"),
            (4, "luft_aus", 5, "luft_ein"),
            (6, "ausgang_2", 3, "stellgroesse"),
            (3, "T_aus", 6, "istwert_2"),
        ],
    )
    lauf = solver.Solver(g).starte(wetterstunden(1, t_au=0.0))
    assert lauf.warnungen == []
    # Ohne Integration ueber die Iterationen bliebe die Temperatur bei 0 °C
    assert lauf.stunden[0][3]["T_aus"] == pytest.approx(18.0, abs=0.05)


def test_speichergroessen_sehen_in_jeder_iteration_den_stundenanfang():
    """Raum- und Wandtemperatur duerfen innerhalb einer Stunde nicht mitlaufen."""
    karten = {1: karte(1, "raum", {"start_temperatur": 20.0, "spez_beleuchtung": 0.0})}
    g = graph.Anlagengraph(karten=karten, verbindungen=[])
    lauf = solver.Solver(g).starte(wetterstunden(1, t_au=0.0))
    einmal = lauf.stunden[0][1]["T_Raum"]

    # Dieselbe Stunde einzeln gerechnet muss denselben Wert liefern
    from core.bausteine import basis as b
    raum = b.hole("raum")()
    p = karten[1].parameter
    ein = {k: 0.0 for k in ("T_AU", "F_AU", "QH_S", "QH_O", "QH_W", "QH_N",
                            "QH_H", "waermelast", "feuchtelast", "QH_stat")}
    aus, _ = raum.berechne(ein, p, raum.anfangszustand(p))
    assert einmal == pytest.approx(aus["T_Raum"], rel=1e-9)


def test_raum_erfaehrt_seine_abluftmenge_vom_abluftventilator():
    """Anlage!AH33 - die Abluftmenge des Raums kommt vom Abluftventilator."""
    karten = {
        1: karte(1, "wetter"),
        2: karte(2, "aussenluft"),
        3: karte(3, "ventilator", {"V_max": 8200.0, "PE_max": 0.001, "regelart": "-"}),
        4: karte(4, "einfacher_raum", {"spez_transmission": 0.5, "sollwert_stat": -50.0}),
        5: karte(5, "ventilator",
                 {"rolle": "abluft", "V_max": 4500.0, "PE_max": 0.001, "regelart": "-"}),
        6: karte(6, "fortluft"),
    }
    g = verbinde(
        karten,
        [
            (1, "T_AU", 2, "T_AU"),
            (1, "F_AU", 2, "F_AU"),
            (2, "luft_aus", 3, "luft_ein"),
            (3, "luft_aus", 4, "zuluft_ein_1"),
            (4, "abluft_aus_1", 5, "luft_ein"),
            (5, "luft_aus", 6, "luft_ein"),
        ],
    )
    lauf = solver.Solver(g).starte(wetterstunden(1, t_au=0.0))
    assert lauf.stunden[0][4]["abluft_aus_1"].V == pytest.approx(4500.0)


def _gedrosselte_anlage(stellung_zuluft, stellung_abluft, v_max=8000.0):
    """Aussenluft -> Zuluftventilator -> einfacher Raum -> Abluftventilator."""
    karten = {
        1: karte(1, "wetter"),
        2: karte(2, "aussenluft"),
        3: karte(3, "ventilator", {
            "rolle": "zuluft", "V_max": v_max, "PE_max": 4.9, "regelart": "F",
            "stellgroesse": stellung_zuluft,
        }),
        4: karte(4, "einfacher_raum",
                 {"spez_transmission": 0.5, "sollwert_stat": 15.0}),
        5: karte(5, "ventilator", {
            "rolle": "abluft", "V_max": v_max, "PE_max": 3.3, "regelart": "F",
            "stellgroesse": stellung_abluft,
        }),
        6: karte(6, "fortluft"),
    }
    return karten, verbinde(
        karten,
        [
            (1, "T_AU", 2, "T_AU"),
            (1, "F_AU", 2, "F_AU"),
            (2, "luft_aus", 3, "luft_ein"),
            (3, "luft_aus", 4, "zuluft_ein_1"),
            (1, "T_AU", 4, "T_AU"),
            (1, "F_AU", 4, "F_AU"),
            (4, "abluft_aus_1", 5, "luft_ein"),
            (5, "luft_aus", 6, "luft_ein"),
        ],
    )


def test_raum_sieht_zu_und_abluft_im_selben_massstab():
    """Anlage!AH32 = Y20 und AH33 = M42/2 - beide Seiten sind GESTELLTE Stroeme.

    Befund vor dieser Pruefung: Die Zuluft kam gestellt beim Raum an (aus dem
    Vorwaertslauf), die Abluft dagegen mit dem Nennwert (aus dem
    Rueckwaertslauf, der die Stellgroesse noch nicht kennt). Bei 30 Prozent sah
    der Raum 2400 m³/h Zuluft gegen 8000 m³/h Abluft, erfand daraus eine
    Infiltration und rechnete eine deutlich zu hohe statische Heizleistung.
    """
    karten, g = _gedrosselte_anlage(30.0, 30.0)
    lauf = solver.Solver(g).starte(wetterstunden(2, t_au=0.0))
    raum = lauf.stunden[-1][4]

    assert raum["V_zuluft_ein_1"] == pytest.approx(2400.0)
    assert raum["V_abluft_aus_1"] == pytest.approx(2400.0)
    # Kein Zuschlag aus einer erfundenen Infiltration: das Bezugsvolumen des
    # Raums ist die Zuluftmenge, nicht die groessere Nennabluftmenge.
    assert raum["bezugsvolumen"] == pytest.approx(2400.0)


def test_gedrosselter_raum_sieht_keine_infiltration():
    """Gleiche Stellung auf beiden Seiten heisst: kein Nachstroemen von aussen.

    Gegenprobe ist derselbe Raum bei voll aufgedrehten Ventilatoren. Auf ein
    Viertel der Luftmenge gedrosselt muss der Raum bei 0 °C aussen deutlich
    weniger statische Heizleistung brauchen als bei voller Menge - genau das
    ging verloren, als die Nennabluft eine Infiltration vortaeuschte: die
    Drosselung brachte dann 43,9 kW statt 42,9 kW, also gar keine Entlastung.
    """
    _, gedrosselt = _gedrosselte_anlage(30.0, 30.0)
    _, voll = _gedrosselte_anlage(100.0, 100.0)

    a = solver.Solver(gedrosselt).starte(wetterstunden(2, t_au=0.0)).stunden[-1][4]
    b = solver.Solver(voll).starte(wetterstunden(2, t_au=0.0)).stunden[-1][4]

    assert a["QH_stat"] < 0.6 * b["QH_stat"]
    assert a["T_frei"] > b["T_frei"]


def test_bauteile_vor_dem_ventilator_bleiben_auf_dem_nennstrom():
    """Anlage!S13 = S9 = V9 = Y9 - vor dem Ventilator gilt der Nennstrom.

    Die Gegenprobe zur vorigen Pruefung: der Sprung der Luftmenge AM Ventilator
    ist der Mappe getreu und darf nicht mitkorrigiert werden.
    """
    karten, g = _gedrosselte_anlage(30.0, 30.0)
    lauf = solver.Solver(g).starte(wetterstunden(2, t_au=0.0))

    assert lauf.stunden[-1][2]["V"] == pytest.approx(8000.0)   # Aussenluft
    assert lauf.stunden[-1][3]["V_ein"] == pytest.approx(8000.0)  # Ventilatoreintritt
    assert lauf.stunden[-1][3]["V"] == pytest.approx(2400.0)      # Ventilatoraustritt


def test_raum_hinter_einem_sammler_bekommt_seine_abluftmenge():
    """Anlage!AH33 = M42/2 - auch wenn ein Sammler dazwischen steht.

    Befund vor dieser Pruefung: 'Sammler.bedarf' meldet den Grundnamen
    'luft_ein', seine Anschluesse heissen aber 'luft_ein_1', 'luft_ein_2'. Der
    Rueckwaertslauf ordnete nur exakt nach Schluessel zu, die Forderung landete
    nirgends - der Raum bekam gar keine Abluftmenge, gab 0 m³/h ab, der Sammler
    mischte auf 0 °C, und die Waermerueckgewinnung dahinter bekam Fortluft von
    Aussentemperatur statt Raumtemperatur und gewann nichts zurueck.
    """
    karten = {
        1: karte(1, "wetter"),
        2: karte(2, "aussenluft"),
        3: karte(3, "ventilator",
                 {"rolle": "zuluft", "V_max": 6000.0, "PE_max": 0.001, "regelart": "-"}),
        4: karte(4, "einfacher_raum",
                 {"spez_transmission": 0.5, "sollwert_stat": 15.0}),
        5: karte(5, "sammler"),
        6: karte(6, "ventilator",
                 {"rolle": "abluft", "V_max": 4500.0, "PE_max": 0.001, "regelart": "-"}),
        7: karte(7, "fortluft"),
    }
    g = verbinde(
        karten,
        [
            (1, "T_AU", 2, "T_AU"),
            (1, "F_AU", 2, "F_AU"),
            (2, "luft_aus", 3, "luft_ein"),
            (3, "luft_aus", 4, "zuluft_ein_1"),
            (1, "T_AU", 4, "T_AU"),
            (1, "F_AU", 4, "F_AU"),
            (4, "abluft_aus_1", 5, "luft_ein_1"),
            (5, "luft_aus", 6, "luft_ein"),
            (6, "luft_aus", 7, "luft_ein"),
        ],
    )
    lauf = solver.Solver(g).starte(wetterstunden(2, t_au=0.0))
    letzte = lauf.stunden[-1]

    assert letzte[4]["abluft_aus_1"].V == pytest.approx(4500.0)
    # Der Sammler fuehrt die Raumluft weiter, nicht 0 m³/h bei 0 °C.
    assert letzte[5]["V"] == pytest.approx(4500.0)
    assert letzte[5]["T_aus"] == pytest.approx(letzte[4]["T_Raum"])


def test_ein_freier_anschluss_bekommt_keinen_anteil_des_bedarfs():
    """Zwei Anschluesse am Sammler, nur einer belegt - er traegt alles.

    Wuerde die Haelfte an den freien Anschluss gehen, forderte sie niemand
    stromaufwaerts an und ginge stillschweigend verloren: der Raum bekaeme nur
    die halbe Abluftmenge. Genau so steht es in der Vorlage ax_sim_2_1, deren
    Sammler einen zweiten, unbelegten Anschluss hat.
    """
    karten = {
        1: karte(1, "einfacher_raum",
                 {"spez_transmission": 0.5, "sollwert_stat": 15.0}),
        2: karte(2, "sammler"),
        3: karte(3, "ventilator",
                 {"rolle": "abluft", "V_max": 4500.0, "PE_max": 0.001, "regelart": "-"}),
        4: karte(4, "fortluft"),
    }
    # Ein zweiter, freier Anschluss am Sammler - wie ihn die Oberflaeche
    # nachwachsen laesst, sobald der erste belegt ist.
    karten[2].ports.append(
        graph.PortInstanz(
            id=299, karte_id=2, schluessel="luft_ein_2", basis="luft_ein",
            art=basis.LUFT, richtung=basis.EINGANG, rolle=basis.LUFTWEG, nummer=2,
        )
    )
    g = verbinde(
        karten,
        [
            (1, "abluft_aus_1", 2, "luft_ein_1"),
            (2, "luft_aus", 3, "luft_ein"),
            (3, "luft_aus", 4, "luft_ein"),
        ],
    )
    lauf = solver.Solver(g).starte(wetterstunden(1, t_au=0.0))
    assert lauf.stunden[0][1]["abluft_aus_1"].V == pytest.approx(4500.0)


def test_kein_baustein_meldet_einen_bedarf_ins_leere():
    """Jeder Schluessel aus 'bedarf' muss einen Anschluss treffen.

    Genau diese beiden Formen versteht der Rueckwaertslauf: entweder einen Port
    ('luft_ein') oder eine Gruppe nummerierter Ports ueber deren Grundnamen
    ('luft_ein' -> 'luft_ein_1', 'luft_ein_2'). Trifft ein Schluessel keins von
    beidem, verschwindet die Forderung spurlos - sie wirft keinen Fehler,
    sondern hinterlaesst nur eine Null, und genau daran war der Befund beim
    Sammler so lange unsichtbar. Diese Pruefung haelt den Vertrag fuer alle
    Bausteine fest, auch fuer kuenftige.
    """
    for klasse in basis.alle():
        p = klasse.vorgabeparameter()
        ports = graph.erzeuge_ports(klasse, p, 1, ab_id=100)
        schluessel = {q.schluessel for q in ports}
        grundnamen = {q.basis for q in ports}
        aus_bedarf = {
            q.schluessel: 1000.0 for q in ports
            if q.art == basis.LUFT and q.richtung == basis.AUSGANG
        }
        for name in klasse().bedarf(aus_bedarf, p):
            assert name in schluessel or name in grundnamen, (
                f"{klasse.KENNUNG}.bedarf() meldet '{name}', "
                f"dazu gibt es weder einen Port noch eine Portgruppe"
            )


def test_zustandsgroessen_werden_zur_naechsten_stunde_fortgeschrieben():
    karten = {1: karte(1, "raum", {"start_temperatur": 20.0, "spez_beleuchtung": 0.0})}
    g = graph.Anlagengraph(karten=karten, verbindungen=[])
    lauf = solver.Solver(g).starte(wetterstunden(3, t_au=0.0))
    temperaturen = [s[1]["T_Raum"] for s in lauf.stunden]
    assert temperaturen[0] > temperaturen[1] > temperaturen[2]


def test_bilanz_summiert_ueber_alle_stunden():
    karten = {
        1: karte(1, "wetter"),
        2: karte(2, "warmwasser", {"speichervolumen": 1000.0, "verbrauch": 462.0,
                                   "sollwert": 50.0}),
        3: karte(3, "bilanz"),
    }
    g = verbinde(karten, [(2, "QH", 3, "waerme_1")])
    lauf = solver.Solver(g).starte(wetterstunden(10))
    assert lauf.bilanz["waerme"] == pytest.approx(10 * 3.2494672754946725, rel=1e-9)


def test_fortschritt_wird_gemeldet():
    karten, g = einfache_anlage()
    gemeldet = []
    solver.Solver(g).starte(
        wetterstunden(5), fortschritt=lambda i, n: gemeldet.append((i, n))
    )
    assert gemeldet[-1] == (5, 5)


def test_abbruch_beendet_den_lauf_vorzeitig():
    karten, g = einfache_anlage()
    lauf = solver.Solver(g).starte(
        wetterstunden(100), abbruch=lambda: True
    )
    assert len(lauf.stunden) < 100


def test_fehlende_konvergenz_wird_gemeldet_aber_bricht_nicht_ab():
    """Ein zu scharf eingestellter Regler an einem stark ueberdimensionierten Erhitzer.

    500 kW auf 1000 m³/h heben die Luft um mehr als tausend Kelvin, sobald der Regler
    aufmacht. Mit Xp = 5 ueberschiesst er in jedem Durchgang und schwingt, statt sich
    einzupendeln. Der Lauf muss trotzdem weiterlaufen und jede betroffene Stunde
    benennen - eine Anlage, die in einzelnen Stunden schwingt, soll immer noch eine
    brauchbare Jahressumme liefern.
    """
    karten = {
        1: karte(1, "wetter"),
        2: karte(2, "aussenluft"),
        3: karte(3, "erhitzer", {"V_nenn": 1000.0, "QH_max": 500.0, "dp_nenn": 0.0}),
        4: karte(4, "ventilator", {"V_max": 1000.0, "PE_max": 0.001, "regelart": "-"}),
        5: karte(5, "fortluft"),
        6: karte(6, "p_regler", {"xp_1": 10.0, "xp_2": 5.0, "sollwert_2": 20.0}),
    }
    g = verbinde(
        karten,
        [
            (1, "T_AU", 2, "T_AU"),
            (1, "F_AU", 2, "F_AU"),
            (2, "luft_aus", 3, "luft_ein"),
            (3, "luft_aus", 4, "luft_ein"),
            (4, "luft_aus", 5, "luft_ein"),
            (6, "ausgang_2", 3, "stellgroesse"),
            (3, "T_aus", 6, "istwert_2"),
        ],
    )
    lauf = solver.Solver(g).starte(wetterstunden(3))

    # Der Lauf bricht nicht ab
    assert len(lauf.stunden) == 3
    # und er meldet jede betroffene Stunde mit Nummer und Restabweichung
    assert len(lauf.warnungen) == 3
    assert lauf.warnungen[0]["stunde"] == 1
    assert lauf.warnungen[0]["abweichung"] > config.MAX_AENDERUNG
    assert "nicht konvergiert" in lauf.warnungen[0]["text"]
