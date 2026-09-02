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


def test_baue_beispiel_gibt_bestehende_anlage_zurueck_statt_zu_verdoppeln(app):
    """Vor dieser Absicherung legte jeder Aufruf von baue_beispiel() fuer
    denselben Kartentyp eine weitere, identisch benannte Anlage im Projekt
    "Bausteine" an - im echten Projekt lagen deswegen zeitweise neun
    Anlagen fuer sieben Kartentypen, "Anlagenbetrieb" und "Heizungspumpen"
    je zweimal (siehe .superpowers/sdd-Report)."""
    with app.app_context():
        projekt = beispielanlagen.projekt_bausteine()
        erster_aufruf = beispielanlagen.baue_beispiel("erhitzer", projekt)
        zweiter_aufruf = beispielanlagen.baue_beispiel("erhitzer", projekt)
        dritter_aufruf = beispielanlagen.baue_beispiel("erhitzer", projekt)

        assert erster_aufruf == zweiter_aufruf == dritter_aufruf
        anlagen_im_projekt = anlagen.anlagen_von(projekt)
        assert len(anlagen_im_projekt) == 1


def test_baue_beispiel_erkennt_verschiedene_kartentypen_als_verschieden(app):
    with app.app_context():
        projekt = beispielanlagen.projekt_bausteine()
        erhitzer = beispielanlagen.baue_beispiel("erhitzer", projekt)
        kuehler = beispielanlagen.baue_beispiel("kuehler", projekt)

        assert erhitzer != kuehler
        assert len(anlagen.anlagen_von(projekt)) == 2


def test_baue_beispiel_legt_nach_umbenennen_eine_neue_frische_anlage_an(app):
    """Eine per Umbenennen persoenlich gemachte Beispielanlage wird beim
    naechsten Oeffnen des Beispiels nicht angetastet - stattdessen entsteht
    (wieder erkennbar am Vorgabenamen) eine neue, frische Beispielanlage,
    kein stilles Ueberschreiben der eigenen Aenderung."""
    with app.app_context():
        projekt = beispielanlagen.projekt_bausteine()
        erste = beispielanlagen.baue_beispiel("erhitzer", projekt)
        anlagen.anlage_umbenennen(erste, "Meine Fassung des Erhitzers")

        zweite = beispielanlagen.baue_beispiel("erhitzer", projekt)

        assert zweite != erste
        namen = {a["id"]: a["name"] for a in anlagen.anlagen_von(projekt)}
        assert namen[erste] == "Meine Fassung des Erhitzers"
        assert namen[zweite] == "Erhitzer"


def test_erwarteter_name_stimmt_mit_klasse_name_fuer_jeden_kartentyp_ueberein():
    """_erwarteter_name() ist der Wiedererkennungsschluessel fuer
    baue_beispiel() - fuer jeden Kartentyp muss er mit dem Namen
    uebereinstimmen, den die zugehoerige bau_<typ>()-Funktion tatsaechlich
    vergibt (bei der Einfuehrung einzeln nachgerechnet, siehe Kommentar
    dort). Diese Stichprobe deckt nur die Erwartung gegen core.bausteine.basis
    ab, nicht jede der 34 bau_<typ>()-Funktionen einzeln - das leistet
    test_beispielanlage_baut_und_rechnet bereits pro Kartentyp."""
    namen_je_kennung = {klasse.KENNUNG: klasse.NAME for klasse in basis.alle()}
    for kennung in beispielanlagen.BAUPLAENE:
        assert beispielanlagen._erwarteter_name(kennung) == namen_je_kennung[kennung]


def test_name_projekt_stimmt_mit_core_anlagen_lehrmaterial_konstante_ueberein():
    """core.anlagen.NAME_PROJEKT_LEHRMATERIAL ist absichtlich dupliziert
    (Begruendung dort: Zirkelbezug-Vermeidung) - hier gegengeprueft, damit
    ein spaeteres Umbenennen des Sammelprojekts nicht unbemerkt nur eine
    der beiden Stellen trifft und die Startseite die Beispielanlagen dann
    wieder zwischen die eigenen Projekte des Benutzers mischt."""
    assert anlagen.NAME_PROJEKT_LEHRMATERIAL == beispielanlagen.NAME_PROJEKT
