"""Datenbankzugriff. Aufbau wie in kapa-planung."""

import sqlite3
import time
from functools import wraps

from flask import g

from core import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS projekt (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    beschreibung  TEXT NOT NULL DEFAULT '',
    erstellt_am   TEXT NOT NULL DEFAULT (datetime('now')),
    geaendert_am  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS anlage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_id    INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    notiz         TEXT NOT NULL DEFAULT '',
    erstellt_am   TEXT NOT NULL DEFAULT (datetime('now')),
    geaendert_am  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS karte (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    anlage_id     INTEGER NOT NULL REFERENCES anlage(id) ON DELETE CASCADE,
    typ           TEXT NOT NULL,
    name          TEXT NOT NULL DEFAULT '',
    pos_x         REAL NOT NULL DEFAULT 0,
    pos_y         REAL NOT NULL DEFAULT 0,
    parameter     TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS port (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    karte_id      INTEGER NOT NULL REFERENCES karte(id) ON DELETE CASCADE,
    schluessel    TEXT NOT NULL,
    basis         TEXT NOT NULL,
    art           TEXT NOT NULL,
    richtung      TEXT NOT NULL,
    rolle         TEXT NOT NULL,
    nummer        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS pfeil (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    anlage_id      INTEGER NOT NULL REFERENCES anlage(id) ON DELETE CASCADE,
    von_karte_id   INTEGER NOT NULL REFERENCES karte(id) ON DELETE CASCADE,
    nach_karte_id  INTEGER NOT NULL REFERENCES karte(id) ON DELETE CASCADE,
    stuetzpunkte   TEXT NOT NULL DEFAULT '[]',
    mehrdeutig     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS verbindung (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    pfeil_id       INTEGER NOT NULL REFERENCES pfeil(id) ON DELETE CASCADE,
    von_port_id    INTEGER NOT NULL REFERENCES port(id) ON DELETE CASCADE,
    nach_port_id   INTEGER NOT NULL REFERENCES port(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_karte_anlage  ON karte(anlage_id);
CREATE INDEX IF NOT EXISTS idx_port_karte    ON port(karte_id);
CREATE INDEX IF NOT EXISTS idx_pfeil_anlage  ON pfeil(anlage_id);
CREATE INDEX IF NOT EXISTS idx_verb_pfeil    ON verbindung(pfeil_id);
"""

SCHEMA += """
CREATE TABLE IF NOT EXISTS wetterdatensatz (
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

CREATE TABLE IF NOT EXISTS wetterstunde (
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
"""

SCHEMA += """
CREATE TABLE IF NOT EXISTS simulation (
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

CREATE TABLE IF NOT EXISTS zeitreihe (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id  INTEGER NOT NULL REFERENCES simulation(id) ON DELETE CASCADE,
    karte_id       INTEGER NOT NULL,
    karte_name     TEXT NOT NULL DEFAULT '',
    groesse        TEXT NOT NULL,
    einheit        TEXT NOT NULL DEFAULT '',
    werte          BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS bilanz (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id  INTEGER NOT NULL REFERENCES simulation(id) ON DELETE CASCADE,
    groesse        TEXT NOT NULL,
    menge          REAL NOT NULL,
    einheit        TEXT NOT NULL,
    preis          REAL NOT NULL DEFAULT 0,
    kosten         REAL NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_zeitreihe_sim ON zeitreihe(simulation_id);
CREATE INDEX IF NOT EXISTS idx_bilanz_sim    ON bilanz(simulation_id);
"""


def retry_on_lock(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        letzter = None
        for versuch in range(config.SQLITE_RETRY_MAX):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as exc:
                letzter = exc
                text = str(exc).lower()
                if ("locked" in text or "busy" in text) and versuch < config.SQLITE_RETRY_MAX - 1:
                    time.sleep(config.SQLITE_RETRY_BACKOFF * (2**versuch))
                    continue
                raise
        raise letzter

    return wrapper


def get_db():
    if "db" not in g:
        pfad = config.DB_PATH
        pfad.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(str(pfad))
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
        g.db.execute("PRAGMA busy_timeout = 5000")
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@retry_on_lock
def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    _migriere(db)
    db.commit()


def _migriere(db):
    """Spaltenzusaetze fuer Datenbanken, die vor dieser Spalte angelegt wurden.

    'CREATE TABLE IF NOT EXISTS' legt eine neue Spalte in einer bereits
    bestehenden Tabelle nicht nachtraeglich an - ohne dies wuerde eine lokale
    Datenbank aus einer frueheren Version mit 'no such column' abbrechen.
    """
    spalten = {z["name"] for z in db.execute("PRAGMA table_info(pfeil)")}
    if "mehrdeutig" not in spalten:
        db.execute(
            "ALTER TABLE pfeil ADD COLUMN mehrdeutig INTEGER NOT NULL DEFAULT 0"
        )
