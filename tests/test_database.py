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


def test_init_db_migriert_eine_datenbank_im_alten_zustand(tmp_path, monkeypatch):
    """Reproduziert genau den gemeldeten Fehler: eine bestehende Datenbank,
    deren Tabellen 'pfeil' und 'simulation' noch ohne 'mehrdeutig',
    'kennung' und 'fortschritt' angelegt wurden (der Stand vor diesen
    Spalten) - init_db() muss sie migrieren koennen, statt beim Index auf
    einer noch fehlenden Spalte mit 'no such column' abzubrechen.

    Ohne diesen Test lief die Migration in der gesamten Testreihe nie gegen
    eine Datenbank, der eine Spalte wirklich fehlte - jeder Test und der
    frisch eingerichtete Dienst starten mit einer neuen, in der die Tabelle
    sofort vollstaendig entsteht."""
    db_pfad = tmp_path / "alt.db"
    monkeypatch.setattr("core.config.DB_PATH", db_pfad)

    alte_verbindung = sqlite3.connect(str(db_pfad))
    alte_verbindung.executescript("""
        CREATE TABLE projekt (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            beschreibung  TEXT NOT NULL DEFAULT '',
            erstellt_am   TEXT NOT NULL DEFAULT (datetime('now')),
            geaendert_am  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE anlage (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id    INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            name          TEXT NOT NULL,
            notiz         TEXT NOT NULL DEFAULT '',
            erstellt_am   TEXT NOT NULL DEFAULT (datetime('now')),
            geaendert_am  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE karte (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            anlage_id     INTEGER NOT NULL REFERENCES anlage(id) ON DELETE CASCADE,
            typ           TEXT NOT NULL,
            name          TEXT NOT NULL DEFAULT '',
            pos_x         REAL NOT NULL DEFAULT 0,
            pos_y         REAL NOT NULL DEFAULT 0,
            parameter     TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE port (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            karte_id      INTEGER NOT NULL REFERENCES karte(id) ON DELETE CASCADE,
            schluessel    TEXT NOT NULL,
            basis         TEXT NOT NULL,
            art           TEXT NOT NULL,
            richtung      TEXT NOT NULL,
            rolle         TEXT NOT NULL,
            nummer        INTEGER NOT NULL DEFAULT 1
        );
        -- alter Stand: noch ohne 'mehrdeutig'
        CREATE TABLE pfeil (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            anlage_id      INTEGER NOT NULL REFERENCES anlage(id) ON DELETE CASCADE,
            von_karte_id   INTEGER NOT NULL REFERENCES karte(id) ON DELETE CASCADE,
            nach_karte_id  INTEGER NOT NULL REFERENCES karte(id) ON DELETE CASCADE,
            stuetzpunkte   TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE verbindung (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            pfeil_id       INTEGER NOT NULL REFERENCES pfeil(id) ON DELETE CASCADE,
            von_port_id    INTEGER NOT NULL REFERENCES port(id) ON DELETE CASCADE,
            nach_port_id   INTEGER NOT NULL REFERENCES port(id) ON DELETE CASCADE
        );
        CREATE TABLE wetterdatensatz (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            quelle        TEXT NOT NULL,
            ort           TEXT NOT NULL DEFAULT '',
            breite        REAL,
            laenge        REAL,
            jahr          INTEGER,
            zeitzone      TEXT NOT NULL DEFAULT 'Europe/Berlin',
            notiz         TEXT NOT NULL DEFAULT '',
            erstellt_am   TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE wetterstunde (
            datensatz_id  INTEGER NOT NULL REFERENCES wetterdatensatz(id) ON DELETE CASCADE,
            stunde        INTEGER NOT NULL,
            zeitpunkt     TEXT NOT NULL,
            t_au          REAL NOT NULL,
            x_au          REAL NOT NULL,
            str_s         REAL NOT NULL DEFAULT 0,
            str_o         REAL NOT NULL DEFAULT 0,
            str_w         REAL NOT NULL DEFAULT 0,
            str_n         REAL NOT NULL DEFAULT 0,
            str_h         REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (datensatz_id, stunde)
        );
        -- alter Stand: noch ohne 'kennung' und 'fortschritt'
        CREATE TABLE simulation (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            anlage_id          INTEGER NOT NULL REFERENCES anlage(id) ON DELETE CASCADE,
            wetterdatensatz_id INTEGER NOT NULL REFERENCES wetterdatensatz(id),
            von_stunde         INTEGER NOT NULL,
            bis_stunde         INTEGER NOT NULL,
            status             TEXT NOT NULL DEFAULT 'fertig',
            gestartet_am       TEXT NOT NULL DEFAULT (datetime('now')),
            dauer_s            REAL NOT NULL DEFAULT 0,
            warnungen          TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE zeitreihe (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            simulation_id  INTEGER NOT NULL REFERENCES simulation(id) ON DELETE CASCADE,
            karte_id       INTEGER NOT NULL,
            karte_name     TEXT NOT NULL DEFAULT '',
            groesse        TEXT NOT NULL,
            einheit        TEXT NOT NULL DEFAULT '',
            werte          BLOB NOT NULL
        );
        CREATE TABLE bilanz (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            simulation_id  INTEGER NOT NULL REFERENCES simulation(id) ON DELETE CASCADE,
            groesse        TEXT NOT NULL,
            menge          REAL NOT NULL,
            einheit        TEXT NOT NULL,
            preis          REAL NOT NULL DEFAULT 0,
            kosten         REAL NOT NULL DEFAULT 0
        );
        -- die Indizes, die es in diesem alten Stand schon gab (ohne die
        -- beiden, die sich erst auf 'kennung' bzw. 'anlage_id, status' auf
        -- der 'simulation'-Tabelle beziehen - genau die fehlten hier noch)
        CREATE INDEX idx_karte_anlage  ON karte(anlage_id);
        CREATE INDEX idx_port_karte    ON port(karte_id);
        CREATE INDEX idx_pfeil_anlage  ON pfeil(anlage_id);
        CREATE INDEX idx_verb_pfeil    ON verbindung(pfeil_id);
        CREATE INDEX idx_zeitreihe_sim ON zeitreihe(simulation_id);
        CREATE INDEX idx_bilanz_sim    ON bilanz(simulation_id);
    """)
    # Eine Zeile, die eine echte alte Installation so haette liegen haben
    # koennen - falls die Migration sie beschaedigt, faellt das unten auf.
    alte_verbindung.execute(
        "INSERT INTO projekt (id, name) VALUES (1, 'Bestandsprojekt')"
    )
    alte_verbindung.commit()
    alte_verbindung.close()

    app = create_app()
    with app.app_context():
        database.init_db()  # darf hier nicht mit 'no such column' abbrechen

        db = database.get_db()
        pfeil_spalten = {r[1] for r in db.execute("PRAGMA table_info(pfeil)")}
        sim_spalten = {r[1] for r in db.execute("PRAGMA table_info(simulation)")}
        assert "mehrdeutig" in pfeil_spalten
        assert {"kennung", "fortschritt", "baustein_warnungen"} <= sim_spalten

        indizes = {
            r["name"]
            for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
        }
        assert {"idx_simulation_kennung", "idx_simulation_anlage_status"} <= indizes

        # Das Bestandsprojekt ist die Migration unbeschadet unbeschaedigt
        # ueberstanden.
        name = db.execute(
            "SELECT name FROM projekt WHERE id = 1"
        ).fetchone()["name"]
        assert name == "Bestandsprojekt"

        # Und die Datenbank ist danach voll benutzbar - ein Simulationslauf
        # kann die neuen Spalten auch tatsaechlich schreiben.
        anlage = ax_sim_2_1.baue(1, "A")
        wetter = speicher.datensatz_anlegen(
            "Test", "upload",
            [{
                "zeitpunkt": datetime(2024, 1, 1), "t_au": 0.0, "x_au": 4.0,
                "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
            }],
        )
        simulation_id = ergebnisse.beginne(anlage, wetter, 0, 1, "nach-migration")
        assert ergebnisse.laufende_simulation(anlage)["kennung"] == "nach-migration"


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
