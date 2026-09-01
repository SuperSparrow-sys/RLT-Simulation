import pytest

from app import create_app
from core import anlagen, database


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def test_karte_anlegen_erzeugt_die_ports(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Testprojekt")
        anlage = anlagen.anlage_anlegen(projekt, "Variante A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 100.0, 200.0)

        db = database.get_db()
        ports = db.execute(
            "SELECT schluessel FROM port WHERE karte_id = ?", (karte,)
        ).fetchall()
        schluessel = {r["schluessel"] for r in ports}
    assert "luft_ein" in schluessel
    assert "stellgroesse" in schluessel


def test_karte_bekommt_die_vorgabeparameter(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        daten = anlagen.als_json(anlage)
    erhitzer = next(k for k in daten["karten"] if k["id"] == karte)
    assert erhitzer["parameter"]["QH_max"] == 101.0


def test_pfeil_verdrahtet_automatisch(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        a = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        b = anlagen.karte_anlegen(anlage, "kuehler", 300.0, 0.0)
        pfeil = anlagen.pfeil_anlegen(anlage, a, b)
    assert len(pfeil["verbindungen"]) == 1
    assert pfeil["verbindungen"][0]["von_schluessel"] == "luft_aus"
    assert pfeil["verbindungen"][0]["nach_schluessel"] == "luft_ein"


def test_regler_pfeil_verdrahtet_hin_und_zurueck(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        regler = anlagen.karte_anlegen(anlage, "p_regler", 0.0, 0.0)
        erhitzer = anlagen.karte_anlegen(anlage, "erhitzer", 300.0, 0.0)
        pfeil = anlagen.pfeil_anlegen(anlage, regler, erhitzer)
    richtungen = {(v["von_karte_id"], v["nach_karte_id"]) for v in pfeil["verbindungen"]}
    assert (regler, erhitzer) in richtungen
    assert (erhitzer, regler) in richtungen


def test_dynamischer_port_waechst_beim_zweiten_pfeil_nach(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        verteiler = anlagen.karte_anlegen(anlage, "verteiler", 0.0, 0.0)
        a = anlagen.karte_anlegen(anlage, "erhitzer", 300.0, 0.0)
        b = anlagen.karte_anlegen(anlage, "erhitzer", 300.0, 200.0)

        erster = anlagen.pfeil_anlegen(anlage, verteiler, a)
        zweiter = anlagen.pfeil_anlegen(anlage, verteiler, b)
    assert erster["verbindungen"][0]["von_schluessel"] == "luft_aus_1"
    assert zweiter["verbindungen"][0]["von_schluessel"] == "luft_aus_2"


def test_pfeil_loeschen_entfernt_alle_verbindungen(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        regler = anlagen.karte_anlegen(anlage, "p_regler", 0.0, 0.0)
        erhitzer = anlagen.karte_anlegen(anlage, "erhitzer", 300.0, 0.0)
        pfeil = anlagen.pfeil_anlegen(anlage, regler, erhitzer)
        anlagen.pfeil_loeschen(pfeil["id"])

        db = database.get_db()
        anzahl = db.execute("SELECT COUNT(*) AS n FROM verbindung").fetchone()["n"]
    assert anzahl == 0


def test_parameter_aendern_wird_gespeichert(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        anlagen.karte_aendern(karte, parameter={"QH_max": 55.0})
        daten = anlagen.als_json(anlage)
    assert next(k for k in daten["karten"] if k["id"] == karte)["parameter"]["QH_max"] == 55.0


def test_graph_laesst_sich_zurueckladen(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        a = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        b = anlagen.karte_anlegen(anlage, "kuehler", 300.0, 0.0)
        anlagen.pfeil_anlegen(anlage, a, b)
        g = anlagen.lade_graph(anlage)
    assert g.reihenfolge() == [a, b]


def test_api_liefert_die_palette(app):
    klient = app.test_client()
    antwort = klient.get("/api/palette")
    assert antwort.status_code == 200
    gruppen = antwort.get_json()
    assert "Luftbehandlung" in gruppen
    kennungen = {k["kennung"] for gruppe in gruppen.values() for k in gruppe}
    assert "erhitzer" in kennungen


def test_api_legt_karte_an(app):
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
    antwort = klient.post(
        "/api/karten",
        json={"anlage_id": anlage, "typ": "kuehler", "pos_x": 10, "pos_y": 20},
    )
    assert antwort.status_code == 201
    assert antwort.get_json()["typ"] == "kuehler"
