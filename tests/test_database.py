import sqlite3
from datetime import datetime

from app import create_app
from core import anlagen, database, ergebnisse
from core.vorlagen import ax_sim_2_1
from core.wetter import speicher


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


def test_verwaiste_laeufe_werden_beim_naechsten_start_abgebrochen(tmp_path, monkeypatch):
    """Ein Prozess, der waehrend eines Laufs abstuerzt oder neu gestartet
    wird, verliert seinen Rechen-Thread und das in-memory _AUFTRAEGE mit ihm -
    die Zeile darf nicht fuer immer 'laeuft' behaupten, obwohl niemand mehr
    daran rechnet (core.database._aufraeume_verwaiste_laeufe, aufgerufen von
    init_db() - also bei jedem Dienststart)."""
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    app = create_app()
    with app.app_context():
        database.init_db()
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = speicher.datensatz_anlegen(
            "Test", "upload",
            [{
                "zeitpunkt": datetime(2024, 1, 1), "t_au": 0.0, "x_au": 4.0,
                "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
            }],
        )
        # ergebnisse.beginne() statt laeufe.starte(): so entsteht die Zeile
        # ohne einen echten Hintergrund-Thread - genau der Zustand, den ein
        # abgestuerzter Prozess hinterlassen wuerde.
        simulation_id = ergebnisse.beginne(anlage, wetter, 0, 1, "verwaiste-kennung")

        db = database.get_db()
        vorher = db.execute(
            "SELECT status FROM simulation WHERE id = ?", (simulation_id,)
        ).fetchone()["status"]
        assert vorher == "laeuft"

        # Ein zweiter, unabhaengiger init_db()-Aufruf steht hier fuer den
        # naechsten Dienststart nach dem (simulierten) Absturz.
        database.init_db()

        nachher = db.execute(
            "SELECT status FROM simulation WHERE id = ?", (simulation_id,)
        ).fetchone()["status"]
        assert nachher == "abgebrochen"


def test_init_db_ohne_verwaiste_laeufe_bleibt_unauffaellig(tmp_path, monkeypatch):
    """Der Regelfall (nichts zum Aufraeumen) darf keine bestehenden,
    abgeschlossenen Zeilen anfassen."""
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    app = create_app()
    with app.app_context():
        database.init_db()
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = speicher.datensatz_anlegen(
            "Test", "upload",
            [{
                "zeitpunkt": datetime(2024, 1, 1), "t_au": 0.0, "x_au": 4.0,
                "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
            }],
        )
        graph = anlagen.lade_graph(anlage)
        from core import solver

        lauf = solver.Lauf(
            stunden=[{}],
            bilanz={"strom_ht": 0.0, "strom_nt": 0.0, "waerme": 0.0,
                    "kaelte": 0.0, "wasser": 0.0},
            warnungen=[],
        )
        sim = ergebnisse.speichere(anlage, wetter, 0, 1, lauf, graph, dauer=0.1)

        database.init_db()

        db = database.get_db()
        status = db.execute(
            "SELECT status FROM simulation WHERE id = ?", (sim,)
        ).fetchone()["status"]
        assert status == "fertig"


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
