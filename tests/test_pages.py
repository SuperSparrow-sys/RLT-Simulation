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


def test_editor_seite_laedt_eine_anlage(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    antwort = klient.get(f"/anlage/{anlage}")
    assert antwort.status_code == 200


def test_editor_seite_bindet_pfeile_js_vor_editor_js_ein(app):
    """Ohne dieses Script-Tag existiert 'Pfeile' nicht und editor.js' Aufrufe
    von Pfeile.zeichneAlle()/Pfeile.binde() brechen mit einem ReferenceError
    ab - das faellt in keinem Python-Test auf, deshalb hier absichern."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    html = klient.get(f"/anlage/{anlage}").get_data(as_text=True)

    assert "js/pfeile.js" in html
    assert html.index("js/pfeile.js") < html.index("js/editor.js")
