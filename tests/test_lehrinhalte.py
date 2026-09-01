"""Der Erklärbereich: Erklärung je Kartentyp, und die Beispielanlagen müssen
sich bauen lassen und tatsächlich rechnen.
"""

from datetime import datetime, timedelta

import pytest

from app import create_app
from core import anlagen, database, solver
from core.bausteine import basis, lade_alle
from core.lehrinhalte import beispielanlagen
from core.lehrinhalte.erklaerungen import ERKLAERUNGEN

lade_alle()


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def _wetterstunden(anzahl):
    # Montag, 01.01.2024 - Index 8..12 faellt in ein Wochenzeitplan-Fenster
    # (Vorgabe 05:00-22:00 werktags), damit die zeitgesteuerten Beispiele
    # tatsaechlich etwas tun.
    start = datetime(2024, 1, 1, 8)
    return [
        {
            "zeitpunkt": start + timedelta(hours=i),
            "t_au": 2.0, "x_au": 3.0,
            "str_s": 120.0, "str_o": 40.0, "str_w": 40.0, "str_n": 10.0, "str_h": 90.0,
        }
        for i in range(anzahl)
    ]


def test_jeder_kartentyp_hat_eine_erklaerung_und_eine_beispielanlage():
    alle_typen = {klasse.KENNUNG for klasse in basis.alle()}
    assert alle_typen == set(ERKLAERUNGEN)
    assert alle_typen == set(beispielanlagen.BAUPLAENE)


@pytest.mark.parametrize("kennung", sorted(beispielanlagen.BAUPLAENE))
def test_beispielanlage_baut_und_rechnet(app, kennung):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Test")
        anlage_id = beispielanlagen.baue_beispiel(kennung, projekt)
        g = anlagen.lade_graph(anlage_id)

        # Muss sich sortieren lassen - keine losen Enden, kein unaufloesbarer Zyklus.
        assert len(g.reihenfolge()) == len(g.karten)

        # Kein Lufteingang darf ohne Quelle bleiben.
        ohne_eingang = [
            k for k in g.karten.values()
            if any(p.art == "luft" and p.richtung == "ein" for p in k.ports)
            and not g.eingaenge_von(k.id)
        ]
        assert ohne_eingang == [], [k.name for k in ohne_eingang]

        lauf = solver.Solver(g).starte(_wetterstunden(4))

    assert len(lauf.stunden) == 4
    assert not lauf.warnungen, lauf.warnungen
