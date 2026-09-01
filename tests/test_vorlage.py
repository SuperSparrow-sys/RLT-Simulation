import pytest

from app import create_app
from core import anlagen, database
from core.vorlagen import ax_sim_2_1


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def test_vorlage_legt_alle_karten_an(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        daten = anlagen.als_json(anlage)
    typen = [k["typ"] for k in daten["karten"]]
    assert typen.count("ventilator") == 3          # zwei Zuluft, eine Abluft
    assert typen.count("kuehler") == 2
    assert typen.count("luftwaescher") == 2
    assert "wrg" in typen
    assert "einfacher_raum" in typen
    assert "bilanz" in typen


def test_vorlage_ist_vollstaendig_verdrahtet(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        g = anlagen.lade_graph(anlage)

    ohne_eingang = [
        k for k in g.karten.values()
        if any(p.art == "luft" and p.richtung == "ein" for p in k.ports)
        and not g.eingaenge_von(k.id)
    ]
    assert ohne_eingang == [], [k.name for k in ohne_eingang]


def test_nennwerte_entsprechen_der_excel(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        daten = anlagen.als_json(anlage)

    nach_name = {k["name"]: k["parameter"] for k in daten["karten"]}
    assert nach_name["Wärmerückgewinnung"]["V_nenn"] == 12200.0
    assert nach_name["Wärmerückgewinnung"]["rueckwaermzahl"] == 81.0
    assert nach_name["Zuluftventilator Halle"]["V_max"] == 8200.0
    assert nach_name["Zuluftventilator Halle"]["PE_max"] == 4.9
    assert nach_name["Erhitzer Halle"]["QH_max"] == 101.0
    assert nach_name["Kühler Halle"]["QK_nenn"] == 63.0


def test_energiepreise_entsprechen_der_excel(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        daten = anlagen.als_json(anlage)
    bilanz = next(k for k in daten["karten"] if k["typ"] == "bilanz")["parameter"]
    assert bilanz["preis_strom_nt"] == 150.0
    assert bilanz["preis_waerme"] == 50.0
    assert bilanz["preis_kaelte"] == 50.0
    assert bilanz["preis_wasser"] == 4.0


def test_vorlage_ist_rechenbar(app):
    """Sie muss sich sortieren lassen und darf keine losen Enden haben."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        g = anlagen.lade_graph(anlage)
    assert len(g.reihenfolge()) == len(g.karten)


def test_api_legt_die_vorlage_an(app):
    klient = app.test_client()
    projekt = klient.post("/api/projekte", json={"name": "P"}).get_json()["id"]
    antwort = klient.post(
        "/api/anlagen/aus_vorlage",
        json={"projekt_id": projekt, "vorlage": "ax_sim_2_1", "name": "Referenz"},
    )
    assert antwort.status_code == 201
    assert antwort.get_json()["id"] > 0
