"""Eine Karte, deren Stellgröße keine Quelle hat, arbeitet mit null Prozent.

Der Fund, der zu dieser Regel führte: In einer Anlage mit
Wärmerückgewinnung war deren Stellgröße nicht verbunden. Die Karte lag
damit vollständig im Bypass - sie übertrug nichts, Q_WRG blieb null, und die
Heizleistung war fast doppelt so hoch wie ausgelegt. Weder die Rechnung noch
die Anlagenprüfung sagten ein Wort; im Bild sah die Anlage vollständig aus,
die Luft floss ordentlich hindurch.

Das ist genau die Sorte stiller Fehler, für die core/pruefung.py da ist -
nur sah sie bisher allein auf die Ausgänge der Regler, nicht auf die
Eingänge der geregelten Karten.
"""

import pytest

from app import create_app
from core import anlagen, database, pruefung


@pytest.fixture
def anlage(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    app = create_app()
    with app.app_context():
        database.init_db()
        projekt = anlagen.projekt_anlegen("Prüfung")
        yield anlagen.anlage_anlegen(projekt, "Probe")


def meldungen_zu(anlage_id, art):
    return [m for m in pruefung.pruefe(anlagen.lade_graph(anlage_id)) if m["art"] == art]


def test_waermerueckgewinnung_ohne_stellgroesse_wird_gemeldet(anlage):
    anlagen.karte_anlegen(anlage, "wrg", 0, 0, {"rueckwaermzahl": 75.0}, "Plattentauscher")
    treffer = meldungen_zu(anlage, "stellgroesse_ohne_quelle")
    assert len(treffer) == 1
    assert "Plattentauscher" in treffer[0]["text"]


def test_erhitzer_ohne_stellgroesse_wird_gemeldet(anlage):
    """Ein Erhitzer ohne Ansteuerung heizt nie - dieselbe stille Wirkung."""
    anlagen.karte_anlegen(anlage, "erhitzer", 0, 0, {"QH_max": 70.0}, "Erhitzer")
    assert len(meldungen_zu(anlage, "stellgroesse_ohne_quelle")) == 1


def test_verbundene_stellgroesse_wird_nicht_gemeldet(anlage):
    erhitzer = anlagen.karte_anlegen(anlage, "erhitzer", 0, 0, {}, "Erhitzer")
    regler = anlagen.karte_anlegen(anlage, "p_regler", 200, 0, {}, "Regler")
    anlagen.verbindung_anlegen(
        anlage,
        anlagen.port_id(regler, "ausgang_2"),
        anlagen.port_id(erhitzer, "stellgroesse"),
    )
    assert meldungen_zu(anlage, "stellgroesse_ohne_quelle") == []


def test_ventilator_ohne_stellgroesse_wird_nicht_gemeldet(anlage):
    """Der Ventilator traegt seine Stellgroesse auch als Parameter - ohne
    Verbindung laeuft er auf dem eingestellten Wert, nicht auf null. Eine
    Meldung waere hier falsch."""
    anlagen.karte_anlegen(
        anlage, "ventilator", 0, 0,
        {"rolle": "zuluft", "V_max": 5000.0, "stellgroesse": 100.0}, "Ventilator",
    )
    assert meldungen_zu(anlage, "stellgroesse_ohne_quelle") == []


def test_meldung_sagt_was_zu_tun_ist(anlage):
    anlagen.karte_anlegen(anlage, "kuehler", 0, 0, {}, "Kühler")
    text = meldungen_zu(anlage, "stellgroesse_ohne_quelle")[0]["text"]
    assert "0 %" in text or "null" in text.lower()
