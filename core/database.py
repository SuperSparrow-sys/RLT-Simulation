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
    stuetzpunkte   TEXT NOT NULL DEFAULT '[]'
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
    db.commit()
