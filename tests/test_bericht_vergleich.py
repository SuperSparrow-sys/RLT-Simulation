"""Vorhaben B, nachgezogen: der Bericht eines Laufs, der Teil einer Reihe
ist (core.laeufe.starte_reihe), bekommt einen Abschnitt "im Vergleich zu den
anderen Jahren dieser Reihe" - core.bericht._vergleich_fuer(),
core.ergebnisse.reihen_geschwister().

Baut die Reihe synchron ueber core.ergebnisse.beginne()/abschliesse() -
denselben Aufruf, den core.laeufe._reihe_laufen() im Hintergrund-Thread
macht -, statt einen echten (oder kuenstlich verlangsamten) Solver-Lauf
abzuwarten. Kein SQL hier, wie ueberall in tests/ ueblich: core.ergebnisse
bleibt die einzige Stelle, die die 'simulation'-Tabelle anfasst."""

import re
from datetime import datetime, timedelta

import pytest

from app import create_app
from core import anlagen, bericht, database, ergebnisse, solver
from core.vorlagen import ax_sim_2_1
from core.wetter import speicher


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def _wetter_anlegen(name, anzahl=10, jahr=2024):
    start = datetime(jahr, 1, 1)
    return speicher.datensatz_anlegen(
        name, "upload",
        [
            {
                "zeitpunkt": start + timedelta(hours=i), "t_au": 0.0, "x_au": 4.0,
                "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
            }
            for i in range(anzahl)
        ],
        jahr=jahr,
    )


def _bilanz_karte_id(graph):
    return next(k.id for k in graph.karten.values() if k.typ == "bilanz")


def _lauf_abschliessen(anlage_id, graph, wetter_id, waerme, anzahl=10,
                        reihen_kennung=None, reihen_index=None, reihen_gesamt=None):
    """Legt einen abgeschlossenen Lauf an - wie core.laeufe._reihe_laufen()
    es fuer ein Jahr einer Reihe tut (beginne() dann abschliesse()), nur
    synchron statt in einem Hintergrund-Thread mit echtem Solver."""
    bilanz_karte_id = _bilanz_karte_id(graph)
    kennung = f"kennung-{wetter_id}-{reihen_index}"
    simulation_id = ergebnisse.beginne(
        anlage_id, wetter_id, 0, anzahl, kennung,
        reihen_kennung=reihen_kennung, reihen_index=reihen_index, reihen_gesamt=reihen_gesamt,
    )
    stunden = [{bilanz_karte_id: {"waerme": waerme / anzahl, "kaelte": 0.0,
                                   "strom_ht": 1.0, "strom_nt": 0.5, "wasser": 0.2}}
               for _ in range(anzahl)]
    lauf = solver.Lauf(
        stunden=stunden,
        bilanz={"waerme": waerme, "kaelte": 0.0, "strom_ht": anzahl * 1.0,
                "strom_nt": anzahl * 0.5, "wasser": anzahl * 0.2},
        warnungen=[],
    )
    ergebnisse.abschliesse(simulation_id, lauf, graph, dauer=0.1, status="fertig")
    return simulation_id


def _reihe_anlegen(app, jahre_waerme):
    """Baut eine Anlage mit einer Reihe aus len(jahre_waerme) Jahren -
    liefert (anlage_id, [simulation_id, ...]) in Reihenfolge."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_id = ax_sim_2_1.baue(projekt, "A")
        graph = anlagen.lade_graph(anlage_id)
        reihen_kennung = "reihe-test"
        gesamt = len(jahre_waerme)
        sim_ids = []
        for index, waerme in enumerate(jahre_waerme, start=1):
            wetter_id = _wetter_anlegen(f"Jahr{index}", jahr=2020 + index)
            sim_ids.append(_lauf_abschliessen(
                anlage_id, graph, wetter_id, waerme,
                reihen_kennung=reihen_kennung, reihen_index=index, reihen_gesamt=gesamt,
            ))
    return anlage_id, sim_ids


# ---------------------------------------------------------------------------
# core.ergebnisse.reihen_geschwister()
# ---------------------------------------------------------------------------

def test_reihen_geschwister_none_fuer_einzellauf(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_id = ax_sim_2_1.baue(projekt, "A")
        wetter_id = _wetter_anlegen("W")
        graph = anlagen.lade_graph(anlage_id)
        simulation_id = ergebnisse.speichere(
            anlage_id, wetter_id, 0, 10,
            solver.Lauf(stunden=[{}] * 10, bilanz={"waerme": 1.0, "kaelte": 0.0,
                                                     "strom_ht": 0.0, "strom_nt": 0.0, "wasser": 0.0},
                        warnungen=[]),
            graph, dauer=0.1,
        )
        assert ergebnisse.reihen_geschwister(simulation_id) is None


def test_reihen_geschwister_liefert_alle_in_reihenfolge(app):
    _anlage_id, sim_ids = _reihe_anlegen(app, [100.0, 50.0, 150.0])
    with app.app_context():
        for sim_id in sim_ids:
            assert ergebnisse.reihen_geschwister(sim_id) == sim_ids


# ---------------------------------------------------------------------------
# core.bericht._vergleich_fuer() / daten_fuer()["vergleich"]
# ---------------------------------------------------------------------------

def test_daten_fuer_ohne_reihe_hat_keinen_vergleich(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_id = ax_sim_2_1.baue(projekt, "A")
        wetter_id = _wetter_anlegen("W")
        graph = anlagen.lade_graph(anlage_id)
        simulation_id = ergebnisse.speichere(
            anlage_id, wetter_id, 0, 10,
            solver.Lauf(stunden=[{}] * 10, bilanz={"waerme": 1.0, "kaelte": 0.0,
                                                     "strom_ht": 0.0, "strom_nt": 0.0, "wasser": 0.0},
                        warnungen=[]),
            graph, dauer=0.1,
        )
        daten = bericht.daten_fuer(simulation_id)
    assert daten["vergleich"] is None
    assert daten["diagramme"]["vergleich"] is None


def test_daten_fuer_reihe_mit_nur_einem_lauf_hat_keinen_vergleich(app):
    """Eine 'Reihe' mit nur diesem einen Jahr (z.B. weil alle uebrigen schon
    beim Start scheiterten - core.laeufe._reihe_laufen) ist kein sinnvoller
    Vergleich."""
    _anlage_id, sim_ids = _reihe_anlegen(app, [100.0])
    with app.app_context():
        daten = bericht.daten_fuer(sim_ids[0])
    assert daten["vergleich"] is None


def test_daten_fuer_reihe_liefert_vergleich_mit_allen_jahren(app):
    _anlage_id, sim_ids = _reihe_anlegen(app, [100.0, 50.0, 150.0])
    with app.app_context():
        daten_erstes = bericht.daten_fuer(sim_ids[0])
        daten_zweites = bericht.daten_fuer(sim_ids[1])

    assert daten_erstes["vergleich"] is not None
    assert [l["simulation_id"] for l in daten_erstes["vergleich"]["laeufe"]] == sim_ids
    assert daten_erstes["vergleich"]["diesen_lauf_id"] == sim_ids[0]
    assert daten_zweites["vergleich"]["diesen_lauf_id"] == sim_ids[1]

    waerme_zeile = next(z for z in daten_erstes["vergleich"]["zeilen"] if z["groesse"] == "waerme")
    assert waerme_zeile["label"] == bericht.BILANZ_LABEL["waerme"]
    # Bilanzwerte in MWh (Faktor 1/1000 auf die uebergebenen kWh) - erstes
    # Jahr ist die Basis (Abweichung 0), das zweite (halb so viel Waerme)
    # weicht um -50% ab.
    assert waerme_zeile["werte"][0]["menge"] == pytest.approx(0.1)
    assert waerme_zeile["werte"][0]["abweichung"] == pytest.approx(0.0)
    assert waerme_zeile["werte"][1]["menge"] == pytest.approx(0.05)
    assert waerme_zeile["werte"][1]["abweichung"] == pytest.approx(-0.5)

    # Das Diagramm ist eine core.zeichnung.Leinwand mit allen drei Jahren.
    leinwand = daten_erstes["diagramme"]["vergleich"]
    assert leinwand is not None
    svg = leinwand.als_svg()
    assert "Jahr1" in svg and "Jahr2" in svg and "Jahr3" in svg


def test_daten_fuer_reihe_mit_noch_laufendem_geschwister_zeigt_kein_ergebnis(app):
    """Ein Bericht existiert erst, wenn DIESER Lauf abgeschlossen ist - ein
    Geschwister kann trotzdem noch laufen (core.laeufe._reihe_laufen ist noch
    nicht am naechsten Jahr angekommen). core.vergleich zeigt das als
    'kein Ergebnis', der Bericht darf daran nicht scheitern."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_id = ax_sim_2_1.baue(projekt, "A")
        graph = anlagen.lade_graph(anlage_id)
        w1 = _wetter_anlegen("Fertig", jahr=2021)
        w2 = _wetter_anlegen("Laeuft", jahr=2022)
        sim1 = _lauf_abschliessen(anlage_id, graph, w1, 100.0,
                                   reihen_kennung="r", reihen_index=1, reihen_gesamt=2)
        sim2 = ergebnisse.beginne(anlage_id, w2, 0, 10, "kennung-laeuft",
                                   reihen_kennung="r", reihen_index=2, reihen_gesamt=2)

        daten = bericht.daten_fuer(sim1)

    assert daten["vergleich"] is not None
    laeufe = {l["simulation_id"]: l for l in daten["vergleich"]["laeufe"]}
    assert laeufe[sim2]["hat_ergebnis"] is False
    assert laeufe[sim2]["status"] == "laeuft"


# ---------------------------------------------------------------------------
# routes/bericht.py - HTML und PDF
# ---------------------------------------------------------------------------

def test_route_html_ohne_reihe_zeigt_keinen_vergleichsabschnitt(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_id = ax_sim_2_1.baue(projekt, "A")
        wetter_id = _wetter_anlegen("W")
        graph = anlagen.lade_graph(anlage_id)
        simulation_id = ergebnisse.speichere(
            anlage_id, wetter_id, 0, 10,
            solver.Lauf(stunden=[{}] * 10, bilanz={"waerme": 1.0, "kaelte": 0.0,
                                                     "strom_ht": 0.0, "strom_nt": 0.0, "wasser": 0.0},
                        warnungen=[]),
            graph, dauer=0.1,
        )
    antwort = app.test_client().get(f"/anlage/{anlage_id}/lauf/{simulation_id}/bericht")
    assert antwort.status_code == 200
    assert "Im Vergleich zu den anderen Jahren dieser Reihe" not in antwort.get_data(as_text=True)


def test_route_html_mit_reihe_zeigt_vergleichsabschnitt(app):
    anlage_id, sim_ids = _reihe_anlegen(app, [100.0, 50.0])
    antwort = app.test_client().get(f"/anlage/{anlage_id}/lauf/{sim_ids[0]}/bericht")
    assert antwort.status_code == 200
    html = antwort.get_data(as_text=True)
    assert "Im Vergleich zu den anderen Jahren dieser Reihe" in html
    assert "Jahr1" in html and "Jahr2" in html
    assert "dieser Bericht" in html


def test_route_pdf_mit_reihe_enthaelt_vergleichsabschnitt(app):
    anlage_id, sim_ids = _reihe_anlegen(app, [100.0, 50.0, 150.0])
    antwort = app.test_client().get(f"/anlage/{anlage_id}/lauf/{sim_ids[1]}/bericht.pdf")
    assert antwort.status_code == 200
    rohdaten = antwort.data
    assert rohdaten.startswith(b"%PDF-1.4")
    assert rohdaten.rstrip().endswith(b"%%EOF")
    # Ueberschrift und Jahresnamen (WinAnsi-kodiert, reines ASCII) muessen im
    # Inhaltsstrom auftauchen - sonst waere nur eine leere Huelle entstanden.
    assert b"Im Vergleich zu den anderen Jahren dieser Reihe" in rohdaten
    assert b"Jahr1" in rohdaten and b"Jahr2" in rohdaten and b"Jahr3" in rohdaten


def test_route_pdf_ohne_reihe_hat_keinen_vergleichsabschnitt(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_id = ax_sim_2_1.baue(projekt, "A")
        wetter_id = _wetter_anlegen("W")
        graph = anlagen.lade_graph(anlage_id)
        simulation_id = ergebnisse.speichere(
            anlage_id, wetter_id, 0, 10,
            solver.Lauf(stunden=[{}] * 10, bilanz={"waerme": 1.0, "kaelte": 0.0,
                                                     "strom_ht": 0.0, "strom_nt": 0.0, "wasser": 0.0},
                        warnungen=[]),
            graph, dauer=0.1,
        )
    antwort = app.test_client().get(f"/anlage/{anlage_id}/lauf/{simulation_id}/bericht.pdf")
    assert antwort.status_code == 200
    assert b"Im Vergleich zu den anderen Jahren dieser Reihe" not in antwort.data
