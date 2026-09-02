"""Datenbankzugriff. Aufbau wie in kapa-planung."""

import sqlite3
import time
from functools import wraps

from flask import current_app, g

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
-- reihen_kennung/reihen_index/reihen_gesamt: fuer den Vergleich mehrerer
-- Wetterjahre derselben Anlage (core/vergleich.py, core/laeufe.py -
-- starte_reihe()). Jedes Jahr einer solchen Reihe bleibt eine ganz normale
-- Zeile dieser Tabelle (ein eigener Lauf mit eigener 'kennung', wie ein
-- einzeln gestarteter); die drei Spalten markieren nur zusaetzlich, zu
-- welcher Reihe die Zeile gehoert und an welcher Stelle. NULL fuer jeden
-- Lauf, der nicht Teil einer Reihe ist. Damit gilt fuer eine Reihe
-- automatisch dieselbe Loeschsperre wie fuer jeden anderen Lauf (ein
-- Wetterdatensatz, auf den eine dieser Zeilen zeigt, laesst sich nicht
-- loeschen - core.wetter.speicher.datensatz_loeschen()), ohne dass diese
-- Regel eigens fuer Reihen nachgebaut werden muesste.
CREATE TABLE IF NOT EXISTS simulation (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    anlage_id          INTEGER NOT NULL REFERENCES anlage(id) ON DELETE CASCADE,
    wetterdatensatz_id INTEGER NOT NULL REFERENCES wetterdatensatz(id),
    von_stunde         INTEGER NOT NULL,
    bis_stunde         INTEGER NOT NULL,
    status             TEXT NOT NULL DEFAULT 'fertig',
    kennung            TEXT,
    fortschritt        INTEGER NOT NULL DEFAULT 0,
    gestartet_am       TEXT NOT NULL DEFAULT (datetime('now')),
    dauer_s            REAL NOT NULL DEFAULT 0,
    warnungen          TEXT NOT NULL DEFAULT '[]',
    baustein_warnungen TEXT NOT NULL DEFAULT '[]',
    reihen_kennung     TEXT,
    reihen_index       INTEGER,
    reihen_gesamt      INTEGER
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
"""

SCHEMA += """
-- Rueckgaengig/Wiederholen (core/verlauf.py): je Anlage eine Reihe
-- vollstaendiger Momentaufnahmen, 'nummer' laufend ab 1. 'daten' ist
-- gzip(JSON) des ganzen Anlagenzustands (Name, Notiz, Karten, Anschluesse,
-- Pfeile, Verbindungen), rund 7 KiB bei einer grossen Anlage. 'buendel'
-- markiert Schritte, die zu EINER Handlung gehoeren duerfen (dieselbe Karte
-- verschoben, dasselbe Parameterfeld getippt) - siehe verlauf._darf_buendeln.
-- Welcher Zustand gerade gilt, steht als 'verlauf_stand' in der Tabelle
-- 'anlage' (siehe _migriere) und nicht in einer eigenen Zeile hier: eine
-- Anlage hat immer genau einen Stand, eine eigene Tabelle haette nur den
-- Sonderfall 'Zeile fehlt noch' hinzugefuegt.
-- ON DELETE CASCADE: der Verlauf verschwindet mit der Anlage.
CREATE TABLE IF NOT EXISTS zustand (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    anlage_id     INTEGER NOT NULL REFERENCES anlage(id) ON DELETE CASCADE,
    nummer        INTEGER NOT NULL,
    beschreibung  TEXT NOT NULL DEFAULT '',
    buendel       TEXT,
    zeitpunkt     TEXT NOT NULL DEFAULT (datetime('now')),
    daten         BLOB NOT NULL
);
"""

# Getrennt von SCHEMA und erst NACH _migriere() ausgefuehrt (siehe init_db()):
# ein Index auf einer Spalte, die eine bestehende Datenbank noch nicht hat
# (z.B. 'kennung' vor dieser Aenderung), schlaegt sofort mit 'no such column'
# fehl - und zwar schon beim Anlegen der Tabellen, bevor _migriere() die
# fehlende Spalte ueberhaupt nachtragen konnte. Erst Tabellen (SCHEMA), dann
# fehlende Spalten (_migriere), dann erst Indizes darauf - jede andere
# Reihenfolge bricht beim naechsten Start gegen eine aeltere Datenbank ab.
INDIZES = """
CREATE INDEX IF NOT EXISTS idx_karte_anlage  ON karte(anlage_id);
CREATE INDEX IF NOT EXISTS idx_port_karte    ON port(karte_id);
CREATE INDEX IF NOT EXISTS idx_pfeil_anlage  ON pfeil(anlage_id);
CREATE INDEX IF NOT EXISTS idx_verb_pfeil    ON verbindung(pfeil_id);
CREATE INDEX IF NOT EXISTS idx_zeitreihe_sim ON zeitreihe(simulation_id);
CREATE INDEX IF NOT EXISTS idx_bilanz_sim    ON bilanz(simulation_id);
CREATE INDEX IF NOT EXISTS idx_simulation_kennung ON simulation(kennung);
CREATE INDEX IF NOT EXISTS idx_simulation_anlage_status ON simulation(anlage_id, status);
CREATE INDEX IF NOT EXISTS idx_simulation_reihen ON simulation(reihen_kennung);
CREATE INDEX IF NOT EXISTS idx_zustand_anlage ON zustand(anlage_id, nummer);
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
    db.executescript(INDIZES)
    _aufraeume_verwaiste_laeufe(db)
    db.commit()


def _migriere(db):
    """Spaltenzusaetze fuer Datenbanken, die vor dieser Spalte angelegt wurden.

    'CREATE TABLE IF NOT EXISTS' legt eine neue Spalte in einer bereits
    bestehenden Tabelle nicht nachtraeglich an - ohne dies wuerde eine lokale
    Datenbank aus einer frueheren Version mit 'no such column' abbrechen.
    Muss vor INDIZES laufen (siehe Kommentar dort) - jede neue Spalte, auf
    der spaeter ein Index steht, gehoert hierher, nicht dazu.
    """
    spalten = {z["name"] for z in db.execute("PRAGMA table_info(pfeil)")}
    if "mehrdeutig" not in spalten:
        db.execute(
            "ALTER TABLE pfeil ADD COLUMN mehrdeutig INTEGER NOT NULL DEFAULT 0"
        )

    # Der Zeiger auf den gerade geltenden Zustand des Verlaufs
    # (core/verlauf.py). 0 heisst: fuer diese Anlage ist noch nichts
    # aufgezeichnet - der erste aufgezeichnete Schritt legt zuerst den
    # Ausgangszustand (nummer 1) an.
    spalten = {z["name"] for z in db.execute("PRAGMA table_info(anlage)")}
    if "verlauf_stand" not in spalten:
        db.execute(
            "ALTER TABLE anlage ADD COLUMN verlauf_stand INTEGER NOT NULL DEFAULT 0"
        )

    spalten = {z["name"] for z in db.execute("PRAGMA table_info(simulation)")}
    if "kennung" not in spalten:
        db.execute("ALTER TABLE simulation ADD COLUMN kennung TEXT")
    if "fortschritt" not in spalten:
        db.execute(
            "ALTER TABLE simulation ADD COLUMN fortschritt INTEGER NOT NULL DEFAULT 0"
        )
    if "baustein_warnungen" not in spalten:
        db.execute(
            "ALTER TABLE simulation ADD COLUMN baustein_warnungen TEXT NOT NULL "
            "DEFAULT '[]'"
        )
    if "reihen_kennung" not in spalten:
        db.execute("ALTER TABLE simulation ADD COLUMN reihen_kennung TEXT")
    if "reihen_index" not in spalten:
        db.execute("ALTER TABLE simulation ADD COLUMN reihen_index INTEGER")
    if "reihen_gesamt" not in spalten:
        db.execute("ALTER TABLE simulation ADD COLUMN reihen_gesamt INTEGER")


def _aufraeume_verwaiste_laeufe(db):
    """Simulationslaeufe, die beim letzten Absturz oder Neustart des Dienstes
    auf 'laeuft' stehengeblieben sind, werden als abgebrochen markiert.

    Der Rechen-Thread eines solchen Laufs existiert nach einem Neustart nicht
    mehr (core/laeufe.py haelt seinen Fortschritt nur im Arbeitsspeicher des
    Prozesses) - die Zeile wuerde sonst fuer immer 'laeuft' behaupten, obwohl
    nie wieder etwas daran rechnet. Laeuft bei jedem init_db() mit: im
    Normalfall (keine verwaiste Zeile) ist das eine leere, guenstige Abfrage.
    """
    verwaist = db.execute(
        "SELECT id, anlage_id FROM simulation WHERE status = 'laeuft'"
    ).fetchall()
    if not verwaist:
        return
    db.execute("UPDATE simulation SET status = 'abgebrochen' WHERE status = 'laeuft'")
    meldung = (
        "Dienst neu gestartet: %d verwaiste(r) Simulationslauf/-laeufe "
        "(Anlagen %s) als abgebrochen markiert - der Rechen-Thread war weg."
    ) % (len(verwaist), sorted({z["anlage_id"] for z in verwaist}))
    try:
        current_app.logger.warning(meldung)
    except RuntimeError:
        # Ausserhalb eines Flask-Anwendungskontexts (z.B. ein Skript unter
        # werkzeuge/) gibt es keinen Logger - die Aufraeumung selbst ist
        # trotzdem wichtig und lief bereits.
        pass
