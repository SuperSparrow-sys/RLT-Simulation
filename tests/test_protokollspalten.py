"""Keine Protokollspalte, die aussieht wie ein Messwert und keiner ist.

Der Solver reicht jeder Karte an ihren LuftAUSGÄNGEN eine Luft herein, die
allein die stromabwärts abgenommene Menge trägt (core/solver.py, _eingaenge).
Davon ist nur der Volumenstrom eine Aussage; die Temperatur ist nie gesetzt.
Mitgeschrieben wurde sie trotzdem: In jeder Stunde jeder Anlage stand
„T_luft_aus 0,0 °C“ im Protokoll - eine Spalte, die man auswählen und in ein
Diagramm legen konnte und die immer eine Nulllinie zeigte.
"""

import pytest

from app import create_app
from core import anlagen, database, solver
from core.bausteine.basis import Luft
from core.vorlagen import VORLAGEN
from werkzeuge.abgleich import lade_wetterstunden


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def test_keine_temperaturspalte_an_einem_luftausgang(app):
    with app.app_context():
        graph = anlagen.lade_graph(
            VORLAGEN["testanlage"].baue(anlagen.projekt_anlegen("Spalten"))
        )
        lauf = solver.Solver(graph).starte(lade_wetterstunden()[:24])

    verdaechtig = []
    for stunde in lauf.stunden:
        for karte_id, werte in stunde.items():
            ausgaenge = {
                port.schluessel for port in graph.karten[karte_id].ports
                if port.art == "luft" and port.richtung == "aus"
            }
            for name in werte:
                if name.startswith("T_") and name[2:] in ausgaenge:
                    verdaechtig.append((graph.karten[karte_id].name, name))
    assert not verdaechtig, f"Scheinbare Messwerte im Protokoll: {set(verdaechtig)}"


def test_die_abgenommene_menge_steht_weiterhin_da(app):
    """Nur die Temperatur faellt weg - der Volumenstrom ist die Aussage, um
    derentwillen die Marke ueberhaupt hereingereicht wird."""
    with app.app_context():
        graph = anlagen.lade_graph(
            VORLAGEN["testanlage"].baue(anlagen.projekt_anlegen("Spalten"))
        )
        lauf = solver.Solver(graph).starte(lade_wetterstunden()[:24])

    gefunden = 0
    for karte_id, karte in graph.karten.items():
        for port in karte.ports:
            if port.art != "luft" or port.richtung != "aus":
                continue
            if f"V_{port.schluessel}" in lauf.stunden[-1].get(karte_id, {}):
                gefunden += 1
    assert gefunden >= 5, "die abgenommenen Mengen fehlen jetzt auch"
