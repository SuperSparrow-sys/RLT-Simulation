import sqlite3

from app import create_app
from core import database


def test_init_db_legt_tabellen_an(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    app = create_app()
    with app.app_context():
        database.init_db()
        db = database.get_db()
        namen = {
            r["name"]
            for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"projekt", "anlage", "karte", "port", "pfeil", "verbindung"} <= namen
        spalten = {r[1] for r in db.execute("PRAGMA table_info(port)")}
        assert "basis" in spalten, "Der Basisname eines Ports gehoert in die Datenbank"


def test_fremdschluessel_sind_aktiv(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    app = create_app()
    with app.app_context():
        database.init_db()
        db = database.get_db()
        try:
            db.execute(
                "INSERT INTO anlage (projekt_id, name) VALUES (999, 'ohne Projekt')"
            )
            db.commit()
        except sqlite3.IntegrityError:
            return
    raise AssertionError("Fremdschluessel wurde nicht durchgesetzt")
