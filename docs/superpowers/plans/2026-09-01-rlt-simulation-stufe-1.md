# RLT-Simulation Stufe 1 — Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine Flask-Anwendung, in der raumlufttechnische Anlagen aus Karten
zusammengezogen, mit Pfeilen verbunden und über ein Wetterjahr simuliert werden —
mit derselben Physik wie die Excel-Mappe AX_SIM 2.1.

**Architecture:** Jeder Kartentyp ist eine Python-Datei unter `core/bausteine/`, die
Parameter, Ports und Rechenvorschrift selbst deklariert; Palette, Parameterfenster und
Datenbank ergeben sich daraus. Der Solver rechnet je Stunde erst rückwärts die
Volumenströme von den Ventilatoren zu den Quellen, dann vorwärts die Luftzustände in
einer Fixpunkt-Iteration bis zur Konvergenz, und schreibt danach die Zustandsgrößen
für die nächste Stunde fort. Persistenz in SQLite, Oberfläche in Vanilla-JavaScript
ohne Build-Schritt.

**Tech Stack:** Python 3.11+, Flask 3, SQLite (WAL), pytest, xlrd (TRY-Import aus
`.xls`), openpyxl (TRY-Import aus `.xlsx`), Vanilla-JS mit SVG.

**Spec:** `docs/superpowers/specs/2026-09-01-rlt-simulation-design.md`

## Global Constraints

- Python 3.11 oder neuer; `Flask>=3.0`, `pytest>=8.0`, `xlrd>=2.0`, `openpyxl>=3.1`.
- Keine weiteren Laufzeitabhängigkeiten in Stufe 1. Insbesondere kein numpy, kein
  Frontend-Build, keine JavaScript-Bibliothek per CDN.
- Oberfläche, Fehlermeldungen, Spaltenüberschriften und Kommentare auf Deutsch.
  Bezeichner im Code auf Deutsch, passend zur Fachsprache der Excel (`T_ein`, `F_ein`,
  `V_nenn`, `Stellgroesse`). Umlaute in Bezeichnern werden ausgeschrieben:
  `Stellgroesse`, `Waerme`, `Kaelte`, `Aussenluft`.
- Einheiten durchgängig wie in der Excel: Volumenstrom m³/h, Temperatur °C, absolute
  Feuchte g/kg, Druck Pa, Leistung kW, Wasser kg/h.
- Gestaltung nach dem Vorbild von `~/projekte/kapa-planung`: CSS-Variablen in
  `static/css/style.css`, helle Flächen, Systemschriften, Anwendung auf Port 5055.
- Datenbankzugriff wie in `~/projekte/kapa-planung/core/database.py`: `get_db`/`close_db`
  über `flask.g`, `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL`,
  `PRAGMA busy_timeout = 5000`.
- Alle Tests laufen mit `pytest` aus dem Projektwurzelverzeichnis.
- Referenzmaterial liegt unter `referenz/`: die Excel-Mappe selbst
  (`RLTSimulation_Vorlage_AX_SIM_2.1.xls`), die ausgelesenen Formeln
  (`anlage-formeln.txt`) und die VBA-Module (`vba-module.txt`).

## Wichtiger Hinweis zur Referenz

Die Excel-Mappe wurde mitten in der iterativen Berechnung gespeichert. Daraus folgt:

- **Verlässlich** sind die Eingabeparameter im Blatt `Anlage` (Nennwerte, Kennzahlen,
  Zeitpläne, Preise, Geometrie) und das vollständige Stundenprotokoll im Blatt
  `Ergebnis` ab Zeile 20 samt Jahressummen — dieses stammt aus einem echten Jahreslauf.
- **Nicht verlässlich** sind einzelne Zwischenwerte im Blatt `Anlage`: Werte an
  Blockgrenzen widersprechen ihren Formeln, weil `T_AU` nach dem Lauf von Hand auf 0
  gesetzt wurde. Innerhalb eines Bausteinblocks sind die Werte konsistent, weichen aber
  in der letzten Nachkommastelle ab.
- Bausteintests verwenden daher Werte aus **einem** Block als Stichprobe mit relativer
  Toleranz 1e-3. Der Gesamtabgleich erfolgt gegen das Stundenprotokoll.

---

## Dateiaufbau

| Datei | Verantwortung |
|---|---|
| `app.py` | Anwendungsfabrik, Blueprints, Logging |
| `core/config.py` | Pfade, Port, Konstanten |
| `core/database.py` | Verbindung, Schema, Wiederholung bei Sperren |
| `core/bausteine/basis.py` | `Param`, `Port`, `Luft`, Rollen, Registrierung |
| `core/bausteine/stoffdaten.py` | Sättigungsdruck, Sättigungsfeuchte, Enthalpie, rel. Feuchte |
| `core/bausteine/erhitzer.py` … | je eine Datei pro Kartentyp |
| `core/graph.py` | Karten, Ports, automatische Verdrahtung, Sortierung |
| `core/solver.py` | Rückwärtslauf, Vorwärtslauf, Iteration, Zustandsfortschreibung |
| `core/anlagen.py` | Lesen und Schreiben von Anlagen, Karten, Pfeilen |
| `core/wetter/try_import.py` | TRY-Dateien einlesen |
| `core/vorlagen/ax_sim_2_1.py` | die Anlage aus der Excel als Vorlage |
| `core/ergebnisse.py` | Zeitreihen und Bilanz speichern und laden |
| `routes/*.py` | Blueprints je Themenbereich |
| `static/js/editor.js` | Leinwand, Karten, Auswahl |
| `static/js/pfeile.js` | Pfeile zeichnen und verbinden |
| `static/js/panel.js` | Parameterfenster |
| `static/symbole/*.svg` | Kartensymbole |
| `tests/` | Spiegelbild der Modulstruktur |

---

## Task 1: Projektgerüst und Datenbank

**Files:**
- Create: `requirements.txt`, `app.py`, `core/__init__.py`, `core/config.py`,
  `core/database.py`, `routes/__init__.py`, `routes/pages.py`,
  `templates/index.html`, `static/css/style.css`, `README.md`, `conftest.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Consumes: nichts
- Produces: `core.config.DB_PATH`, `core.config.PORT`, `core.database.get_db()`,
  `core.database.close_db(exception=None)`, `core.database.init_db()`,
  `app.create_app() -> Flask`

- [ ] **Step 1: Write the failing test**

`tests/test_database.py`:

```python
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
        spalten = {r[1] for r in db.execute("PRAGMA table_info(port)")}
    assert {"projekt", "anlage", "karte", "port", "pfeil", "verbindung"} <= namen
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
```

`conftest.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_database.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Write the implementation**

`requirements.txt`:

```
Flask>=3.0
pytest>=8.0
xlrd>=2.0
openpyxl>=3.1
```

`core/config.py`:

```python
"""Zentrale Einstellungen der RLT-Simulation."""

import os
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent

DB_PATH = WURZEL / "rlt.db"
LOG_FILE = WURZEL / "rlt.log"
LOG_LEVEL = os.environ.get("RLT_LOG_LEVEL", "INFO")

PORT = int(os.environ.get("RLT_PORT", "5055"))
SECRET_KEY = os.environ.get("RLT_SECRET_KEY", "rlt-simulation-lokal")

SQLITE_RETRY_MAX = 5
SQLITE_RETRY_BACKOFF = 0.05

# Grenzen der Fixpunkt-Iteration, entsprechend Application.Iteration in der Excel
MAX_ITERATIONEN = 100
MAX_AENDERUNG = 0.001
```

`core/database.py`:

```python
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
```

`routes/pages.py`:

```python
from flask import Blueprint, render_template

bp = Blueprint("pages", __name__)


@bp.route("/")
def index():
    return render_template("index.html")
```

`routes/__init__.py`: leer.

`app.py`:

```python
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask

from core import config
from core.database import close_db, init_db


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY

    config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        str(config.LOG_FILE), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    app.logger.addHandler(handler)
    app.logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    app.teardown_appcontext(close_db)

    from routes import pages

    app.register_blueprint(pages.bp)

    with app.app_context():
        init_db()

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=config.PORT, debug=True)
```

`templates/index.html`:

```html
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RLT-Simulation</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
  <div class="app">
    <p>RLT-Simulation</p>
  </div>
</body>
</html>
```

`static/css/style.css`:

```css
:root {
  --bg: #f8f9fa;
  --surface: #ffffff;
  --border: #dadce0;
  --border-light: #e8eaed;
  --text: #3c4043;
  --text-secondary: #5f6368;
  --blue: #1a73e8;
  --blue-tint: #e8f0fe;
  --danger: #d93025;
  --radius: 10px;
  --font-body: Roboto, Arial, sans-serif;
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  height: 100%;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  font-size: 14px;
}

.app { display: flex; height: 100vh; }
```

`README.md`:

```markdown
# RLT-Simulation

Simulation raumlufttechnischer Anlagen als Flask-Webanwendung — Nachfolger der
Excel-Mappe `RLTSimulation_Vorlage_AX_SIM_2.1`.

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Starten

```bash
python3 app.py
```

Danach im Browser `http://127.0.0.1:5055` öffnen. Im lokalen Netz ist die Anwendung
über `http://<IP-Adresse>:5055` erreichbar. Beim ersten Start wird die
SQLite-Datenbank `rlt.db` angelegt.

## Tests

```bash
pytest
```

## Referenz

Unter `referenz/` liegen die ursprüngliche Excel-Mappe, ihre ausgelesenen Formeln und
die VBA-Module. Sie sind die fachliche Grundlage und die Prüfgrundlage der Umsetzung.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_database.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add requirements.txt app.py core routes templates static README.md conftest.py tests
git commit -m "Projektgeruest mit Flask, SQLite-Schema und Tests"
```

---

## Task 2: Referenzdaten aus der Excel ziehen

Erzeugt die Prüfgrundlage für alle späteren Tasks: die Wetterdaten und das
Stundenprotokoll des Jahreslaufs als CSV.

**Files:**
- Create: `werkzeuge/__init__.py`, `werkzeuge/referenz_export.py`, `tests/daten/wetterdaten_try04.csv`,
  `tests/daten/ergebnis_jahreslauf.csv`, `tests/daten/jahresbilanz.json`
- Test: `tests/test_referenzdaten.py`

**Interfaces:**
- Consumes: `referenz/RLTSimulation_Vorlage_AX_SIM_2.1.xls`
- Produces: die drei Dateien unter `tests/daten/`

- [ ] **Step 1: Write the export tool**

`werkzeuge/referenz_export.py`:

```python
"""Zieht Wetterdaten, Stundenprotokoll und Jahresbilanz aus der Excel-Mappe.

Aufruf:  python3 werkzeuge/referenz_export.py
Ergebnis: drei Dateien unter tests/daten/
"""

import csv
import json
from pathlib import Path

import xlrd

WURZEL = Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "referenz" / "RLTSimulation_Vorlage_AX_SIM_2.1.xls"
ZIEL = WURZEL / "tests" / "daten"


def exportiere():
    ZIEL.mkdir(parents=True, exist_ok=True)
    mappe = xlrd.open_workbook(str(QUELLE))

    wetter = mappe.sheet_by_name("Wetterdaten")
    with open(ZIEL / "wetterdaten_try04.csv", "w", newline="", encoding="utf-8") as f:
        schreiber = csv.writer(f)
        schreiber.writerow(
            ["datum", "t_au", "x_au", "str_s", "str_o", "str_w", "str_n", "str_h"]
        )
        for zeile in range(4, wetter.nrows):
            schreiber.writerow(wetter.row_values(zeile)[:8])

    ergebnis = mappe.sheet_by_name("Ergebnis")
    with open(ZIEL / "ergebnis_jahreslauf.csv", "w", newline="", encoding="utf-8") as f:
        schreiber = csv.writer(f)
        schreiber.writerow(
            [
                "datum", "t_au", "x_au", "strom_ht", "strom_nt",
                "waerme", "kaelte", "wasser", "wrg", "t_raum", "f_raum",
            ]
        )
        for zeile in range(19, ergebnis.nrows):
            werte = ergebnis.row_values(zeile)[:11]
            if werte[0] in ("", None):
                continue
            schreiber.writerow(werte)

    bilanz = {
        "strom_ht_mwh": ergebnis.cell_value(4, 1),
        "strom_nt_mwh": ergebnis.cell_value(5, 1),
        "waerme_mwh": ergebnis.cell_value(11, 1),
        "kaelte_mwh": ergebnis.cell_value(12, 1),
        "wasser_m3": ergebnis.cell_value(13, 1),
        "wrg_mwh": ergebnis.cell_value(15, 8),
        "kosten_gesamt_eur": ergebnis.cell_value(14, 5),
    }
    (ZIEL / "jahresbilanz.json").write_text(
        json.dumps(bilanz, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("geschrieben:", sorted(p.name for p in ZIEL.glob("*")))


if __name__ == "__main__":
    exportiere()
```

- [ ] **Step 2: Run the export**

Run: `python3 werkzeuge/referenz_export.py`
Expected: `geschrieben: ['ergebnis_jahreslauf.csv', 'jahresbilanz.json', 'wetterdaten_try04.csv']`

- [ ] **Step 3: Write the test that guards the reference data**

`tests/test_referenzdaten.py`:

```python
import csv
import json
from pathlib import Path

DATEN = Path(__file__).parent / "daten"


def test_wetterdaten_haben_8760_stunden():
    with open(DATEN / "wetterdaten_try04.csv", encoding="utf-8") as f:
        zeilen = list(csv.DictReader(f))
    assert len(zeilen) == 8760
    assert float(zeilen[0]["t_au"]) == 2.5
    assert float(zeilen[0]["x_au"]) == 4.4


def test_jahreslauf_hat_8760_stunden():
    with open(DATEN / "ergebnis_jahreslauf.csv", encoding="utf-8") as f:
        zeilen = list(csv.DictReader(f))
    assert len(zeilen) == 8760
    assert float(zeilen[0]["t_raum"]) == 15.0


def test_jahresbilanz_entspricht_der_excel():
    bilanz = json.loads((DATEN / "jahresbilanz.json").read_text(encoding="utf-8"))
    assert bilanz["strom_nt_mwh"] == 85.04562246648032
    assert bilanz["waerme_mwh"] == 328.9201998669775
    assert bilanz["kaelte_mwh"] == 45.4806315625887
    assert bilanz["wasser_m3"] == 111.63868300163553
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_referenzdaten.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add werkzeuge tests/daten tests/test_referenzdaten.py
git commit -m "Referenzdaten aus der Excel-Mappe als Pruefgrundlage exportiert"
```

---

## Task 3: Bausteinbasis und Stoffdaten

**Files:**
- Create: `core/bausteine/__init__.py`, `core/bausteine/basis.py`,
  `core/bausteine/stoffdaten.py`
- Test: `tests/bausteine/__init__.py`, `tests/bausteine/conftest.py`,
  `tests/bausteine/test_basis.py`, `tests/bausteine/test_stoffdaten.py`

**Interfaces:**
- Consumes: nichts
- Produces:
  - `basis.Param(schluessel, label, einheit, vorgabe, auswahl=())`
  - `basis.Port(schluessel, art, richtung, rolle, dynamisch=False)`
  - `basis.Luft(V=0.0, T=0.0, x=0.0, dp=0.0)`
  - Konstanten `LUFT`, `SIGNAL`, `EINGANG`, `AUSGANG` und die Rollen
    `ZULUFT`, `ABLUFT`, `AUSSENLUFT`, `FORTLUFT`, `UMLUFT`, `STELLGROESSE`,
    `ISTWERT`, `SOLLWERT`, `MESSWERT` sowie die Energierollen `STROM`,
    `WAERME`, `KAELTE`, `WASSER`
  - `basis.Baustein` mit `berechne(ein, p, zustand) -> (aus, zustand)`,
    `bedarf(aus_bedarf, p) -> dict`, `anfangszustand(p) -> dict` und dem
    Klassenmerkmal `ZUSTAND_UEBER_ITERATION` (Vorgabe `False`)
  - `basis.registriere(klasse)`, `basis.hole(kennung)`, `basis.alle()`
  - `stoffdaten.p_saett(T)`, `stoffdaten.x_saett(T)`, `stoffdaten.enthalpie(T, x)`,
    `stoffdaten.rel_feuchte(T, x)`

- [ ] **Step 1: Write the failing tests**

`tests/bausteine/test_stoffdaten.py`:

```python
import pytest

from core.bausteine import stoffdaten as st


def test_saettigungsdruck_entspricht_der_excel():
    # Anlage!T6 fuer to = 7,94999999999999 (Anlage!T3)
    assert st.p_saett(7.94999999999999) == pytest.approx(1068.3046916476103, rel=1e-9)


def test_saettigungsfeuchte_entspricht_der_excel():
    # Anlage!T7
    assert st.x_saett(7.94999999999999) == pytest.approx(6.716609031450752, rel=1e-9)


def test_enthalpie_entspricht_der_excel():
    # Anlage!S20 fuer T = 18,999999999999936 und x = 0
    assert st.enthalpie(18.999999999999936, 0.0) == pytest.approx(19.19, rel=1e-9)


def test_enthalpie_mit_feuchte():
    # h = 1,01*20 + 8/1000*(2501 + 1,86*20)
    assert st.enthalpie(20.0, 8.0) == pytest.approx(20.2 + 0.008 * 2538.2, rel=1e-12)


def test_relative_feuchte_bei_saettigung_ist_hundert():
    T = 15.0
    assert st.rel_feuchte(T, st.x_saett(T)) == pytest.approx(100.0, abs=0.05)
```

`tests/bausteine/test_basis.py`:

```python
import pytest

from core.bausteine import basis


def test_luft_hat_vorgabewerte():
    luft = basis.Luft()
    assert (luft.V, luft.T, luft.x, luft.dp) == (0.0, 0.0, 0.0, 0.0)


def test_registrierung_findet_baustein():
    @basis.registriere
    class Testbaustein(basis.Baustein):
        KENNUNG = "test_dummy"
        NAME = "Testbaustein"
        GRUPPE = "Test"
        SYMBOL = "test.svg"
        PARAMETER = [basis.Param("a", "A", "kW", 1.0)]
        PORTS = [basis.Port("luft_ein", basis.LUFT, basis.EINGANG, basis.ZULUFT)]
        AUSGABEN = []

        def berechne(self, ein, p, zustand):
            return {}, zustand

    assert basis.hole("test_dummy") is Testbaustein
    assert Testbaustein in basis.alle()


def test_doppelte_kennung_wird_gemeldet():
    """Eine doppelt vergebene Kennung darf nicht stillschweigend ueberschreiben."""

    @basis.registriere
    class Erster(basis.Baustein):
        KENNUNG = "test_doppelt"
        NAME = "Erster"
        GRUPPE = "Test"
        SYMBOL = "test.svg"
        PARAMETER = []
        PORTS = []
        AUSGABEN = []

        def berechne(self, ein, p, zustand):
            return {}, zustand

    with pytest.raises(ValueError, match="schon von Erster belegt"):

        @basis.registriere
        class Zweiter(basis.Baustein):
            KENNUNG = "test_doppelt"
            NAME = "Zweiter"
            GRUPPE = "Test"
            SYMBOL = "test.svg"
            PARAMETER = []
            PORTS = []
            AUSGABEN = []

            def berechne(self, ein, p, zustand):
                return {}, zustand


def test_wegwerfbausteine_lecken_nicht_zwischen_tests():
    """Die conftest-Vorrichtung stellt das Register nach jedem Test wieder her."""
    assert "test_dummy" not in {k.KENNUNG for k in basis.alle()}


def test_hole_meldet_unbekannten_typ():
    with pytest.raises(KeyError, match="gibt es nicht"):
        basis.hole("kein_baustein")


def test_vorgabeparameter_werden_aus_der_deklaration_gebildet():
    @basis.registriere
    class MitVorgabe(basis.Baustein):
        KENNUNG = "test_vorgabe"
        NAME = "Mit Vorgabe"
        GRUPPE = "Test"
        SYMBOL = "test.svg"
        PARAMETER = [
            basis.Param("V_nenn", "V_nenn", "m³/h", 8200.0),
            basis.Param("art", "Art", "-", "F", auswahl=("F", "D", "-")),
        ]
        PORTS = []
        AUSGABEN = []

        def berechne(self, ein, p, zustand):
            return {}, zustand

    assert MitVorgabe.vorgabeparameter() == {"V_nenn": 8200.0, "art": "F"}


def test_bedarf_reicht_volumenstrom_standardmaessig_durch():
    @basis.registriere
    class Durchreiche(basis.Baustein):
        KENNUNG = "test_durchreiche"
        NAME = "Durchreiche"
        GRUPPE = "Test"
        SYMBOL = "test.svg"
        PARAMETER = []
        PORTS = [
            basis.Port("luft_ein", basis.LUFT, basis.EINGANG, basis.ZULUFT),
            basis.Port("luft_aus", basis.LUFT, basis.AUSGANG, basis.ZULUFT),
        ]
        AUSGABEN = []

        def berechne(self, ein, p, zustand):
            return {}, zustand

    assert Durchreiche().bedarf({"luft_aus": 5000.0}, {}) == {"luft_ein": 5000.0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/bausteine -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'core.bausteine'`

- [ ] **Step 3: Write the implementation**

`core/bausteine/stoffdaten.py`:

```python
"""Stoffgleichungen feuchter Luft, uebernommen aus der Excel-Mappe.

Die Polynome stehen dort in Anlage!T6, Anlage!T7, Anlage!S20 und Anlage!X147/X148.
Sie werden bewusst unveraendert nachgebildet, damit die Ergebnisse vergleichbar
bleiben - eine genauere Zustandsgleichung wuerde andere Zahlen liefern.
"""

import math


def p_saett(T: float) -> float:
    """Saettigungsdampfdruck in Pa bei der Temperatur T in °C."""
    return 611.0 * math.exp(
        -1.91275e-4
        + 7.258e-2 * T
        - 2.939e-4 * T**2
        + 9.841e-7 * T**3
        - 1.92e-9 * T**4
    )


def x_saett(T: float) -> float:
    """Saettigungsfeuchte in g/kg bei der Temperatur T in °C."""
    p = p_saett(T)
    return 0.622 * p / (100000.0 - p) * 1000.0


def enthalpie(T: float, x: float) -> float:
    """Spezifische Enthalpie feuchter Luft in kJ/kg."""
    return 1.01 * T + x / 1000.0 * (2501.0 + 1.86 * T)


def rel_feuchte(T: float, x: float) -> float:
    """Relative Feuchte in Prozent."""
    p_dampf = x / 1000.0 / (0.6222 + x / 1000.0) * 100000.0
    return p_dampf / p_saett(T) * 100.0
```

`core/bausteine/basis.py`:

```python
"""Grundtypen aller Bausteine: Parameter, Ports, Luftzustand, Registrierung.

Ein Baustein deklariert sich vollstaendig selbst. Palette, Parameterfenster,
Portanlage in der Datenbank und Ergebnisspalten werden aus dieser Deklaration
erzeugt - ein neuer Kartentyp ist deshalb genau eine neue Datei.
"""

from dataclasses import dataclass

# Portarten
LUFT = "luft"
SIGNAL = "signal"

# Portrichtungen
EINGANG = "ein"
AUSGANG = "aus"

# Portrollen. Sie steuern die automatische Verdrahtung.
ZULUFT = "zuluft"
ABLUFT = "abluft"
AUSSENLUFT = "aussenluft"
FORTLUFT = "fortluft"
UMLUFT = "umluft"
# Neutraler Luftweg: Verteiler und Sammler stehen in jedem Strang, sie duerfen
# sowohl an Zuluft als auch an Abluft haengen.
LUFTWEG = "luftweg"
STELLGROESSE = "stellgroesse"
ISTWERT = "istwert"
SOLLWERT = "sollwert"
MESSWERT = "messwert"

# Energierollen. Sie sorgen dafuer, dass beim Verbinden mit der Bilanzkarte die
# elektrische Leistung auf Strom trifft und nicht auf Waerme.
STROM = "strom"
WAERME = "waerme"
KAELTE = "kaelte"
WASSER = "wasser"

LUFTROLLEN = (ZULUFT, ABLUFT, AUSSENLUFT, FORTLUFT, UMLUFT, LUFTWEG)
ENERGIEROLLEN = (STROM, WAERME, KAELTE, WASSER)


@dataclass(frozen=True)
class Param:
    """Ein einstellbarer Parameter einer Karte."""

    schluessel: str
    label: str
    einheit: str
    vorgabe: float | str
    auswahl: tuple = ()


@dataclass(frozen=True)
class Port:
    """Ein Anschluss einer Karte."""

    schluessel: str
    art: str
    richtung: str
    rolle: str
    dynamisch: bool = False


@dataclass
class Luft:
    """Ein Luftzustand, wie er ueber einen Luft-Port fliesst."""

    V: float = 0.0    # Volumenstrom in m³/h
    T: float = 0.0    # Temperatur in °C
    x: float = 0.0    # absolute Feuchte in g/kg
    dp: float = 0.0   # Druckverlust in Pa

    def kopie(self) -> "Luft":
        return Luft(self.V, self.T, self.x, self.dp)


class Baustein:
    """Oberklasse aller Kartentypen.

    ZUSTAND_UEBER_ITERATION unterscheidet die beiden Arten von Gedaechtnis:

    * False (Vorgabe) - Speichergroessen von Stunde zu Stunde, etwa Raum- und
      Wandtemperatur. Innerhalb einer Stunde sehen alle Iterationen denselben
      Startwert; erst am Ende der Stunde wird fortgeschrieben. Das entspricht
      dem VBA-Unterprogramm Speicher().
    * True - Groessen, die sich ueber die Iterationen selbst aufbauen. Das sind
      die Regler: in der Excel bezieht sich ihr Ausgang auf den eigenen Vorwert
      (K51 = J57 - Regelabweichung/Xp), wodurch sie waehrend der iterativen
      Neuberechnung integrieren. Ohne dieses Kennzeichen wuerde ein Regler je
      Stunde nur einen einzigen Proportionalschritt machen und den Sollwert nie
      erreichen.
    """

    ZUSTAND_UEBER_ITERATION: bool = False
    KENNUNG: str = ""
    NAME: str = ""
    GRUPPE: str = ""
    SYMBOL: str = ""
    PARAMETER: list = []
    PORTS: list = []
    AUSGABEN: list = []

    @classmethod
    def vorgabeparameter(cls) -> dict:
        return {p.schluessel: p.vorgabe for p in cls.PARAMETER}

    @classmethod
    def port(cls, schluessel: str) -> Port:
        for p in cls.PORTS:
            if p.schluessel == schluessel:
                return p
        raise KeyError(f"Port '{schluessel}' gibt es nicht in {cls.KENNUNG}")

    def berechne(self, ein: dict, p: dict, zustand: dict) -> tuple:
        """Rechnet den Baustein fuer eine Stunde.

        ein     -- {portschluessel: Luft oder Zahl}
        p       -- Parameterwerte
        zustand -- Speichergroessen der vorigen Stunde

        Rueckgabe: ({portschluessel und Ausgabegroessen: Wert}, neuer Zustand)
        """
        raise NotImplementedError

    def bedarf(self, aus_bedarf: dict, p: dict) -> dict:
        """Volumenstrombedarf im Rueckwaertslauf.

        Vorgabe: die Summe dessen, was an den Luftausgaengen abgenommen wird,
        wird auf den einzigen Lufteingang gefordert. Bausteine, die den
        Volumenstrom selbst bestimmen - vor allem Ventilatoren - ueberschreiben
        diese Methode.
        """
        summe = sum(aus_bedarf.values())
        eingaenge = [
            p_.schluessel
            for p_ in self.PORTS
            if p_.art == LUFT and p_.richtung == EINGANG
        ]
        if not eingaenge:
            return {}
        return {eingaenge[0]: summe}

    def anfangszustand(self, p: dict) -> dict:
        """Speichergroessen zu Beginn der Simulation."""
        return {}


_REGISTER: dict = {}


def registriere(klasse):
    """Klassendekorator: macht einen Baustein in Palette und Solver bekannt."""
    if not klasse.KENNUNG:
        raise ValueError(f"{klasse.__name__} hat keine KENNUNG")
    vorhanden = _REGISTER.get(klasse.KENNUNG)
    if vorhanden is not None and vorhanden is not klasse:
        raise ValueError(
            f"Die Kennung '{klasse.KENNUNG}' ist schon von {vorhanden.__name__} belegt"
        )
    _REGISTER[klasse.KENNUNG] = klasse
    return klasse


def hole(kennung: str):
    if kennung not in _REGISTER:
        raise KeyError(f"Den Baustein '{kennung}' gibt es nicht")
    return _REGISTER[kennung]


def alle() -> list:
    return list(_REGISTER.values())


def nach_gruppen() -> dict:
    """Alle Bausteine nach Palettengruppe sortiert."""
    gruppen: dict = {}
    for klasse in _REGISTER.values():
        gruppen.setdefault(klasse.GRUPPE, []).append(klasse)
    return gruppen
```

`core/bausteine/__init__.py`:

```python
"""Bausteinbibliothek.

Beim Import werden alle Kartentypen geladen und registrieren sich selbst.
Ein neuer Kartentyp braucht nur eine neue Datei und eine Zeile in DIESE Liste.
"""

from core.bausteine import basis, stoffdaten  # noqa: F401

MODULE = []


def lade_alle():
    import importlib

    for name in MODULE:
        importlib.import_module(f"core.bausteine.{name}")
```

`tests/bausteine/__init__.py`: leer anlegen.

`tests/bausteine/conftest.py`:

```python
"""Haelt das Bausteinregister zwischen den Tests sauber.

Mehrere Tests melden Wegwerf-Bausteine an. Ohne Wiederherstellung blieben sie
fuer den Rest des Testlaufs im Register und taeuchten in jeder spaeteren
Auswertung von basis.alle() oder basis.nach_gruppen() auf.
"""

import pytest

from core.bausteine import basis


@pytest.fixture(autouse=True)
def register_zuruecksetzen():
    vorher = dict(basis._REGISTER)
    yield
    basis._REGISTER.clear()
    basis._REGISTER.update(vorher)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/bausteine -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add core/bausteine tests/bausteine
git commit -m "Bausteinbasis mit Ports, Rollen, Registrierung und Stoffdaten"
```

---

## Hinweis zur Testgestaltung der Bausteine

Wo die Excel einen belastbaren Rechenstand enthält, wird gegen dessen Zahlen geprüft —
das sind die Blöcke Wärmerückgewinnung (`I:K`, Zeilen 9–21), Luftwäscher (`AA:AC`,
Zeilen 31–43), Zuluftventilator (`X:Z`, Zeilen 9–21), Erhitzer (`L:N`, Zeilen 9–21) und
die Raumgeometrie (`AG100:AL134`). Diese Werte sind nachgerechnet und konsistent; sie
stehen als Zahlenliteral im Test, damit eine spätere Änderung an der Physik auffällt.

Wo der gespeicherte Zustand die Karte abgeschaltet zeigt (Kühler, Mischkammer,
Dampfbefeuchter), prüfen die Tests stattdessen Verhalten an nachvollziehbaren Fällen:
Grenzfälle bei Stellgröße 0 und 100, Sättigungsbegrenzung, Erhaltungssätze. Der
eigentliche Nachweis dieser Bausteine ist der Jahresabgleich in Task 22.

---

## Task 4: Erhitzer und Kühler

**Files:**
- Create: `core/bausteine/erhitzer.py`, `core/bausteine/kuehler.py`
- Modify: `core/bausteine/__init__.py` (Liste `MODULE`)
- Test: `tests/bausteine/test_erhitzer.py`, `tests/bausteine/test_kuehler.py`

**Interfaces:**
- Consumes: `basis.Baustein`, `basis.Luft`, `basis.Param`, `basis.Port`,
  `stoffdaten.x_saett`, `stoffdaten.enthalpie`
- Produces: `erhitzer.Erhitzer` (Kennung `"erhitzer"`), `kuehler.Kuehler`
  (Kennung `"kuehler"`). Beide geben aus `berechne` ein Wörterbuch mit
  `"luft_aus"` (`Luft`) und den Ausgabegrößen zurück; Erhitzer zusätzlich `"QH"`,
  Kühler `"QK"` und `"warnung"`.

- [ ] **Step 1: Write the failing tests**

`tests/bausteine/test_erhitzer.py`:

```python
import pytest

from core.bausteine.basis import Luft
from core.bausteine.erhitzer import Erhitzer


def parameter(**abweichend):
    p = Erhitzer.vorgabeparameter()
    p.update(abweichend)
    return p


def test_erhitzer_entspricht_der_excel():
    """Anlage!L9:N21 - Erhitzer 1 der ersten Anlage."""
    p = parameter(V_nenn=12200.0, dp_nenn=30.0, QH_max=27.0)
    ein = {
        "luft_ein": Luft(V=12200.0, T=12.614754098360613, x=0.0),
        "stellgroesse": 96.84604938271573,
    }
    aus, _ = Erhitzer().berechne(ein, p, {})
    assert aus["QH"] == pytest.approx(26.148433333333248, rel=1e-12)
    assert aus["luft_aus"].T == pytest.approx(18.999999999999936, rel=1e-12)
    assert aus["luft_aus"].x == 0.0
    assert aus["luft_aus"].dp == pytest.approx(30.0, rel=1e-12)


def test_erhitzer_bei_stellgroesse_null_veraendert_nichts():
    p = parameter(V_nenn=12200.0, dp_nenn=30.0, QH_max=27.0)
    ein = {"luft_ein": Luft(V=12200.0, T=5.0, x=3.0), "stellgroesse": 0.0}
    aus, _ = Erhitzer().berechne(ein, p, {})
    assert aus["QH"] == 0.0
    assert aus["luft_aus"].T == pytest.approx(5.0)


def test_erhitzer_ohne_volumenstrom_heizt_nicht():
    p = parameter(V_nenn=12200.0, dp_nenn=30.0, QH_max=27.0)
    ein = {"luft_ein": Luft(V=0.0, T=5.0, x=3.0), "stellgroesse": 100.0}
    aus, _ = Erhitzer().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(5.0)


def test_druckverlust_steigt_quadratisch_mit_dem_volumenstrom():
    p = parameter(V_nenn=12200.0, dp_nenn=30.0, QH_max=27.0)
    ein = {"luft_ein": Luft(V=6100.0, T=5.0, x=3.0), "stellgroesse": 0.0}
    aus, _ = Erhitzer().berechne(ein, p, {})
    assert aus["luft_aus"].dp == pytest.approx(30.0 * 0.25)
```

`tests/bausteine/test_kuehler.py`:

```python
import pytest

from core.bausteine import stoffdaten as st
from core.bausteine.basis import Luft
from core.bausteine.kuehler import Kuehler


def parameter(**abweichend):
    p = Kuehler.vorgabeparameter()
    p.update(abweichend)
    return p


def test_kuehler_bei_stellgroesse_null_entspricht_der_excel():
    """Anlage!R9:T21 - der Kuehler steht im gespeicherten Zustand auf 0 %."""
    p = parameter(V_nenn=8200.0, dp_nenn=240.0, QK_nenn=63.0, T_KW_mittel=6.0)
    ein = {
        "luft_ein": Luft(V=8200.0, T=18.999999999999936, x=0.0),
        "stellgroesse": 0.0,
    }
    aus, _ = Kuehler().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(18.999999999999936, rel=1e-12)
    assert aus["QK"] == pytest.approx(0.0, abs=1e-12)
    assert aus["luft_aus"].dp == pytest.approx(240.0)


def test_oberflaechentemperatur_liegt_zwischen_kaltwasser_und_eintritt():
    p = parameter(T_KW_mittel=6.0)
    assert Kuehler().oberflaechentemperatur(30.0, p) == pytest.approx(6.0 + 0.15 * 24.0)


def test_kuehler_entfeuchtet_bis_zur_saettigung_der_oberflaeche():
    p = parameter(V_nenn=8200.0, dp_nenn=240.0, QK_nenn=250.0, T_KW_mittel=6.0)
    ein = {"luft_ein": Luft(V=8200.0, T=30.0, x=12.0), "stellgroesse": 80.0}
    aus, _ = Kuehler().berechne(ein, p, {})

    T_O = 6.0 + 0.15 * (30.0 - 6.0)
    assert aus["luft_aus"].T == pytest.approx(30.0 - 0.8 * (30.0 - T_O))
    assert aus["luft_aus"].x == pytest.approx(12.0 - 0.8 * (12.0 - st.x_saett(T_O)))
    assert aus["luft_aus"].x < 12.0


def test_kuehler_entfeuchtet_nicht_bei_trockener_luft():
    p = parameter(V_nenn=8200.0, dp_nenn=240.0, QK_nenn=250.0, T_KW_mittel=6.0)
    ein = {"luft_ein": Luft(V=8200.0, T=30.0, x=2.0), "stellgroesse": 80.0}
    aus, _ = Kuehler().berechne(ein, p, {})
    assert aus["luft_aus"].x == pytest.approx(2.0)


def test_kuehler_meldet_zu_niedrige_leistung():
    p = parameter(V_nenn=8200.0, dp_nenn=240.0, QK_nenn=5.0, T_KW_mittel=6.0)
    ein = {"luft_ein": Luft(V=8200.0, T=30.0, x=12.0), "stellgroesse": 100.0}
    aus, _ = Kuehler().berechne(ein, p, {})
    assert aus["warnung"] == "Kuehlleistung zu niedrig"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/bausteine/test_erhitzer.py tests/bausteine/test_kuehler.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'core.bausteine.erhitzer'`

- [ ] **Step 3: Write the implementation**

`core/bausteine/erhitzer.py`:

```python
"""Lufterhitzer. Formeln aus Anlage!M19, M17, M21 und dem Block R116:T136."""

from core.bausteine.basis import (
    AUSGANG, EINGANG, LUFT, MESSWERT, SIGNAL, STELLGROESSE, WAERME, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)


@registriere
class Erhitzer(Baustein):
    KENNUNG = "erhitzer"
    NAME = "Erhitzer"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "erhitzer.svg"

    PARAMETER = [
        Param("V_nenn", "V_nenn", "m³/h", 8200.0),
        Param("dp_nenn", "dp_nenn", "Pa", 240.0),
        Param("QH_max", "QH_max", "kW", 101.0),
    ]

    PORTS = [
        Port("luft_ein", LUFT, EINGANG, ZULUFT),
        Port("luft_aus", LUFT, AUSGANG, ZULUFT),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
        Port("QH", SIGNAL, AUSGANG, WAERME),
    ]

    AUSGABEN = ["T_aus", "F_aus", "QH", "dp"]

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        u = float(ein.get("stellgroesse", 0.0))

        QH = 0.0 if luft.V <= 0 else u / 100.0 * p["QH_max"]

        T_aus = luft.T
        if luft.V > 0:
            T_aus = luft.T + 3600.0 * QH / (1.2 * 1.007 * luft.V)

        dp = 0.0
        if p["V_nenn"]:
            dp = p["dp_nenn"] * (luft.V / p["V_nenn"]) ** 2

        aus = Luft(V=luft.V, T=T_aus, x=luft.x, dp=dp)
        return {"luft_aus": aus, "QH": QH, "T_aus": T_aus, "F_aus": luft.x, "dp": dp}, zustand
```

`core/bausteine/kuehler.py`:

```python
"""Luftkuehler mit Taupunktentfeuchtung.

Formeln aus Anlage!AC117, AB131 bis AB135 sowie der Warnung in AA136.
Die Oberflaechentemperatur wird wie in der Excel als Kaltwassertemperatur plus
15 Prozent der Spreizung zur Eintrittsluft angesetzt.
"""

from core.bausteine import stoffdaten as st
from core.bausteine.basis import (
    AUSGANG, EINGANG, KAELTE, LUFT, MESSWERT, SIGNAL, STELLGROESSE, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)


@registriere
class Kuehler(Baustein):
    KENNUNG = "kuehler"
    NAME = "Kühler"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "kuehler.svg"

    PARAMETER = [
        Param("V_nenn", "V_nenn", "m³/h", 8200.0),
        Param("dp_nenn", "dp_nenn", "Pa", 240.0),
        Param("QK_nenn", "QK_nenn", "kW", 63.0),
        Param("T_KW_mittel", "T_KW_mittel", "°C", 6.0),
    ]

    PORTS = [
        Port("luft_ein", LUFT, EINGANG, ZULUFT),
        Port("luft_aus", LUFT, AUSGANG, ZULUFT),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
        Port("QK", SIGNAL, AUSGANG, KAELTE),
    ]

    AUSGABEN = ["T_aus", "F_aus", "QK", "dp"]

    def oberflaechentemperatur(self, T_ein, p):
        return p["T_KW_mittel"] + 0.15 * (T_ein - p["T_KW_mittel"])

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        u = float(ein.get("stellgroesse", 0.0))

        T_O = self.oberflaechentemperatur(luft.T, p)
        x_O = st.x_saett(T_O)

        T_aus = luft.T - u / 100.0 * (luft.T - T_O)
        x_aus = luft.x
        if x_O < luft.x:
            x_aus = luft.x - u / 100.0 * (luft.x - x_O)

        QK = 0.0
        if luft.V > 0:
            QK = luft.V / 3600.0 * 1.2 * (
                st.enthalpie(luft.T, luft.x) - st.enthalpie(T_aus, x_aus)
            )

        dp = 0.0
        if p["V_nenn"]:
            dp = p["dp_nenn"] * (luft.V / p["V_nenn"]) ** 2

        warnung = "Kuehlleistung zu niedrig" if QK > p["QK_nenn"] else ""

        aus = Luft(V=luft.V, T=T_aus, x=x_aus, dp=dp)
        return (
            {
                "luft_aus": aus, "QK": QK, "warnung": warnung,
                "T_aus": T_aus, "F_aus": x_aus, "dp": dp,
            },
            zustand,
        )
```

`core/bausteine/__init__.py` — `MODULE` ergänzen:

```python
MODULE = ["erhitzer", "kuehler"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/bausteine -v`
Expected: alle Tests bestanden

- [ ] **Step 5: Commit**

```bash
git add core/bausteine tests/bausteine
git commit -m "Bausteine Erhitzer und Kuehler mit Excel-Formeln"
```

---

## Task 5: Wärmerückgewinnung und Mischkammer

**Files:**
- Create: `core/bausteine/wrg.py`, `core/bausteine/mischkammer.py`
- Modify: `core/bausteine/__init__.py`
- Test: `tests/bausteine/test_wrg.py`, `tests/bausteine/test_mischkammer.py`

**Interfaces:**
- Produces: `wrg.Waermerueckgewinnung` (Kennung `"wrg"`), Ports `zuluft_ein`,
  `zuluft_aus`, `abluft_ein`, `abluft_aus`, `stellgroesse`, `stellgroesse_bypass`,
  `Q_WRG`; `mischkammer.Mischkammer` (Kennung `"mischkammer"`), Ports
  `aussenluft_ein`, `umluft_ein`, `luft_aus`, `umluftanteil`.

- [ ] **Step 1: Write the failing tests**

`tests/bausteine/test_wrg.py`:

```python
import pytest

from core.bausteine.basis import Luft
from core.bausteine.wrg import Waermerueckgewinnung


def parameter(**abweichend):
    p = Waermerueckgewinnung.vorgabeparameter()
    p.update(abweichend)
    return p


def test_wrg_entspricht_der_excel():
    """Anlage!I9:K21 - dieser Block ist im gespeicherten Zustand konsistent."""
    p = parameter(
        V_nenn=12200.0,
        dp_WRG_nenn=170.0,
        dp_Bypass_nenn=50.0,
        rueckwaermzahl=81.0,
        rueckfeuchtzahl=0.0,
    )
    ein = {
        "zuluft_ein": Luft(V=12200.0, T=0.0, x=0.0),
        "abluft_ein": Luft(V=10000.0, T=18.999999999999936, x=0.0),
        "stellgroesse": 100.0,
        "stellgroesse_bypass": 0.0,
    }
    aus, _ = Waermerueckgewinnung().berechne(ein, p, {})

    assert aus["zuluft_aus"].T == pytest.approx(12.614754098360613, rel=1e-12)
    assert aus["abluft_aus"].T == pytest.approx(3.6099999999999888, rel=1e-10)
    assert aus["Q_WRG"] == pytest.approx(51.659099999999825, rel=1e-10)
    assert aus["zuluft_aus"].dp == pytest.approx(170.0, rel=1e-12)
    assert aus["abluft_aus"].dp == pytest.approx(114.21660843859178, rel=1e-12)


def test_wrg_ohne_abluft_uebertraegt_nichts():
    p = parameter(rueckwaermzahl=81.0)
    ein = {
        "zuluft_ein": Luft(V=12200.0, T=0.0, x=0.0),
        "abluft_ein": Luft(V=0.0, T=20.0, x=8.0),
        "stellgroesse": 100.0,
        "stellgroesse_bypass": 0.0,
    }
    aus, _ = Waermerueckgewinnung().berechne(ein, p, {})
    assert aus["zuluft_aus"].T == pytest.approx(0.0)
    assert aus["Q_WRG"] == pytest.approx(0.0)


def test_geoeffneter_bypass_schaltet_die_rueckgewinnung_ab():
    p = parameter(V_nenn=12200.0, rueckwaermzahl=81.0)
    ein = {
        "zuluft_ein": Luft(V=12200.0, T=0.0, x=0.0),
        "abluft_ein": Luft(V=12200.0, T=20.0, x=8.0),
        "stellgroesse": 100.0,
        "stellgroesse_bypass": 100.0,
    }
    aus, _ = Waermerueckgewinnung().berechne(ein, p, {})
    assert aus["zuluft_aus"].T == pytest.approx(0.0)


def test_rueckfeuchtzahl_uebertraegt_feuchte():
    p = parameter(V_nenn=10000.0, rueckwaermzahl=0.0, rueckfeuchtzahl=50.0)
    ein = {
        "zuluft_ein": Luft(V=10000.0, T=0.0, x=2.0),
        "abluft_ein": Luft(V=10000.0, T=20.0, x=10.0),
        "stellgroesse": 100.0,
        "stellgroesse_bypass": 0.0,
    }
    aus, _ = Waermerueckgewinnung().berechne(ein, p, {})
    assert aus["zuluft_aus"].x == pytest.approx(2.0 + 0.5 * 8.0)
```

`tests/bausteine/test_mischkammer.py`:

```python
import pytest

from core.bausteine.basis import Luft
from core.bausteine.mischkammer import Mischkammer


def test_mischt_nach_umluftanteil():
    p = {"max_umluft": 80.0}
    ein = {
        "aussenluft_ein": Luft(V=7000.0, T=0.0, x=2.0),
        "umluft_ein": Luft(V=3000.0, T=20.0, x=10.0),
        "umluftanteil": 30.0,
    }
    aus, _ = Mischkammer().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(6.0)
    assert aus["luft_aus"].x == pytest.approx(0.7 * 2.0 + 0.3 * 10.0)


def test_umluftanteil_wird_auf_das_maximum_begrenzt():
    p = {"max_umluft": 40.0}
    ein = {
        "aussenluft_ein": Luft(V=7000.0, T=0.0, x=0.0),
        "umluft_ein": Luft(V=3000.0, T=20.0, x=0.0),
        "umluftanteil": 90.0,
    }
    aus, _ = Mischkammer().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(0.4 * 20.0)


def test_ohne_umluft_bleibt_die_aussenluft_unveraendert():
    p = {"max_umluft": 80.0}
    ein = {
        "aussenluft_ein": Luft(V=10000.0, T=-5.0, x=1.5),
        "umluft_ein": Luft(V=0.0, T=20.0, x=10.0),
        "umluftanteil": 0.0,
    }
    aus, _ = Mischkammer().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(-5.0)
    assert aus["luft_aus"].x == pytest.approx(1.5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/bausteine/test_wrg.py tests/bausteine/test_mischkammer.py -v`
Expected: FAIL mit `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/bausteine/wrg.py`:

```python
"""Waermerueckgewinnung mit Bypass.

Formeln aus Anlage!J152 bis J157 (Zuluft, Fortluft, Q_WRG, Druckverluste).
Der Wirkungsgrad wird mit dem Verhaeltnis des kleineren zum jeweiligen
Volumenstrom gewichtet, genau wie in der Excel.
"""

from core.bausteine.basis import (
    ABLUFT, AUSGANG, EINGANG, LUFT, MESSWERT, SIGNAL, STELLGROESSE, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)


@registriere
class Waermerueckgewinnung(Baustein):
    KENNUNG = "wrg"
    NAME = "Wärmerückgewinnung"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "wrg.svg"

    PARAMETER = [
        Param("V_nenn", "V_nenn", "m³/h", 12200.0),
        Param("dp_WRG_nenn", "dp_WRG_nenn", "Pa", 170.0),
        Param("dp_Bypass_nenn", "dp_Byp_nenn", "Pa", 50.0),
        Param("rueckwaermzahl", "Rückwärmzahl", "%", 81.0),
        Param("rueckfeuchtzahl", "Rückfeuchtzahl", "%", 0.0),
    ]

    PORTS = [
        Port("zuluft_ein", LUFT, EINGANG, ZULUFT),
        Port("zuluft_aus", LUFT, AUSGANG, ZULUFT),
        Port("abluft_ein", LUFT, EINGANG, ABLUFT),
        Port("abluft_aus", LUFT, AUSGANG, ABLUFT),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("stellgroesse_bypass", SIGNAL, EINGANG, STELLGROESSE),
        Port("Q_WRG", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["T_ZU", "F_ZU", "T_FO", "F_FO", "Q_WRG", "dp_ZU", "dp_AB"]

    def berechne(self, ein, p, zustand):
        zu = ein.get("zuluft_ein", Luft())
        ab = ein.get("abluft_ein", Luft())
        u = float(ein.get("stellgroesse", 0.0))
        byp = float(ein.get("stellgroesse_bypass", 0.0))

        wirksam = 0.0
        if zu.V > 0 and ab.V > 0:
            wirksam = u / 100.0 * (100.0 - byp) / 100.0

        kleiner = min(zu.V, ab.V) if (zu.V > 0 and ab.V > 0) else 0.0

        T_ZU, F_ZU, T_FO, F_FO = zu.T, zu.x, ab.T, ab.x
        if wirksam > 0:
            anteil_zu = kleiner / zu.V
            anteil_ab = kleiner / ab.V
            T_ZU = zu.T + p["rueckwaermzahl"] / 100.0 * (ab.T - zu.T) * anteil_zu * wirksam
            F_ZU = zu.x + p["rueckfeuchtzahl"] / 100.0 * (ab.x - zu.x) * anteil_zu * wirksam
            T_FO = ab.T - p["rueckwaermzahl"] / 100.0 * (ab.T - zu.T) * anteil_ab * wirksam
            F_FO = ab.x - p["rueckfeuchtzahl"] / 100.0 * (ab.x - zu.x) * anteil_ab * wirksam

        Q_WRG = zu.V / 3600.0 * 1.2 * 1.007 * (T_ZU - zu.T)

        dp_ZU = dp_AB = 0.0
        if p["V_nenn"]:
            offen = (100.0 - byp) / 100.0
            zu_byp = byp / 100.0
            dp_ZU = (zu.V / p["V_nenn"]) ** 2 * (
                p["dp_WRG_nenn"] * offen + p["dp_Bypass_nenn"] * zu_byp
            )
            # Anlage!J43 klammert auf der Abluftseite anders - bewusst uebernommen
            dp_AB = (ab.V / p["V_nenn"]) ** 2 * p["dp_WRG_nenn"] * offen + (
                p["dp_Bypass_nenn"] * zu_byp
            )

        return (
            {
                "zuluft_aus": Luft(V=zu.V, T=T_ZU, x=F_ZU, dp=dp_ZU),
                "abluft_aus": Luft(V=ab.V, T=T_FO, x=F_FO, dp=dp_AB),
                "Q_WRG": Q_WRG,
                "T_ZU": T_ZU, "F_ZU": F_ZU, "T_FO": T_FO, "F_FO": F_FO,
                "dp_ZU": dp_ZU, "dp_AB": dp_AB,
            },
            zustand,
        )

    def bedarf(self, aus_bedarf, p):
        return {
            "zuluft_ein": aus_bedarf.get("zuluft_aus", 0.0),
            "abluft_ein": aus_bedarf.get("abluft_aus", 0.0),
        }
```

`core/bausteine/mischkammer.py`:

```python
"""Mischkammer aus Aussenluft und Umluft. Formeln aus Anlage!M132 bis M134."""

from core.bausteine.basis import (
    AUSGANG, AUSSENLUFT, EINGANG, LUFT, SIGNAL, STELLGROESSE, UMLUFT, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)


@registriere
class Mischkammer(Baustein):
    KENNUNG = "mischkammer"
    NAME = "Mischkammer"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "mischkammer.svg"

    PARAMETER = [Param("max_umluft", "max. Umluft", "%", 80.0)]

    PORTS = [
        Port("aussenluft_ein", LUFT, EINGANG, AUSSENLUFT),
        Port("umluft_ein", LUFT, EINGANG, UMLUFT),
        Port("luft_aus", LUFT, AUSGANG, ZULUFT),
        Port("umluftanteil", SIGNAL, EINGANG, STELLGROESSE),
    ]

    AUSGABEN = ["T_MI", "F_MI", "umluftanteil"]

    def berechne(self, ein, p, zustand):
        au = ein.get("aussenluft_ein", Luft())
        um = ein.get("umluft_ein", Luft())
        anteil = min(float(ein.get("umluftanteil", 0.0)), p["max_umluft"])

        T = ((100.0 - anteil) * au.T + anteil * um.T) / 100.0
        x = ((100.0 - anteil) * au.x + anteil * um.x) / 100.0
        V = au.V + um.V

        return (
            {
                "luft_aus": Luft(V=V, T=T, x=x, dp=0.0),
                "T_MI": T, "F_MI": x, "umluftanteil": anteil,
            },
            zustand,
        )

    def bedarf(self, aus_bedarf, p):
        gesamt = sum(aus_bedarf.values())
        return {"aussenluft_ein": gesamt, "umluft_ein": 0.0}
```

`core/bausteine/__init__.py`:

```python
MODULE = ["erhitzer", "kuehler", "wrg", "mischkammer"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/bausteine -v`
Expected: alle Tests bestanden

- [ ] **Step 5: Commit**

```bash
git add core/bausteine tests/bausteine
git commit -m "Bausteine Waermerueckgewinnung und Mischkammer"
```

---

## Task 6: Dampfbefeuchter und Luftwäscher

**Files:**
- Create: `core/bausteine/dampfbefeuchter.py`, `core/bausteine/luftwaescher.py`
- Modify: `core/bausteine/__init__.py`
- Test: `tests/bausteine/test_dampfbefeuchter.py`, `tests/bausteine/test_luftwaescher.py`

**Interfaces:**
- Produces: `dampfbefeuchter.Dampfbefeuchter` (Kennung `"dampfbefeuchter"`, Ausgaben
  `QH`, `wasser`, `warnung`), `luftwaescher.Luftwaescher` (Kennung `"luftwaescher"`,
  Ausgaben `PE_Pumpe`, `wasser`).

- [ ] **Step 1: Write the failing tests**

`tests/bausteine/test_luftwaescher.py`:

```python
import pytest

from core.bausteine.basis import Luft
from core.bausteine.luftwaescher import Luftwaescher


def parameter(**abweichend):
    p = Luftwaescher.vorgabeparameter()
    p.update(abweichend)
    return p


def test_luftwaescher_entspricht_der_excel():
    """Anlage!AA31:AC43 - dieser Block ist im gespeicherten Zustand konsistent."""
    p = parameter(
        V_nenn=4000.0, dp_nenn=50.0, absalzverlust=10.0, pumpenart="H"
    )
    ein = {
        "luft_ein": Luft(V=4000.0, T=37.76861966236339, x=0.0),
        "stellgroesse": 100.0,
    }
    aus, _ = Luftwaescher().berechne(ein, p, {})

    assert aus["luft_aus"].T == pytest.approx(15.839048772668132, rel=1e-12)
    assert aus["luft_aus"].x == pytest.approx(8.747590530135225, rel=1e-12)
    assert aus["wasser"] == pytest.approx(46.18727799911399, rel=1e-12)
    assert aus["PE_Pumpe"] == pytest.approx(0.17777777777777778, rel=1e-12)
    assert aus["luft_aus"].dp == pytest.approx(50.0, rel=1e-12)


def test_bei_stellgroesse_null_bleibt_die_luft_unveraendert():
    p = parameter(V_nenn=4000.0, dp_nenn=50.0, pumpenart="H")
    ein = {"luft_ein": Luft(V=4000.0, T=30.0, x=6.0), "stellgroesse": 0.0}
    aus, _ = Luftwaescher().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(30.0)
    assert aus["luft_aus"].x == pytest.approx(6.0)
    assert aus["wasser"] == pytest.approx(0.0)


def test_befeuchtung_kuehlt_die_luft_ab():
    p = parameter(V_nenn=4000.0, dp_nenn=50.0, pumpenart="H")
    ein = {"luft_ein": Luft(V=4000.0, T=32.0, x=5.0), "stellgroesse": 100.0}
    aus, _ = Luftwaescher().berechne(ein, p, {})
    assert aus["luft_aus"].T < 32.0
    assert aus["luft_aus"].x > 5.0
```

`tests/bausteine/test_dampfbefeuchter.py`:

```python
import pytest

from core.bausteine import stoffdaten as st
from core.bausteine.basis import Luft
from core.bausteine.dampfbefeuchter import Dampfbefeuchter


def parameter(**abweichend):
    p = Dampfbefeuchter.vorgabeparameter()
    p.update(abweichend)
    return p


def test_elektrodampf_verwendet_feste_enthalpie():
    p = parameter(dampfart="E")
    assert Dampfbefeuchter().dampfenthalpie(p) == 2676.0


def test_fremddampf_folgt_dem_polynom_der_excel():
    p = parameter(dampfart="F", dampftemperatur=180.0)
    erwartet = (
        2501.482
        + 1.789736 * 180.0
        + 8.957546e-4 * 180.0**2
        - 1.300254e-5 * 180.0**3
    )
    assert Dampfbefeuchter().dampfenthalpie(p) == pytest.approx(erwartet)


def test_befeuchtung_erhoeht_feuchte_und_temperatur():
    p = parameter(
        dampfart="E", max_leistung=32.0, absalzverlust=10.0, dampftemperatur=180.0
    )
    ein = {"luft_ein": Luft(V=8200.0, T=20.0, x=5.0), "stellgroesse": 50.0}
    aus, _ = Dampfbefeuchter().berechne(ein, p, {})

    assert aus["luft_aus"].x == pytest.approx(5.0 + 1000.0 * 0.5 * 32.0 / (8200.0 * 1.2))
    assert aus["luft_aus"].T == pytest.approx(
        20.0 + 0.5 * 32.0 * (2676.0 - 2256.9) / (8200.0 * 1.2 * 1.007)
    )
    assert aus["wasser"] == pytest.approx(1.1 * 0.5 * 32.0)
    assert aus["QH"] == pytest.approx(1.1 * 16.0 * (2676.0 - 42.0) / 3600.0)


def test_feuchte_wird_bei_saettigung_begrenzt_und_gemeldet():
    p = parameter(dampfart="E", max_leistung=500.0, absalzverlust=0.0)
    ein = {"luft_ein": Luft(V=1000.0, T=20.0, x=5.0), "stellgroesse": 100.0}
    aus, _ = Dampfbefeuchter().berechne(ein, p, {})
    assert aus["luft_aus"].x == pytest.approx(st.x_saett(20.0))
    assert aus["warnung"] == "Uebersaettigung"


def test_ohne_volumenstrom_passiert_nichts():
    p = parameter(dampfart="E", max_leistung=32.0)
    ein = {"luft_ein": Luft(V=0.0, T=20.0, x=5.0), "stellgroesse": 100.0}
    aus, _ = Dampfbefeuchter().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(20.0)
    assert aus["luft_aus"].x == pytest.approx(5.0)
    assert aus["wasser"] == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/bausteine/test_dampfbefeuchter.py tests/bausteine/test_luftwaescher.py -v`
Expected: FAIL mit `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/bausteine/luftwaescher.py`:

```python
"""Luftwaescher, adiabate Befeuchtung.

Formeln aus Anlage!AF120 bis AF122 (Saettigungszustand aus der Enthalpie) und
AE131 bis AE135. Der feste Faktor 0,9 ist der Saettigungswirkungsgrad der Excel.
"""

from core.bausteine import stoffdaten as st
from core.bausteine.basis import (
    AUSGANG, EINGANG, LUFT, MESSWERT, SIGNAL, STELLGROESSE, STROM, WASSER, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)

SAETTIGUNGSWIRKUNGSGRAD = 0.9


@registriere
class Luftwaescher(Baustein):
    KENNUNG = "luftwaescher"
    NAME = "Luftwäscher"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "luftwaescher.svg"

    PARAMETER = [
        Param("V_nenn", "V_nenn", "m³/h", 8200.0),
        Param("dp_nenn", "dp_nenn", "Pa", 50.0),
        Param("absalzverlust", "Absalzverlust", "%", 10.0),
        Param("pumpenart", "Ventil/FU/HD", "-", "H", auswahl=("V", "F", "H")),
    ]

    PORTS = [
        Port("luft_ein", LUFT, EINGANG, ZULUFT),
        Port("luft_aus", LUFT, AUSGANG, ZULUFT),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
        Port("PE_Pumpe", SIGNAL, AUSGANG, STROM),
        Port("wasser", SIGNAL, AUSGANG, WASSER),
    ]

    AUSGABEN = ["T_aus", "F_aus", "PE_Pumpe", "wasser", "dp"]

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        u = float(ein.get("stellgroesse", 0.0))

        h_ein = st.enthalpie(luft.T, luft.x)
        x_saett = 0.0009 * h_ein**2 + 0.1669 * h_ein + 2.0433
        t_saett = -0.0024 * h_ein**2 + 0.5746 * h_ein - 5.0241

        anteil = SAETTIGUNGSWIRKUNGSGRAD * u / 100.0
        T_aus = luft.T - anteil * (luft.T - t_saett)
        x_aus = luft.x + anteil * (x_saett - luft.x)

        wasser = 0.0
        if luft.V > 0:
            wasser = (
                luft.V * 1.2 * (x_aus - luft.x) / 1000.0
                * (100.0 + p["absalzverlust"]) / 100.0
            )

        PE = 0.0
        if luft.V > 0:
            art = str(p["pumpenart"]).upper()
            if art == "F":
                kennlinie = (u / 100.0) ** 2
            elif art == "V":
                kennlinie = (u / 100.0) ** 0.3
            elif art == "H":
                kennlinie = 0.4 * (u / 100.0) ** 2
            else:
                kennlinie = 1.0
            PE = p["V_nenn"] * 1.2 / 3600.0 * 200.0 / 0.6 / 1000.0 * kennlinie

        dp = 0.0
        if p["V_nenn"]:
            dp = p["dp_nenn"] * (luft.V / p["V_nenn"]) ** 2

        return (
            {
                "luft_aus": Luft(V=luft.V, T=T_aus, x=x_aus, dp=dp),
                "PE_Pumpe": PE, "wasser": wasser,
                "T_aus": T_aus, "F_aus": x_aus, "dp": dp,
            },
            zustand,
        )
```

`core/bausteine/dampfbefeuchter.py`:

```python
"""Dampfbefeuchter mit Elektro- oder Fremddampf.

Formeln aus Anlage!Q120 bis Q122 und P131 bis P134. Bei Elektrodampf rechnet die
Excel mit fester Dampfenthalpie 2676 kJ/kg und schlaegt den Absalzverlust auf den
Wasserverbrauch auf.
"""

from core.bausteine import stoffdaten as st
from core.bausteine.basis import (
    AUSGANG, EINGANG, LUFT, MESSWERT, SIGNAL, STELLGROESSE, WAERME, WASSER, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)


@registriere
class Dampfbefeuchter(Baustein):
    KENNUNG = "dampfbefeuchter"
    NAME = "Dampfbefeuchter"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "dampfbefeuchter.svg"

    PARAMETER = [
        Param("dampftemperatur", "Dampftemp.", "°C", 180.0),
        Param("absalzverlust", "Absalzverlust", "%", 10.0),
        Param("max_leistung", "max. Bef.Leist", "kg/h", 32.0),
        Param("dampfart", "E-/Fremddampf", "-", "E", auswahl=("E", "F")),
    ]

    PORTS = [
        Port("luft_ein", LUFT, EINGANG, ZULUFT),
        Port("luft_aus", LUFT, AUSGANG, ZULUFT),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
        Port("QH", SIGNAL, AUSGANG, WAERME),
        Port("wasser", SIGNAL, AUSGANG, WASSER),
    ]

    AUSGABEN = ["T_aus", "F_aus", "QH", "wasser", "warnung"]

    def dampfenthalpie(self, p):
        if str(p["dampfart"]).upper() == "E":
            return 2676.0
        T_D = p["dampftemperatur"]
        return (
            2501.482
            + 1.789736 * T_D
            + 8.957546e-4 * T_D**2
            - 1.300254e-5 * T_D**3
        )

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        u = float(ein.get("stellgroesse", 0.0))
        h_D = self.dampfenthalpie(p)

        if luft.V <= 0:
            return (
                {
                    "luft_aus": luft.kopie(), "QH": 0.0, "wasser": 0.0, "warnung": "",
                    "T_aus": luft.T, "F_aus": luft.x,
                },
                zustand,
            )

        T_aus = luft.T + u / 100.0 * p["max_leistung"] * (h_D - 2256.9) / (
            luft.V * 1.2 * 1.007
        )
        x_grenze = st.x_saett(luft.T)
        x_roh = luft.x + 1000.0 * u / 100.0 * p["max_leistung"] / (luft.V * 1.2)
        x_aus = min(x_grenze, x_roh)

        aufschlag = 1.0
        if str(p["dampfart"]).upper() == "E":
            aufschlag = (100.0 + p["absalzverlust"]) / 100.0
        wasser = aufschlag * u / 100.0 * p["max_leistung"]
        QH = wasser * (h_D - 42.0) / 3600.0

        warnung = "Uebersaettigung" if x_roh >= x_grenze else ""

        return (
            {
                "luft_aus": Luft(V=luft.V, T=T_aus, x=x_aus, dp=luft.dp),
                "QH": QH, "wasser": wasser, "warnung": warnung,
                "T_aus": T_aus, "F_aus": x_aus,
            },
            zustand,
        )
```

`core/bausteine/__init__.py`:

```python
MODULE = [
    "erhitzer", "kuehler", "wrg", "mischkammer",
    "dampfbefeuchter", "luftwaescher",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/bausteine -v`
Expected: alle Tests bestanden

- [ ] **Step 5: Commit**

```bash
git add core/bausteine tests/bausteine
git commit -m "Bausteine Dampfbefeuchter und Luftwaescher"
```

---

## Task 7: Ventilator

**Files:**
- Create: `core/bausteine/ventilator.py`
- Modify: `core/bausteine/__init__.py`
- Test: `tests/bausteine/test_ventilator.py`

**Interfaces:**
- Produces: `ventilator.Ventilator` (Kennung `"ventilator"`), Parameter `rolle`
  (`"zuluft"` oder `"abluft"`) bestimmt die Portrollen zur Laufzeit über
  `ports_fuer(p)`. `bedarf` gibt den selbst bestimmten Volumenstrom zurück —
  der Ventilator ist der Ausgangspunkt des Rückwärtslaufs.

- [ ] **Step 1: Write the failing test**

`tests/bausteine/test_ventilator.py`:

```python
import pytest

from core.bausteine.basis import Luft
from core.bausteine.ventilator import Ventilator


def parameter(**abweichend):
    p = Ventilator.vorgabeparameter()
    p.update(abweichend)
    return p


def test_ventilator_entspricht_der_excel():
    """Anlage!X9:Z21 - Zuluftventilator mit Frequenzumrichter bei 100 %."""
    p = parameter(
        V_max=8200.0, dp_max=1400.0, dp_konst=1400.0, PE_max=4.9, regelart="F"
    )
    ein = {
        "luft_ein": Luft(V=8200.0, T=37.3471794996003, x=0.0),
        "stellgroesse": 100.0,
    }
    aus, _ = Ventilator().berechne(ein, p, {})

    assert aus["luft_aus"].V == pytest.approx(8200.0, rel=1e-12)
    assert aus["dp"] == pytest.approx(1400.0, rel=1e-12)
    assert aus["PE"] == pytest.approx(4.9, rel=1e-9)
    assert aus["luft_aus"].T == pytest.approx(39.127400876789245, rel=1e-10)


def test_wirkungsgrad_entspricht_der_excel():
    """Anlage!Z7 - V_max * dp_max / 3600000 / PE_max."""
    p = parameter(V_max=8200.0, dp_max=1400.0, PE_max=4.9)
    assert Ventilator().wirkungsgrad(p) == pytest.approx(0.6507936507936508, rel=1e-12)


def test_teillast_senkt_volumenstrom_und_druck():
    p = parameter(
        V_max=8200.0, dp_max=1400.0, dp_konst=0.0, PE_max=4.9, regelart="F"
    )
    ein = {"luft_ein": Luft(V=8200.0, T=20.0, x=5.0), "stellgroesse": 50.0}
    aus, _ = Ventilator().berechne(ein, p, {})
    assert aus["luft_aus"].V == pytest.approx(4100.0)
    assert aus["dp"] == pytest.approx(1400.0 * 0.25)


def test_ungeregelter_ventilator_laeuft_mit_nennleistung():
    p = parameter(
        V_max=8200.0, dp_max=1400.0, dp_konst=1400.0, PE_max=4.9, regelart="-"
    )
    ein = {"luft_ein": Luft(V=8200.0, T=20.0, x=5.0), "stellgroesse": 60.0}
    aus, _ = Ventilator().berechne(ein, p, {})
    assert aus["luft_aus"].V == pytest.approx(8200.0)
    assert aus["PE"] == pytest.approx(4.9)


def test_drallregler_hat_grundlast():
    p = parameter(
        V_max=8200.0, dp_max=1400.0, dp_konst=0.0, PE_max=4.9, regelart="D"
    )
    ein = {"luft_ein": Luft(V=8200.0, T=20.0, x=5.0), "stellgroesse": 0.0}
    aus, _ = Ventilator().berechne(ein, p, {})
    assert aus["PE"] == pytest.approx(0.0)


def test_ventilator_bestimmt_den_volumenstrom_im_rueckwaertslauf():
    p = parameter(V_max=8200.0, regelart="F")
    assert Ventilator().bedarf({"luft_aus": 0.0}, p) == {"luft_ein": 8200.0}


def test_ohne_angeschlossenen_regler_gilt_die_feste_stellgroesse():
    """Anlage!Y16 - in der Excel ist die Stellgroesse des Ventilators eine Konstante."""
    p = parameter(
        V_max=8200.0, dp_max=1400.0, dp_konst=1400.0, PE_max=4.9,
        regelart="F", stellgroesse=100.0,
    )
    aus, _ = Ventilator().berechne({"luft_ein": Luft(V=8200.0, T=20.0, x=5.0)}, p, {})
    assert aus["PE"] == pytest.approx(4.9, rel=1e-9)
    assert aus["luft_aus"].V == pytest.approx(8200.0)


def test_abluftrolle_vergibt_abluftports():
    p = parameter(rolle="abluft")
    rollen = {port.schluessel: port.rolle for port in Ventilator.ports_fuer(p)}
    assert rollen["luft_ein"] == "abluft"
    assert rollen["luft_aus"] == "abluft"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/bausteine/test_ventilator.py -v`
Expected: FAIL mit `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/bausteine/ventilator.py`:

```python
"""Ventilator mit Frequenzumrichter, Drallregler oder ungeregelt.

Formeln aus Anlage!Z121, Z122, Y131 bis Y135. Der Ventilator ist der einzige
Baustein, der den Volumenstrom selbst festlegt; im Rueckwaertslauf ist er daher
der Ausgangspunkt.
"""

from core.bausteine.basis import (
    ABLUFT, AUSGANG, EINGANG, LUFT, MESSWERT, SIGNAL, STELLGROESSE, STROM, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)


@registriere
class Ventilator(Baustein):
    KENNUNG = "ventilator"
    NAME = "Ventilator"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "ventilator.svg"

    PARAMETER = [
        Param("rolle", "Zuluft/Abluft", "-", "zuluft", auswahl=("zuluft", "abluft")),
        Param("V_max", "V_max", "m³/h", 8200.0),
        Param("dp_max", "dp_max", "Pa", 1400.0),
        Param("dp_konst", "dp_konst", "Pa", 1400.0),
        Param("PE_max", "PE_max", "kW", 4.9),
        Param("regelart", "FU/DD/-", "-", "F", auswahl=("F", "D", "-")),
        Param("stellgroesse", "Stellgröße (fest)", "%", 100.0),
    ]

    PORTS = [
        Port("luft_ein", LUFT, EINGANG, ZULUFT),
        Port("luft_aus", LUFT, AUSGANG, ZULUFT),
        Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
        Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
        Port("PE", SIGNAL, AUSGANG, STROM),
    ]

    AUSGABEN = ["T_aus", "F_aus", "PE", "dp", "V"]

    @classmethod
    def ports_fuer(cls, p):
        """Die Luftports tragen je nach Rolle Zuluft oder Abluft."""
        rolle = ABLUFT if p.get("rolle") == "abluft" else ZULUFT
        return [
            Port("luft_ein", LUFT, EINGANG, rolle),
            Port("luft_aus", LUFT, AUSGANG, rolle),
            Port("stellgroesse", SIGNAL, EINGANG, STELLGROESSE),
            Port("T_aus", SIGNAL, AUSGANG, MESSWERT),
            Port("PE", SIGNAL, AUSGANG, STROM),
        ]

    def wirkungsgrad(self, p):
        if not p["PE_max"]:
            return 0.0
        return p["V_max"] * p["dp_max"] / 3600000.0 / p["PE_max"]

    def volumenstrom(self, u, p):
        if str(p["regelart"]) in ("", "-"):
            return p["V_max"]
        return u / 100.0 * p["V_max"]

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        # Ist der Stellgroessen-Port nicht belegt, gilt der eingestellte Wert. In der
        # Excel steht die Stellgroesse des Ventilators ebenfalls als feste Zelle
        # (Anlage!Y16 = 100 %), sie wird dort nicht vom Zeitplan gestellt.
        u = float(ein.get("stellgroesse", p["stellgroesse"]))

        V = self.volumenstrom(u, p)
        dp = 0.0
        if p["V_max"]:
            dp = (p["dp_max"] - p["dp_konst"]) * (u / 100.0) ** 2 + p["dp_konst"]

        eta = self.wirkungsgrad(p)
        eta_teil = eta * (u / 100.0) ** 0.8

        art = str(p["regelart"]).upper()
        PE = 0.0
        if p["V_max"] and u and p["PE_max"] and p["dp_max"] and eta_teil:
            if art == "F":
                PE = u / 100.0 * p["V_max"] / 3600000.0 * dp / eta_teil
            elif art == "D":
                PE = 0.32 * p["PE_max"] + 0.68 * (
                    u / 100.0 * p["V_max"] * dp
                ) / 3600000.0 / eta_teil
            else:
                PE = p["PE_max"]
        elif art not in ("F", "D") and p["V_max"]:
            PE = p["PE_max"]

        T_aus = luft.T
        if V > 0:
            T_aus = luft.T + 3600.0 * PE / (1.2 * 1.007 * V)

        return (
            {
                "luft_aus": Luft(V=V, T=T_aus, x=luft.x, dp=dp),
                "PE": PE, "T_aus": T_aus, "F_aus": luft.x, "dp": dp, "V": V,
            },
            zustand,
        )

    def bedarf(self, aus_bedarf, p):
        return {"luft_ein": p["V_max"]}
```

**Hinweis zur `bedarf`-Vorgabe:** Im Rückwärtslauf ist die Stellgröße noch nicht
bekannt, deshalb wird `V_max` gefordert. Der Vorwärtslauf korrigiert den tatsächlichen
Volumenstrom, und die Iteration gleicht die vorgelagerten Bausteine an. Dieses
Vorgehen entspricht der Excel, in der `V_nenn` fest verdrahtet ist.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/bausteine -v`
Expected: alle Tests bestanden

- [ ] **Step 5: Commit**

```bash
git add core/bausteine/ventilator.py core/bausteine/__init__.py tests/bausteine/test_ventilator.py
git commit -m "Baustein Ventilator mit Kennlinien fuer FU, Drallregler und ungeregelt"
```

---

## Task 8: Verteilung und Quellen

**Files:**
- Create: `core/bausteine/verteiler.py`, `core/bausteine/sammler.py`,
  `core/bausteine/aussenluft.py`, `core/bausteine/fortluft.py`,
  `core/bausteine/wetterkarte.py`
- Modify: `core/bausteine/__init__.py`
- Test: `tests/bausteine/test_verteilung.py`, `tests/bausteine/test_quellen.py`

**Interfaces:**
- Produces:
  - `verteiler.Verteiler` (Kennung `"verteiler"`): `luft_ein`, dynamischer
    `luft_aus`; Parameter `anteile` als Wörterbuch `{portschluessel: Prozent}`.
  - `sammler.Sammler` (Kennung `"sammler"`): dynamischer `luft_ein`, `luft_aus`.
  - `aussenluft.Aussenluft` (Kennung `"aussenluft"`): Signal-Eingänge `T_AU`, `F_AU`,
    Luft-Ausgang `luft_aus` mit Rolle Außenluft.
  - `fortluft.Fortluft` (Kennung `"fortluft"`): Luft-Eingang mit Rolle Fortluft.
  - `wetterkarte.Wetterkarte` (Kennung `"wetter"`): Signal-Ausgänge `T_AU`, `F_AU`,
    `QH_S`, `QH_O`, `QH_W`, `QH_N`, `QH_H`. Die Werte kommen nicht aus `ein`, sondern
    aus `zustand["stunde"]`, das der Solver vor jeder Stunde setzt.

- [ ] **Step 1: Write the failing tests**

`tests/bausteine/test_verteilung.py`:

```python
import pytest

from core.bausteine.basis import Luft
from core.bausteine.sammler import Sammler
from core.bausteine.verteiler import Verteiler


def test_verteiler_gibt_den_zustand_unveraendert_an_alle_abgaenge():
    ein = {"luft_ein": Luft(V=12000.0, T=18.0, x=6.0, dp=100.0)}
    p = {"anteile": {}}
    verteiler = Verteiler()
    verteiler.abgaenge = ["luft_aus_1", "luft_aus_2"]
    verteiler.bedarf_je_abgang = {"luft_aus_1": 8000.0, "luft_aus_2": 4000.0}
    aus, _ = verteiler.berechne(ein, p, {})
    assert aus["luft_aus_1"].T == pytest.approx(18.0)
    assert aus["luft_aus_2"].x == pytest.approx(6.0)
    assert aus["luft_aus_1"].V == pytest.approx(8000.0)
    assert aus["luft_aus_2"].V == pytest.approx(4000.0)


def test_verteiler_kuerzt_proportional_bei_unterdeckung():
    ein = {"luft_ein": Luft(V=6000.0, T=18.0, x=6.0)}
    p = {"anteile": {}}
    verteiler = Verteiler()
    verteiler.abgaenge = ["luft_aus_1", "luft_aus_2"]
    verteiler.bedarf_je_abgang = {"luft_aus_1": 8000.0, "luft_aus_2": 4000.0}
    aus, _ = verteiler.berechne(ein, p, {})
    assert aus["luft_aus_1"].V == pytest.approx(4000.0)
    assert aus["luft_aus_2"].V == pytest.approx(2000.0)
    assert aus["warnung"] == "Volumenstrom reicht nicht fuer alle Gaenge"


def test_verteiler_nutzt_anteile_wenn_kein_bedarf_gemeldet_wird():
    ein = {"luft_ein": Luft(V=10000.0, T=18.0, x=6.0)}
    p = {"anteile": {"luft_aus_1": 70.0, "luft_aus_2": 30.0}}
    verteiler = Verteiler()
    verteiler.abgaenge = ["luft_aus_1", "luft_aus_2"]
    verteiler.bedarf_je_abgang = {"luft_aus_1": 0.0, "luft_aus_2": 0.0}
    aus, _ = verteiler.berechne(ein, p, {})
    assert aus["luft_aus_1"].V == pytest.approx(7000.0)
    assert aus["luft_aus_2"].V == pytest.approx(3000.0)


def test_verteiler_fordert_die_summe_der_abgaenge():
    verteiler = Verteiler()
    assert verteiler.bedarf(
        {"luft_aus_1": 8000.0, "luft_aus_2": 4000.0}, {"anteile": {}}
    ) == {"luft_ein": 12000.0}


def test_sammler_mischt_massenstromgewichtet():
    ein = {
        "luft_ein_1": Luft(V=8000.0, T=20.0, x=8.0),
        "luft_ein_2": Luft(V=2000.0, T=10.0, x=3.0),
    }
    aus, _ = Sammler().berechne(ein, {}, {})
    assert aus["luft_aus"].V == pytest.approx(10000.0)
    assert aus["luft_aus"].T == pytest.approx((8000 * 20.0 + 2000 * 10.0) / 10000)
    assert aus["luft_aus"].x == pytest.approx((8000 * 8.0 + 2000 * 3.0) / 10000)


def test_sammler_ohne_luft_liefert_nullzustand():
    aus, _ = Sammler().berechne({}, {}, {})
    assert aus["luft_aus"].V == 0.0
    assert aus["luft_aus"].T == 0.0
```

`tests/bausteine/test_quellen.py`:

```python
import pytest

from core.bausteine.aussenluft import Aussenluft
from core.bausteine.wetterkarte import Wetterkarte


def test_wetterkarte_gibt_die_werte_der_aktuellen_stunde_aus():
    zustand = {
        "stunde": {
            "t_au": 2.5, "x_au": 4.4,
            "str_s": 10.0, "str_o": 20.0, "str_w": 30.0,
            "str_n": 40.0, "str_h": 50.0,
        }
    }
    aus, _ = Wetterkarte().berechne({}, {}, zustand)
    assert aus["T_AU"] == 2.5
    assert aus["F_AU"] == 4.4
    assert aus["QH_S"] == 10.0
    assert aus["QH_H"] == 50.0


def test_wetterkarte_ohne_stunde_liefert_nullen():
    aus, _ = Wetterkarte().berechne({}, {}, {})
    assert aus["T_AU"] == 0.0
    assert aus["QH_S"] == 0.0


def test_aussenluft_baut_den_luftzustand_aus_den_signalen():
    ein = {"T_AU": 2.5, "F_AU": 4.4}
    aus, _ = Aussenluft().berechne(ein, {}, {})
    assert aus["luft_aus"].T == pytest.approx(2.5)
    assert aus["luft_aus"].x == pytest.approx(4.4)


def test_aussenluft_reicht_den_geforderten_volumenstrom_durch():
    aus, _ = Aussenluft().berechne(
        {"T_AU": 2.5, "F_AU": 4.4}, {}, {"bedarf": 12200.0}
    )
    assert aus["luft_aus"].V == pytest.approx(12200.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/bausteine/test_verteilung.py tests/bausteine/test_quellen.py -v`
Expected: FAIL mit `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/bausteine/verteiler.py`:

```python
"""Verteiler: ein Luftstrang auf mehrere Gaenge.

In der Excel gibt es diesen Baustein nur als Formel - S9 = V9 reicht den
Volumenstrom weiter, M9 = S9 + S31 summiert zwei Geraete. Hier wird daraus eine
eigene Karte mit dynamischen Ausgaengen.

Der Volumenstrom je Gang ergibt sich aus dem, was stromabwaerts gefordert wird.
Meldet ein Gang keinen Bedarf, greift der Parameter 'anteile'.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, LUFT, LUFTWEG, Baustein, Luft, Param, Port, registriere,
)


@registriere
class Verteiler(Baustein):
    KENNUNG = "verteiler"
    NAME = "Verteiler"
    GRUPPE = "Verteilung"
    SYMBOL = "verteiler.svg"

    PARAMETER = [Param("anteile", "Anteile je Gang", "%", {})]

    PORTS = [
        Port("luft_ein", LUFT, EINGANG, LUFTWEG),
        Port("luft_aus", LUFT, AUSGANG, LUFTWEG, dynamisch=True),
    ]

    AUSGABEN = ["warnung"]

    def __init__(self):
        self.abgaenge = []
        self.bedarf_je_abgang = {}

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        abgaenge = self.abgaenge or ["luft_aus"]

        gefordert = {a: self.bedarf_je_abgang.get(a, 0.0) for a in abgaenge}
        summe = sum(gefordert.values())

        warnung = ""
        if summe <= 0:
            anteile = p.get("anteile") or {}
            rest = [a for a in abgaenge]
            gesamt_anteil = sum(anteile.get(a, 0.0) for a in rest)
            if gesamt_anteil > 0:
                verteilt = {
                    a: luft.V * anteile.get(a, 0.0) / gesamt_anteil for a in rest
                }
            else:
                verteilt = {a: luft.V / len(rest) for a in rest}
        elif summe > luft.V:
            faktor = luft.V / summe if summe else 0.0
            verteilt = {a: v * faktor for a, v in gefordert.items()}
            warnung = "Volumenstrom reicht nicht fuer alle Gaenge"
        else:
            verteilt = gefordert

        aus = {
            a: Luft(V=v, T=luft.T, x=luft.x, dp=luft.dp) for a, v in verteilt.items()
        }
        aus["warnung"] = warnung
        return aus, zustand

    def bedarf(self, aus_bedarf, p):
        return {"luft_ein": sum(aus_bedarf.values())}
```

`core/bausteine/sammler.py`:

```python
"""Sammler: mehrere Gaenge auf einen Luftstrang.

Die Mischung folgt derselben Regel wie die Mischkammer (Anlage!M132/M133),
nur ueber beliebig viele Straenge und massenstromgewichtet.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, LUFT, LUFTWEG, Baustein, Luft, Port, registriere,
)


@registriere
class Sammler(Baustein):
    KENNUNG = "sammler"
    NAME = "Sammler"
    GRUPPE = "Verteilung"
    SYMBOL = "sammler.svg"

    PARAMETER = []

    PORTS = [
        Port("luft_ein", LUFT, EINGANG, LUFTWEG, dynamisch=True),
        Port("luft_aus", LUFT, AUSGANG, LUFTWEG),
    ]

    AUSGABEN = ["T_aus", "F_aus", "V"]

    def berechne(self, ein, p, zustand):
        straenge = [w for w in ein.values() if isinstance(w, Luft)]
        gesamt = sum(s.V for s in straenge)

        if gesamt <= 0:
            leer = Luft()
            return {"luft_aus": leer, "T_aus": 0.0, "F_aus": 0.0, "V": 0.0}, zustand

        T = sum(s.V * s.T for s in straenge) / gesamt
        x = sum(s.V * s.x for s in straenge) / gesamt
        dp = max((s.dp for s in straenge), default=0.0)

        return (
            {"luft_aus": Luft(V=gesamt, T=T, x=x, dp=dp), "T_aus": T, "F_aus": x, "V": gesamt},
            zustand,
        )

    def bedarf(self, aus_bedarf, p):
        """Der geforderte Volumenstrom wird gleichmaessig auf die Straenge verteilt.

        Die tatsaechliche Aufteilung ergibt sich im Vorwaertslauf aus den
        Ventilatoren der einzelnen Straenge; dieser Wert ist nur der Startwert
        der Iteration.
        """
        return {"luft_ein": sum(aus_bedarf.values())}
```

`core/bausteine/aussenluft.py`:

```python
"""Anschlusspunkt Aussenluft. Wandelt die Wettersignale in einen Luftzustand."""

from core.bausteine.basis import (
    AUSGANG, AUSSENLUFT, EINGANG, LUFT, MESSWERT, SIGNAL,
    Baustein, Luft, Port, registriere,
)


@registriere
class Aussenluft(Baustein):
    KENNUNG = "aussenluft"
    NAME = "Außenluft"
    GRUPPE = "Quellen und Senken"
    SYMBOL = "aussenluft.svg"

    PARAMETER = []

    PORTS = [
        Port("T_AU", SIGNAL, EINGANG, MESSWERT),
        Port("F_AU", SIGNAL, EINGANG, MESSWERT),
        Port("luft_aus", LUFT, AUSGANG, AUSSENLUFT),
    ]

    AUSGABEN = ["T_AU", "F_AU", "V"]

    def berechne(self, ein, p, zustand):
        T = float(ein.get("T_AU", 0.0))
        x = float(ein.get("F_AU", 0.0))
        V = float(zustand.get("bedarf", 0.0))
        return (
            {"luft_aus": Luft(V=V, T=T, x=x, dp=0.0), "T_AU": T, "F_AU": x, "V": V},
            zustand,
        )

    def bedarf(self, aus_bedarf, p):
        return {}
```

`core/bausteine/fortluft.py`:

```python
"""Anschlusspunkt Fortluft. Endpunkt eines Abluftwegs."""

from core.bausteine.basis import (
    EINGANG, FORTLUFT, LUFT, Baustein, Luft, Port, registriere,
)


@registriere
class Fortluft(Baustein):
    KENNUNG = "fortluft"
    NAME = "Fortluft"
    GRUPPE = "Quellen und Senken"
    SYMBOL = "fortluft.svg"

    PARAMETER = []

    PORTS = [Port("luft_ein", LUFT, EINGANG, FORTLUFT)]

    AUSGABEN = ["T_FO", "F_FO", "V"]

    def berechne(self, ein, p, zustand):
        luft = ein.get("luft_ein", Luft())
        return {"T_FO": luft.T, "F_FO": luft.x, "V": luft.V}, zustand

    def bedarf(self, aus_bedarf, p):
        return {}
```

`core/bausteine/wetterkarte.py`:

```python
"""Wetterkarte. Liefert die Werte der aktuellen Stunde als Signale.

Entspricht dem Block Anlage!F2:H22, den das VBA-Makro vor jeder Stunde
beschreibt. Der Solver legt die Stundenwerte in zustand['stunde'] ab.
"""

from core.bausteine.basis import (
    AUSGANG, MESSWERT, SIGNAL, Baustein, Port, registriere,
)

FELDER = {
    "T_AU": "t_au",
    "F_AU": "x_au",
    "QH_S": "str_s",
    "QH_O": "str_o",
    "QH_W": "str_w",
    "QH_N": "str_n",
    "QH_H": "str_h",
}


@registriere
class Wetterkarte(Baustein):
    KENNUNG = "wetter"
    NAME = "Wetterdaten"
    GRUPPE = "Quellen und Senken"
    SYMBOL = "wetter.svg"

    PARAMETER = []

    PORTS = [
        Port(name, SIGNAL, AUSGANG, MESSWERT) for name in FELDER
    ]

    AUSGABEN = list(FELDER)

    def berechne(self, ein, p, zustand):
        stunde = zustand.get("stunde") or {}
        return {
            port: float(stunde.get(feld, 0.0)) for port, feld in FELDER.items()
        }, zustand

    def bedarf(self, aus_bedarf, p):
        return {}
```

`core/bausteine/__init__.py`:

```python
MODULE = [
    "erhitzer", "kuehler", "wrg", "mischkammer",
    "dampfbefeuchter", "luftwaescher", "ventilator",
    "verteiler", "sammler", "aussenluft", "fortluft", "wetterkarte",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/bausteine -v`
Expected: alle Tests bestanden

- [ ] **Step 5: Commit**

```bash
git add core/bausteine tests/bausteine
git commit -m "Bausteine Verteiler, Sammler, Aussenluft, Fortluft und Wetterkarte"
```

---

## Task 9: Einfacher Raum und statische Heizung

**Files:**
- Create: `core/bausteine/einfacher_raum.py`, `core/bausteine/statische_heizung.py`
- Modify: `core/bausteine/__init__.py`
- Test: `tests/bausteine/test_einfacher_raum.py`

**Interfaces:**
- Produces: `einfacher_raum.EinfacherRaum` (Kennung `"einfacher_raum"`), Methode
  `freie_temperatur(zuluft, abluft_soll, T_AU, Q_i, p) -> float`; Ausgaben
  `T_Raum`, `F_Raum`, `QH_stat`. `statische_heizung.StatischeHeizung`
  (Kennung `"statische_heizung"`).

- [ ] **Step 1: Write the failing test**

`tests/bausteine/test_einfacher_raum.py`:

```python
import pytest

from core.bausteine.basis import Luft
from core.bausteine.einfacher_raum import EinfacherRaum


def parameter(**abweichend):
    p = EinfacherRaum.vorgabeparameter()
    p.update(abweichend)
    return p


def eingaben():
    """Anlage!AG31:AI50 - der gespeicherte Zustand des einfachen Raums."""
    return {
        "zuluft_ein_1": Luft(V=8200.0, T=20.78022137718888, x=0.0),
        "zuluft_ein_2": Luft(V=4000.0, T=15.839048772668132, x=8.747590530135225),
        "abluft_aus_1": Luft(V=4500.0),
        "abluft_aus_2": Luft(V=4500.0),
        "T_AU": 0.0,
        "F_AU": 0.0,
        "waermelast": 0.25,
        "feuchtelast": 0.25,
    }


def test_freie_raumtemperatur_entspricht_der_excel():
    """Anlage!AH48."""
    p = parameter(spez_transmission=0.5, sollwert_stat=15.0)
    aus, _ = EinfacherRaum().berechne(eingaben(), p, {})
    assert aus["T_frei"] == pytest.approx(17.12973787168357, rel=1e-10)


def test_raumfeuchte_entspricht_der_excel():
    """Anlage!AH46."""
    p = parameter(spez_transmission=0.5, sollwert_stat=15.0)
    aus, _ = EinfacherRaum().berechne(eingaben(), p, {})
    assert aus["F_Raum"] == pytest.approx(2.885138971629036, rel=1e-12)


def test_statischer_sollwert_hebt_die_raumtemperatur_an():
    p = parameter(spez_transmission=0.5, sollwert_stat=25.0)
    aus, _ = EinfacherRaum().berechne(eingaben(), p, {})
    assert aus["T_Raum"] == pytest.approx(25.0)
    assert aus["QH_stat"] > 0.0


def test_ohne_heizbedarf_ist_die_statische_leistung_null():
    p = parameter(spez_transmission=0.5, sollwert_stat=15.0)
    aus, _ = EinfacherRaum().berechne(eingaben(), p, {})
    assert aus["QH_stat"] == pytest.approx(0.0)
    assert aus["T_Raum"] == pytest.approx(17.12973787168357, rel=1e-10)


def test_ueberwiegende_abluft_zieht_aussenluft_nach():
    """Bei mehr Ab- als Zuluft rechnet die Excel einen Infiltrationsanteil ein."""
    p = parameter(spez_transmission=0.5, sollwert_stat=-50.0)
    ein = eingaben()
    ein["abluft_aus_1"] = Luft(V=12000.0)
    ein["abluft_aus_2"] = Luft(V=12000.0)
    ein["T_AU"] = -10.0
    aus, _ = EinfacherRaum().berechne(ein, p, {})
    assert aus["T_frei"] < 17.12973787168357


def test_abluft_bekommt_den_raumzustand():
    p = parameter(spez_transmission=0.5, sollwert_stat=15.0)
    aus, _ = EinfacherRaum().berechne(eingaben(), p, {})
    assert aus["abluft_aus_1"].T == pytest.approx(aus["T_Raum"])
    assert aus["abluft_aus_1"].x == pytest.approx(aus["F_Raum"])
    assert aus["abluft_aus_1"].V == pytest.approx(4500.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/bausteine/test_einfacher_raum.py -v`
Expected: FAIL mit `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/bausteine/einfacher_raum.py`:

```python
"""Einfacher Raum: stationaere Mischbilanz ohne Speicher.

Formeln aus Anlage!AH45 bis AH50. Die Excel setzt Volumenstroeme, die null sind,
auf 0,001 - das verhindert eine Division durch null und wird hier uebernommen.
"""

from core.bausteine.basis import (
    ABLUFT, AUSGANG, EINGANG, LUFT, MESSWERT, SIGNAL, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)

MINDESTVOLUMEN = 0.001
LUFT_WAERMEKAPAZITAET = 1.2 * 1.007  # kJ/(m³ K), wie in der Excel


@registriere
class EinfacherRaum(Baustein):
    KENNUNG = "einfacher_raum"
    NAME = "Einfacher Raum"
    GRUPPE = "Räume"
    SYMBOL = "einfacher_raum.svg"

    PARAMETER = [
        Param("spez_transmission", "spez. Transmission", "kW/K", 0.5),
        Param("sollwert_stat", "Sollwert für stat. Hzg", "°C", 15.0),
    ]

    PORTS = [
        Port("zuluft_ein", LUFT, EINGANG, ZULUFT, dynamisch=True),
        Port("abluft_aus", LUFT, AUSGANG, ABLUFT, dynamisch=True),
        Port("T_AU", SIGNAL, EINGANG, MESSWERT),
        Port("F_AU", SIGNAL, EINGANG, MESSWERT),
        Port("waermelast", SIGNAL, EINGANG, MESSWERT),
        Port("feuchtelast", SIGNAL, EINGANG, MESSWERT),
        Port("T_Raum", SIGNAL, AUSGANG, MESSWERT),
        Port("F_Raum", SIGNAL, AUSGANG, MESSWERT),
        Port("QH_stat", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["T_Raum", "F_Raum", "T_frei", "QH_stat"]

    def berechne(self, ein, p, zustand):
        zuluft = [
            (s, w) for s, w in ein.items()
            if s.startswith("zuluft_ein") and isinstance(w, Luft)
        ]
        abluft = [
            (s, w) for s, w in ein.items()
            if s.startswith("abluft_aus") and isinstance(w, Luft)
        ]

        T_AU = float(ein.get("T_AU", 0.0))
        F_AU = float(ein.get("F_AU", 0.0))
        Q_i = float(ein.get("waermelast", 0.0))
        M_i = float(ein.get("feuchtelast", 0.0))
        k = p["spez_transmission"]

        V_zu = [max(w.V, MINDESTVOLUMEN) for _, w in zuluft] or [MINDESTVOLUMEN]
        V_ab = [max(w.V, MINDESTVOLUMEN) for _, w in abluft] or [MINDESTVOLUMEN]
        summe_zu = sum(V_zu)
        summe_ab = sum(V_ab)

        C_zu = summe_zu / 3600.0 * LUFT_WAERMEKAPAZITAET
        waerme_zuluft = sum(
            V * w.T for V, (_, w) in zip(V_zu, zuluft)
        ) / 3600.0 * LUFT_WAERMEKAPAZITAET

        if summe_zu >= summe_ab:
            T_frei = (waerme_zuluft + Q_i + k * T_AU) / (C_zu + k)
            bezug = summe_zu
        else:
            C_inf = (summe_ab - summe_zu) / 3600.0 * LUFT_WAERMEKAPAZITAET
            T_frei = (C_inf * T_AU + waerme_zuluft + Q_i + k * T_AU) / (C_inf + C_zu + k)
            bezug = summe_ab

        T_Raum = max(T_frei, p["sollwert_stat"])

        if summe_zu >= summe_ab:
            feuchte_mischung = sum(
                V * w.x for V, (_, w) in zip(V_zu, zuluft)
            ) / summe_zu
            F_Raum = min(feuchte_mischung + M_i * 1000.0 / summe_zu / 1.2, 99.9)
        else:
            feuchte_mischung = (
                sum(V * w.x for V, (_, w) in zip(V_zu, zuluft))
                + F_AU * (summe_ab - summe_zu)
            ) / summe_ab
            F_Raum = min(feuchte_mischung + M_i * 1000.0 / summe_ab / 1.2, 99.9)

        QH_stat = 0.0
        if p["sollwert_stat"] > T_frei:
            QH_stat = k * (p["sollwert_stat"] - T_AU) - Q_i
            QH_stat -= sum(
                V / 3600.0 * LUFT_WAERMEKAPAZITAET * (w.T - p["sollwert_stat"])
                for V, (_, w) in zip(V_zu, zuluft)
            )
            if summe_zu < summe_ab:
                QH_stat -= (summe_ab - summe_zu) / 3600.0 * LUFT_WAERMEKAPAZITAET * (
                    T_AU - p["sollwert_stat"]
                )

        aus = {
            "T_Raum": T_Raum, "F_Raum": F_Raum, "T_frei": T_frei,
            "QH_stat": QH_stat, "bezugsvolumen": bezug,
        }
        for schluessel, w in abluft:
            aus[schluessel] = Luft(V=w.V, T=T_Raum, x=F_Raum, dp=0.0)
        return aus, zustand

    def bedarf(self, aus_bedarf, p):
        return {}
```

`core/bausteine/statische_heizung.py`:

```python
"""Statische Heizung als eigene Karte.

Nimmt die vom Raum gemeldete Unterdeckung auf und begrenzt sie auf die
Nennleistung, entsprechend Anlage!AH128/AH129.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, MESSWERT, SIGNAL, WAERME, Baustein, Param, Port, registriere,
)


@registriere
class StatischeHeizung(Baustein):
    KENNUNG = "statische_heizung"
    NAME = "Statische Heizung"
    GRUPPE = "Räume"
    SYMBOL = "statische_heizung.svg"

    PARAMETER = [Param("QH_nenn", "QH_nenn", "kW", 0.0)]

    PORTS = [
        Port("bedarf", SIGNAL, EINGANG, MESSWERT),
        Port("QH", SIGNAL, AUSGANG, WAERME),
    ]

    AUSGABEN = ["QH"]

    def berechne(self, ein, p, zustand):
        gefordert = float(ein.get("bedarf", 0.0))
        QH = max(min(gefordert, p["QH_nenn"]), 0.0)
        return {"QH": QH}, zustand
```

`core/bausteine/__init__.py` — `MODULE` um `"einfacher_raum"` und
`"statische_heizung"` ergänzen.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/bausteine -v`
Expected: alle Tests bestanden

- [ ] **Step 5: Commit**

```bash
git add core/bausteine tests/bausteine
git commit -m "Bausteine einfacher Raum und statische Heizung"
```

---

## Task 10: Raum mit Bauphysik und Wandspeicher

Der aufwendigste Baustein. Er rechnet Geometrie, Transmission, Solargewinne,
Lüftungswärmeverlust und die exponentielle Aufheizkurve über die Stunde, und führt
Raum- und Wandtemperatur als Speichergrößen fort.

**Files:**
- Create: `core/bausteine/raum.py`
- Modify: `core/bausteine/__init__.py`
- Test: `tests/bausteine/test_raum.py`

**Interfaces:**
- Produces: `raum.Raum` (Kennung `"raum"`) mit den Hilfsmethoden
  `geometrie(p) -> dict` (Schlüssel `volumen`, `grundflaeche`, `innenwand`,
  `aussenwand`, `dachflaeche`, `fensterflaeche`, `trans_aw`, `trans_fe`,
  `trans_fb`, `trans_da`, `luftwechsel`, `spez_verlust`) und
  `solargewinn(p, strahlung, T_Raum) -> float`.
  Zustand: `{"T_Raum": float, "T_Wand": float}`.

- [ ] **Step 1: Write the failing test**

`tests/bausteine/test_raum.py`:

```python
import pytest

from core.bausteine.basis import Luft
from core.bausteine.raum import Raum


def parameter(**abweichend):
    """Die Geometrie aus Anlage!AG100:AL134 der Beispielanlage."""
    p = Raum.vorgabeparameter()
    p.update(
        {
            "laenge_a": 22.0, "laenge_b": 33.0, "laenge_c": 22.0, "laenge_d": 33.0,
            "laenge_e": 0.0,
            "aw_anteil_a": 1.0, "aw_anteil_b": 0.5, "aw_anteil_c": 0.35,
            "aw_anteil_d": 1.0, "aw_anteil_e": 0.0,
            "u_wand_a": 1.62, "u_wand_b": 1.9, "u_wand_c": 1.9, "u_wand_d": 1.9,
            "fenster_a": 0.0, "fenster_b": 72.6, "fenster_c": 0.0, "fenster_d": 123.8,
            "u_fenster_a": 2.5, "u_fenster_b": 2.5, "u_fenster_c": 2.5,
            "u_fenster_d": 2.5,
            "dach_laenge": 0.0, "dach_anteil": 1.0, "u_dach": 0.91,
            "fenster_dach": 0.0, "u_fenster_dach": 2.5,
            "boden_anteil": 1.0, "u_boden": 0.16,
            "geschosse": 1.0, "hoehe": 6.15,
            "bauart": 90.0, "ausrichtung": 65.0,
            "waermebruecke": 0.1, "waermeuebergang": 7.7,
            "g_faktor": 0.8, "verschattung_1": 0.7, "verschattung_2": 0.9,
            "verschattung_3": 0.9, "verschattung_4": 1.0,
            "spez_beleuchtung": 2.0,
        }
    )
    p.update(abweichend)
    return p


def test_geometrie_entspricht_der_excel():
    g = Raum().geometrie(parameter())
    assert g["grundflaeche"] == pytest.approx(726.0)
    assert g["volumen"] == pytest.approx(4464.9)
    assert g["dachflaeche"] == pytest.approx(726.0)
    assert g["fensterflaeche"] == pytest.approx(196.4)
    assert g["aussenwand"] == pytest.approx(290.68000000000006, rel=1e-12)
    assert g["innenwand"] == pytest.approx(1932.1, rel=1e-12)


def test_spezifische_transmission_entspricht_der_excel():
    g = Raum().geometrie(parameter())
    assert g["trans_aw"] == pytest.approx(583.378, rel=1e-10)
    assert g["trans_fe"] == pytest.approx(491.0, rel=1e-12)
    assert g["trans_fb"] == pytest.approx(116.16, rel=1e-12)
    assert g["trans_da"] == pytest.approx(660.66, rel=1e-12)


def test_luftwechsel_und_lueftungsverlust_entsprechen_der_excel():
    g = Raum().geometrie(parameter())
    assert g["luftwechsel"] == pytest.approx(0.308371027346637, rel=1e-12)
    assert g["spez_verlust"] == pytest.approx(468.127572, rel=1e-10)


def test_beleuchtungswaerme_entspricht_der_excel():
    """Anlage!AK134 - 2 W/m² auf 726 m²."""
    assert Raum().beleuchtungswaerme(parameter()) == pytest.approx(1.452)


def test_solargewinn_wird_ueber_22_grad_abgemindert():
    p = parameter()
    strahlung = {"QH_S": 400.0, "QH_O": 100.0, "QH_W": 100.0, "QH_N": 50.0, "QH_H": 300.0}
    kalt = Raum().solargewinn(p, strahlung, T_Raum=18.0)
    warm = Raum().solargewinn(p, strahlung, T_Raum=25.0)
    assert warm == pytest.approx(0.2 * kalt)
    assert kalt > 0.0


def test_solargewinn_ist_nachts_null():
    p = parameter()
    strahlung = {"QH_S": 0.0, "QH_O": 0.0, "QH_W": 0.0, "QH_N": 0.0, "QH_H": 0.0}
    assert Raum().solargewinn(p, strahlung, T_Raum=18.0) == pytest.approx(0.0)


def test_raumtemperatur_strebt_dem_beharrungswert_entgegen():
    """Ohne Last und ohne Zuluft naehert sich der Raum der Aussentemperatur."""
    p = parameter(spez_beleuchtung=0.0)
    ein = {
        "zuluft_ein": Luft(V=0.0, T=0.0, x=0.0),
        "abluft_aus": Luft(V=0.0),
        "T_AU": 0.0, "F_AU": 0.0,
        "QH_S": 0.0, "QH_O": 0.0, "QH_W": 0.0, "QH_N": 0.0, "QH_H": 0.0,
        "waermelast": 0.0, "feuchtelast": 0.0,
    }
    zustand = {"T_Raum": 20.0, "T_Wand": 20.0}
    for _ in range(200):
        aus, zustand = Raum().berechne(ein, p, zustand)
    assert aus["T_Raum"] < 5.0


def test_wandtemperatur_folgt_der_raumtemperatur():
    p = parameter(spez_beleuchtung=0.0)
    ein = {
        "zuluft_ein": Luft(V=8200.0, T=30.0, x=6.0),
        "abluft_aus": Luft(V=8200.0),
        "T_AU": 10.0, "F_AU": 4.0,
        "QH_S": 0.0, "QH_O": 0.0, "QH_W": 0.0, "QH_N": 0.0, "QH_H": 0.0,
        "waermelast": 0.0, "feuchtelast": 0.0,
    }
    zustand = {"T_Raum": 10.0, "T_Wand": 10.0}
    vorher = zustand["T_Wand"]
    for _ in range(50):
        aus, zustand = Raum().berechne(ein, p, zustand)
    assert zustand["T_Wand"] > vorher
    assert zustand["T_Wand"] < aus["T_Raum"] + 0.5


def test_raumfeuchte_folgt_der_zuluft_und_der_feuchtelast():
    p = parameter()
    ein = {
        "zuluft_ein": Luft(V=10000.0, T=20.0, x=6.0),
        "abluft_aus": Luft(V=10000.0),
        "T_AU": 10.0, "F_AU": 4.0,
        "QH_S": 0.0, "QH_O": 0.0, "QH_W": 0.0, "QH_N": 0.0, "QH_H": 0.0,
        "waermelast": 0.0, "feuchtelast": 12.0,
    }
    aus, _ = Raum().berechne(ein, p, {"T_Raum": 20.0, "T_Wand": 20.0})
    assert aus["F_Raum"] == pytest.approx(6.0 + 12.0 * 1000.0 / (10000.0 * 1.2))


def test_abluft_traegt_den_raumzustand():
    p = parameter()
    ein = {
        "zuluft_ein": Luft(V=8200.0, T=20.0, x=6.0),
        "abluft_aus": Luft(V=4500.0),
        "T_AU": 10.0, "F_AU": 4.0,
        "QH_S": 0.0, "QH_O": 0.0, "QH_W": 0.0, "QH_N": 0.0, "QH_H": 0.0,
        "waermelast": 0.0, "feuchtelast": 0.0,
    }
    aus, _ = Raum().berechne(ein, p, {"T_Raum": 18.0, "T_Wand": 18.0})
    assert aus["abluft_aus"].V == pytest.approx(4500.0)
    assert aus["abluft_aus"].T == pytest.approx(aus["T_Raum"])


def test_anfangszustand_setzt_raum_und_wand_auf_den_startwert():
    p = parameter(start_temperatur=15.0)
    assert Raum().anfangszustand(p) == {"T_Raum": 15.0, "T_Wand": 15.0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/bausteine/test_raum.py -v`
Expected: FAIL mit `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/bausteine/raum.py`:

```python
"""Raum mit Bauphysik, Solargewinnen und Wandspeicher.

Formeln aus Anlage!AG70:AL134. Kern ist die exponentielle Loesung der
Waermebilanz ueber eine Stunde (Anlage!AJ89):

    T_neu = (T_alt + B/A) * exp(A/C) - B/A

A ist die Summe aller Waermeabfluesse je Kelvin, B die Summe aller Zufluesse,
C die Waermekapazitaet der Raumluft. Die Wandtemperatur wird ueber die
Speicherfaehigkeit der Innenwaende fortgeschrieben (Anlage!AK127/AK128).
"""

import math

from core.bausteine.basis import (
    ABLUFT, AUSGANG, EINGANG, LUFT, MESSWERT, SIGNAL, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)

LUFT_C = 1.005 * 1000.0 / 3600.0 * 1.2  # W/(K) je m³/h, wie in Anlage!AJ85
ERDREICH = 10.0  # °C hinter der Bodenplatte, Anlage!AH125


@registriere
class Raum(Baustein):
    KENNUNG = "raum"
    NAME = "Raum"
    GRUPPE = "Räume"
    SYMBOL = "raum.svg"

    PARAMETER = [
        Param("laenge_a", "Länge a", "m", 22.0),
        Param("laenge_b", "Länge b", "m", 33.0),
        Param("laenge_c", "Länge c", "m", 22.0),
        Param("laenge_d", "Länge d", "m", 33.0),
        Param("laenge_e", "Länge e", "m", 0.0),
        Param("aw_anteil_a", "Außenwand a", "-", 1.0),
        Param("aw_anteil_b", "Außenwand b", "-", 0.5),
        Param("aw_anteil_c", "Außenwand c", "-", 0.35),
        Param("aw_anteil_d", "Außenwand d", "-", 1.0),
        Param("aw_anteil_e", "Außenwand e", "-", 0.0),
        Param("u_wand_a", "U Wand a", "W/m²K", 1.62),
        Param("u_wand_b", "U Wand b", "W/m²K", 1.9),
        Param("u_wand_c", "U Wand c", "W/m²K", 1.9),
        Param("u_wand_d", "U Wand d", "W/m²K", 1.9),
        Param("fenster_a", "Fenster a", "m²", 0.0),
        Param("fenster_b", "Fenster b", "m²", 72.6),
        Param("fenster_c", "Fenster c", "m²", 0.0),
        Param("fenster_d", "Fenster d", "m²", 123.8),
        Param("u_fenster_a", "U Fenster a", "W/m²K", 2.5),
        Param("u_fenster_b", "U Fenster b", "W/m²K", 2.5),
        Param("u_fenster_c", "U Fenster c", "W/m²K", 2.5),
        Param("u_fenster_d", "U Fenster d", "W/m²K", 2.5),
        Param("dach_laenge", "Dachanteil", "m", 0.0),
        Param("dach_anteil", "Dach Anteil", "-", 1.0),
        Param("u_dach", "U Dach", "W/m²K", 0.91),
        Param("fenster_dach", "Dachfenster", "m²", 0.0),
        Param("u_fenster_dach", "U Dachfenster", "W/m²K", 2.5),
        Param("boden_anteil", "Bodenplatte Anteil", "-", 1.0),
        Param("u_boden", "U Bodenplatte", "W/m²K", 0.16),
        Param("geschosse", "Geschosse", "-", 1.0),
        Param("hoehe", "Höhe", "m", 6.15),
        Param("bauart", "Bauart", "Wh/(m²K)", 90.0),
        Param("ausrichtung", "Ausrichtung", "Grad", 65.0),
        Param("waermebruecke", "Wärmebrücke", "W/(m²K)", 0.1),
        Param("waermeuebergang", "Wärmeüberg.", "W/m²K", 7.7),
        Param("g_faktor", "g-Faktor", "-", 0.8),
        Param("verschattung_1", "Verschattung 1", "-", 0.7),
        Param("verschattung_2", "Verschattung 2", "-", 0.9),
        Param("verschattung_3", "Verschattung 3", "-", 0.9),
        Param("verschattung_4", "Verschattung 4", "-", 1.0),
        Param("spez_beleuchtung", "spez. Leistung Beleuchtung", "W/m²", 2.0),
        Param("start_temperatur", "Starttemperatur", "°C", 20.0),
    ]

    PORTS = [
        Port("zuluft_ein", LUFT, EINGANG, ZULUFT, dynamisch=True),
        Port("abluft_aus", LUFT, AUSGANG, ABLUFT, dynamisch=True),
        Port("T_AU", SIGNAL, EINGANG, MESSWERT),
        Port("F_AU", SIGNAL, EINGANG, MESSWERT),
        Port("QH_S", SIGNAL, EINGANG, MESSWERT),
        Port("QH_O", SIGNAL, EINGANG, MESSWERT),
        Port("QH_W", SIGNAL, EINGANG, MESSWERT),
        Port("QH_N", SIGNAL, EINGANG, MESSWERT),
        Port("QH_H", SIGNAL, EINGANG, MESSWERT),
        Port("waermelast", SIGNAL, EINGANG, MESSWERT),
        Port("feuchtelast", SIGNAL, EINGANG, MESSWERT),
        Port("QH_stat", SIGNAL, EINGANG, MESSWERT),
        Port("T_Raum", SIGNAL, AUSGANG, MESSWERT),
        Port("F_Raum", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["T_Raum", "F_Raum", "T_Wand", "QH_Solar", "Q_Bel", "Q_Raum"]

    # -- Geometrie -------------------------------------------------------

    def geometrie(self, p):
        h = p["hoehe"]
        laengen = [p["laenge_a"], p["laenge_b"], p["laenge_c"], p["laenge_d"]]
        anteile = [p["aw_anteil_a"], p["aw_anteil_b"], p["aw_anteil_c"], p["aw_anteil_d"]]
        u_wand = [p["u_wand_a"], p["u_wand_b"], p["u_wand_c"], p["u_wand_d"]]
        fenster = [p["fenster_a"], p["fenster_b"], p["fenster_c"], p["fenster_d"]]
        u_fenster = [
            p["u_fenster_a"], p["u_fenster_b"], p["u_fenster_c"], p["u_fenster_d"]
        ]

        grundflaeche = (p["laenge_a"] + p["laenge_c"]) / 2.0 * (
            (p["laenge_b"] + p["laenge_d"]) / 2.0
        )
        volumen = grundflaeche * h
        dachflaeche = (
            (p["laenge_b"] / 2.0) / math.cos(math.radians(p["dach_laenge"]))
        ) * p["laenge_a"] * 2.0
        fensterflaeche = sum(fenster) + p["fenster_dach"]

        umfang = sum(laengen) + p["laenge_e"] * 2.0
        innenwand = (
            umfang * h + p["geschosse"] * grundflaeche + dachflaeche - fensterflaeche
        )
        aussenwand = sum(l * a for l, a in zip(laengen, anteile)) * h - fensterflaeche

        trans_aw = sum(
            (l * h - f) * a * u
            for l, a, u, f in zip(laengen, anteile, u_wand, fenster)
        )
        trans_fe = sum(f * u for f, u in zip(fenster, u_fenster)) + (
            p["fenster_dach"] * p["u_fenster_dach"]
        )
        trans_fb = p["u_boden"] * grundflaeche * p["boden_anteil"]
        trans_da = p["u_dach"] * dachflaeche * p["dach_anteil"]

        luftwechsel = (
            1.135 * (aussenwand + dachflaeche + fensterflaeche) / volumen
            if volumen else 0.0
        )
        spez_verlust = 0.34 * luftwechsel * volumen

        return {
            "grundflaeche": grundflaeche,
            "volumen": volumen,
            "dachflaeche": dachflaeche,
            "fensterflaeche": fensterflaeche,
            "innenwand": innenwand,
            "aussenwand": aussenwand,
            "trans_aw": trans_aw,
            "trans_fe": trans_fe,
            "trans_fb": trans_fb,
            "trans_da": trans_da,
            "luftwechsel": luftwechsel,
            "spez_verlust": spez_verlust,
        }

    def beleuchtungswaerme(self, p):
        return p["spez_beleuchtung"] * self.geometrie(p)["grundflaeche"] / 1000.0

    def solargewinn(self, p, strahlung, T_Raum):
        """Anlage!AK122 - Fenster nach Ausrichtung gewichtet."""
        a = p["ausrichtung"] / 90.0
        b = 1.0 - a
        g = p["g_faktor"]
        v = p["verschattung_1"] * p["verschattung_2"] * p["verschattung_3"]
        v_dach = p["verschattung_1"] * p["verschattung_2"] * p["verschattung_4"]

        S = strahlung.get("QH_S", 0.0)
        O = strahlung.get("QH_O", 0.0)
        W = strahlung.get("QH_W", 0.0)
        N = strahlung.get("QH_N", 0.0)
        H = strahlung.get("QH_H", 0.0)

        summe = (
            p["fenster_a"] * (b * N + a * O)
            + p["fenster_b"] * (b * O + a * S)
            + p["fenster_c"] * (b * S + a * W)
            + p["fenster_d"] * (b * W + a * N)
        ) * g * v * p["verschattung_4"]
        summe += p["fenster_dach"] * H * g * v_dach
        summe /= 1000.0

        return 0.2 * summe if T_Raum > 22.0 else summe

    # -- Bilanz ----------------------------------------------------------

    def berechne(self, ein, p, zustand):
        g = self.geometrie(p)

        T_Raum_alt = float(zustand.get("T_Raum", p["start_temperatur"]))
        T_Wand = float(zustand.get("T_Wand", p["start_temperatur"]))

        zuluft = [
            w for s, w in ein.items()
            if s.startswith("zuluft_ein") and isinstance(w, Luft)
        ]
        abluft = [
            (s, w) for s, w in ein.items()
            if s.startswith("abluft_aus") and isinstance(w, Luft)
        ]

        V_zu = sum(w.V for w in zuluft)
        T_zu = sum(w.V * w.T for w in zuluft) / V_zu if V_zu else 0.0
        x_zu = sum(w.V * w.x for w in zuluft) / V_zu if V_zu else 0.0

        T_AU = float(ein.get("T_AU", 0.0))
        F_AU = float(ein.get("F_AU", 0.0))
        Q_i = float(ein.get("waermelast", 0.0))
        M_i = float(ein.get("feuchtelast", 0.0))
        QH_stat = float(ein.get("QH_stat", 0.0))

        strahlung = {
            k: float(ein.get(k, 0.0))
            for k in ("QH_S", "QH_O", "QH_W", "QH_N", "QH_H")
        }
        QH_Solar = self.solargewinn(p, strahlung, T_Raum_alt)
        Q_Bel = self.beleuchtungswaerme(p)

        huelle = g["aussenwand"] + g["dachflaeche"] + g["grundflaeche"] + g["fensterflaeche"]
        trans_summe = g["trans_aw"] + g["trans_fe"] + g["trans_fb"] + g["trans_da"]
        wand_kopplung = g["innenwand"] * p["waermeuebergang"]

        # Anlage!AH85 - alle Abfluesse je Kelvin, negativ
        A = -(
            wand_kopplung
            + trans_summe
            + p["waermebruecke"] * huelle
            + g["spez_verlust"]
            + V_zu * LUFT_C
        )
        # Anlage!AI85 - alle Zufluesse in Watt
        B = (
            Q_Bel * 1000.0
            + QH_Solar * 1000.0
            + wand_kopplung * T_Wand
            + g["trans_fb"] * ERDREICH
            + (g["trans_da"] + g["trans_aw"] + g["trans_fe"]) * T_AU
            + p["waermebruecke"] * huelle * T_AU
            + g["spez_verlust"] * T_AU
            + V_zu * LUFT_C * T_zu
            + QH_stat * 1000.0
            + Q_i * 1000.0
        )
        C = LUFT_C * g["volumen"]  # Anlage!AJ85

        if A == 0 or C == 0:
            T_Raum = T_Raum_alt
        else:
            beharrung = B / A
            T_Raum = (T_Raum_alt + beharrung) * math.exp(A / C) - beharrung

        # Wandspeicher, Anlage!AK127/AK128
        QH_Wand = (T_Wand - T_Raum) * p["waermeuebergang"] * g["innenwand"] / 1000.0
        C_Wand = g["innenwand"] * p["bauart"] / 3600.0
        T_Wand_neu = T_Wand - QH_Wand / C_Wand if C_Wand else T_Wand

        # Feuchtebilanz, Anlage!AJ90
        if V_zu > 0:
            F_Raum = (V_zu * x_zu * 1.2 + M_i * 1000.0) / (V_zu * 1.2)
        else:
            F_Raum = F_AU + (M_i * 1000.0 / g["volumen"] if g["volumen"] else 0.0)

        Q_Raum = T_Raum * (1.005 * 1.2 * g["volumen"] / 3600.0)

        aus = {
            "T_Raum": T_Raum,
            "F_Raum": F_Raum,
            "T_Wand": T_Wand_neu,
            "QH_Solar": QH_Solar,
            "Q_Bel": Q_Bel,
            "Q_Raum": Q_Raum,
        }
        for schluessel, w in abluft:
            aus[schluessel] = Luft(V=w.V, T=T_Raum, x=F_Raum, dp=0.0)

        return aus, {"T_Raum": T_Raum, "T_Wand": T_Wand_neu}

    def anfangszustand(self, p):
        return {
            "T_Raum": p["start_temperatur"],
            "T_Wand": p["start_temperatur"],
        }

    def bedarf(self, aus_bedarf, p):
        return {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/bausteine/test_raum.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add core/bausteine/raum.py core/bausteine/__init__.py tests/bausteine/test_raum.py
git commit -m "Baustein Raum mit Bauphysik, Solargewinnen und Wandspeicher"
```

---

## Task 11: Regler

**Files:**
- Create: `core/bausteine/p_regler.py`, `core/bausteine/sequenzregler.py`,
  `core/bausteine/hysterese_regler.py`, `core/bausteine/kaskade.py`
- Modify: `core/bausteine/__init__.py`
- Test: `tests/bausteine/test_regler.py`

**Interfaces:**
- Produces:
  - `p_regler.PRegler` (Kennung `"p_regler"`): Eingänge `sollwert_1`, `istwert_1`,
    `sollwert_2`, `istwert_2`; Ausgänge `ausgang_1`, `ausgang_2`;
    Zustand `{"y1": float, "y2": float}`.
  - `sequenzregler.Sequenzregler` (Kennung `"sequenzregler"`): Eingang `istwert`;
    Ausgänge `waermer_3`, `waermer_2`, `waermer_1`, `kaelter_1`, `kaelter_2`;
    Zustand `{"e": float}`.
  - `hysterese_regler.HystereseRegler` (Kennung `"hysterese_regler"`): Eingänge
    `sollwert`, `istwert`; Ausgang `ausgang`; Zustand `{"zustand": float}`.
  - `kaskade.RaumZuluftKaskade` (Kennung `"kaskade"`): Eingänge `T_AU`, `T_Raum`,
    `T_ZU`; Ausgänge wie beim Sequenzregler plus `sollwert`.

- [ ] **Step 1: Write the failing test**

`tests/bausteine/test_regler.py`:

```python
import pytest

from core.bausteine.hysterese_regler import HystereseRegler
from core.bausteine.kaskade import RaumZuluftKaskade
from core.bausteine.p_regler import PRegler
from core.bausteine.sequenzregler import Sequenzregler


# ---------------------------------------------------------------- P-Regler

def test_p_regler_faehrt_bei_zu_kaltem_istwert_auf():
    """Anlage!K51/J57 - der Ausgang integriert ueber die Iterationen."""
    p = {"xp_1": 5.0, "xp_2": 5.0}
    ein = {"sollwert_2": 20.0, "istwert_2": 18.0}
    zustand = {"y1": 0.0, "y2": 50.0}
    aus, zustand = PRegler().berechne(ein, p, zustand)
    assert aus["ausgang_2"] == pytest.approx(50.0 + 2.0 / 5.0)


def test_p_regler_faehrt_bei_zu_warmem_istwert_zu():
    p = {"xp_1": 5.0, "xp_2": 5.0}
    ein = {"sollwert_2": 20.0, "istwert_2": 25.0}
    aus, _ = PRegler().berechne(ein, p, {"y1": 0.0, "y2": 50.0})
    assert aus["ausgang_2"] == pytest.approx(50.0 - 1.0)


def test_p_regler_bleibt_zwischen_null_und_hundert():
    p = {"xp_1": 5.0, "xp_2": 1.0}
    ein = {"sollwert_2": 20.0, "istwert_2": -200.0}
    aus, _ = PRegler().berechne(ein, p, {"y1": 0.0, "y2": 50.0})
    assert aus["ausgang_2"] == 100.0

    ein = {"sollwert_2": 20.0, "istwert_2": 400.0}
    aus, _ = PRegler().berechne(ein, p, {"y1": 0.0, "y2": 50.0})
    assert aus["ausgang_2"] == 0.0


def test_p_regler_konvergiert_auf_den_sollwert():
    """Wiederholtes Rechnen wie im Vorwaertslauf treibt den Ausgang an den Anschlag."""
    p = {"xp_1": 5.0, "xp_2": 5.0}
    zustand = {"y1": 0.0, "y2": 0.0}
    for _ in range(100):
        aus, zustand = PRegler().berechne(
            {"sollwert_2": 20.0, "istwert_2": 15.0}, p, zustand
        )
    assert aus["ausgang_2"] == 100.0


# ----------------------------------------------------------- Sequenzregler

def test_sequenzregler_ist_im_totband_ruhig():
    p = {"oberer_sw": 24.0, "unterer_sw": 20.0, "xp": 5.0}
    aus, zustand = Sequenzregler().berechne({"istwert": 22.0}, p, {"e": 0.0})
    assert zustand["e"] == 0.0
    assert aus["waermer_1"] == 0.0
    assert aus["kaelter_1"] == 0.0


def test_sequenzregler_oeffnet_die_erste_waermestufe():
    p = {"oberer_sw": 24.0, "unterer_sw": 20.0, "xp": 5.0}
    aus, _ = Sequenzregler().berechne({"istwert": 10.0}, p, {"e": -20.0})
    assert aus["waermer_1"] == 100.0
    assert aus["kaelter_1"] == 0.0


def test_sequenzregler_staffelt_die_stufen():
    p = {"oberer_sw": 24.0, "unterer_sw": 20.0, "xp": 5.0}
    aus, _ = Sequenzregler().berechne({"istwert": 10.0}, p, {"e": -251.0})
    assert aus["waermer_1"] == 100.0
    assert aus["waermer_2"] == 100.0
    assert aus["waermer_3"] == pytest.approx(52.0)


def test_sequenzregler_begrenzt_die_regelabweichung():
    p = {"oberer_sw": 24.0, "unterer_sw": 20.0, "xp": 5.0}
    _, zustand = Sequenzregler().berechne({"istwert": -500.0}, p, {"e": -299.0})
    assert zustand["e"] == -300.0


def test_sequenzregler_kuehlt_bei_zu_warmem_istwert():
    p = {"oberer_sw": 24.0, "unterer_sw": 20.0, "xp": 5.0}
    aus, _ = Sequenzregler().berechne({"istwert": 30.0}, p, {"e": 150.0})
    assert aus["kaelter_1"] == 100.0
    assert aus["kaelter_2"] == pytest.approx(50.6)
    assert aus["waermer_1"] == 0.0


# -------------------------------------------------------- Hysterese-Regler

def test_hysterese_schaltet_oberhalb_der_schaltdifferenz_ein():
    p = {"hysterese": 0.2}
    aus, zustand = HystereseRegler().berechne(
        {"sollwert": 5.0, "istwert": 5.2}, p, {"zustand": 0.0}
    )
    assert aus["ausgang"] == 100.0
    assert zustand["zustand"] == 100.0


def test_hysterese_schaltet_unterhalb_der_schaltdifferenz_aus():
    p = {"hysterese": 0.2}
    aus, _ = HystereseRegler().berechne(
        {"sollwert": 5.0, "istwert": 4.8}, p, {"zustand": 100.0}
    )
    assert aus["ausgang"] == 0.0


def test_hysterese_haelt_den_zustand_im_totband():
    p = {"hysterese": 1.0}
    aus, _ = HystereseRegler().berechne(
        {"sollwert": 5.0, "istwert": 5.2}, p, {"zustand": 100.0}
    )
    assert aus["ausgang"] == 100.0

    aus, _ = HystereseRegler().berechne(
        {"sollwert": 5.0, "istwert": 5.2}, p, {"zustand": 0.0}
    )
    assert aus["ausgang"] == 0.0


# ----------------------------------------------------------------- Kaskade

def test_kaskade_haelt_den_mindestsollwert_bei_kalter_aussenluft():
    p = {
        "T_Raum_min": 22.0, "T_AU_min": 20.0,
        "T_Raum_max": 28.0, "T_AU_max": 32.0,
        "T_ZU_min": 16.0, "T_ZU_max": 25.0, "xp": 5.0,
    }
    assert RaumZuluftKaskade().gleitender_sollwert(10.0, p) == pytest.approx(22.0)


def test_kaskade_hebt_den_sollwert_bei_warmer_aussenluft():
    p = {
        "T_Raum_min": 22.0, "T_AU_min": 20.0,
        "T_Raum_max": 28.0, "T_AU_max": 32.0,
        "T_ZU_min": 16.0, "T_ZU_max": 25.0, "xp": 5.0,
    }
    assert RaumZuluftKaskade().gleitender_sollwert(26.0, p) == pytest.approx(25.0)


def test_kaskade_begrenzt_den_sollwert_nach_oben():
    p = {
        "T_Raum_min": 22.0, "T_AU_min": 20.0,
        "T_Raum_max": 28.0, "T_AU_max": 32.0,
        "T_ZU_min": 16.0, "T_ZU_max": 25.0, "xp": 5.0,
    }
    assert RaumZuluftKaskade().gleitender_sollwert(40.0, p) == pytest.approx(28.0)


def test_kaskade_greift_ein_wenn_die_zuluft_zu_warm_wird():
    p = {
        "T_Raum_min": 22.0, "T_AU_min": 20.0,
        "T_Raum_max": 28.0, "T_AU_max": 32.0,
        "T_ZU_min": 16.0, "T_ZU_max": 25.0, "xp": 5.0,
    }
    ein = {"T_AU": 10.0, "T_Raum": 22.0, "T_ZU": 31.0}
    _, zustand = RaumZuluftKaskade().berechne(ein, p, {"e": 0.0})
    assert zustand["e"] == pytest.approx(2.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/bausteine/test_regler.py -v`
Expected: FAIL mit `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/bausteine/p_regler.py`:

```python
"""Zweistufiger P-Regler.

Formeln aus Anlage!K51/J57 (schnelle Stufe) und K53/J61 (traege Stufe). Der
Ausgang bezieht sich auf seinen eigenen Vorwert; ueber die Iterationen des
Vorwaertslaufs wirkt der Regler dadurch integrierend. Das ist in der Excel so
gewollt und wird bewusst uebernommen.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, ISTWERT, SIGNAL, SOLLWERT, STELLGROESSE,
    Baustein, Param, Port, registriere,
)


def klemme(wert, unten=0.0, oben=100.0):
    return max(unten, min(oben, wert))


@registriere
class PRegler(Baustein):
    # Der Ausgang bezieht sich auf seinen eigenen Vorwert - er baut sich ueber
    # die Iterationen des Vorwaertslaufs auf, genau wie in der Excel.
    ZUSTAND_UEBER_ITERATION = True

    KENNUNG = "p_regler"
    NAME = "P-Regler"
    GRUPPE = "Regelung"
    SYMBOL = "p_regler.svg"

    PARAMETER = [
        Param("xp_1", "Xp Regler 1 (schnell)", "-", 10.0),
        Param("xp_2", "Xp Regler 2 (träge)", "-", 5.0),
        Param("sollwert_1", "Sollwert 1", "-", 0.0),
        Param("sollwert_2", "Sollwert 2", "°C", 20.0),
    ]

    PORTS = [
        Port("sollwert_1", SIGNAL, EINGANG, SOLLWERT),
        Port("istwert_1", SIGNAL, EINGANG, ISTWERT),
        Port("sollwert_2", SIGNAL, EINGANG, SOLLWERT),
        Port("istwert_2", SIGNAL, EINGANG, ISTWERT),
        Port("ausgang_1", SIGNAL, AUSGANG, STELLGROESSE),
        Port("ausgang_2", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["ausgang_1", "ausgang_2"]

    def _stufe(self, y_alt, sollwert, istwert, xp):
        if not xp:
            return y_alt
        return klemme(y_alt - (istwert - sollwert) / xp)

    def berechne(self, ein, p, zustand):
        # Ist der Sollwert-Port nicht belegt, gilt der eingestellte Parameter -
        # in der Excel steht der Sollwert ebenfalls als feste Zelle (Anlage!M59).
        y1 = self._stufe(
            float(zustand.get("y1", 0.0)),
            float(ein.get("sollwert_1", p["sollwert_1"])),
            float(ein.get("istwert_1", 0.0)),
            p["xp_1"],
        )
        y2 = self._stufe(
            float(zustand.get("y2", 0.0)),
            float(ein.get("sollwert_2", p["sollwert_2"])),
            float(ein.get("istwert_2", 0.0)),
            p["xp_2"],
        )
        return {"ausgang_1": y1, "ausgang_2": y2}, {"y1": y1, "y2": y2}

    def anfangszustand(self, p):
        return {"y1": 0.0, "y2": 0.0}
```

`core/bausteine/sequenzregler.py`:

```python
"""Sequenzregler: eine Regelabweichung auf fuenf Stufen.

Formeln aus Anlage!T138 bis S148. Die Regelabweichung laeuft zwischen -300 und
+200; daraus werden drei Waerme- und zwei Kaeltestufen abgeleitet.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, ISTWERT, SIGNAL, STELLGROESSE,
    Baustein, Param, Port, registriere,
)

STUFEN = (
    ("waermer_3", -200.0, -1.0),
    ("waermer_2", -100.0, -1.0),
    ("waermer_1", 0.0, -1.0),
    ("kaelter_1", 0.0, 1.0),
    ("kaelter_2", -100.0, 1.0),
)


@registriere
class Sequenzregler(Baustein):
    # Der Ausgang bezieht sich auf seinen eigenen Vorwert - er baut sich ueber
    # die Iterationen des Vorwaertslaufs auf, genau wie in der Excel.
    ZUSTAND_UEBER_ITERATION = True

    KENNUNG = "sequenzregler"
    NAME = "Sequenzregler"
    GRUPPE = "Regelung"
    SYMBOL = "sequenzregler.svg"

    PARAMETER = [
        Param("oberer_sw", "oberer Sollwert", "°C", 24.0),
        Param("unterer_sw", "unterer Sollwert", "°C", 20.0),
        Param("xp", "Xp", "-", 5.0),
    ]

    PORTS = [
        Port("istwert", SIGNAL, EINGANG, ISTWERT),
        Port("waermer_3", SIGNAL, AUSGANG, STELLGROESSE),
        Port("waermer_2", SIGNAL, AUSGANG, STELLGROESSE),
        Port("waermer_1", SIGNAL, AUSGANG, STELLGROESSE),
        Port("kaelter_1", SIGNAL, AUSGANG, STELLGROESSE),
        Port("kaelter_2", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["waermer_3", "waermer_2", "waermer_1", "kaelter_1", "kaelter_2", "e"]

    def berechne(self, ein, p, zustand):
        istwert = float(ein.get("istwert", 0.0))
        e_alt = float(zustand.get("e", 0.0))

        if p["unterer_sw"] < istwert < p["oberer_sw"]:
            e = 0.0
        else:
            if istwert < p["unterer_sw"]:
                delta = (istwert - p["unterer_sw"]) / 10.0
            else:
                delta = (istwert - p["oberer_sw"]) / 10.0
            e = max(-300.0, min(200.0, e_alt + delta))

        aus = {}
        for name, versatz, vorzeichen in STUFEN:
            aus[name] = max(0.0, min(vorzeichen * (e + versatz) * 1.0, 100.0))
        aus["e"] = e
        return aus, {"e": e}

    def anfangszustand(self, p):
        return {"e": 0.0}
```

**Achtung bei den Stufen:** Die Excel schreibt `MAX(0;MIN(-(e+200);100))` für
`wärmer 3`, `MAX(0;MIN(-(e+100);100))` für `wärmer 2`, `MAX(0;MIN(-e;100))` für
`wärmer 1`, `MAX(0;MIN(e;100))` für `kälter 1` und `MAX(0;MIN(e-100;100))` für
`kälter 2`. Die Tabelle `STUFEN` bildet genau das ab: Vorzeichen −1 mit Versatz
−200/−100/0 und Vorzeichen +1 mit Versatz 0/−100.

`core/bausteine/hysterese_regler.py`:

```python
"""Zweipunktregler mit Schaltdifferenz. Formel aus Anlage!V155/AB57."""

from core.bausteine.basis import (
    AUSGANG, EINGANG, ISTWERT, SIGNAL, SOLLWERT, STELLGROESSE,
    Baustein, Param, Port, registriere,
)


@registriere
class HystereseRegler(Baustein):
    # Der Ausgang bezieht sich auf seinen eigenen Vorwert - er baut sich ueber
    # die Iterationen des Vorwaertslaufs auf, genau wie in der Excel.
    ZUSTAND_UEBER_ITERATION = True

    KENNUNG = "hysterese_regler"
    NAME = "Hysterese-Regler"
    GRUPPE = "Regelung"
    SYMBOL = "hysterese_regler.svg"

    PARAMETER = [
        Param("hysterese", "Hysterese", "-", 0.1),
        Param("sollwert", "Sollwert", "-", 0.0),
    ]

    PORTS = [
        Port("sollwert", SIGNAL, EINGANG, SOLLWERT),
        Port("istwert", SIGNAL, EINGANG, ISTWERT),
        Port("ausgang", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["ausgang"]

    def berechne(self, ein, p, zustand):
        sollwert = float(ein.get("sollwert", p["sollwert"]))
        istwert = float(ein.get("istwert", 0.0))
        vorher = float(zustand.get("zustand", 0.0))
        halb = p["hysterese"] / 2.0

        if istwert > sollwert + halb:
            y = 100.0
        elif istwert < sollwert - halb:
            y = 0.0
        else:
            y = vorher

        return {"ausgang": y}, {"zustand": y}

    def anfangszustand(self, p):
        return {"zustand": 0.0}
```

`core/bausteine/kaskade.py`:

```python
"""Raum-/Zuluft-Kaskade mit aussentemperaturgefuehrtem Sollwert.

Formeln aus Anlage!P143 (gleitender Raumsollwert), Q140 (Regelabweichung mit
Vorrang der Zuluftbegrenzung) und Q138/P153 bis P157 (Sequenzausgaenge).
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, ISTWERT, MESSWERT, SIGNAL, STELLGROESSE,
    Baustein, Param, Port, registriere,
)
from core.bausteine.sequenzregler import STUFEN


@registriere
class RaumZuluftKaskade(Baustein):
    # Der Ausgang bezieht sich auf seinen eigenen Vorwert - er baut sich ueber
    # die Iterationen des Vorwaertslaufs auf, genau wie in der Excel.
    ZUSTAND_UEBER_ITERATION = True

    KENNUNG = "kaskade"
    NAME = "Raum-/Zuluft-Kaskade"
    GRUPPE = "Regelung"
    SYMBOL = "kaskade.svg"

    PARAMETER = [
        Param("T_Raum_min", "min. T_Raum", "°C", 22.0),
        Param("T_AU_min", "bei T_AU", "°C", 20.0),
        Param("T_Raum_max", "max. T_Raum", "°C", 28.0),
        Param("T_AU_max", "bei T_AU", "°C", 32.0),
        Param("T_ZU_min", "min. T_ZU", "°C", 16.0),
        Param("T_ZU_max", "max. T_ZU", "°C", 25.0),
        Param("xp", "Xp", "-", 5.0),
    ]

    PORTS = [
        Port("T_AU", SIGNAL, EINGANG, MESSWERT),
        Port("T_Raum", SIGNAL, EINGANG, ISTWERT),
        Port("T_ZU", SIGNAL, EINGANG, ISTWERT),
        Port("sollwert", SIGNAL, AUSGANG, MESSWERT),
        Port("waermer_3", SIGNAL, AUSGANG, STELLGROESSE),
        Port("waermer_2", SIGNAL, AUSGANG, STELLGROESSE),
        Port("waermer_1", SIGNAL, AUSGANG, STELLGROESSE),
        Port("kaelter_1", SIGNAL, AUSGANG, STELLGROESSE),
        Port("kaelter_2", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = [
        "sollwert", "waermer_3", "waermer_2", "waermer_1",
        "kaelter_1", "kaelter_2", "e",
    ]

    def gleitender_sollwert(self, T_AU, p):
        if T_AU < p["T_AU_min"]:
            return p["T_Raum_min"]
        spanne = p["T_AU_max"] - p["T_AU_min"]
        if spanne == 0:
            return p["T_Raum_max"]
        gleitend = p["T_Raum_min"] + (T_AU - p["T_AU_min"]) * (
            p["T_Raum_max"] - p["T_Raum_min"]
        ) / spanne
        return min(gleitend, p["T_Raum_max"])

    def berechne(self, ein, p, zustand):
        T_AU = float(ein.get("T_AU", 0.0))
        T_Raum = float(ein.get("T_Raum", 0.0))
        T_ZU = float(ein.get("T_ZU", 0.0))
        e_alt = float(zustand.get("e", 0.0))

        soll = self.gleitender_sollwert(T_AU, p)

        if T_ZU > p["T_ZU_max"]:
            delta = (T_ZU - p["T_ZU_max"]) / 3.0
        elif T_ZU < p["T_ZU_min"]:
            delta = (T_ZU - p["T_ZU_min"]) / 3.0
        else:
            delta = (T_Raum - soll) / 3.0

        e = max(-300.0, min(200.0, e_alt + delta))

        aus = {"sollwert": soll, "e": e}
        for name, versatz, vorzeichen in STUFEN:
            aus[name] = max(0.0, min(vorzeichen * (e + versatz), 100.0))
        return aus, {"e": e}

    def anfangszustand(self, p):
        return {"e": 0.0}
```

`core/bausteine/__init__.py` — `MODULE` um `"p_regler"`, `"sequenzregler"`,
`"hysterese_regler"`, `"kaskade"` ergänzen.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/bausteine/test_regler.py -v`
Expected: alle Tests bestanden

- [ ] **Step 5: Commit**

```bash
git add core/bausteine tests/bausteine/test_regler.py
git commit -m "Bausteine P-Regler, Sequenzregler, Hysterese-Regler und Kaskade"
```

---

## Task 12: Zeitpläne und Anlagenbetrieb

**Files:**
- Create: `core/bausteine/wochenzeitplan.py`, `core/bausteine/monatsprofil.py`,
  `core/bausteine/tageslastprofil.py`, `core/bausteine/ferien.py`,
  `core/bausteine/anlagenbetrieb.py`
- Modify: `core/bausteine/__init__.py`
- Test: `tests/bausteine/test_zeitplaene.py`

**Interfaces:**
- Alle Zeitkarten lesen den Zeitpunkt aus `zustand["stunde"]["zeitpunkt"]`
  (ein `datetime.datetime`). Sie haben keine Lufteingänge.
- Produces:
  - `wochenzeitplan.Wochenzeitplan` (Kennung `"wochenzeitplan"`), Parameter
    `von_montag` … `bis_sonntag` als Tagesbruchteil (0,5 = 12:00 Uhr);
    Ausgang `betrieb` (0 oder 1).
  - `ferien.Ferien` (Kennung `"ferien"`), Parameter `zeitraeume` als Liste von
    `{"name": str, "von": "TT.MM.", "bis": "TT.MM."}`; Ausgang `ferien`.
  - `monatsprofil.Monatsprofil` (Kennung `"monatsprofil"`), Parameter `monate` als
    Liste von 12 Wahrheitswerten; Ausgang `betrieb`.
  - `tageslastprofil.Tageslastprofil` (Kennung `"tageslastprofil"`), Parameter
    `lastgang_1/2/3` als Liste von 24 Zahlen; Ausgänge `lastgang_1/2/3`.
  - `anlagenbetrieb.Anlagenbetrieb` (Kennung `"anlagenbetrieb"`), Eingänge
    `zeitplan`, `ferien`, `tagesprofil`; Ausgänge `betrieb`, `stellgrad`.

- [ ] **Step 1: Write the failing test**

`tests/bausteine/test_zeitplaene.py`:

```python
from datetime import datetime

import pytest

from core.bausteine.anlagenbetrieb import Anlagenbetrieb
from core.bausteine.ferien import Ferien
from core.bausteine.monatsprofil import Monatsprofil
from core.bausteine.tageslastprofil import Tageslastprofil
from core.bausteine.wochenzeitplan import Wochenzeitplan


def stunde(jahr, monat, tag, uhr):
    return {"stunde": {"zeitpunkt": datetime(jahr, monat, tag, uhr)}}


def wochenparameter():
    """Anlage!AK4:AN14 - werktags 05:00 bis 22:00, Sonntag aus."""
    p = Wochenzeitplan.vorgabeparameter()
    for tag in ("montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag"):
        p[f"von_{tag}"] = 5.0 / 24.0
        p[f"bis_{tag}"] = 22.0 / 24.0
    p["von_sonntag"] = 0.0
    p["bis_sonntag"] = 0.0
    return p


def test_wochenzeitplan_laeuft_werktags_in_der_betriebszeit():
    # 2. Januar 2024 ist ein Dienstag
    aus, _ = Wochenzeitplan().berechne({}, wochenparameter(), stunde(2024, 1, 2, 10))
    assert aus["betrieb"] == 1.0


def test_wochenzeitplan_steht_nachts():
    aus, _ = Wochenzeitplan().berechne({}, wochenparameter(), stunde(2024, 1, 2, 3))
    assert aus["betrieb"] == 0.0


def test_wochenzeitplan_steht_sonntags():
    # 7. Januar 2024 ist ein Sonntag
    aus, _ = Wochenzeitplan().berechne({}, wochenparameter(), stunde(2024, 1, 7, 10))
    assert aus["betrieb"] == 0.0


def test_ferien_erkennen_den_zeitraum():
    p = {"zeitraeume": [{"name": "Weihnachten", "von": "22.12.", "bis": "06.01."}]}
    aus, _ = Ferien().berechne({}, p, stunde(2024, 12, 27, 10))
    assert aus["ferien"] == 1.0


def test_ferien_ueber_den_jahreswechsel():
    p = {"zeitraeume": [{"name": "Weihnachten", "von": "22.12.", "bis": "06.01."}]}
    aus, _ = Ferien().berechne({}, p, stunde(2024, 1, 3, 10))
    assert aus["ferien"] == 1.0


def test_ausserhalb_der_ferien_ist_null():
    p = {"zeitraeume": [{"name": "Weihnachten", "von": "22.12.", "bis": "06.01."}]}
    aus, _ = Ferien().berechne({}, p, stunde(2024, 6, 15, 10))
    assert aus["ferien"] == 0.0


def test_monatsprofil_schaltet_den_sommer_ab():
    """Anlage!AO16:AR27 - Mai bis September aus."""
    monate = [True, True, True, True, False, False, False, False, False, True, True, True]
    aus, _ = Monatsprofil().berechne({}, {"monate": monate}, stunde(2024, 7, 15, 10))
    assert aus["betrieb"] == 0.0

    aus, _ = Monatsprofil().berechne({}, {"monate": monate}, stunde(2024, 2, 15, 10))
    assert aus["betrieb"] == 1.0


def test_tageslastprofil_liefert_den_wert_der_stunde():
    """Anlage!AS6:AV32 - nachts 0,4, tagsueber 1,0."""
    lastgang = [0.4] * 7 + [1.0] * 13 + [0.4] * 4
    p = {"lastgang_1": lastgang, "lastgang_2": [0.0] * 24, "lastgang_3": [0.0] * 24}
    aus, _ = Tageslastprofil().berechne({}, p, stunde(2024, 3, 5, 12))
    assert aus["lastgang_1"] == pytest.approx(1.0)

    aus, _ = Tageslastprofil().berechne({}, p, stunde(2024, 3, 5, 3))
    assert aus["lastgang_1"] == pytest.approx(0.4)


def test_anlagenbetrieb_verknuepft_zeitplan_ferien_und_profil():
    """Anlage!AL37/AL38."""
    ein = {"zeitplan": 1.0, "ferien": 0.0, "tagesprofil": 0.4}
    aus, _ = Anlagenbetrieb().berechne(ein, {}, {})
    assert aus["betrieb"] == 1.0
    assert aus["stellgrad"] == pytest.approx(40.0)


def test_ferien_sperren_den_betrieb():
    ein = {"zeitplan": 1.0, "ferien": 1.0, "tagesprofil": 1.0}
    aus, _ = Anlagenbetrieb().berechne(ein, {}, {})
    assert aus["betrieb"] == 0.0
    assert aus["stellgrad"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/bausteine/test_zeitplaene.py -v`
Expected: FAIL mit `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/bausteine/wochenzeitplan.py`:

```python
"""Wochenzeitplan. Formeln aus Anlage!AN7 bis AL14.

Die Zeiten stehen als Tagesbruchteil, wie in der Excel: 0,20833 entspricht
05:00 Uhr. Der Betrieb ist 1, wenn Wochentag und Uhrzeit passen.
"""

from core.bausteine.basis import (
    AUSGANG, MESSWERT, SIGNAL, Baustein, Param, Port, registriere,
)

TAGE = ("montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag")


@registriere
class Wochenzeitplan(Baustein):
    KENNUNG = "wochenzeitplan"
    NAME = "Wochenzeitplan"
    GRUPPE = "Zeit und Betrieb"
    SYMBOL = "wochenzeitplan.svg"

    PARAMETER = [
        Param(f"{grenze}_{tag}", f"{tag.capitalize()} {grenze}", "Tagesanteil",
              5.0 / 24.0 if grenze == "von" else 22.0 / 24.0)
        for tag in TAGE
        for grenze in ("von", "bis")
    ]

    PORTS = [Port("betrieb", SIGNAL, AUSGANG, MESSWERT)]

    AUSGABEN = ["betrieb"]

    def berechne(self, ein, p, zustand):
        s = zustand.get("stunde") or {}
        zeitpunkt = s.get("zeitpunkt")
        if zeitpunkt is None:
            return {"betrieb": 0.0}, zustand

        tag = TAGE[zeitpunkt.weekday()]
        anteil = (
            zeitpunkt.hour + zeitpunkt.minute / 60.0 + zeitpunkt.second / 3600.0
        ) / 24.0
        von = p.get(f"von_{tag}", 0.0)
        bis = p.get(f"bis_{tag}", 0.0)

        betrieb = 1.0 if (von < bis and von <= anteil < bis) else 0.0
        return {"betrieb": betrieb}, zustand
```

`core/bausteine/ferien.py`:

```python
"""Ferien und Sondertage. Formel aus Anlage!AN21 bis AL28.

Die Zeitraeume werden als Tag und Monat angegeben, damit sie in jedem
Wetterjahr gelten. Zeitraeume ueber den Jahreswechsel sind erlaubt.
"""

from core.bausteine.basis import (
    AUSGANG, MESSWERT, SIGNAL, Baustein, Param, Port, registriere,
)


def _als_tagesnummer(text):
    tag, monat = text.strip(". ").split(".")[:2]
    return int(monat) * 100 + int(tag)


@registriere
class Ferien(Baustein):
    KENNUNG = "ferien"
    NAME = "Ferien"
    GRUPPE = "Zeit und Betrieb"
    SYMBOL = "ferien.svg"

    PARAMETER = [Param("zeitraeume", "Zeiträume", "-", [])]

    PORTS = [Port("ferien", SIGNAL, AUSGANG, MESSWERT)]

    AUSGABEN = ["ferien"]

    def berechne(self, ein, p, zustand):
        s = zustand.get("stunde") or {}
        zeitpunkt = s.get("zeitpunkt")
        if zeitpunkt is None:
            return {"ferien": 0.0}, zustand

        heute = zeitpunkt.month * 100 + zeitpunkt.day
        for zeitraum in p.get("zeitraeume") or []:
            von = _als_tagesnummer(zeitraum["von"])
            bis = _als_tagesnummer(zeitraum["bis"])
            if von <= bis:
                treffer = von <= heute <= bis
            else:  # ueber den Jahreswechsel
                treffer = heute >= von or heute <= bis
            if treffer:
                return {"ferien": 1.0}, zustand
        return {"ferien": 0.0}, zustand
```

`core/bausteine/monatsprofil.py`:

```python
"""Monatsprofil. Formel aus Anlage!AR16 bis AR28."""

from core.bausteine.basis import (
    AUSGANG, MESSWERT, SIGNAL, Baustein, Param, Port, registriere,
)


@registriere
class Monatsprofil(Baustein):
    KENNUNG = "monatsprofil"
    NAME = "Monatsprofil"
    GRUPPE = "Zeit und Betrieb"
    SYMBOL = "monatsprofil.svg"

    PARAMETER = [Param("monate", "Monate ein/aus", "-", [True] * 12)]

    PORTS = [Port("betrieb", SIGNAL, AUSGANG, MESSWERT)]

    AUSGABEN = ["betrieb"]

    def berechne(self, ein, p, zustand):
        s = zustand.get("stunde") or {}
        zeitpunkt = s.get("zeitpunkt")
        if zeitpunkt is None:
            return {"betrieb": 0.0}, zustand
        monate = p.get("monate") or [True] * 12
        return {"betrieb": 1.0 if monate[zeitpunkt.month - 1] else 0.0}, zustand
```

`core/bausteine/tageslastprofil.py`:

```python
"""Tageslastprofil mit drei Lastgaengen. Formel aus Anlage!AT32 bis AV32."""

from core.bausteine.basis import (
    AUSGANG, MESSWERT, SIGNAL, Baustein, Param, Port, registriere,
)


@registriere
class Tageslastprofil(Baustein):
    KENNUNG = "tageslastprofil"
    NAME = "Tageslastprofil"
    GRUPPE = "Zeit und Betrieb"
    SYMBOL = "tageslastprofil.svg"

    PARAMETER = [
        Param("lastgang_1", "Lastgang 1", "-", [1.0] * 24),
        Param("lastgang_2", "Lastgang 2", "-", [0.0] * 24),
        Param("lastgang_3", "Lastgang 3", "-", [0.0] * 24),
    ]

    PORTS = [
        Port("lastgang_1", SIGNAL, AUSGANG, MESSWERT),
        Port("lastgang_2", SIGNAL, AUSGANG, MESSWERT),
        Port("lastgang_3", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["lastgang_1", "lastgang_2", "lastgang_3"]

    def berechne(self, ein, p, zustand):
        s = zustand.get("stunde") or {}
        zeitpunkt = s.get("zeitpunkt")
        if zeitpunkt is None:
            return {name: 0.0 for name in self.AUSGABEN}, zustand

        stunde_des_tages = zeitpunkt.hour
        aus = {}
        for name in self.AUSGABEN:
            werte = p.get(name) or [0.0] * 24
            aus[name] = float(werte[stunde_des_tages])
        return aus, zustand
```

`core/bausteine/anlagenbetrieb.py`:

```python
"""Anlagenbetrieb. Verknuepft Zeitplan, Ferien und Tagesprofil.

Formeln aus Anlage!AL37 (Betrieb) und AL38 (Stellgrad in Prozent).
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, MESSWERT, SIGNAL, STELLGROESSE,
    Baustein, Port, registriere,
)


@registriere
class Anlagenbetrieb(Baustein):
    KENNUNG = "anlagenbetrieb"
    NAME = "Anlagenbetrieb"
    GRUPPE = "Zeit und Betrieb"
    SYMBOL = "anlagenbetrieb.svg"

    PARAMETER = []

    PORTS = [
        Port("zeitplan", SIGNAL, EINGANG, MESSWERT),
        Port("ferien", SIGNAL, EINGANG, MESSWERT),
        Port("tagesprofil", SIGNAL, EINGANG, MESSWERT),
        Port("betrieb", SIGNAL, AUSGANG, MESSWERT),
        Port("stellgrad", SIGNAL, AUSGANG, STELLGROESSE),
    ]

    AUSGABEN = ["betrieb", "stellgrad"]

    def berechne(self, ein, p, zustand):
        zeitplan = float(ein.get("zeitplan", 1.0))
        ferien = float(ein.get("ferien", 0.0))
        profil = float(ein.get("tagesprofil", 1.0))

        betrieb = zeitplan * (1.0 - ferien)
        stellgrad = betrieb * profil * 100.0
        return {"betrieb": betrieb, "stellgrad": stellgrad}, zustand
```

`core/bausteine/__init__.py` — `MODULE` um die fünf Zeitkarten ergänzen.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/bausteine/test_zeitplaene.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add core/bausteine tests/bausteine/test_zeitplaene.py
git commit -m "Bausteine Wochenzeitplan, Ferien, Monatsprofil, Tageslastprofil und Anlagenbetrieb"
```

---

## Task 13: Verbraucher, Bilanz und Datenlogger

**Files:**
- Create: `core/bausteine/heizungspumpen.py`, `core/bausteine/warmwasser.py`,
  `core/bausteine/zirkulation.py`, `core/bausteine/beleuchtung.py`,
  `core/bausteine/enthalpierechner.py`, `core/bausteine/bilanz.py`,
  `core/bausteine/datenlogger.py`
- Modify: `core/bausteine/__init__.py`
- Test: `tests/bausteine/test_verbraucher.py`, `tests/bausteine/test_bilanz.py`

**Interfaces:**
- Produces:
  - `heizungspumpen.Heizungspumpen` (Kennung `"heizungspumpen"`), Ausgang `PE`.
  - `warmwasser.Warmwasserbereitung` (Kennung `"warmwasser"`), Ausgang `QH`.
  - `zirkulation.Zirkulation` (Kennung `"zirkulation"`), Ausgänge `QH`, `PE`.
  - `beleuchtung.Beleuchtung` (Kennung `"beleuchtung"`), Ausgänge `Q_Bel`, `PE`.
  - `enthalpierechner.Enthalpierechner` (Kennung `"enthalpierechner"`), Ausgänge
    `h`, `rF`.
  - `bilanz.Bilanz` (Kennung `"bilanz"`), dynamische Eingänge `strom`, `waerme`,
    `kaelte`, `wasser`; Ausgaben `strom_ht`, `strom_nt`, `waerme`, `kaelte`,
    `wasser`, `hochtarif`.
  - `datenlogger.Datenlogger` (Kennung `"datenlogger"`), zehn dynamische Eingänge
    `wert_1` … `wert_10` mit Namen und Einheit als Parameter.

- [ ] **Step 1: Write the failing tests**

`tests/bausteine/test_verbraucher.py`:

```python
import pytest

from core.bausteine.beleuchtung import Beleuchtung
from core.bausteine.heizungspumpen import Heizungspumpen
from core.bausteine.warmwasser import Warmwasserbereitung
from core.bausteine.zirkulation import Zirkulation


def test_heizungspumpen_entsprechen_der_excel():
    """Anlage!AE145 - Allgemein voll, WWB und Kessel je zur Haelfte."""
    p = {"P_allgemein": 2.0, "P_wwb": 1.0, "P_kessel": 3.0}
    aus, _ = Heizungspumpen().berechne({"betrieb": 1.0}, p, {})
    assert aus["PE"] == pytest.approx(2.0 + 0.5 * 1.0 + 0.5 * 3.0)


def test_heizungspumpen_stehen_ausser_betrieb():
    p = {"P_allgemein": 2.0, "P_wwb": 1.0, "P_kessel": 3.0}
    aus, _ = Heizungspumpen().berechne({"betrieb": 0.0}, p, {})
    assert aus["PE"] == 0.0


def test_speicherverlust_entspricht_der_excel():
    """Anlage!AF148 fuer 1000 Liter."""
    erwartet = ((1000.0 / 1000.0) ** 0.333) ** 2 * 5.0 * 8.0 * 20.0 / 1000.0
    assert Warmwasserbereitung().speicherverlust({"speichervolumen": 1000.0}) == pytest.approx(erwartet)


def test_warmwasserleistung_entspricht_der_excel():
    """Anlage!AE156 - 462 m³/a auf 50 °C bei 1000 Liter Speicher."""
    p = {"speichervolumen": 1000.0, "verbrauch": 462.0, "sollwert": 50.0}
    aus, _ = Warmwasserbereitung().berechne({}, p, {})
    assert aus["QH"] == pytest.approx(3.2494672754946725, rel=1e-10)


def test_zirkulation_entspricht_der_excel():
    """Anlage!AE157/AE158 - 1,5 m³/h bei 5 K Spreizung."""
    p = {"volumenstrom": 1.5, "spreizung": 5.0, "P_pumpe": 0.04}
    aus, _ = Zirkulation().berechne({"betrieb": 1.0}, p, {})
    assert aus["QH"] == pytest.approx(1.5 * 1000.0 / 3600.0 * 4.18 * 5.0 * 0.75)
    assert aus["PE"] == pytest.approx(0.04)


def test_zirkulation_steht_ausser_betrieb():
    p = {"volumenstrom": 1.5, "spreizung": 5.0, "P_pumpe": 0.04}
    aus, _ = Zirkulation().berechne({"betrieb": 0.0}, p, {})
    assert aus["QH"] == 0.0
    assert aus["PE"] == 0.0


def test_beleuchtung_entspricht_der_excel():
    """Anlage!AK134 - 2 W/m² auf 726 m²."""
    p = {"spez_leistung": 2.0, "grundflaeche": 726.0, "nennbeleuchtung": 300.0}
    aus, _ = Beleuchtung().berechne({"betrieb": 1.0}, p, {})
    assert aus["Q_Bel"] == pytest.approx(1.452)
    assert aus["PE"] == pytest.approx(1.452)


def test_beleuchtung_folgt_dem_betriebssignal():
    p = {"spez_leistung": 2.0, "grundflaeche": 726.0, "nennbeleuchtung": 300.0}
    aus, _ = Beleuchtung().berechne({"betrieb": 0.5}, p, {})
    assert aus["Q_Bel"] == pytest.approx(0.726)
```

`tests/bausteine/test_bilanz.py`:

```python
from datetime import datetime

import pytest

from core.bausteine.bilanz import Bilanz
from core.bausteine.datenlogger import Datenlogger


def parameter(**abweichend):
    p = Bilanz.vorgabeparameter()
    p.update(
        {
            "preis_strom_ht": 150.0,
            "preis_strom_nt": 150.0,
            "preis_waerme": 50.0,
            "preis_kaelte": 50.0,
            "preis_wasser": 4.0,
            "ht_von": 7.0 / 24.0,
            "ht_bis": 20.0 / 24.0,
        }
    )
    p.update(abweichend)
    return p


def stunde(jahr, monat, tag, uhr):
    return {"stunde": {"zeitpunkt": datetime(jahr, monat, tag, uhr)}}


def test_werktags_tagsueber_gilt_der_hochtarif():
    # 2. Januar 2024 ist ein Dienstag
    aus, _ = Bilanz().berechne({"strom_1": 10.0}, parameter(), stunde(2024, 1, 2, 12))
    assert aus["hochtarif"] == 1.0
    assert aus["strom_ht"] == pytest.approx(10.0)
    assert aus["strom_nt"] == 0.0


def test_nachts_gilt_der_niedertarif():
    aus, _ = Bilanz().berechne({"strom_1": 10.0}, parameter(), stunde(2024, 1, 2, 3))
    assert aus["hochtarif"] == 0.0
    assert aus["strom_nt"] == pytest.approx(10.0)


def test_am_wochenende_gilt_der_niedertarif():
    # 6. Januar 2024 ist ein Samstag
    aus, _ = Bilanz().berechne({"strom_1": 10.0}, parameter(), stunde(2024, 1, 6, 12))
    assert aus["hochtarif"] == 0.0


def test_bilanz_summiert_alle_angeschlossenen_leistungen():
    ein = {
        "strom_1": 4.9, "strom_2": 1.7, "strom_3": 0.18,
        "waerme_1": 26.1, "waerme_2": 50.5,
        "kaelte_1": 12.0,
        "wasser_1": 46.2,
    }
    aus, _ = Bilanz().berechne(ein, parameter(), stunde(2024, 1, 2, 3))
    assert aus["strom_nt"] == pytest.approx(4.9 + 1.7 + 0.18)
    assert aus["waerme"] == pytest.approx(76.6)
    assert aus["kaelte"] == pytest.approx(12.0)
    assert aus["wasser"] == pytest.approx(46.2)


def test_datenlogger_gibt_die_benannten_werte_zurueck():
    p = {
        "namen": ["WRG", "T Raum", "F Raum"] + [""] * 7,
        "einheiten": ["kW", "°C", "g/kg"] + [""] * 7,
    }
    ein = {"wert_1": 51.66, "wert_2": 16.61, "wert_3": 5.33}
    aus, _ = Datenlogger().berechne(ein, p, {})
    assert aus["wert_1"] == pytest.approx(51.66)
    assert aus["wert_3"] == pytest.approx(5.33)


def test_datenlogger_meldet_seine_spalten():
    p = {
        "namen": ["WRG", "T Raum"] + [""] * 8,
        "einheiten": ["kW", "°C"] + [""] * 8,
    }
    assert Datenlogger().spalten(p) == [
        ("wert_1", "WRG", "kW"),
        ("wert_2", "T Raum", "°C"),
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/bausteine/test_verbraucher.py tests/bausteine/test_bilanz.py -v`
Expected: FAIL mit `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/bausteine/heizungspumpen.py`:

```python
"""Heizungspumpen. Formel aus Anlage!AE145."""

from core.bausteine.basis import (
    AUSGANG, EINGANG, MESSWERT, SIGNAL, STROM, Baustein, Param, Port, registriere,
)


@registriere
class Heizungspumpen(Baustein):
    KENNUNG = "heizungspumpen"
    NAME = "Heizungspumpen"
    GRUPPE = "Verbraucher"
    SYMBOL = "heizungspumpen.svg"

    PARAMETER = [
        Param("P_allgemein", "Allgemein", "kW", 0.0),
        Param("P_wwb", "WWB", "kW", 0.0),
        Param("P_kessel", "Kessel", "kW", 0.0),
    ]

    PORTS = [
        Port("betrieb", SIGNAL, EINGANG, MESSWERT),
        Port("PE", SIGNAL, AUSGANG, STROM),
    ]

    AUSGABEN = ["PE"]

    def berechne(self, ein, p, zustand):
        betrieb = float(ein.get("betrieb", 0.0))
        PE = betrieb * (
            p["P_allgemein"] + 0.5 * p["P_wwb"] + 0.5 * p["P_kessel"]
        )
        return {"PE": PE}, zustand
```

`core/bausteine/warmwasser.py`:

```python
"""Warmwasserbereitung. Formeln aus Anlage!AE156 und AF148.

Der Jahresverbrauch wird gleichmaessig auf 8760 Stunden verteilt; dazu kommt
der Speicherverlust, der nur von der Speichergroesse abhaengt.
"""

from core.bausteine.basis import (
    AUSGANG, SIGNAL, WAERME, Baustein, Param, Port, registriere,
)

KALTWASSER = 10.0  # °C, Anlage!AE156


@registriere
class Warmwasserbereitung(Baustein):
    KENNUNG = "warmwasser"
    NAME = "Warmwasserbereitung"
    GRUPPE = "Verbraucher"
    SYMBOL = "warmwasser.svg"

    PARAMETER = [
        Param("speichervolumen", "Speichervol.", "l", 1000.0),
        Param("verbrauch", "Verbrauch", "m³/a", 462.0),
        Param("sollwert", "Sollwert", "°C", 50.0),
    ]

    PORTS = [Port("QH", SIGNAL, AUSGANG, WAERME)]

    AUSGABEN = ["QH", "speicherverlust"]

    def speicherverlust(self, p):
        return ((p["speichervolumen"] / 1000.0) ** 0.333) ** 2 * 5.0 * 8.0 * 20.0 / 1000.0

    def berechne(self, ein, p, zustand):
        verlust = self.speicherverlust(p)
        QH = (
            p["verbrauch"] * 1000.0 / 8760.0 * 4.18 * (p["sollwert"] - KALTWASSER) / 3600.0
            + verlust
        )
        return {"QH": QH, "speicherverlust": verlust}, zustand
```

`core/bausteine/zirkulation.py`:

```python
"""Zirkulationsleitung. Formeln aus Anlage!AE157 und AE158."""

from core.bausteine.basis import (
    AUSGANG, EINGANG, MESSWERT, SIGNAL, STROM, WAERME,
    Baustein, Param, Port, registriere,
)


@registriere
class Zirkulation(Baustein):
    KENNUNG = "zirkulation"
    NAME = "Zirkulation"
    GRUPPE = "Verbraucher"
    SYMBOL = "zirkulation.svg"

    PARAMETER = [
        Param("volumenstrom", "Zirkulation", "m³/h", 1.5),
        Param("spreizung", "Zirk. VL-RL", "K", 5.0),
        Param("P_pumpe", "Zirk_PU", "kW", 0.04),
    ]

    PORTS = [
        Port("betrieb", SIGNAL, EINGANG, MESSWERT),
        Port("QH", SIGNAL, AUSGANG, WAERME),
        Port("PE", SIGNAL, AUSGANG, STROM),
    ]

    AUSGABEN = ["QH", "PE"]

    def berechne(self, ein, p, zustand):
        betrieb = float(ein.get("betrieb", 0.0))
        QH = p["volumenstrom"] * 1000.0 / 3600.0 * 4.18 * p["spreizung"] * 0.75 * betrieb
        PE = p["P_pumpe"] * betrieb
        return {"QH": QH, "PE": PE}, zustand
```

`core/bausteine/beleuchtung.py`:

```python
"""Beleuchtung. Formel aus Anlage!AK134.

In der Excel steckt die Beleuchtung fest im Raumblock. Hier ist sie eine eigene
Karte, damit Raeume unterschiedlich beleuchtet gerechnet werden koennen. Die
abgegebene Waerme entspricht der aufgenommenen elektrischen Leistung.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, MESSWERT, SIGNAL, STROM, Baustein, Param, Port, registriere,
)


@registriere
class Beleuchtung(Baustein):
    KENNUNG = "beleuchtung"
    NAME = "Beleuchtung"
    GRUPPE = "Verbraucher"
    SYMBOL = "beleuchtung.svg"

    PARAMETER = [
        Param("spez_leistung", "sp. Leistung", "W/m²", 2.0),
        Param("grundflaeche", "Grundfläche", "m²", 726.0),
        Param("nennbeleuchtung", "Nennbel.", "lx", 300.0),
    ]

    PORTS = [
        Port("betrieb", SIGNAL, EINGANG, MESSWERT),
        Port("Q_Bel", SIGNAL, AUSGANG, MESSWERT),
        Port("PE", SIGNAL, AUSGANG, STROM),
    ]

    AUSGABEN = ["Q_Bel", "PE"]

    def berechne(self, ein, p, zustand):
        betrieb = float(ein.get("betrieb", 1.0))
        Q = p["spez_leistung"] * p["grundflaeche"] / 1000.0 * betrieb
        return {"Q_Bel": Q, "PE": Q}, zustand
```

`core/bausteine/enthalpierechner.py`:

```python
"""Hilfsbaustein zur Zustandsumrechnung. Anlage!U138:W148 und X141:Z148."""

from core.bausteine import stoffdaten as st
from core.bausteine.basis import (
    AUSGANG, EINGANG, MESSWERT, SIGNAL, Baustein, Port, registriere,
)


@registriere
class Enthalpierechner(Baustein):
    KENNUNG = "enthalpierechner"
    NAME = "Enthalpie / rel. Feuchte"
    GRUPPE = "Verbraucher"
    SYMBOL = "enthalpierechner.svg"

    PARAMETER = []

    PORTS = [
        Port("t", SIGNAL, EINGANG, MESSWERT),
        Port("x", SIGNAL, EINGANG, MESSWERT),
        Port("h", SIGNAL, AUSGANG, MESSWERT),
        Port("rF", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["h", "rF"]

    def berechne(self, ein, p, zustand):
        t = float(ein.get("t", 0.0))
        x = float(ein.get("x", 0.0))
        rF = st.rel_feuchte(t, x) if x > 0 else 0.0
        return {"h": st.enthalpie(t, x), "rF": rF}, zustand
```

`core/bausteine/bilanz.py`:

```python
"""Energiebilanz und Preise. Formeln aus Anlage!C32 bis D31 und AO30:AR42.

Die Karte summiert alles, was an ihre dynamischen Eingaenge angeschlossen ist,
und teilt den Strom nach Hoch- und Niedertarif auf.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, KAELTE, MESSWERT, SIGNAL, STROM, WAERME, WASSER,
    Baustein, Param, Port, registriere,
)


@registriere
class Bilanz(Baustein):
    KENNUNG = "bilanz"
    NAME = "Energiepreise und Bilanz"
    GRUPPE = "Verbraucher"
    SYMBOL = "bilanz.svg"

    PARAMETER = [
        Param("preis_strom_ht", "Strom HT", "EUR/MWh", 150.0),
        Param("preis_strom_nt", "Strom NT", "EUR/MWh", 150.0),
        Param("preis_strom_leistung", "Strom Leist.", "EUR/kW/a", 0.0),
        Param("preis_waerme", "Wärme", "EUR/MWh", 50.0),
        Param("preis_kaelte", "Kälte", "EUR/MWh", 50.0),
        Param("preis_wasser", "Wasser", "EUR/m³", 4.0),
        Param("ht_von", "HT von", "Tagesanteil", 7.0 / 24.0),
        Param("ht_bis", "HT bis", "Tagesanteil", 20.0 / 24.0),
    ]

    PORTS = [
        Port("strom", SIGNAL, EINGANG, STROM, dynamisch=True),
        Port("waerme", SIGNAL, EINGANG, WAERME, dynamisch=True),
        Port("kaelte", SIGNAL, EINGANG, KAELTE, dynamisch=True),
        Port("wasser", SIGNAL, EINGANG, WASSER, dynamisch=True),
        Port("hochtarif", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["strom_ht", "strom_nt", "waerme", "kaelte", "wasser", "hochtarif"]

    def _summe(self, ein, praefix):
        return sum(
            float(w) for s, w in ein.items()
            if s.startswith(praefix) and isinstance(w, (int, float))
        )

    def berechne(self, ein, p, zustand):
        s = zustand.get("stunde") or {}
        zeitpunkt = s.get("zeitpunkt")

        hochtarif = 0.0
        if zeitpunkt is not None and zeitpunkt.weekday() < 5:
            anteil = (zeitpunkt.hour + zeitpunkt.minute / 60.0) / 24.0
            if p["ht_von"] < anteil < p["ht_bis"]:
                hochtarif = 1.0

        strom = self._summe(ein, "strom")
        return (
            {
                "strom_ht": strom if hochtarif else 0.0,
                "strom_nt": 0.0 if hochtarif else strom,
                "waerme": self._summe(ein, "waerme"),
                "kaelte": self._summe(ein, "kaelte"),
                "wasser": self._summe(ein, "wasser"),
                "hochtarif": hochtarif,
            },
            zustand,
        )
```

`core/bausteine/datenlogger.py`:

```python
"""Datenlogger. Entspricht den Spalten Wert1 bis Wert10 aus Anlage!B26:D46.

Angeschlossene Groessen erscheinen als eigene Spalte im Stundenprotokoll.
"""

from core.bausteine.basis import (
    EINGANG, MESSWERT, SIGNAL, Baustein, Param, Port, registriere,
)

ANZAHL = 10


@registriere
class Datenlogger(Baustein):
    KENNUNG = "datenlogger"
    NAME = "Datenlogger"
    GRUPPE = "Verbraucher"
    SYMBOL = "datenlogger.svg"

    PARAMETER = [
        Param("namen", "Spaltennamen", "-", [""] * ANZAHL),
        Param("einheiten", "Einheiten", "-", [""] * ANZAHL),
    ]

    PORTS = [
        Port(f"wert_{i}", SIGNAL, EINGANG, MESSWERT) for i in range(1, ANZAHL + 1)
    ]

    AUSGABEN = [f"wert_{i}" for i in range(1, ANZAHL + 1)]

    def spalten(self, p):
        """Die belegten Spalten als (Portschluessel, Name, Einheit)."""
        namen = p.get("namen") or [""] * ANZAHL
        einheiten = p.get("einheiten") or [""] * ANZAHL
        return [
            (f"wert_{i + 1}", namen[i], einheiten[i])
            for i in range(ANZAHL)
            if namen[i]
        ]

    def berechne(self, ein, p, zustand):
        return {
            f"wert_{i}": float(ein.get(f"wert_{i}", 0.0))
            for i in range(1, ANZAHL + 1)
        }, zustand
```

`core/bausteine/__init__.py` — `MODULE` um die sieben neuen Karten ergänzen. Die
Liste enthält danach alle 31 Kartentypen (Außenluft und Fortluft sind zwei eigene
Karten, weil sie unterschiedliche Ports haben).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/bausteine -v`
Expected: alle Tests bestanden

- [ ] **Step 5: Verify the catalogue is complete**

```bash
python3 -c "
from core.bausteine import lade_alle, basis
lade_alle()
gruppen = basis.nach_gruppen()
gesamt = sum(len(v) for v in gruppen.values())
for name, klassen in sorted(gruppen.items()):
    print(f'{name}: {len(klassen)}')
print('gesamt:', gesamt)
assert gesamt == 31, gesamt
"
```
Expected: `gesamt: 31`

- [ ] **Step 6: Commit**

```bash
git add core/bausteine tests/bausteine
git commit -m "Bausteine Verbraucher, Bilanz, Enthalpierechner und Datenlogger"
```

---

## Regel für dynamische Ports

Ein **fester** Port heißt in `ein` und `aus` genau so, wie er deklariert ist:
`ein["luft_ein"]`. Ein **dynamischer** Port wird durchnummeriert — aus
`zuluft_ein` werden `zuluft_ein_1`, `zuluft_ein_2` und so weiter. Bausteine mit
dynamischen Ports müssen ihre Eingänge deshalb über das Präfix einsammeln:

```python
zuluft = [w for s, w in ein.items() if s.startswith("zuluft_ein")]
```

Dynamische Ports haben in Stufe 1 genau fünf Karten: Verteiler (`luft_aus`),
Sammler (`luft_ein`), Raum und einfacher Raum (`zuluft_ein`, `abluft_aus`) sowie
Bilanz (`strom`, `waerme`, `kaelte`, `wasser`). Alle anderen Karten haben feste
Ports; Verzweigungen entstehen über Verteiler und Sammler. Eine
Wärmerückgewinnung, die zwei Lüftungsgeräte versorgt, wird also als
Wärmerückgewinnung plus Verteiler gebaut — das entspricht dem, was die Excel in
`M9 = S9 + S31` als Formel tut.

---

## Task 14: Graph, Ports und automatische Verdrahtung

Hier entsteht das Herzstück der Bedienung: ein Pfeil zwischen zwei Karten erzeugt
alle passenden Portverbindungen von selbst.

**Files:**
- Create: `core/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Produces:
  - `graph.PortInstanz(id, karte_id, schluessel, basis, art, richtung, rolle, nummer)`
  - `graph.KarteInstanz(id, typ, name, parameter, baustein, ports)`
  - `graph.Anlagengraph(karten, verbindungen)` mit
    `reihenfolge() -> list[int]` (topologisch sortierte Karten-IDs) und
    `rueckkanten() -> set[tuple[int, int]]`
  - `graph.erzeuge_ports(klasse, parameter, karte_id, ab_id) -> list[PortInstanz]`
  - `graph.verdrahte(von, nach, belegt) -> list[tuple[PortInstanz, PortInstanz]]`
  - `graph.fehlende_ports(karte, belegt) -> list[PortInstanz]` — die Ports, die
    nach dem Verbinden nachwachsen müssen

- [ ] **Step 1: Write the failing test**

`tests/test_graph.py`:

```python
import pytest

from core import graph
from core.bausteine import basis, lade_alle

lade_alle()


def karte(karte_id, typ, parameter=None):
    klasse = basis.hole(typ)
    p = klasse.vorgabeparameter()
    p.update(parameter or {})
    ports = graph.erzeuge_ports(klasse, p, karte_id, ab_id=karte_id * 100)
    return graph.KarteInstanz(
        id=karte_id, typ=typ, name=klasse.NAME, parameter=p,
        baustein=klasse(), ports=ports,
    )


# --------------------------------------------------------------- Portanlage

def test_feste_ports_behalten_ihren_schluessel():
    k = karte(1, "erhitzer")
    schluessel = {p.schluessel for p in k.ports}
    assert "luft_ein" in schluessel
    assert "stellgroesse" in schluessel


def test_dynamische_ports_werden_nummeriert():
    k = karte(1, "sammler")
    eingaenge = [p for p in k.ports if p.richtung == basis.EINGANG]
    assert [p.schluessel for p in eingaenge] == ["luft_ein_1"]
    assert eingaenge[0].basis == "luft_ein"


def test_ventilator_bekommt_abluftrollen_nach_parameter():
    k = karte(1, "ventilator", {"rolle": "abluft"})
    rollen = {p.schluessel: p.rolle for p in k.ports}
    assert rollen["luft_ein"] == basis.ABLUFT


# ---------------------------------------------------- automatische Verdrahtung

def test_ein_pfeil_verdrahtet_den_luftweg():
    a, b = karte(1, "erhitzer"), karte(2, "kuehler")
    paare = graph.verdrahte(a, b, belegt=set())
    assert len(paare) == 1
    von, nach = paare[0]
    assert von.schluessel == "luft_aus"
    assert nach.schluessel == "luft_ein"


def test_pfeil_vom_raum_zur_wrg_trifft_den_abluftweg():
    raum, wrg = karte(1, "einfacher_raum"), karte(2, "wrg")
    paare = graph.verdrahte(raum, wrg, belegt=set())
    assert [(v.basis, n.schluessel) for v, n in paare] == [
        ("abluft_aus", "abluft_ein")
    ]


def test_pfeil_vom_regler_verdrahtet_stellgroesse_und_istwert():
    regler, erhitzer = karte(1, "p_regler"), karte(2, "erhitzer")
    paare = graph.verdrahte(regler, erhitzer, belegt=set())
    richtungen = {(v.schluessel, n.schluessel) for v, n in paare}
    assert ("ausgang_1", "stellgroesse") in richtungen or (
        "ausgang_2", "stellgroesse"
    ) in richtungen
    # Rueckrichtung: der Messwert des Erhitzers geht auf den Istwert des Reglers
    assert any(v.karte_id == 2 and n.karte_id == 1 for v, n in paare)


def test_gleiche_schluessel_werden_bevorzugt_gepaart():
    """Die Wetterkarte am Raum verdrahtet T_AU auf T_AU, QH_S auf QH_S und so fort."""
    wetter, raum = karte(1, "wetter"), karte(2, "raum")
    paare = graph.verdrahte(wetter, raum, belegt=set())
    zuordnung = {v.schluessel: n.schluessel for v, n in paare}
    assert zuordnung["T_AU"] == "T_AU"
    assert zuordnung["QH_S"] == "QH_S"
    assert zuordnung["QH_H"] == "QH_H"
    assert len(paare) == 7


def test_wrg_zur_fortluft_nimmt_den_abluftweg():
    """Der Zuluftausgang darf niemals auf einen Fortluftanschluss laufen."""
    wrg, fortluft = karte(1, "wrg"), karte(2, "fortluft")
    paare = graph.verdrahte(wrg, fortluft, belegt=set())
    assert [v.schluessel for v, _ in paare] == ["abluft_aus"]


def test_aussenluft_geht_auf_den_zuluftweg():
    aussenluft, wrg = karte(1, "aussenluft"), karte(2, "wrg")
    paare = graph.verdrahte(aussenluft, wrg, belegt=set())
    assert [n.schluessel for _, n in paare] == ["zuluft_ein"]


def test_sammler_nimmt_abluft_an():
    """Verteiler und Sammler haben eine neutrale Luftrolle."""
    raum, sammler = karte(1, "einfacher_raum"), karte(2, "sammler")
    paare = graph.verdrahte(raum, sammler, belegt=set())
    assert [(v.basis, n.schluessel) for v, n in paare] == [
        ("abluft_aus", "luft_ein_1")
    ]


def test_raum_geht_nicht_auf_den_zuluftweg_einer_wrg():
    raum, wrg = karte(1, "einfacher_raum"), karte(2, "wrg")
    paare = graph.verdrahte(raum, wrg, belegt=set())
    assert all(n.schluessel != "zuluft_ein" for _, n in paare)


def test_leistungen_treffen_die_richtige_bilanzspalte():
    """Ohne eigene Energierollen liefe die Ventilatorleistung auf 'Wärme'."""
    ventilator, bilanz = karte(1, "ventilator"), karte(2, "bilanz")
    paare = graph.verdrahte(ventilator, bilanz, belegt=set())
    zuordnung = {v.schluessel: n.schluessel for v, n in paare}
    assert zuordnung["PE"] == "strom_1"
    assert "waerme_1" not in zuordnung.values()


def test_erhitzer_speist_die_waermespalte():
    erhitzer, bilanz = karte(1, "erhitzer"), karte(2, "bilanz")
    zuordnung = {
        v.schluessel: n.schluessel
        for v, n in graph.verdrahte(erhitzer, bilanz, belegt=set())
    }
    assert zuordnung["QH"] == "waerme_1"


def test_luftwaescher_speist_strom_und_wasser():
    waescher, bilanz = karte(1, "luftwaescher"), karte(2, "bilanz")
    zuordnung = {
        v.schluessel: n.schluessel
        for v, n in graph.verdrahte(waescher, bilanz, belegt=set())
    }
    assert zuordnung["PE_Pumpe"] == "strom_1"
    assert zuordnung["wasser"] == "wasser_1"


def test_datenlogger_belegt_die_spalten_der_reihe_nach():
    """Ein Textvergleich wuerde hier 'wert_10' vor 'wert_2' einsortieren."""
    raum, logger = karte(1, "einfacher_raum"), karte(2, "datenlogger")
    paare = graph.verdrahte(raum, logger, belegt=set())
    ziele = [n.schluessel for _, n in paare]
    assert ziele[:2] == ["wert_1", "wert_2"]


def test_belegte_ports_werden_uebersprungen():
    a, b = karte(1, "erhitzer"), karte(2, "kuehler")
    belegt = {p.id for p in a.ports if p.schluessel == "luft_aus"}
    assert graph.verdrahte(a, b, belegt=belegt) == []


def test_dynamischer_port_waechst_nach_dem_verbinden_nach():
    verteiler, erhitzer = karte(1, "verteiler"), karte(2, "erhitzer")
    paare = graph.verdrahte(verteiler, erhitzer, belegt=set())
    belegt = {v.id for v, _ in paare}
    neue = graph.fehlende_ports(verteiler, belegt)
    assert [p.schluessel for p in neue] == ["luft_aus_2"]


def test_kein_nachwachsen_solange_ein_port_frei_ist():
    verteiler = karte(1, "verteiler")
    assert graph.fehlende_ports(verteiler, belegt=set()) == []


def test_zwei_raeume_belegen_nacheinander_die_verteilerabgaenge():
    verteiler = karte(1, "verteiler")
    raum_a, raum_b = karte(2, "einfacher_raum"), karte(3, "einfacher_raum")

    paare_a = graph.verdrahte(verteiler, raum_a, belegt=set())
    belegt = {v.id for v, _ in paare_a} | {n.id for _, n in paare_a}
    verteiler.ports += graph.fehlende_ports(verteiler, belegt)

    paare_b = graph.verdrahte(verteiler, raum_b, belegt=belegt)
    assert paare_a[0][0].schluessel == "luft_aus_1"
    assert paare_b[0][0].schluessel == "luft_aus_2"


# ------------------------------------------------------------------ Sortierung

def baue_graph(karten, kanten):
    verbindungen = []
    for von_id, von_port, nach_id, nach_port in kanten:
        v = next(p for p in karten[von_id].ports if p.schluessel == von_port)
        n = next(p for p in karten[nach_id].ports if p.schluessel == nach_port)
        verbindungen.append(graph.VerbindungInstanz(von_port=v, nach_port=n))
    return graph.Anlagengraph(karten=karten, verbindungen=verbindungen)


def test_reihenfolge_ist_topologisch():
    karten = {i: karte(i, t) for i, t in [(1, "erhitzer"), (2, "kuehler"), (3, "luftwaescher")]}
    g = baue_graph(
        karten,
        [(1, "luft_aus", 2, "luft_ein"), (2, "luft_aus", 3, "luft_ein")],
    )
    assert g.reihenfolge() == [1, 2, 3]


def test_zyklus_wird_aufgebrochen_und_gemeldet():
    karten = {i: karte(i, t) for i, t in [(1, "erhitzer"), (2, "kuehler")]}
    g = baue_graph(
        karten,
        [(1, "luft_aus", 2, "luft_ein"), (2, "QK", 1, "stellgroesse")],
    )
    reihenfolge = g.reihenfolge()
    assert sorted(reihenfolge) == [1, 2]
    assert g.rueckkanten() == {(2, 1)}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'core.graph'`

- [ ] **Step 3: Write the implementation**

`core/graph.py`:

```python
"""Karten, Ports, automatische Verdrahtung und Reihenfolge.

Verbunden werden Karten, nicht Ports: ein Pfeil von A nach B erzeugt alle
passenden Portverbindungen auf einmal. Grundlage ist die Rolle jedes Ports.
"""

from dataclasses import dataclass, field

from core.bausteine import basis


@dataclass
class PortInstanz:
    id: int
    karte_id: int
    schluessel: str
    basis: str
    art: str
    richtung: str
    rolle: str
    nummer: int = 1


@dataclass
class KarteInstanz:
    id: int
    typ: str
    name: str
    parameter: dict
    baustein: object
    ports: list = field(default_factory=list)

    def port(self, schluessel):
        for p in self.ports:
            if p.schluessel == schluessel:
                return p
        raise KeyError(f"Port '{schluessel}' gibt es nicht an Karte {self.id}")


@dataclass
class VerbindungInstanz:
    von_port: PortInstanz
    nach_port: PortInstanz


def _deklarierte_ports(klasse, parameter):
    """Beruecksichtigt Karten, deren Ports von Parametern abhaengen."""
    if hasattr(klasse, "ports_fuer"):
        return klasse.ports_fuer(parameter)
    return klasse.PORTS


def erzeuge_ports(klasse, parameter, karte_id, ab_id):
    """Legt die Ports einer frisch angelegten Karte an."""
    ports = []
    laufend = ab_id
    for deklariert in _deklarierte_ports(klasse, parameter):
        schluessel = (
            f"{deklariert.schluessel}_1" if deklariert.dynamisch
            else deklariert.schluessel
        )
        ports.append(
            PortInstanz(
                id=laufend,
                karte_id=karte_id,
                schluessel=schluessel,
                basis=deklariert.schluessel,
                art=deklariert.art,
                richtung=deklariert.richtung,
                rolle=deklariert.rolle,
                nummer=1,
            )
        )
        laufend += 1
    return ports


def _ist_dynamisch(karte, port):
    for deklariert in _deklarierte_ports(basis.hole(karte.typ), karte.parameter):
        if deklariert.schluessel == port.basis:
            return deklariert.dynamisch
    return False


def fehlende_ports(karte, belegt):
    """Laesst dynamische Ports nachwachsen, deren letzter frei gewordener belegt ist."""
    neue = []
    naechste_id = max((p.id for p in karte.ports), default=0) + 1

    gruppen = {}
    for p in karte.ports:
        if _ist_dynamisch(karte, p):
            gruppen.setdefault((p.basis, p.richtung), []).append(p)

    for (basis_name, richtung), ports in gruppen.items():
        if any(p.id not in belegt for p in ports):
            continue
        vorbild = ports[-1]
        nummer = max(p.nummer for p in ports) + 1
        neue.append(
            PortInstanz(
                id=naechste_id,
                karte_id=karte.id,
                schluessel=f"{basis_name}_{nummer}",
                basis=basis_name,
                art=vorbild.art,
                richtung=richtung,
                rolle=vorbild.rolle,
                nummer=nummer,
            )
        )
        naechste_id += 1
    return neue


# Luftwege, die niemals zusammengehoeren. Ohne diese Sperre wuerde ein Pfeil von
# der Waermerueckgewinnung zur Fortluft den Zuluftstrang erwischen.
VERBOTEN = {
    (basis.ZULUFT, basis.ABLUFT),
    (basis.ZULUFT, basis.FORTLUFT),
    (basis.ABLUFT, basis.ZULUFT),
    (basis.ABLUFT, basis.AUSSENLUFT),
    (basis.AUSSENLUFT, basis.ABLUFT),
    (basis.AUSSENLUFT, basis.FORTLUFT),
}

# Luftwege, die sinnvoll aufeinander folgen, ohne dieselbe Rolle zu tragen.
FOLGT_AUF = {
    (basis.AUSSENLUFT, basis.ZULUFT),
    (basis.ABLUFT, basis.FORTLUFT),
    (basis.ABLUFT, basis.UMLUFT),
    (basis.ZULUFT, basis.UMLUFT),
}


def _luftpunkte(von, nach):
    if basis.LUFTWEG in (von.rolle, nach.rolle):
        return 2          # Verteiler und Sammler passen in jeden Strang
    if (von.rolle, nach.rolle) in VERBOTEN:
        return 0
    if von.rolle == nach.rolle or (von.rolle, nach.rolle) in FOLGT_AUF:
        return 2
    return 1


def _punkte(von, nach):
    """Wie gut passen zwei Ports zueinander? Hoeher ist besser, 0 heisst gar nicht."""
    if von.art != nach.art:
        return 0
    if von.richtung != basis.AUSGANG or nach.richtung != basis.EINGANG:
        return 0
    if von.art == basis.LUFT:
        punkte = _luftpunkte(von, nach)
        return 3 if (punkte and von.basis == nach.basis) else punkte
    if von.basis == nach.basis:
        return 3
    if von.rolle == nach.rolle:
        return 2
    if von.rolle == basis.MESSWERT and nach.rolle == basis.ISTWERT:
        return 2
    return 0


def _paare(von_karte, nach_karte, belegt):
    kandidaten = []
    for v in von_karte.ports:
        if v.id in belegt or v.richtung != basis.AUSGANG:
            continue
        for n in nach_karte.ports:
            if n.id in belegt or n.richtung != basis.EINGANG:
                continue
            punkte = _punkte(v, n)
            if punkte:
                kandidaten.append((punkte, v, n))

    # Nach Punkten, dann nach der Reihenfolge, in der die Ports angelegt wurden.
    # Ein Textvergleich waere falsch: 'wert_10' stuende vor 'wert_2'.
    kandidaten.sort(key=lambda k: (-k[0], k[1].id, k[2].id))

    gewaehlt = []
    vergeben = set()
    for _, v, n in kandidaten:
        if v.id in vergeben or n.id in vergeben:
            continue
        gewaehlt.append((v, n))
        vergeben.add(v.id)
        vergeben.add(n.id)
    return gewaehlt, vergeben


def verdrahte(von_karte, nach_karte, belegt):
    """Erzeugt alle Portverbindungen eines Pfeils von einer Karte zur anderen.

    Zusaetzlich wird die Rueckrichtung ergaenzt: schickt A eine Stellgroesse an B,
    so bekommt A den passenden Messwert von B als Istwert zurueck. Damit ist ein
    Regler mit einem einzigen Pfeil vollstaendig angeschlossen.
    """
    vorwaerts, vergeben = _paare(von_karte, nach_karte, belegt)

    schickt_stellgroesse = any(
        v.rolle == basis.STELLGROESSE for v, _ in vorwaerts
    )
    rueckwaerts = []
    if schickt_stellgroesse:
        rueckwaerts, _ = _paare(nach_karte, von_karte, belegt | vergeben)
        rueckwaerts = [
            (v, n) for v, n in rueckwaerts if n.rolle == basis.ISTWERT
        ]

    return vorwaerts + rueckwaerts


class Anlagengraph:
    """Die Karten einer Anlage samt ihrer Verbindungen."""

    def __init__(self, karten, verbindungen):
        self.karten = karten
        self.verbindungen = verbindungen
        self._rueckkanten = set()
        self._reihenfolge = None

    def kanten(self):
        return [
            (v.von_port.karte_id, v.nach_port.karte_id)
            for v in self.verbindungen
            if v.von_port.karte_id != v.nach_port.karte_id
        ]

    def eingaenge_von(self, karte_id):
        """Alle Verbindungen, die auf diese Karte zeigen."""
        return [v for v in self.verbindungen if v.nach_port.karte_id == karte_id]

    def reihenfolge(self):
        """Topologische Reihenfolge; Zyklen werden an Rueckkanten aufgebrochen.

        Es wird eine Tiefensuche verwendet, damit die Rueckkanten eindeutig
        bestimmt sind. Der Solver iteriert ueber diese Reihenfolge, bis sich
        nichts mehr aendert - die aufgebrochenen Kanten schliessen sich dadurch.
        """
        if self._reihenfolge is not None:
            return self._reihenfolge

        nachfolger = {kid: [] for kid in self.karten}
        for von, nach in self.kanten():
            if nach not in nachfolger[von]:
                nachfolger[von].append(nach)

        WEISS, GRAU, SCHWARZ = 0, 1, 2
        farbe = {kid: WEISS for kid in self.karten}
        ergebnis = []
        rueckkanten = set()

        def besuche(kid):
            farbe[kid] = GRAU
            for folge in sorted(nachfolger[kid]):
                if farbe[folge] == GRAU:
                    rueckkanten.add((kid, folge))
                elif farbe[folge] == WEISS:
                    besuche(folge)
            farbe[kid] = SCHWARZ
            ergebnis.append(kid)

        for kid in sorted(self.karten):
            if farbe[kid] == WEISS:
                besuche(kid)

        self._rueckkanten = rueckkanten
        self._reihenfolge = list(reversed(ergebnis))
        return self._reihenfolge

    def rueckkanten(self):
        self.reihenfolge()
        return self._rueckkanten
```

**Hinweis zur Rekursionstiefe:** Die Tiefensuche ist rekursiv. Bei sehr großen
Anlagen mit mehr als tausend Karten müsste sie auf eine Schleife umgestellt werden;
für die vorgesehene Größenordnung von einigen Dutzend Karten ist die Rekursion
unproblematisch und deutlich besser lesbar.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph.py -v`
Expected: 22 passed

- [ ] **Step 5: Commit**

```bash
git add core/graph.py tests/test_graph.py
git commit -m "Graph mit Portanlage, automatischer Verdrahtung und Sortierung"
```

---

## Task 15: Solver

**Files:**
- Create: `core/solver.py`
- Test: `tests/test_solver.py`

**Interfaces:**
- Produces:
  - `solver.Ergebnis(werte, warnungen, iterationen)` je Stunde
  - `solver.Solver(graph)` mit
    `starte(wetterstunden, fortschritt=None, abbruch=None) -> Lauf`
  - `solver.Lauf(stunden, bilanz, warnungen)` — `stunden` ist eine Liste von
    Wörterbüchern `{karte_id: {ausgabename: wert}}`

- [ ] **Step 1: Write the failing test**

`tests/test_solver.py`:

```python
from datetime import datetime, timedelta

import pytest

from core import graph, solver
from core.bausteine import basis, lade_alle

lade_alle()


def karte(karte_id, typ, parameter=None):
    klasse = basis.hole(typ)
    p = klasse.vorgabeparameter()
    p.update(parameter or {})
    ports = graph.erzeuge_ports(klasse, p, karte_id, ab_id=karte_id * 100)
    return graph.KarteInstanz(
        id=karte_id, typ=typ, name=klasse.NAME, parameter=p,
        baustein=klasse(), ports=ports,
    )


def verbinde(karten, kanten):
    verbindungen = []
    for von_id, von_port, nach_id, nach_port in kanten:
        verbindungen.append(
            graph.VerbindungInstanz(
                von_port=karten[von_id].port(von_port),
                nach_port=karten[nach_id].port(nach_port),
            )
        )
    return graph.Anlagengraph(karten=karten, verbindungen=verbindungen)


def wetterstunden(anzahl, t_au=0.0, x_au=0.0):
    start = datetime(2024, 1, 1, 0)
    return [
        {
            "zeitpunkt": start + timedelta(hours=i),
            "t_au": t_au, "x_au": x_au,
            "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
        }
        for i in range(anzahl)
    ]


def einfache_anlage():
    """Wetter -> Aussenluft -> Erhitzer -> Ventilator -> Fortluft."""
    karten = {
        1: karte(1, "wetter"),
        2: karte(2, "aussenluft"),
        3: karte(3, "erhitzer", {"V_nenn": 8200.0, "QH_max": 100.0, "dp_nenn": 100.0}),
        4: karte(4, "ventilator", {"V_max": 8200.0, "PE_max": 4.9, "regelart": "F"}),
        5: karte(5, "fortluft"),
    }
    return karten, verbinde(
        karten,
        [
            (1, "T_AU", 2, "T_AU"),
            (1, "F_AU", 2, "F_AU"),
            (2, "luft_aus", 3, "luft_ein"),
            (3, "luft_aus", 4, "luft_ein"),
            (4, "luft_aus", 5, "luft_ein"),
        ],
    )


def test_volumenstrom_wird_vom_ventilator_rueckwaerts_gesetzt():
    karten, g = einfache_anlage()
    lauf = solver.Solver(g).starte(wetterstunden(1, t_au=5.0))
    assert lauf.stunden[0][3]["V_ein"] == pytest.approx(8200.0)


def test_wetterwerte_erreichen_die_aussenluft():
    karten, g = einfache_anlage()
    lauf = solver.Solver(g).starte(wetterstunden(1, t_au=5.0, x_au=3.0))
    assert lauf.stunden[0][2]["T_AU"] == pytest.approx(5.0)
    assert lauf.stunden[0][2]["F_AU"] == pytest.approx(3.0)


def test_ohne_stellgroesse_heizt_der_erhitzer_nicht():
    karten, g = einfache_anlage()
    lauf = solver.Solver(g).starte(wetterstunden(1, t_au=5.0))
    assert lauf.stunden[0][3]["QH"] == pytest.approx(0.0)


def test_geschlossener_regelkreis_konvergiert():
    """Regler haelt die Temperatur nach dem Erhitzer auf dem Sollwert."""
    karten = {
        1: karte(1, "wetter"),
        2: karte(2, "aussenluft"),
        3: karte(3, "erhitzer", {"V_nenn": 8200.0, "QH_max": 200.0, "dp_nenn": 0.0}),
        4: karte(4, "ventilator", {"V_max": 8200.0, "PE_max": 0.001, "regelart": "-"}),
        5: karte(5, "fortluft"),
        6: karte(6, "p_regler",
                 {"xp_1": 10.0, "xp_2": 5.0, "sollwert_2": 20.0}),
    }
    g = verbinde(
        karten,
        [
            (1, "T_AU", 2, "T_AU"),
            (1, "F_AU", 2, "F_AU"),
            (2, "luft_aus", 3, "luft_ein"),
            (3, "luft_aus", 4, "luft_ein"),
            (4, "luft_aus", 5, "luft_ein"),
            (6, "ausgang_2", 3, "stellgroesse"),
            (3, "QH", 6, "istwert_2"),
        ],
    )
    lauf = solver.Solver(g).starte(wetterstunden(1, t_au=0.0))
    assert lauf.warnungen == []
    # Der Regler faehrt auf, weil der Istwert (QH) unter dem Sollwert liegt.
    assert lauf.stunden[0][3]["QH"] > 0.0


def test_regler_erreicht_den_sollwert_innerhalb_einer_stunde():
    """Der Regler integriert ueber die Iterationen - wie Application.Iteration."""
    karten = {
        1: karte(1, "wetter"),
        2: karte(2, "aussenluft"),
        3: karte(3, "erhitzer", {"V_nenn": 8200.0, "QH_max": 200.0, "dp_nenn": 0.0}),
        4: karte(4, "ventilator", {"V_max": 8200.0, "PE_max": 0.001, "regelart": "-"}),
        5: karte(5, "fortluft"),
        6: karte(6, "p_regler",
                 {"xp_1": 10.0, "xp_2": 5.0, "sollwert_2": 18.0}),
    }
    g = verbinde(
        karten,
        [
            (1, "T_AU", 2, "T_AU"),
            (1, "F_AU", 2, "F_AU"),
            (2, "luft_aus", 3, "luft_ein"),
            (3, "luft_aus", 4, "luft_ein"),
            (4, "luft_aus", 5, "luft_ein"),
            (6, "ausgang_2", 3, "stellgroesse"),
            (3, "T_aus", 6, "istwert_2"),
        ],
    )
    lauf = solver.Solver(g).starte(wetterstunden(1, t_au=0.0))
    assert lauf.warnungen == []
    # Ohne Integration ueber die Iterationen bliebe die Temperatur bei 0 °C
    assert lauf.stunden[0][3]["T_aus"] == pytest.approx(18.0, abs=0.05)


def test_speichergroessen_sehen_in_jeder_iteration_den_stundenanfang():
    """Raum- und Wandtemperatur duerfen innerhalb einer Stunde nicht mitlaufen."""
    karten = {1: karte(1, "raum", {"start_temperatur": 20.0, "spez_beleuchtung": 0.0})}
    g = graph.Anlagengraph(karten=karten, verbindungen=[])
    lauf = solver.Solver(g).starte(wetterstunden(1, t_au=0.0))
    einmal = lauf.stunden[0][1]["T_Raum"]

    # Dieselbe Stunde einzeln gerechnet muss denselben Wert liefern
    from core.bausteine import basis as b
    raum = b.hole("raum")()
    p = karten[1].parameter
    ein = {k: 0.0 for k in ("T_AU", "F_AU", "QH_S", "QH_O", "QH_W", "QH_N",
                            "QH_H", "waermelast", "feuchtelast", "QH_stat")}
    aus, _ = raum.berechne(ein, p, raum.anfangszustand(p))
    assert einmal == pytest.approx(aus["T_Raum"], rel=1e-9)


def test_zustandsgroessen_werden_zur_naechsten_stunde_fortgeschrieben():
    karten = {1: karte(1, "raum", {"start_temperatur": 20.0, "spez_beleuchtung": 0.0})}
    g = graph.Anlagengraph(karten=karten, verbindungen=[])
    lauf = solver.Solver(g).starte(wetterstunden(3, t_au=0.0))
    temperaturen = [s[1]["T_Raum"] for s in lauf.stunden]
    assert temperaturen[0] > temperaturen[1] > temperaturen[2]


def test_bilanz_summiert_ueber_alle_stunden():
    karten = {
        1: karte(1, "wetter"),
        2: karte(2, "warmwasser", {"speichervolumen": 1000.0, "verbrauch": 462.0,
                                   "sollwert": 50.0}),
        3: karte(3, "bilanz"),
    }
    g = verbinde(karten, [(2, "QH", 3, "waerme_1")])
    lauf = solver.Solver(g).starte(wetterstunden(10))
    assert lauf.bilanz["waerme"] == pytest.approx(10 * 3.2494672754946725, rel=1e-9)


def test_fortschritt_wird_gemeldet():
    karten, g = einfache_anlage()
    gemeldet = []
    solver.Solver(g).starte(
        wetterstunden(5), fortschritt=lambda i, n: gemeldet.append((i, n))
    )
    assert gemeldet[-1] == (5, 5)


def test_abbruch_beendet_den_lauf_vorzeitig():
    karten, g = einfache_anlage()
    lauf = solver.Solver(g).starte(
        wetterstunden(100), abbruch=lambda: True
    )
    assert len(lauf.stunden) < 100


def test_fehlende_konvergenz_wird_gemeldet_aber_bricht_nicht_ab():
    """Zwei Erhitzer, die sich gegenseitig aufschaukeln."""
    karten = {
        1: karte(1, "wetter"),
        2: karte(2, "aussenluft"),
        3: karte(3, "erhitzer", {"V_nenn": 1000.0, "QH_max": 1e6, "dp_nenn": 0.0}),
        4: karte(4, "ventilator", {"V_max": 1000.0, "PE_max": 0.001, "regelart": "-"}),
        5: karte(5, "fortluft"),
    }
    g = verbinde(
        karten,
        [
            (1, "T_AU", 2, "T_AU"),
            (2, "luft_aus", 3, "luft_ein"),
            (3, "luft_aus", 4, "luft_ein"),
            (4, "luft_aus", 5, "luft_ein"),
            (3, "QH", 3, "stellgroesse"),
        ],
    )
    lauf = solver.Solver(g).starte(wetterstunden(1))
    assert len(lauf.stunden) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_solver.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'core.solver'`

- [ ] **Step 3: Write the implementation**

`core/solver.py`:

```python
"""Der Rechenkern.

Je Stunde laufen zwei Durchgaenge:

1. Rueckwaertslauf - vom Ende des Luftwegs zu den Quellen. Jeder Baustein meldet
   ueber 'bedarf', welchen Volumenstrom er an seinen Eingaengen braucht; an
   Verzweigungen summieren sich die Forderungen. Das bildet nach, dass in der
   Excel der Volumenstrom vom Ventilator zur Quelle durchgereicht wird
   (S9 = V9) und sich an Sammelstellen addiert (M9 = S9 + S31).

2. Vorwaertslauf - die Zustaende laufen durch die Kette. Weil der Graph Zyklen
   enthaelt (Waermerueckgewinnung, Raumrueckfuehrung, jeder Regler), wird der
   Durchgang wiederholt, bis sich keine Groesse mehr um mehr als MAX_AENDERUNG
   aendert. Das entspricht Application.Iteration in der Excel.

Danach werden die Speichergroessen auf die naechste Stunde uebertragen - die
Entsprechung des VBA-Unterprogramms Speicher().
"""

from dataclasses import dataclass, field

from core import config
from core.bausteine import basis
from core.bausteine.basis import Luft

BILANZGROESSEN = ("strom_ht", "strom_nt", "waerme", "kaelte", "wasser")


@dataclass
class Lauf:
    stunden: list = field(default_factory=list)
    bilanz: dict = field(default_factory=dict)
    warnungen: list = field(default_factory=list)


class Solver:
    def __init__(self, anlagengraph):
        self.graph = anlagengraph
        self.reihenfolge = anlagengraph.reihenfolge()

    # -- Rueckwaertslauf --------------------------------------------------

    def _volumenstroeme(self):
        """Ermittelt je Lufteingang den geforderten Volumenstrom."""
        gefordert = {}  # port_id -> m³/h

        for karte_id in reversed(self.reihenfolge):
            karte = self.graph.karten[karte_id]
            aus_bedarf = {}
            for port in karte.ports:
                if port.art != basis.LUFT or port.richtung != basis.AUSGANG:
                    continue
                menge = 0.0
                for v in self.graph.verbindungen:
                    if v.von_port.id == port.id:
                        menge += gefordert.get(v.nach_port.id, 0.0)
                aus_bedarf[port.schluessel] = menge

            eigener = karte.baustein.bedarf(aus_bedarf, karte.parameter)
            for schluessel, menge in eigener.items():
                for port in karte.ports:
                    if port.schluessel == schluessel:
                        gefordert[port.id] = menge

            # Verteiler braucht die Aufteilung im Vorwaertslauf
            if hasattr(karte.baustein, "bedarf_je_abgang"):
                karte.baustein.abgaenge = [
                    p.schluessel for p in karte.ports
                    if p.art == basis.LUFT and p.richtung == basis.AUSGANG
                ]
                karte.baustein.bedarf_je_abgang = dict(aus_bedarf)

        return gefordert

    # -- Vorwaertslauf ----------------------------------------------------

    def _eingaenge(self, karte, ausgaben, gefordert):
        ein = {}
        for port in karte.ports:
            if port.richtung != basis.EINGANG:
                continue
            quellen = [
                v for v in self.graph.verbindungen if v.nach_port.id == port.id
            ]
            if not quellen:
                if port.art == basis.LUFT:
                    ein[port.schluessel] = Luft()
                continue
            v = quellen[0]
            wert = ausgaben.get(v.von_port.karte_id, {}).get(v.von_port.schluessel)
            if wert is None:
                wert = Luft() if port.art == basis.LUFT else 0.0
            ein[port.schluessel] = wert
        return ein

    def _abweichung(self, alt, neu):
        groesste = 0.0
        for karte_id, werte in neu.items():
            vorher = alt.get(karte_id, {})
            for name, wert in werte.items():
                if isinstance(wert, Luft):
                    vor = vorher.get(name)
                    if not isinstance(vor, Luft):
                        return float("inf")
                    groesste = max(
                        groesste,
                        abs(wert.T - vor.T), abs(wert.x - vor.x),
                        abs(wert.V - vor.V) / 1000.0,
                    )
                elif isinstance(wert, (int, float)):
                    vor = vorher.get(name)
                    if not isinstance(vor, (int, float)):
                        return float("inf")
                    groesste = max(groesste, abs(wert - vor))
        return groesste

    def _rechne_stunde(self, stunde, zustaende, gefordert):
        ausgaben = {}
        letzte_abweichung = float("inf")

        # Zwei Arten von Gedaechtnis, siehe Baustein.ZUSTAND_UEBER_ITERATION:
        # Speichergroessen sehen in jeder Iteration den Stundenanfang, Regler
        # sehen ihren eigenen Wert aus der vorigen Iteration.
        iterationszustaende = {
            karte_id: dict(werte) for karte_id, werte in zustaende.items()
        }

        for durchgang in range(config.MAX_ITERATIONEN):
            vorher = {k: dict(v) for k, v in ausgaben.items()}
            neue_zustaende = {}

            for karte_id in self.reihenfolge:
                karte = self.graph.karten[karte_id]
                ein = self._eingaenge(karte, ausgaben, gefordert)

                if karte.baustein.ZUSTAND_UEBER_ITERATION:
                    zustand = dict(iterationszustaende.get(karte_id, {}))
                else:
                    zustand = dict(zustaende.get(karte_id, {}))
                zustand["stunde"] = stunde
                for port in karte.ports:
                    if port.art == basis.LUFT and port.richtung == basis.EINGANG:
                        if not self.graph.eingaenge_von(karte_id):
                            zustand["bedarf"] = gefordert.get(port.id, 0.0)

                if karte.typ == "aussenluft":
                    ausgang = next(
                        p for p in karte.ports
                        if p.art == basis.LUFT and p.richtung == basis.AUSGANG
                    )
                    menge = 0.0
                    for v in self.graph.verbindungen:
                        if v.von_port.id == ausgang.id:
                            menge += gefordert.get(v.nach_port.id, 0.0)
                    zustand["bedarf"] = menge

                werte, zustand_neu = karte.baustein.berechne(
                    ein, karte.parameter, zustand
                )
                zustand_neu.pop("stunde", None)
                zustand_neu.pop("bedarf", None)
                ausgaben[karte_id] = werte
                neue_zustaende[karte_id] = zustand_neu
                iterationszustaende[karte_id] = zustand_neu

                # Eingangsgroessen mitschreiben, damit sie protokolliert werden koennen
                for schluessel, wert in ein.items():
                    if isinstance(wert, Luft):
                        werte.setdefault(f"V_{schluessel}", wert.V)
                        werte.setdefault(f"T_{schluessel}", wert.T)
                    elif isinstance(wert, (int, float)):
                        werte.setdefault(f"in_{schluessel}", wert)
                if "luft_ein" in ein and isinstance(ein["luft_ein"], Luft):
                    werte.setdefault("V_ein", ein["luft_ein"].V)

            letzte_abweichung = self._abweichung(vorher, ausgaben)
            if letzte_abweichung < config.MAX_AENDERUNG:
                return ausgaben, neue_zustaende, durchgang + 1, None

        return (
            ausgaben,
            neue_zustaende,
            config.MAX_ITERATIONEN,
            letzte_abweichung,
        )

    # -- Lauf -------------------------------------------------------------

    def starte(self, wetterstunden, fortschritt=None, abbruch=None):
        lauf = Lauf()
        lauf.bilanz = {name: 0.0 for name in BILANZGROESSEN}

        zustaende = {
            karte_id: karte.baustein.anfangszustand(karte.parameter)
            for karte_id, karte in self.graph.karten.items()
        }
        gefordert = self._volumenstroeme()

        gesamt = len(wetterstunden)
        for nummer, stunde in enumerate(wetterstunden, start=1):
            if abbruch is not None and abbruch():
                break

            ausgaben, zustaende, durchgaenge, abweichung = self._rechne_stunde(
                stunde, zustaende, gefordert
            )
            if abweichung is not None:
                lauf.warnungen.append(
                    {
                        "stunde": nummer,
                        "zeitpunkt": str(stunde.get("zeitpunkt", "")),
                        "abweichung": abweichung,
                        "text": (
                            f"Stunde {nummer} nicht konvergiert, "
                            f"groesste Aenderung {abweichung:.4f}"
                        ),
                    }
                )

            lauf.stunden.append(ausgaben)
            for werte in ausgaben.values():
                for name in BILANZGROESSEN:
                    if name in werte:
                        lauf.bilanz[name] += float(werte[name])

            if fortschritt is not None:
                fortschritt(nummer, gesamt)

        return lauf
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_solver.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add core/solver.py tests/test_solver.py
git commit -m "Solver mit Rueckwaertslauf, Fixpunkt-Iteration und Zustandsfortschreibung"
```

---

## Task 16: Anlagen speichern und laden

**Files:**
- Create: `core/anlagen.py`, `routes/anlagen.py`
- Modify: `app.py` (Blueprint registrieren)
- Test: `tests/test_anlagen.py`

**Interfaces:**
- Produces:
  - `anlagen.projekt_anlegen(name) -> int`
  - `anlagen.anlage_anlegen(projekt_id, name) -> int`
  - `anlagen.karte_anlegen(anlage_id, typ, pos_x, pos_y) -> int` (legt die Ports mit an)
  - `anlagen.karte_aendern(karte_id, pos_x=None, pos_y=None, parameter=None, name=None)`
  - `anlagen.karte_loeschen(karte_id)`
  - `anlagen.pfeil_anlegen(anlage_id, von_karte_id, nach_karte_id) -> dict`
    (verdrahtet automatisch, lässt dynamische Ports nachwachsen)
  - `anlagen.pfeil_loeschen(pfeil_id)`
  - `anlagen.lade_graph(anlage_id) -> graph.Anlagengraph`
  - `anlagen.als_json(anlage_id) -> dict` für die Oberfläche
- HTTP: `GET/POST /api/projekte`, `GET/POST /api/anlagen`,
  `GET /api/anlagen/<id>`, `POST/PATCH/DELETE /api/karten`,
  `POST/DELETE /api/pfeile`

- [ ] **Step 1: Write the failing test**

`tests/test_anlagen.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_anlagen.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'core.anlagen'`

- [ ] **Step 3: Write the implementation**

`core/anlagen.py`:

```python
"""Anlagen, Karten, Ports und Pfeile lesen und schreiben."""

import json

from core import graph
from core.bausteine import basis, lade_alle
from core.database import get_db

lade_alle()


# -- Projekte und Anlagen -------------------------------------------------

def projekt_anlegen(name, beschreibung=""):
    db = get_db()
    cur = db.execute(
        "INSERT INTO projekt (name, beschreibung) VALUES (?, ?)", (name, beschreibung)
    )
    db.commit()
    return cur.lastrowid


def anlage_anlegen(projekt_id, name, notiz=""):
    db = get_db()
    cur = db.execute(
        "INSERT INTO anlage (projekt_id, name, notiz) VALUES (?, ?, ?)",
        (projekt_id, name, notiz),
    )
    db.commit()
    return cur.lastrowid


# -- Karten ---------------------------------------------------------------

def karte_anlegen(anlage_id, typ, pos_x=0.0, pos_y=0.0, parameter=None, name=None):
    klasse = basis.hole(typ)
    werte = klasse.vorgabeparameter()
    werte.update(parameter or {})

    db = get_db()
    cur = db.execute(
        "INSERT INTO karte (anlage_id, typ, name, pos_x, pos_y, parameter) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (anlage_id, typ, name or klasse.NAME, pos_x, pos_y,
         json.dumps(werte, ensure_ascii=False)),
    )
    karte_id = cur.lastrowid

    for port in graph.erzeuge_ports(klasse, werte, karte_id, ab_id=0):
        db.execute(
            "INSERT INTO port (karte_id, schluessel, basis, art, richtung, rolle, nummer) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (karte_id, port.schluessel, port.basis, port.art, port.richtung,
             port.rolle, port.nummer),
        )
    db.commit()
    return karte_id


def karte_aendern(karte_id, pos_x=None, pos_y=None, parameter=None, name=None):
    db = get_db()
    zeile = db.execute("SELECT * FROM karte WHERE id = ?", (karte_id,)).fetchone()
    if zeile is None:
        raise KeyError(f"Karte {karte_id} gibt es nicht")

    werte = json.loads(zeile["parameter"])
    if parameter:
        werte.update(parameter)

    db.execute(
        "UPDATE karte SET pos_x = ?, pos_y = ?, parameter = ?, name = ? WHERE id = ?",
        (
            zeile["pos_x"] if pos_x is None else pos_x,
            zeile["pos_y"] if pos_y is None else pos_y,
            json.dumps(werte, ensure_ascii=False),
            zeile["name"] if name is None else name,
            karte_id,
        ),
    )
    db.commit()


def karte_loeschen(karte_id):
    db = get_db()
    db.execute("DELETE FROM karte WHERE id = ?", (karte_id,))
    db.commit()


# -- Pfeile ---------------------------------------------------------------

def _karte_instanz(zeile, ports):
    klasse = basis.hole(zeile["typ"])
    werte = json.loads(zeile["parameter"])
    return graph.KarteInstanz(
        id=zeile["id"],
        typ=zeile["typ"],
        name=zeile["name"],
        parameter=werte,
        baustein=klasse(),
        ports=[
            graph.PortInstanz(
                id=p["id"], karte_id=p["karte_id"], schluessel=p["schluessel"],
                basis=p["basis"], art=p["art"], richtung=p["richtung"],
                rolle=p["rolle"], nummer=p["nummer"],
            )
            for p in ports
        ],
    )


def _lade_karte(karte_id):
    db = get_db()
    zeile = db.execute("SELECT * FROM karte WHERE id = ?", (karte_id,)).fetchone()
    ports = db.execute(
        "SELECT * FROM port WHERE karte_id = ? ORDER BY id", (karte_id,)
    ).fetchall()
    return _karte_instanz(zeile, ports)


def _belegte_ports(anlage_id):
    db = get_db()
    zeilen = db.execute(
        "SELECT v.von_port_id AS a, v.nach_port_id AS b "
        "FROM verbindung v JOIN pfeil p ON p.id = v.pfeil_id WHERE p.anlage_id = ?",
        (anlage_id,),
    ).fetchall()
    belegt = set()
    for z in zeilen:
        belegt.add(z["a"])
        belegt.add(z["b"])
    return belegt


def pfeil_anlegen(anlage_id, von_karte_id, nach_karte_id):
    db = get_db()
    von = _lade_karte(von_karte_id)
    nach = _lade_karte(nach_karte_id)
    belegt = _belegte_ports(anlage_id)

    paare = graph.verdrahte(von, nach, belegt)
    if not paare:
        raise ValueError(
            f"Zwischen '{von.name}' und '{nach.name}' passt kein freier Anschluss "
            "zusammen"
        )

    cur = db.execute(
        "INSERT INTO pfeil (anlage_id, von_karte_id, nach_karte_id) VALUES (?, ?, ?)",
        (anlage_id, von_karte_id, nach_karte_id),
    )
    pfeil_id = cur.lastrowid

    verbindungen = []
    for v, n in paare:
        db.execute(
            "INSERT INTO verbindung (pfeil_id, von_port_id, nach_port_id) "
            "VALUES (?, ?, ?)",
            (pfeil_id, v.id, n.id),
        )
        verbindungen.append(
            {
                "von_karte_id": v.karte_id, "von_schluessel": v.schluessel,
                "nach_karte_id": n.karte_id, "nach_schluessel": n.schluessel,
            }
        )

    # dynamische Ports nachwachsen lassen
    neu_belegt = belegt | {v.id for v, _ in paare} | {n.id for _, n in paare}
    for karte in (von, nach):
        for port in graph.fehlende_ports(karte, neu_belegt):
            db.execute(
                "INSERT INTO port (karte_id, schluessel, basis, art, richtung, rolle, "
                "nummer) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (karte.id, port.schluessel, port.basis, port.art, port.richtung,
                 port.rolle, port.nummer),
            )

    db.commit()
    return {"id": pfeil_id, "verbindungen": verbindungen}


def pfeil_loeschen(pfeil_id):
    db = get_db()
    db.execute("DELETE FROM pfeil WHERE id = ?", (pfeil_id,))
    db.commit()


# -- Lesen ----------------------------------------------------------------

def lade_graph(anlage_id):
    db = get_db()
    karten = {}
    for zeile in db.execute(
        "SELECT * FROM karte WHERE anlage_id = ? ORDER BY id", (anlage_id,)
    ):
        ports = db.execute(
            "SELECT * FROM port WHERE karte_id = ? ORDER BY id", (zeile["id"],)
        ).fetchall()
        karten[zeile["id"]] = _karte_instanz(zeile, ports)

    nach_id = {p.id: p for k in karten.values() for p in k.ports}
    verbindungen = []
    for zeile in db.execute(
        "SELECT v.* FROM verbindung v JOIN pfeil p ON p.id = v.pfeil_id "
        "WHERE p.anlage_id = ?",
        (anlage_id,),
    ):
        von = nach_id.get(zeile["von_port_id"])
        nach = nach_id.get(zeile["nach_port_id"])
        if von and nach:
            verbindungen.append(graph.VerbindungInstanz(von_port=von, nach_port=nach))

    return graph.Anlagengraph(karten=karten, verbindungen=verbindungen)


def als_json(anlage_id):
    db = get_db()
    anlage = db.execute("SELECT * FROM anlage WHERE id = ?", (anlage_id,)).fetchone()
    g = lade_graph(anlage_id)

    karten = []
    for zeile in db.execute(
        "SELECT * FROM karte WHERE anlage_id = ? ORDER BY id", (anlage_id,)
    ):
        klasse = basis.hole(zeile["typ"])
        karte = g.karten[zeile["id"]]
        karten.append(
            {
                "id": zeile["id"],
                "typ": zeile["typ"],
                "name": zeile["name"],
                "symbol": klasse.SYMBOL,
                "gruppe": klasse.GRUPPE,
                "pos_x": zeile["pos_x"],
                "pos_y": zeile["pos_y"],
                "parameter": karte.parameter,
                "felder": [
                    {
                        "schluessel": f.schluessel, "label": f.label,
                        "einheit": f.einheit, "auswahl": list(f.auswahl),
                    }
                    for f in klasse.PARAMETER
                ],
                "ports": [
                    {
                        "id": p.id, "schluessel": p.schluessel, "art": p.art,
                        "richtung": p.richtung, "rolle": p.rolle,
                    }
                    for p in karte.ports
                ],
            }
        )

    pfeile = []
    for zeile in db.execute(
        "SELECT * FROM pfeil WHERE anlage_id = ? ORDER BY id", (anlage_id,)
    ):
        verbindungen = db.execute(
            "SELECT * FROM verbindung WHERE pfeil_id = ?", (zeile["id"],)
        ).fetchall()
        pfeile.append(
            {
                "id": zeile["id"],
                "von_karte_id": zeile["von_karte_id"],
                "nach_karte_id": zeile["nach_karte_id"],
                "stuetzpunkte": json.loads(zeile["stuetzpunkte"]),
                "verbindungen": [
                    {"von_port_id": v["von_port_id"], "nach_port_id": v["nach_port_id"]}
                    for v in verbindungen
                ],
            }
        )

    return {
        "id": anlage_id,
        "name": anlage["name"] if anlage else "",
        "karten": karten,
        "pfeile": pfeile,
    }


def palette():
    """Die Kartentypen nach Gruppen, fuer die Symbolleiste."""
    gruppen = {}
    for klasse in basis.alle():
        gruppen.setdefault(klasse.GRUPPE, []).append(
            {"kennung": klasse.KENNUNG, "name": klasse.NAME, "symbol": klasse.SYMBOL}
        )
    for klassen in gruppen.values():
        klassen.sort(key=lambda k: k["name"])
    return gruppen
```

`routes/anlagen.py`:

```python
from flask import Blueprint, jsonify, request

from core import anlagen

bp = Blueprint("anlagen", __name__, url_prefix="/api")


@bp.get("/palette")
def palette():
    return jsonify(anlagen.palette())


@bp.post("/projekte")
def projekt_anlegen():
    daten = request.get_json(force=True)
    projekt_id = anlagen.projekt_anlegen(daten["name"], daten.get("beschreibung", ""))
    return jsonify({"id": projekt_id}), 201


@bp.post("/anlagen")
def anlage_anlegen():
    daten = request.get_json(force=True)
    anlage_id = anlagen.anlage_anlegen(daten["projekt_id"], daten["name"])
    return jsonify({"id": anlage_id}), 201


@bp.get("/anlagen/<int:anlage_id>")
def anlage_lesen(anlage_id):
    return jsonify(anlagen.als_json(anlage_id))


@bp.post("/karten")
def karte_anlegen():
    daten = request.get_json(force=True)
    karte_id = anlagen.karte_anlegen(
        daten["anlage_id"], daten["typ"],
        daten.get("pos_x", 0.0), daten.get("pos_y", 0.0),
    )
    karten = anlagen.als_json(daten["anlage_id"])["karten"]
    return jsonify(next(k for k in karten if k["id"] == karte_id)), 201


@bp.patch("/karten/<int:karte_id>")
def karte_aendern(karte_id):
    daten = request.get_json(force=True)
    anlagen.karte_aendern(
        karte_id,
        pos_x=daten.get("pos_x"), pos_y=daten.get("pos_y"),
        parameter=daten.get("parameter"), name=daten.get("name"),
    )
    return jsonify({"ok": True})


@bp.delete("/karten/<int:karte_id>")
def karte_loeschen(karte_id):
    anlagen.karte_loeschen(karte_id)
    return jsonify({"ok": True})


@bp.post("/pfeile")
def pfeil_anlegen():
    daten = request.get_json(force=True)
    try:
        pfeil = anlagen.pfeil_anlegen(
            daten["anlage_id"], daten["von_karte_id"], daten["nach_karte_id"]
        )
    except ValueError as fehler:
        return jsonify({"fehler": str(fehler)}), 400
    return jsonify(pfeil), 201


@bp.delete("/pfeile/<int:pfeil_id>")
def pfeil_loeschen(pfeil_id):
    anlagen.pfeil_loeschen(pfeil_id)
    return jsonify({"ok": True})
```

`app.py` — im `create_app` ergänzen:

```python
    from routes import anlagen as anlagen_routen, pages

    app.register_blueprint(pages.bp)
    app.register_blueprint(anlagen_routen.bp)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_anlagen.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add core/anlagen.py routes/anlagen.py app.py tests/test_anlagen.py
git commit -m "Anlagen, Karten und Pfeile speichern, laden und automatisch verdrahten"
```

---

## Task 17: Wetterdaten einlesen

**Files:**
- Create: `core/wetter/__init__.py`, `core/wetter/try_import.py`,
  `core/wetter/speicher.py`, `routes/wetter.py`
- Modify: `core/database.py` (Schema erweitern), `app.py`
- Test: `tests/test_wetter.py`

**Interfaces:**
- Produces:
  - `try_import.lese_datei(pfad) -> list[dict]` mit den Schlüsseln `zeitpunkt`,
    `t_au`, `x_au`, `str_s`, `str_o`, `str_w`, `str_n`, `str_h`
  - `try_import.excel_datum(zahl, jahr=None) -> datetime`
  - `speicher.datensatz_anlegen(name, quelle, stunden, **felder) -> int`
  - `speicher.lade_stunden(datensatz_id, von=None, bis=None) -> list[dict]`
  - `speicher.datensaetze() -> list[dict]`
- HTTP: `GET /api/wetter`, `POST /api/wetter/upload`

- [ ] **Step 1: Write the failing test**

`tests/test_wetter.py`:

```python
from datetime import datetime
from pathlib import Path

import pytest

from app import create_app
from core import database
from core.wetter import speicher, try_import

REFERENZ = Path(__file__).parent.parent / "referenz" / "RLTSimulation_Vorlage_AX_SIM_2.1.xls"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def test_excel_datum_wird_umgerechnet():
    # 36526 ist der 1. Januar 2000 in der Excel-Zaehlung
    assert try_import.excel_datum(36526.0).date() == datetime(2000, 1, 1).date()


def test_excel_datum_mit_uhrzeit():
    zeitpunkt = try_import.excel_datum(36526.041666666664)
    assert zeitpunkt.hour == 1


def test_try_datei_wird_vollstaendig_gelesen():
    stunden = try_import.lese_datei(REFERENZ)
    assert len(stunden) == 8760
    assert stunden[0]["t_au"] == pytest.approx(2.5)
    assert stunden[0]["x_au"] == pytest.approx(4.4)
    assert stunden[0]["str_h"] == pytest.approx(0.0)


def test_mittags_im_sommer_scheint_die_sonne():
    stunden = try_import.lese_datei(REFERENZ)
    sommer = [
        s for s in stunden
        if s["zeitpunkt"].month == 7 and s["zeitpunkt"].hour == 12
    ]
    assert max(s["str_h"] for s in sommer) > 100.0


def test_datensatz_wird_gespeichert_und_gelesen(app):
    stunden = [
        {
            "zeitpunkt": datetime(2024, 1, 1, i), "t_au": float(i), "x_au": 4.0,
            "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
        }
        for i in range(24)
    ]
    with app.app_context():
        datensatz = speicher.datensatz_anlegen("Test 2024", "upload", stunden)
        zurueck = speicher.lade_stunden(datensatz)
    assert len(zurueck) == 24
    assert zurueck[5]["t_au"] == pytest.approx(5.0)
    assert zurueck[0]["zeitpunkt"].hour == 0


def test_ausschnitt_laesst_sich_laden(app):
    stunden = [
        {
            "zeitpunkt": datetime(2024, 1, 1, i % 24), "t_au": float(i), "x_au": 4.0,
            "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
        }
        for i in range(100)
    ]
    with app.app_context():
        datensatz = speicher.datensatz_anlegen("Test", "upload", stunden)
        ausschnitt = speicher.lade_stunden(datensatz, von=10, bis=20)
    assert len(ausschnitt) == 10
    assert ausschnitt[0]["t_au"] == pytest.approx(10.0)


def test_api_listet_die_datensaetze(app):
    with app.app_context():
        speicher.datensatz_anlegen(
            "TRY04", "upload",
            [
                {
                    "zeitpunkt": datetime(2024, 1, 1, 0), "t_au": 1.0, "x_au": 4.0,
                    "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
                }
            ],
        )
    antwort = app.test_client().get("/api/wetter")
    assert antwort.status_code == 200
    assert antwort.get_json()[0]["name"] == "TRY04"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wetter.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'core.wetter'`

- [ ] **Step 3: Write the implementation**

`core/database.py` — an `SCHEMA` anhängen:

```python
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
```

`core/wetter/try_import.py`:

```python
"""Liest Wetterdaten im Format des Excel-Blattes 'Wetterdaten'.

Aufbau dort: Zeile 1 bis 4 Kopf, ab Zeile 5 je Stunde
Datum als Excel-Zahl, Temperatur in °C, absolute Feuchte in g/kg und
die Strahlung auf Sued, Ost, West, Nord und die Horizontale in W/m².
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path

SPALTEN = ("t_au", "x_au", "str_s", "str_o", "str_w", "str_n", "str_h")

# Excel zaehlt Tage ab dem 30.12.1899 (mit dem bekannten Schaltjahrfehler von 1900,
# der fuer Datumsangaben ab 1900 keine Rolle mehr spielt).
EXCEL_NULLPUNKT = datetime(1899, 12, 30)


def excel_datum(zahl, jahr=None):
    zeitpunkt = EXCEL_NULLPUNKT + timedelta(days=float(zahl))
    # Auf volle Stunden runden - die Excel speichert 0,0416666666 statt 1/24
    zeitpunkt += timedelta(seconds=30 * 60)
    zeitpunkt = zeitpunkt.replace(minute=0, second=0, microsecond=0)
    if jahr is not None:
        zeitpunkt = zeitpunkt.replace(year=jahr)
    return zeitpunkt


def _zeilen_aus_xls(pfad):
    import xlrd

    mappe = xlrd.open_workbook(str(pfad))
    blatt = (
        mappe.sheet_by_name("Wetterdaten")
        if "Wetterdaten" in mappe.sheet_names()
        else mappe.sheet_by_index(0)
    )
    for nummer in range(4, blatt.nrows):
        yield blatt.row_values(nummer)[:8]


def _zeilen_aus_xlsx(pfad):
    import openpyxl

    mappe = openpyxl.load_workbook(str(pfad), data_only=True)
    blatt = mappe["Wetterdaten"] if "Wetterdaten" in mappe.sheetnames else mappe.worksheets[0]
    for nummer, zeile in enumerate(blatt.iter_rows(values_only=True), start=1):
        if nummer <= 4:
            continue
        yield list(zeile)[:8]


def _zeilen_aus_csv(pfad):
    with open(pfad, encoding="utf-8-sig", newline="") as datei:
        leser = csv.reader(datei, delimiter=";" if _semikolon(pfad) else ",")
        for nummer, zeile in enumerate(leser, start=1):
            if nummer <= 4:
                continue
            yield zeile[:8]


def _semikolon(pfad):
    with open(pfad, encoding="utf-8-sig") as datei:
        kopf = datei.readline()
    return kopf.count(";") > kopf.count(",")


def lese_datei(pfad, jahr=None):
    pfad = Path(pfad)
    endung = pfad.suffix.lower()
    if endung == ".xls":
        zeilen = _zeilen_aus_xls(pfad)
    elif endung in (".xlsx", ".xlsm"):
        zeilen = _zeilen_aus_xlsx(pfad)
    elif endung == ".csv":
        zeilen = _zeilen_aus_csv(pfad)
    else:
        raise ValueError(f"Format '{endung}' wird nicht unterstuetzt")

    stunden = []
    for zeile in zeilen:
        if not zeile or zeile[0] in ("", None):
            continue
        try:
            zeitpunkt = excel_datum(zeile[0], jahr)
        except (TypeError, ValueError):
            continue
        werte = {"zeitpunkt": zeitpunkt}
        for index, name in enumerate(SPALTEN, start=1):
            wert = zeile[index] if index < len(zeile) else 0.0
            werte[name] = float(wert) if wert not in ("", None) else 0.0
        stunden.append(werte)
    return stunden
```

`core/wetter/speicher.py`:

```python
"""Wetterdatensaetze in der Datenbank."""

from datetime import datetime

from core.database import get_db

SPALTEN = ("t_au", "x_au", "str_s", "str_o", "str_w", "str_n", "str_h")


def datensatz_anlegen(name, quelle, stunden, ort="", breite=None, laenge=None,
                      jahr=None, notiz=""):
    db = get_db()
    if jahr is None and stunden:
        jahr = stunden[0]["zeitpunkt"].year

    cur = db.execute(
        "INSERT INTO wetterdatensatz (name, quelle, ort, breite, laenge, jahr, notiz) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, quelle, ort, breite, laenge, jahr, notiz),
    )
    datensatz_id = cur.lastrowid

    db.executemany(
        "INSERT INTO wetterstunde "
        "(datensatz_id, stunde, zeitpunkt, t_au, x_au, str_s, str_o, str_w, str_n, str_h) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (datensatz_id, nummer, s["zeitpunkt"].isoformat())
            + tuple(float(s.get(name, 0.0)) for name in SPALTEN)
            for nummer, s in enumerate(stunden)
        ],
    )
    db.commit()
    return datensatz_id


def lade_stunden(datensatz_id, von=None, bis=None):
    db = get_db()
    abfrage = "SELECT * FROM wetterstunde WHERE datensatz_id = ?"
    werte = [datensatz_id]
    if von is not None:
        abfrage += " AND stunde >= ?"
        werte.append(von)
    if bis is not None:
        abfrage += " AND stunde < ?"
        werte.append(bis)
    abfrage += " ORDER BY stunde"

    ergebnis = []
    for zeile in db.execute(abfrage, werte):
        eintrag = {"zeitpunkt": datetime.fromisoformat(zeile["zeitpunkt"])}
        for name in SPALTEN:
            eintrag[name] = zeile[name]
        ergebnis.append(eintrag)
    return ergebnis


def datensaetze():
    db = get_db()
    return [
        {
            "id": z["id"], "name": z["name"], "quelle": z["quelle"], "ort": z["ort"],
            "jahr": z["jahr"], "stunden": z["stunden"],
        }
        for z in db.execute(
            "SELECT w.*, (SELECT COUNT(*) FROM wetterstunde s "
            "             WHERE s.datensatz_id = w.id) AS stunden "
            "FROM wetterdatensatz w ORDER BY w.id DESC"
        )
    ]
```

`routes/wetter.py`:

```python
import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

from core.wetter import speicher, try_import

bp = Blueprint("wetter", __name__, url_prefix="/api/wetter")


@bp.get("")
def liste():
    return jsonify(speicher.datensaetze())


@bp.post("/upload")
def hochladen():
    datei = request.files.get("datei")
    if datei is None or not datei.filename:
        return jsonify({"fehler": "Keine Datei übermittelt"}), 400

    name = request.form.get("name") or Path(datei.filename).stem
    endung = Path(datei.filename).suffix.lower()

    with tempfile.NamedTemporaryFile(suffix=endung, delete=False) as ziel:
        datei.save(ziel.name)
        pfad = ziel.name

    try:
        stunden = try_import.lese_datei(pfad)
    except ValueError as fehler:
        return jsonify({"fehler": str(fehler)}), 400
    finally:
        Path(pfad).unlink(missing_ok=True)

    if not stunden:
        return jsonify({"fehler": "Die Datei enthält keine Stundenwerte"}), 400

    datensatz_id = speicher.datensatz_anlegen(name, "upload", stunden)
    return jsonify({"id": datensatz_id, "stunden": len(stunden)}), 201
```

`core/wetter/__init__.py`: leer.
`app.py` — Blueprint `wetter.bp` registrieren.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_wetter.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add core/wetter routes/wetter.py core/database.py app.py tests/test_wetter.py
git commit -m "Wetterdaten im TRY-Format einlesen und speichern"
```

---

## Task 18: Vorlage „AX_SIM 2.1"

Baut die Anlage aus der Excel-Mappe als mitgelieferte Vorlage nach: zwei
Lüftungsgeräte an einer gemeinsamen Wärmerückgewinnung, ein Raum, die Regler und
Zeitpläne. Sie ist zugleich das Prüfobjekt für Task 20.

**Files:**
- Create: `core/vorlagen/__init__.py`, `core/vorlagen/ax_sim_2_1.py`
- Modify: `routes/anlagen.py` (Endpunkt zum Anlegen aus einer Vorlage)
- Test: `tests/test_vorlage.py`

**Interfaces:**
- Produces: `ax_sim_2_1.BESCHREIBUNG`, `ax_sim_2_1.baue(projekt_id, name) -> int`
  (gibt die Anlagen-ID zurück), `vorlagen.alle() -> dict[str, modul]`
- HTTP: `POST /api/anlagen/aus_vorlage` mit `{"projekt_id": …, "vorlage": "ax_sim_2_1"}`

- [ ] **Step 1: Write the failing test**

`tests/test_vorlage.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vorlage.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'core.vorlagen'`

- [ ] **Step 3: Write the implementation**

`core/vorlagen/ax_sim_2_1.py`:

```python
"""Die Anlage aus RLTSimulation_Vorlage_AX_SIM_2.1 als Vorlage.

Aufbau (Anlage!I2:AC43):

    Wetter -> Aussenluft -> Waermerueckgewinnung -> Vorerhitzer -> Verteiler
        Gang 1 "Halle":  Kuehler -> Erhitzer -> Zuluftventilator -> Luftwaescher
        Gang 2 "Umkl.":  Kuehler -> Erhitzer -> Zuluftventilator -> Luftwaescher
    beide Gaenge -> Raum -> Sammler -> Abluftventilator -> Waermerueckgewinnung
                                                        -> Fortluft

Alle Nennwerte sind aus dem Blatt 'Anlage' uebernommen; die Zellbezuege stehen
jeweils als Kommentar daneben.
"""

from core import anlagen

BESCHREIBUNG = "Zwei Lüftungsgeräte an gemeinsamer WRG, ein Raum (aus der Excel)"


def baue(projekt_id, name="AX_SIM 2.1"):
    anlage = anlagen.anlage_anlegen(
        projekt_id, name, notiz="Nachbau der Excel-Mappe AX_SIM 2.1"
    )

    def karte(typ, x, y, bezeichnung, **parameter):
        karte_id = anlagen.karte_anlegen(anlage, typ, x, y, parameter, bezeichnung)
        return karte_id

    # -- Quellen ------------------------------------------------------
    wetter = karte("wetter", 40, 40, "Wetterdaten")
    aussenluft = karte("aussenluft", 40, 200, "Außenluft")

    # -- Gemeinsame Vorbehandlung, Anlage!I9:N21 ----------------------
    wrg = karte(
        "wrg", 240, 200, "Wärmerückgewinnung",
        V_nenn=12200.0,        # Anlage!J9
        dp_WRG_nenn=170.0,     # Anlage!J10
        dp_Bypass_nenn=50.0,   # Anlage!J11
        rueckwaermzahl=81.0,   # Anlage!J12
        rueckfeuchtzahl=0.0,   # Anlage!J13
    )
    vorerhitzer = karte(
        "erhitzer", 440, 200, "Vorerhitzer",
        V_nenn=12200.0, dp_nenn=30.0, QH_max=27.0,   # Anlage!M9, M10, M11
    )
    verteiler = karte("verteiler", 620, 200, "Verteiler")

    # -- Gang 1 "Halle", Anlage!R9:AC21 -------------------------------
    kuehler_1 = karte(
        "kuehler", 780, 120, "Kühler Halle",
        V_nenn=8200.0, dp_nenn=240.0, QK_nenn=63.0, T_KW_mittel=6.0,
    )
    erhitzer_1 = karte(
        "erhitzer", 960, 120, "Erhitzer Halle",
        V_nenn=8200.0, dp_nenn=147.0, QH_max=101.0,
    )
    zuluft_1 = karte(
        "ventilator", 1140, 120, "Zuluftventilator Halle",
        rolle="zuluft", V_max=8200.0, dp_max=1400.0, dp_konst=1400.0,
        PE_max=4.9, regelart="F", stellgroesse=100.0,   # Anlage!Y16
    )
    waescher_1 = karte(
        "luftwaescher", 1320, 120, "Luftwäscher Halle",
        V_nenn=8200.0, dp_nenn=50.0, absalzverlust=10.0, pumpenart="H",
    )

    # -- Gang 2 "Umkleide", Anlage!R31:AC43 ---------------------------
    kuehler_2 = karte(
        "kuehler", 780, 320, "Kühler Umkleide",
        V_nenn=4000.0, dp_nenn=150.0, QK_nenn=250.0, T_KW_mittel=9.0,
    )
    erhitzer_2 = karte(
        "erhitzer", 960, 320, "Erhitzer Umkleide",
        V_nenn=4000.0, dp_nenn=62.0, QH_max=47.0,
    )
    zuluft_2 = karte(
        "ventilator", 1140, 320, "Zuluftventilator Umkleide",
        rolle="zuluft", V_max=4000.0, dp_max=1190.0, dp_konst=4000.0,
        PE_max=1.7, regelart="F", stellgroesse=100.0,   # Anlage!Y38
    )
    waescher_2 = karte(
        "luftwaescher", 1320, 320, "Luftwäscher Umkleide",
        V_nenn=4000.0, dp_nenn=50.0, absalzverlust=10.0, pumpenart="H",
    )

    # -- Raum und Abluft, Anlage!AG31:AI50 und L31:N43 ----------------
    raum = karte(
        "einfacher_raum", 1520, 220, "Einfacher Raum",
        spez_transmission=0.5,   # Anlage!AH31
        sollwert_stat=15.0,      # Anlage!AH44
    )
    sammler = karte("sammler", 1520, 420, "Sammler Abluft")
    abluft = karte(
        "ventilator", 1320, 480, "Abluftventilator",
        rolle="abluft", V_max=10000.0, dp_max=750.0, dp_konst=600.0,
        PE_max=3.3, regelart="F", stellgroesse=90.0,    # Anlage!M38
    )
    fortluft = karte("fortluft", 40, 420, "Fortluft")

    # -- Regelung, Anlage!I52:W72 -------------------------------------
    regler_vor = karte(
        "p_regler", 440, 400, "Regler Vorerhitzer",
        xp_1=10.0, xp_2=5.0, sollwert_2=19.0,   # Anlage!N52, N54, M59
    )
    regler_erhitzer_1 = karte(
        "p_regler", 960, 20, "Regler Erhitzer Halle",
        xp_1=10.0, xp_2=5.0, sollwert_2=20.0,   # Anlage!W52, W54, V59
    )
    regler_kuehler_1 = karte(
        "p_regler", 780, 20, "Regler Kühler Halle",
        xp_1=10.0, xp_2=5.0, sollwert_2=15.0,   # Anlage!T52, T54, S70
    )
    regler_erhitzer_2 = karte(
        "p_regler", 960, 440, "Regler Erhitzer Umkleide",
        xp_1=10.0, xp_2=5.0, sollwert_2=20.0,
    )
    regler_kuehler_2 = karte(
        "p_regler", 780, 440, "Regler Kühler Umkleide",
        xp_1=10.0, xp_2=5.0, sollwert_2=15.0,
    )
    regler_waescher_1 = karte(
        "hysterese_regler", 1320, 20, "Regler Luftwäscher Halle",
        hysterese=0.1, sollwert=2.885138971629036,   # Anlage!AB54, AB55
    )
    regler_waescher_2 = karte(
        "hysterese_regler", 1320, 440, "Regler Luftwäscher Umkleide",
        hysterese=0.1, sollwert=2.885138971629036,
    )

    # -- Zeit und Betrieb, Anlage!AK4:AV32 ----------------------------
    zeitplan = karte("wochenzeitplan", 40, 560, "Wochenzeitplan")
    ferien = karte(
        "ferien", 240, 560, "Ferien",
        zeitraeume=[
            {"name": "Weihnachten", "von": "22.12.", "bis": "06.01."},
            {"name": "Ostern", "von": "22.03.", "bis": "06.04."},
            {"name": "Pfingsten", "von": "17.05.", "bis": "01.06."},
            {"name": "Sommer", "von": "24.07.", "bis": "07.09."},
            {"name": "Herbst", "von": "25.10.", "bis": "02.11."},
        ],
    )
    tagesprofil = karte(
        "tageslastprofil", 440, 560, "Tageslastprofil",
        lastgang_1=[0.4] * 7 + [1.0] * 13 + [0.4] * 4,   # Anlage!AT7:AT30
    )
    betrieb = karte("anlagenbetrieb", 640, 560, "Anlagenbetrieb")

    # -- Bilanz und Protokoll, Anlage!AO30:AR42 und B26:D46 -----------
    bilanz = karte(
        "bilanz", 1720, 560, "Energiepreise und Bilanz",
        preis_strom_ht=150.0, preis_strom_nt=150.0, preis_strom_leistung=0.0,
        preis_waerme=50.0, preis_kaelte=50.0, preis_wasser=4.0,
        ht_von=7.0 / 24.0, ht_bis=20.0 / 24.0,
    )
    logger = karte(
        "datenlogger", 1720, 220, "Datenlogger",
        namen=["WRG", "T Raum", "F Raum"] + [""] * 7,
        einheiten=["kW", "°C", "g/kg"] + [""] * 7,
    )

    # -- Verdrahtung --------------------------------------------------
    for von, nach in [
        (wetter, aussenluft),
        (aussenluft, wrg),
        (wrg, vorerhitzer),
        (vorerhitzer, verteiler),
        (verteiler, kuehler_1),
        (kuehler_1, erhitzer_1),
        (erhitzer_1, zuluft_1),
        (zuluft_1, waescher_1),
        (waescher_1, raum),
        (verteiler, kuehler_2),
        (kuehler_2, erhitzer_2),
        (erhitzer_2, zuluft_2),
        (zuluft_2, waescher_2),
        (waescher_2, raum),
        (raum, sammler),
        (sammler, abluft),
        (abluft, wrg),
        (wrg, fortluft),
        (wetter, raum),
        (regler_vor, vorerhitzer),
        (regler_kuehler_1, kuehler_1),
        (regler_erhitzer_1, erhitzer_1),
        (regler_kuehler_2, kuehler_2),
        (regler_erhitzer_2, erhitzer_2),
        (regler_waescher_1, waescher_1),
        (regler_waescher_2, waescher_2),
        (zeitplan, betrieb),
        (ferien, betrieb),
        (tagesprofil, betrieb),
        (zuluft_1, bilanz),
        (zuluft_2, bilanz),
        (abluft, bilanz),
        (waescher_1, bilanz),
        (waescher_2, bilanz),
        (vorerhitzer, bilanz),
        (erhitzer_1, bilanz),
        (erhitzer_2, bilanz),
        (kuehler_1, bilanz),
        (kuehler_2, bilanz),
        (wrg, logger),
        (raum, logger),
    ]:
        anlagen.pfeil_anlegen(anlage, von, nach)

    return anlage
```

`core/vorlagen/__init__.py`:

```python
"""Mitgelieferte Anlagenvorlagen."""

from core.vorlagen import ax_sim_2_1

VORLAGEN = {"ax_sim_2_1": ax_sim_2_1}


def alle():
    return {
        kennung: {"name": kennung, "beschreibung": modul.BESCHREIBUNG}
        for kennung, modul in VORLAGEN.items()
    }


def baue(kennung, projekt_id, name):
    if kennung not in VORLAGEN:
        raise KeyError(f"Die Vorlage '{kennung}' gibt es nicht")
    return VORLAGEN[kennung].baue(projekt_id, name)
```

`routes/anlagen.py` — ergänzen:

```python
from core import vorlagen


@bp.get("/vorlagen")
def vorlagen_liste():
    return jsonify(vorlagen.alle())


@bp.post("/anlagen/aus_vorlage")
def anlage_aus_vorlage():
    daten = request.get_json(force=True)
    try:
        anlage_id = vorlagen.baue(
            daten["vorlage"], daten["projekt_id"], daten.get("name", "Neue Anlage")
        )
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 400
    return jsonify({"id": anlage_id}), 201
```

**Warum der Anlagenbetrieb nicht auf die Ventilatoren verdrahtet ist.** In der Excel
sind die Stellgrößen der drei Ventilatoren feste Zellen — 100 %, 100 % und 90 % —, der
Zeitplanblock steht daneben, greift aber nicht auf sie durch. Der aufgezeichnete
Jahreslauf bestätigt das: er weist in jeder der 8760 Stunden dieselben 9,708 kW aus,
und 9,708 kW × 8760 h = 85,046 MWh sind genau die Stromsumme im Blatt `Ergebnis`.
Würde der Zeitplan die Ventilatoren stellen, läge die Jahressumme weit darunter und der
Abgleich in Task 20 könnte nicht aufgehen. Die Karte `Anlagenbetrieb` bleibt deshalb auf
der Leinwand — sie gehört zur Anlage und ist für eigene Rechnungen da —, wird aber nicht
mit den Ventilatoren verbunden.

**Wichtig bei der Umsetzung:** Falls ein Pfeil in der obigen Liste keinen passenden
Anschluss findet, wirft `pfeil_anlegen` einen `ValueError` mit den Namen beider
Karten. Das ist der Hinweis, dass die Rollen zweier Ports nicht zusammenpassen —
dann Task 14 nachbessern, nicht die Vorlage verbiegen.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vorlage.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add core/vorlagen routes/anlagen.py tests/test_vorlage.py
git commit -m "Vorlage AX_SIM 2.1 als Nachbau der Excel-Anlage"
```

---

## Task 19: Simulation ausführen und Ergebnisse speichern

**Files:**
- Create: `core/ergebnisse.py`, `core/laeufe.py`, `routes/simulation.py`
- Modify: `core/database.py`, `app.py`
- Test: `tests/test_ergebnisse.py`

**Interfaces:**
- Produces:
  - `ergebnisse.speichere(anlage_id, wetterdatensatz_id, von, bis, lauf, dauer) -> int`
  - `ergebnisse.lade_bilanz(simulation_id) -> list[dict]`
  - `ergebnisse.lade_zeitreihe(simulation_id, karte_id, groesse) -> list[float]`
  - `ergebnisse.reihen(simulation_id) -> list[dict]`
  - `laeufe.starte(anlage_id, wetterdatensatz_id, von, bis) -> str` (Auftragskennung,
    Lauf im Hintergrundfaden), `laeufe.stand(kennung) -> dict`,
    `laeufe.abbrechen(kennung)`
- HTTP: `POST /api/simulation`, `GET /api/simulation/<kennung>`,
  `POST /api/simulation/<kennung>/abbrechen`,
  `GET /api/simulation/<id>/bilanz`

- [ ] **Step 1: Write the failing test**

`tests/test_ergebnisse.py`:

```python
import time
from datetime import datetime

import pytest

from app import create_app
from core import anlagen, database, ergebnisse, laeufe, solver
from core.vorlagen import ax_sim_2_1
from core.wetter import speicher


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def wetter_anlegen(anzahl=24):
    return speicher.datensatz_anlegen(
        "Test", "upload",
        [
            {
                "zeitpunkt": datetime(2024, 1, 1, i % 24), "t_au": 0.0, "x_au": 4.0,
                "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
            }
            for i in range(anzahl)
        ],
    )


def test_zeitreihe_wird_verlustfrei_gespeichert(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(5)

        lauf = solver.Lauf(
            stunden=[{1: {"T_aus": float(i)}} for i in range(5)],
            bilanz={"strom_ht": 0.0, "strom_nt": 1.0, "waerme": 2.0,
                    "kaelte": 3.0, "wasser": 4.0},
            warnungen=[],
        )
        sim = ergebnisse.speichere(anlage, wetter, 0, 5, lauf, dauer=1.0)
        werte = ergebnisse.lade_zeitreihe(sim, 1, "T_aus")
    assert werte == [0.0, 1.0, 2.0, 3.0, 4.0]


def test_bilanz_wird_mit_preisen_gespeichert(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(5)
        lauf = solver.Lauf(
            stunden=[{}],
            bilanz={"strom_ht": 0.0, "strom_nt": 1000.0, "waerme": 2000.0,
                    "kaelte": 0.0, "wasser": 100.0},
            warnungen=[],
        )
        sim = ergebnisse.speichere(anlage, wetter, 0, 5, lauf, dauer=1.0)
        zeilen = {z["groesse"]: z for z in ergebnisse.lade_bilanz(sim)}

    assert zeilen["strom_nt"]["menge"] == pytest.approx(1.0)      # kWh -> MWh
    assert zeilen["strom_nt"]["kosten"] == pytest.approx(150.0)
    assert zeilen["waerme"]["menge"] == pytest.approx(2.0)
    assert zeilen["waerme"]["kosten"] == pytest.approx(100.0)
    assert zeilen["wasser"]["menge"] == pytest.approx(0.1)        # kg -> m³
    assert zeilen["wasser"]["kosten"] == pytest.approx(0.4)


def test_lauf_im_hintergrund_meldet_fortschritt_und_endet(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(24)
        kennung = laeufe.starte(app, anlage, wetter, 0, 24)

        for _ in range(200):
            stand = laeufe.stand(kennung)
            if stand["status"] in ("fertig", "fehler"):
                break
            time.sleep(0.05)

    assert stand["status"] == "fertig", stand.get("fehler")
    assert stand["fertig"] == 24
    assert stand["simulation_id"] > 0


def test_abbruch_beendet_den_lauf(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(2000)
        kennung = laeufe.starte(app, anlage, wetter, 0, 2000)
        laeufe.abbrechen(kennung)

        for _ in range(200):
            stand = laeufe.stand(kennung)
            if stand["status"] in ("fertig", "abgebrochen", "fehler"):
                break
            time.sleep(0.05)
    assert stand["status"] in ("abgebrochen", "fertig")


def test_api_startet_und_liefert_den_stand(app):
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(24)

    antwort = klient.post(
        "/api/simulation",
        json={"anlage_id": anlage, "wetterdatensatz_id": wetter, "von": 0, "bis": 24},
    )
    assert antwort.status_code == 202
    kennung = antwort.get_json()["kennung"]

    for _ in range(200):
        stand = klient.get(f"/api/simulation/{kennung}").get_json()
        if stand["status"] in ("fertig", "fehler"):
            break
        time.sleep(0.05)
    assert stand["status"] == "fertig", stand.get("fehler")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ergebnisse.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'core.ergebnisse'`

- [ ] **Step 3: Write the implementation**

`core/database.py` — an `SCHEMA` anhängen:

```python
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
```

`core/ergebnisse.py`:

```python
"""Ergebnisse einer Simulation speichern und lesen.

Zeitreihen liegen als Block von 32-Bit-Gleitkommazahlen, eine je Stunde. Ein
Jahr belegt damit rund 35 KB je Groesse; ein Diagramm laedt seine Reihe in einem
einzigen Zugriff, und die Datenbank waechst nicht auf Millionen Zeilen.
"""

import array
import json

from core.bausteine.basis import Luft
from core.database import get_db

# Preisschluessel der Bilanzkarte und die Umrechnung der Stundensummen
BILANZ = {
    "strom_ht": ("MWh", "preis_strom_ht", 1 / 1000.0),
    "strom_nt": ("MWh", "preis_strom_nt", 1 / 1000.0),
    "waerme": ("MWh", "preis_waerme", 1 / 1000.0),
    "kaelte": ("MWh", "preis_kaelte", 1 / 1000.0),
    "wasser": ("m³", "preis_wasser", 1 / 1000.0),
}


def _als_blob(werte):
    return array.array("f", werte).tobytes()


def _aus_blob(rohdaten):
    feld = array.array("f")
    feld.frombytes(rohdaten)
    return list(feld)


def _preise(anlage_id):
    """Die Preise der ersten Bilanzkarte dieser Anlage."""
    db = get_db()
    zeile = db.execute(
        "SELECT parameter FROM karte WHERE anlage_id = ? AND typ = 'bilanz' "
        "ORDER BY id LIMIT 1",
        (anlage_id,),
    ).fetchone()
    return json.loads(zeile["parameter"]) if zeile else {}


def speichere(anlage_id, wetterdatensatz_id, von, bis, lauf, dauer, status="fertig"):
    db = get_db()
    cur = db.execute(
        "INSERT INTO simulation (anlage_id, wetterdatensatz_id, von_stunde, "
        "bis_stunde, status, dauer_s, warnungen) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (anlage_id, wetterdatensatz_id, von, bis, status, dauer,
         json.dumps(lauf.warnungen, ensure_ascii=False)),
    )
    simulation_id = cur.lastrowid

    namen = {
        z["id"]: z["name"]
        for z in db.execute("SELECT id, name FROM karte WHERE anlage_id = ?", (anlage_id,))
    }

    # Alle vorkommenden Groessen einsammeln
    reihen = {}
    for nummer, stunde in enumerate(lauf.stunden):
        for karte_id, werte in stunde.items():
            for groesse, wert in werte.items():
                if isinstance(wert, Luft) or not isinstance(wert, (int, float)):
                    continue
                reihen.setdefault((karte_id, groesse), [0.0] * len(lauf.stunden))
                reihen[(karte_id, groesse)][nummer] = float(wert)

    db.executemany(
        "INSERT INTO zeitreihe (simulation_id, karte_id, karte_name, groesse, werte) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (simulation_id, karte_id, namen.get(karte_id, ""), groesse, _als_blob(werte))
            for (karte_id, groesse), werte in sorted(reihen.items())
        ],
    )

    preise = _preise(anlage_id)
    zeilen = []
    for groesse, (einheit, preisschluessel, faktor) in BILANZ.items():
        menge = lauf.bilanz.get(groesse, 0.0) * faktor
        preis = float(preise.get(preisschluessel, 0.0))
        zeilen.append((simulation_id, groesse, menge, einheit, preis, menge * preis))
    db.executemany(
        "INSERT INTO bilanz (simulation_id, groesse, menge, einheit, preis, kosten) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        zeilen,
    )

    db.commit()
    return simulation_id


def lade_bilanz(simulation_id):
    db = get_db()
    return [
        dict(z)
        for z in db.execute(
            "SELECT groesse, menge, einheit, preis, kosten FROM bilanz "
            "WHERE simulation_id = ? ORDER BY id",
            (simulation_id,),
        )
    ]


def lade_zeitreihe(simulation_id, karte_id, groesse):
    db = get_db()
    zeile = db.execute(
        "SELECT werte FROM zeitreihe WHERE simulation_id = ? AND karte_id = ? "
        "AND groesse = ?",
        (simulation_id, karte_id, groesse),
    ).fetchone()
    return _aus_blob(zeile["werte"]) if zeile else []


def reihen(simulation_id):
    db = get_db()
    return [
        {"karte_id": z["karte_id"], "karte_name": z["karte_name"],
         "groesse": z["groesse"], "einheit": z["einheit"]}
        for z in db.execute(
            "SELECT karte_id, karte_name, groesse, einheit FROM zeitreihe "
            "WHERE simulation_id = ? ORDER BY karte_name, groesse",
            (simulation_id,),
        )
    ]
```

`core/laeufe.py`:

```python
"""Simulationslaeufe im Hintergrund, mit Fortschritt und Abbruch."""

import threading
import time
import uuid

from core import anlagen, ergebnisse, solver
from core.wetter import speicher

_AUFTRAEGE = {}
_SPERRE = threading.Lock()


def _setze(kennung, **felder):
    with _SPERRE:
        _AUFTRAEGE.setdefault(kennung, {}).update(felder)


def stand(kennung):
    with _SPERRE:
        return dict(_AUFTRAEGE.get(kennung, {"status": "unbekannt"}))


def abbrechen(kennung):
    _setze(kennung, abbruch=True)


def _laufen(app, kennung, anlage_id, wetterdatensatz_id, von, bis):
    with app.app_context():
        begonnen = time.time()
        try:
            stunden = speicher.lade_stunden(wetterdatensatz_id, von, bis)
            graph = anlagen.lade_graph(anlage_id)

            def fortschritt(nummer, gesamt):
                _setze(kennung, fertig=nummer, gesamt=gesamt)

            def abbruch():
                return bool(stand(kennung).get("abbruch"))

            lauf = solver.Solver(graph).starte(
                stunden, fortschritt=fortschritt, abbruch=abbruch
            )
            abgebrochen = bool(stand(kennung).get("abbruch"))
            simulation_id = ergebnisse.speichere(
                anlage_id, wetterdatensatz_id, von, bis, lauf,
                dauer=time.time() - begonnen,
                status="abgebrochen" if abgebrochen else "fertig",
            )
            _setze(
                kennung,
                status="abgebrochen" if abgebrochen else "fertig",
                simulation_id=simulation_id,
                warnungen=len(lauf.warnungen),
                dauer=time.time() - begonnen,
            )
        except Exception as fehler:  # noqa: BLE001 - der Lauf darf die App nicht kippen
            _setze(kennung, status="fehler", fehler=str(fehler))


def starte(app, anlage_id, wetterdatensatz_id, von, bis):
    kennung = uuid.uuid4().hex
    _setze(
        kennung,
        status="laeuft", fertig=0, gesamt=max(bis - von, 0),
        abbruch=False, simulation_id=0,
    )
    faden = threading.Thread(
        target=_laufen,
        args=(app, kennung, anlage_id, wetterdatensatz_id, von, bis),
        daemon=True,
    )
    faden.start()
    return kennung
```

`routes/simulation.py`:

```python
from flask import Blueprint, current_app, jsonify, request

from core import ergebnisse, laeufe

bp = Blueprint("simulation", __name__, url_prefix="/api/simulation")


@bp.post("")
def starten():
    daten = request.get_json(force=True)
    kennung = laeufe.starte(
        current_app._get_current_object(),
        daten["anlage_id"],
        daten["wetterdatensatz_id"],
        int(daten.get("von", 0)),
        int(daten.get("bis", 8760)),
    )
    return jsonify({"kennung": kennung}), 202


@bp.get("/<kennung>")
def stand(kennung):
    return jsonify(laeufe.stand(kennung))


@bp.post("/<kennung>/abbrechen")
def abbrechen(kennung):
    laeufe.abbrechen(kennung)
    return jsonify({"ok": True})


@bp.get("/<int:simulation_id>/bilanz")
def bilanz(simulation_id):
    return jsonify(
        {
            "bilanz": ergebnisse.lade_bilanz(simulation_id),
            "reihen": ergebnisse.reihen(simulation_id),
        }
    )
```

**Hinweis:** Der Endpunkt `/api/simulation/<kennung>` und
`/api/simulation/<int:simulation_id>/bilanz` unterscheiden sich durch den Typ der
Wegmarke; Flask ordnet die Zahl zuerst zu. Die Auftragskennung ist ein
Hexadezimaltext und kollidiert daher nicht.

`app.py` — Blueprint `simulation.bp` registrieren.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ergebnisse.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add core/ergebnisse.py core/laeufe.py routes/simulation.py core/database.py app.py tests/test_ergebnisse.py
git commit -m "Simulationslauf im Hintergrund mit Ergebnis- und Bilanzspeicherung"
```

---

## Task 20: Abgleich gegen die Excel

Der eigentliche Nachweis, dass der Nachbau stimmt. Diese Aufgabe kann fehlschlagen —
das ist beabsichtigt und Teil der Arbeit. Sie enthält deshalb ein Werkzeug, das
zeigt, **wo** die Rechnung auseinanderläuft.

**Files:**
- Create: `werkzeuge/abgleich.py`
- Test: `tests/test_abgleich.py`

**Interfaces:**
- Consumes: `tests/daten/wetterdaten_try04.csv`, `tests/daten/ergebnis_jahreslauf.csv`,
  `tests/daten/jahresbilanz.json` aus Task 2; die Vorlage aus Task 18
- Produces: `abgleich.rechne_referenzjahr(app) -> dict` mit den Schlüsseln
  `bilanz`, `stunden`, `warnungen`; `abgleich.vergleiche(eigene, excel) -> list[dict]`

- [ ] **Step 1: Write the failing test**

`tests/test_abgleich.py`:

```python
import json
from pathlib import Path

import pytest

from app import create_app
from core import database
from werkzeuge import abgleich

DATEN = Path(__file__).parent / "daten"
TOLERANZ = 0.005  # 0,5 Prozent je Bilanzgroesse


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "rlt.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


@pytest.mark.slow
def test_jahresbilanz_stimmt_mit_der_excel_ueberein(app):
    excel = json.loads((DATEN / "jahresbilanz.json").read_text(encoding="utf-8"))
    eigene = abgleich.rechne_referenzjahr(app)

    abweichungen = abgleich.vergleiche(eigene["bilanz"], excel)
    schlimmste = [a for a in abweichungen if a["relativ"] > TOLERANZ]
    assert not schlimmste, abgleich.als_text(abweichungen)


@pytest.mark.slow
def test_der_lauf_konvergiert_in_jeder_stunde(app):
    eigene = abgleich.rechne_referenzjahr(app)
    assert len(eigene["warnungen"]) == 0, eigene["warnungen"][:5]
```

`pytest.ini` anlegen, damit die Marke bekannt ist:

```ini
[pytest]
markers =
    slow: laeuft ueber ein volles Jahr und dauert einige Sekunden
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_abgleich.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'werkzeuge.abgleich'`

- [ ] **Step 3: Write the tool**

`werkzeuge/abgleich.py`:

```python
"""Rechnet die Vorlage mit den TRY-Daten der Excel und vergleicht die Ergebnisse.

Aufruf von Hand:  python3 werkzeuge/abgleich.py
Dann werden die Abweichungen je Bilanzgroesse und die erste stark abweichende
Stunde ausgegeben - das ist der Einstiegspunkt zur Fehlersuche.
"""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DATEN = WURZEL / "tests" / "daten"

# Zuordnung Bilanzschluessel -> Schluessel in jahresbilanz.json
ZUORDNUNG = {
    "strom_ht": "strom_ht_mwh",
    "strom_nt": "strom_nt_mwh",
    "waerme": "waerme_mwh",
    "kaelte": "kaelte_mwh",
    "wasser": "wasser_m3",
}


def lade_wetterstunden():
    stunden = []
    start = datetime(2000, 1, 1, 0)
    with open(DATEN / "wetterdaten_try04.csv", encoding="utf-8") as datei:
        for nummer, zeile in enumerate(csv.DictReader(datei)):
            stunden.append(
                {
                    "zeitpunkt": start + timedelta(hours=nummer),
                    "t_au": float(zeile["t_au"]),
                    "x_au": float(zeile["x_au"]),
                    "str_s": float(zeile["str_s"]),
                    "str_o": float(zeile["str_o"]),
                    "str_w": float(zeile["str_w"]),
                    "str_n": float(zeile["str_n"]),
                    "str_h": float(zeile["str_h"]),
                }
            )
    return stunden


def lade_excel_stunden():
    with open(DATEN / "ergebnis_jahreslauf.csv", encoding="utf-8") as datei:
        return list(csv.DictReader(datei))


def rechne_referenzjahr(app):
    from core import anlagen, solver
    from core.vorlagen import ax_sim_2_1

    with app.app_context():
        projekt = anlagen.projekt_anlegen("Abgleich")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        graph = anlagen.lade_graph(anlage)
        lauf = solver.Solver(graph).starte(lade_wetterstunden())

    bilanz = {
        "strom_ht": lauf.bilanz["strom_ht"] / 1000.0,
        "strom_nt": lauf.bilanz["strom_nt"] / 1000.0,
        "waerme": lauf.bilanz["waerme"] / 1000.0,
        "kaelte": lauf.bilanz["kaelte"] / 1000.0,
        "wasser": lauf.bilanz["wasser"] / 1000.0,
    }
    return {"bilanz": bilanz, "stunden": lauf.stunden, "warnungen": lauf.warnungen}


def vergleiche(eigene, excel):
    ergebnis = []
    for schluessel, excel_schluessel in ZUORDNUNG.items():
        meins = eigene.get(schluessel, 0.0)
        seins = float(excel.get(excel_schluessel, 0.0))
        nenner = abs(seins) if abs(seins) > 1e-9 else 1.0
        ergebnis.append(
            {
                "groesse": schluessel,
                "eigene": meins,
                "excel": seins,
                "differenz": meins - seins,
                "relativ": abs(meins - seins) / nenner,
            }
        )
    return ergebnis


def als_text(abweichungen):
    zeilen = [f"{'Groesse':12} {'eigene':>14} {'Excel':>14} {'Abw. %':>9}"]
    for a in abweichungen:
        zeilen.append(
            f"{a['groesse']:12} {a['eigene']:14.4f} {a['excel']:14.4f} "
            f"{a['relativ'] * 100:8.2f}%"
        )
    return "\n".join(zeilen)


def erste_abweichende_stunde(eigene_stunden, excel_stunden, spalte="waerme", grenze=0.5):
    """Findet die erste Stunde, in der eine Groesse deutlich abweicht."""
    for nummer, (meine, seine) in enumerate(zip(eigene_stunden, excel_stunden)):
        summe = 0.0
        for werte in meine.values():
            if spalte in werte:
                summe += float(werte[spalte])
        seins = float(seine.get(spalte, 0.0))
        if abs(summe - seins) > grenze:
            return {
                "stunde": nummer,
                "zeitpunkt": seine.get("datum"),
                "eigene": summe,
                "excel": seins,
            }
    return None


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(WURZEL))
    from app import create_app
    from core import database

    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()

    excel = json.loads((DATEN / "jahresbilanz.json").read_text(encoding="utf-8"))
    eigene = rechne_referenzjahr(anwendung)

    print(als_text(vergleiche(eigene["bilanz"], excel)))
    print(f"\nKonvergenzwarnungen: {len(eigene['warnungen'])}")
    for warnung in eigene["warnungen"][:5]:
        print("  ", warnung["text"])

    treffer = erste_abweichende_stunde(eigene["stunden"], lade_excel_stunden())
    if treffer:
        print("\nErste deutlich abweichende Stunde:", treffer)
```

- [ ] **Step 4: Run the comparison and read the result**

Run: `python3 werkzeuge/abgleich.py`

Erwartet wird eine Tabelle mit fünf Zeilen. **Wenn die Abweichung über 0,5 Prozent
liegt, ist das kein Grund, die Toleranz zu erhöhen.** Dann in dieser Reihenfolge
vorgehen:

1. **Konvergenzwarnungen zuerst.** Melden sich Stunden als nicht konvergiert, stimmt
   etwas an der Reglerverdrahtung oder an einer Rückkante nicht. Task 15 prüfen.
2. **Erste abweichende Stunde ansehen.** Das Werkzeug nennt sie. Dann für diese eine
   Stunde die Zwischenwerte der Karten ausgeben und mit dem Blatt `Anlage`
   vergleichen — Baustein für Baustein entlang des Luftwegs.
3. **Einzelne Bilanzgröße prüfen.** Weicht nur der Strom ab, liegt es an den
   Ventilatoren oder an der Tarifaufteilung; weicht nur das Wasser ab, an den
   Befeuchtern; weicht die Wärme ab, am Vorerhitzer oder an der Rückwärmzahl.
4. **Parameter der Vorlage gegen die Excel prüfen.** Task 18 hat alle Nennwerte mit
   Zellbezug kommentiert; die Regler-Sollwerte sind die wahrscheinlichste
   Fehlerquelle, weil die Excel sie über mehrere Zellen verteilt.

Erst wenn alle vier Punkte geprüft sind und eine Restabweichung bleibt, wird sie im
Testkommentar begründet festgehalten — mit Angabe, welche Größe um wie viel abweicht
und warum. Eine unbegründet angehobene Toleranz macht den Test wertlos.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_abgleich.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add werkzeuge/abgleich.py tests/test_abgleich.py pytest.ini
git commit -m "Abgleich der Jahresbilanz gegen die Excel-Ergebnisse"
```

---

## Hinweis zu den Oberflächen-Aufgaben

Die globalen Vorgaben schließen einen Build-Schritt und JavaScript-Bibliotheken aus.
Damit gibt es in Stufe 1 keinen JavaScript-Testläufer. Die Aufgaben 21 bis 24 enden
deshalb mit einer **festgelegten Handprüfung**: eine kurze Liste von Schritten mit
genau beschriebenem erwartetem Verhalten. Was serverseitig prüfbar ist — Palette,
Karten, Pfeile, Simulationsstand — ist bereits in den Tasks 16 bis 19 durch Tests
abgedeckt.

---

## Task 21: Leinwand und Palette

**Files:**
- Create: `static/js/editor.js`, `static/js/palette.js`,
  `static/symbole/*.svg` (31 Dateien), `templates/editor.html`
- Modify: `static/css/style.css`, `routes/pages.py`
- Test: Handprüfung (siehe Schritt 4)

**Interfaces:**
- `editor.js` stellt bereit: `Editor.laden(anlageId)`, `Editor.zeichne()`,
  `Editor.karteHinzufuegen(typ, x, y)`, `Editor.auswahl` (die gewählte Karten-ID)
- Die Leinwand ist ein einzelnes `<svg id="leinwand">` mit einer Gruppe
  `<g id="welt">`, auf die Verschiebung und Zoom als `transform` wirken.

- [ ] **Step 1: Symbole anlegen**

Für jeden der 31 Kartentypen eine SVG-Datei in `static/symbole/`, benannt wie das
Feld `SYMBOL` des Bausteins. Jede Datei ist ein quadratisches Symbol mit
`viewBox="0 0 48 48"`, ohne feste Farben — gezeichnet mit
`stroke="currentColor" fill="none" stroke-width="2"`, damit die Farbe aus dem CSS
kommt. Die Formen orientieren sich an den Symbolen der Excel:

| Datei | Form |
|---|---|
| `erhitzer.svg` | Quadrat mit Diagonale von links unten nach rechts oben und Pluszeichen |
| `kuehler.svg` | Quadrat mit Diagonale von links oben nach rechts unten |
| `wrg.svg` | zwei ineinandergreifende Dreiecke im Quadrat |
| `mischkammer.svg` | Quadrat mit zwei zusammenlaufenden Pfeilen |
| `dampfbefeuchter.svg` | Quadrat mit drei aufsteigenden Wellenlinien |
| `luftwaescher.svg` | Quadrat mit senkrechten Tropfenreihen |
| `ventilator.svg` | Kreis mit drei Flügeln |
| `verteiler.svg` | ein Strich, der sich in zwei teilt |
| `sammler.svg` | zwei Striche, die zu einem werden |
| `aussenluft.svg` | Pfeil in ein offenes Rechteck hinein |
| `fortluft.svg` | Pfeil aus einem offenen Rechteck heraus |
| `wetter.svg` | Sonne hinter einer Wolke |
| `raum.svg` | Haus mit Fenster |
| `einfacher_raum.svg` | einfaches Rechteck mit Zu- und Abluftpfeil |
| `statische_heizung.svg` | Heizkörper mit drei Rippen |
| `p_regler.svg` | Quadrat mit Sprungantwortkurve |
| `sequenzregler.svg` | Quadrat mit Treppenkurve |
| `hysterese_regler.svg` | Quadrat mit Hystereseschleife |
| `kaskade.svg` | zwei verkettete Regelkreise |
| `wochenzeitplan.svg` | Kalenderblatt |
| `monatsprofil.svg` | Kalenderblatt mit zwölf Feldern |
| `tageslastprofil.svg` | Balkenfolge |
| `ferien.svg` | Kalenderblatt mit Kreuz |
| `anlagenbetrieb.svg` | Schalter |
| `heizungspumpen.svg` | Kreis mit Pfeil |
| `warmwasser.svg` | Speicher mit Wellenlinie |
| `zirkulation.svg` | Ringleitung mit Pfeil |
| `beleuchtung.svg` | Glühlampe |
| `enthalpierechner.svg` | h-x-Diagramm angedeutet |
| `bilanz.svg` | Balkendiagramm mit Eurozeichen |
| `datenlogger.svg` | Kurvenschreiber |

Beispiel `static/symbole/erhitzer.svg`:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"
     fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
  <rect x="6" y="6" width="36" height="36" rx="2"/>
  <line x1="6" y1="42" x2="42" y2="6"/>
  <line x1="30" y1="18" x2="30" y2="30"/>
  <line x1="24" y1="24" x2="36" y2="24"/>
</svg>
```

- [ ] **Step 2: Write the editor**

`templates/editor.html`:

```html
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RLT-Simulation</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
  <div class="app">
    <aside class="palette" id="palette"></aside>

    <main class="buehne">
      <header class="leiste">
        <span class="titel" id="anlagenname">Anlage</span>
        <button class="knopf-haupt" id="btn-simulieren">Simulieren</button>
      </header>
      <svg id="leinwand">
        <g id="welt">
          <g id="pfeile"></g>
          <g id="karten"></g>
        </g>
      </svg>
    </main>

    <aside class="panel" id="panel"></aside>
  </div>

  <script>window.ANLAGE_ID = {{ anlage_id }};</script>
  <script src="{{ url_for('static', filename='js/palette.js') }}"></script>
  <script src="{{ url_for('static', filename='js/pfeile.js') }}"></script>
  <script src="{{ url_for('static', filename='js/panel.js') }}"></script>
  <script src="{{ url_for('static', filename='js/editor.js') }}"></script>
</body>
</html>
```

`static/js/editor.js`:

```javascript
/* Leinwand: Karten zeichnen, verschieben, auswaehlen. */

const NS = "http://www.w3.org/2000/svg";

const Editor = {
  anlage: null,
  auswahl: null,
  sicht: { x: 0, y: 0, zoom: 1 },

  async laden(anlageId) {
    const antwort = await fetch(`/api/anlagen/${anlageId}`);
    this.anlage = await antwort.json();
    document.getElementById("anlagenname").textContent = this.anlage.name;
    this.zeichne();
  },

  karteNach(id) {
    return this.anlage.karten.find((k) => k.id === id);
  },

  zeichne() {
    const ebene = document.getElementById("karten");
    ebene.textContent = "";
    for (const karte of this.anlage.karten) {
      ebene.appendChild(this.zeichneKarte(karte));
    }
    Pfeile.zeichneAlle(this.anlage);
    this.aktualisiereSicht();
  },

  zeichneKarte(karte) {
    const gruppe = document.createElementNS(NS, "g");
    gruppe.setAttribute("class", "karte");
    gruppe.setAttribute("data-id", karte.id);
    gruppe.setAttribute("transform", `translate(${karte.pos_x} ${karte.pos_y})`);
    if (this.auswahl === karte.id) gruppe.classList.add("gewaehlt");

    const rahmen = document.createElementNS(NS, "rect");
    rahmen.setAttribute("class", "karte-rahmen");
    rahmen.setAttribute("width", 150);
    rahmen.setAttribute("height", 96);
    rahmen.setAttribute("rx", 8);
    gruppe.appendChild(rahmen);

    const bild = document.createElementNS(NS, "image");
    bild.setAttribute("href", `/static/symbole/${karte.symbol}`);
    bild.setAttribute("x", 10);
    bild.setAttribute("y", 10);
    bild.setAttribute("width", 32);
    bild.setAttribute("height", 32);
    gruppe.appendChild(bild);

    const beschriftung = document.createElementNS(NS, "text");
    beschriftung.setAttribute("class", "karte-name");
    beschriftung.setAttribute("x", 50);
    beschriftung.setAttribute("y", 30);
    beschriftung.textContent = karte.name;
    gruppe.appendChild(beschriftung);

    const werte = document.createElementNS(NS, "text");
    werte.setAttribute("class", "karte-werte");
    werte.setAttribute("x", 10);
    werte.setAttribute("y", 66);
    werte.setAttribute("data-werte", karte.id);
    gruppe.appendChild(werte);

    for (const port of karte.ports) {
      gruppe.appendChild(this.zeichnePort(karte, port));
    }

    gruppe.addEventListener("pointerdown", (e) => this.karteGreifen(e, karte));
    return gruppe;
  },

  portPosition(karte, port) {
    const gleiche = karte.ports.filter(
      (p) => p.richtung === port.richtung && p.art === port.art
    );
    const index = gleiche.indexOf(port);
    const abstand = 96 / (gleiche.length + 1);
    const y = abstand * (index + 1);
    const x = port.richtung === "ein" ? 0 : 150;
    return { x, y };
  },

  zeichnePort(karte, port) {
    const { x, y } = this.portPosition(karte, port);
    const punkt = document.createElementNS(NS, "circle");
    punkt.setAttribute("class", `port port-${port.art}`);
    punkt.setAttribute("cx", x);
    punkt.setAttribute("cy", y);
    punkt.setAttribute("r", 4);
    punkt.setAttribute("data-port", port.id);
    const titel = document.createElementNS(NS, "title");
    titel.textContent = `${port.schluessel} (${port.rolle})`;
    punkt.appendChild(titel);
    return punkt;
  },

  karteGreifen(ereignis, karte) {
    if (ereignis.button !== 0) return;
    ereignis.stopPropagation();
    this.auswahl = karte.id;
    Panel.zeige(karte);

    const start = { x: ereignis.clientX, y: ereignis.clientY };
    const anfang = { x: karte.pos_x, y: karte.pos_y };
    const gruppe = ereignis.currentTarget;
    document.querySelectorAll(".karte.gewaehlt").forEach((g) =>
      g.classList.remove("gewaehlt")
    );
    gruppe.classList.add("gewaehlt");

    const bewegen = (e) => {
      karte.pos_x = anfang.x + (e.clientX - start.x) / this.sicht.zoom;
      karte.pos_y = anfang.y + (e.clientY - start.y) / this.sicht.zoom;
      gruppe.setAttribute("transform", `translate(${karte.pos_x} ${karte.pos_y})`);
      Pfeile.zeichneAlle(this.anlage);
    };
    const loslassen = async () => {
      window.removeEventListener("pointermove", bewegen);
      window.removeEventListener("pointerup", loslassen);
      await fetch(`/api/karten/${karte.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pos_x: karte.pos_x, pos_y: karte.pos_y }),
      });
    };
    window.addEventListener("pointermove", bewegen);
    window.addEventListener("pointerup", loslassen);
  },

  async karteHinzufuegen(typ, x, y) {
    const antwort = await fetch("/api/karten", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ anlage_id: this.anlage.id, typ, pos_x: x, pos_y: y }),
    });
    const karte = await antwort.json();
    this.anlage.karten.push(karte);
    this.zeichne();
  },

  aktualisiereSicht() {
    document
      .getElementById("welt")
      .setAttribute(
        "transform",
        `translate(${this.sicht.x} ${this.sicht.y}) scale(${this.sicht.zoom})`
      );
  },

  bindeLeinwand() {
    const leinwand = document.getElementById("leinwand");

    leinwand.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".karte")) return;
      this.auswahl = null;
      Panel.leeren();
      document.querySelectorAll(".karte.gewaehlt").forEach((g) =>
        g.classList.remove("gewaehlt")
      );
      const start = { x: e.clientX, y: e.clientY };
      const anfang = { ...this.sicht };
      const bewegen = (m) => {
        this.sicht.x = anfang.x + (m.clientX - start.x);
        this.sicht.y = anfang.y + (m.clientY - start.y);
        this.aktualisiereSicht();
      };
      const loslassen = () => {
        window.removeEventListener("pointermove", bewegen);
        window.removeEventListener("pointerup", loslassen);
      };
      window.addEventListener("pointermove", bewegen);
      window.addEventListener("pointerup", loslassen);
    });

    leinwand.addEventListener("wheel", (e) => {
      e.preventDefault();
      const faktor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
      this.sicht.zoom = Math.min(3, Math.max(0.2, this.sicht.zoom * faktor));
      this.aktualisiereSicht();
    }, { passive: false });

    leinwand.addEventListener("dragover", (e) => e.preventDefault());
    leinwand.addEventListener("drop", (e) => {
      e.preventDefault();
      const typ = e.dataTransfer.getData("text/kartentyp");
      if (!typ) return;
      const kasten = leinwand.getBoundingClientRect();
      const x = (e.clientX - kasten.left - this.sicht.x) / this.sicht.zoom;
      const y = (e.clientY - kasten.top - this.sicht.y) / this.sicht.zoom;
      this.karteHinzufuegen(typ, Math.round(x), Math.round(y));
    });

    window.addEventListener("keydown", async (e) => {
      if (e.key !== "Delete" || this.auswahl === null) return;
      await fetch(`/api/karten/${this.auswahl}`, { method: "DELETE" });
      this.auswahl = null;
      await this.laden(this.anlage.id);
    });
  },
};

window.addEventListener("DOMContentLoaded", async () => {
  Editor.bindeLeinwand();
  await Palette.laden();
  await Editor.laden(window.ANLAGE_ID);
  Pfeile.binde(Editor);
});
```

`static/js/palette.js`:

```javascript
/* Symbolpalette links: Kartentypen nach Gruppen, per Ziehen auf die Leinwand. */

const Palette = {
  async laden() {
    const gruppen = await (await fetch("/api/palette")).json();
    const behaelter = document.getElementById("palette");
    behaelter.textContent = "";

    const reihenfolge = [
      "Luftbehandlung", "Verteilung", "Räume", "Regelung",
      "Zeit und Betrieb", "Quellen und Senken", "Verbraucher",
    ];
    const namen = Object.keys(gruppen).sort(
      (a, b) => reihenfolge.indexOf(a) - reihenfolge.indexOf(b)
    );

    for (const name of namen) {
      const ueberschrift = document.createElement("h2");
      ueberschrift.className = "gruppe";
      ueberschrift.textContent = name;
      behaelter.appendChild(ueberschrift);

      const liste = document.createElement("div");
      liste.className = "gruppe-liste";
      for (const typ of gruppen[name]) {
        const eintrag = document.createElement("div");
        eintrag.className = "palette-eintrag";
        eintrag.draggable = true;
        eintrag.title = typ.name;
        eintrag.innerHTML =
          `<img src="/static/symbole/${typ.symbol}" alt="">` +
          `<span>${typ.name}</span>`;
        eintrag.addEventListener("dragstart", (e) => {
          e.dataTransfer.setData("text/kartentyp", typ.kennung);
        });
        liste.appendChild(eintrag);
      }
      behaelter.appendChild(liste);
    }
  },
};
```

`routes/pages.py` — ergänzen:

```python
@bp.route("/anlage/<int:anlage_id>")
def editor(anlage_id):
    return render_template("editor.html", anlage_id=anlage_id)
```

`static/css/style.css` — ergänzen:

```css
.palette { width: 220px; flex-shrink: 0; background: var(--surface);
           border-right: 1px solid var(--border-light); overflow-y: auto;
           padding: 12px; }
.gruppe { font-size: 11px; text-transform: uppercase; letter-spacing: .04em;
          color: var(--text-secondary); margin: 16px 0 6px; }
.gruppe-liste { display: flex; flex-direction: column; gap: 2px; }
.palette-eintrag { display: flex; align-items: center; gap: 8px; padding: 6px 8px;
                   border-radius: 6px; cursor: grab; color: var(--text); }
.palette-eintrag:hover { background: var(--blue-tint); }
.palette-eintrag img { width: 20px; height: 20px; }

.buehne { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.leiste { height: 52px; display: flex; align-items: center; gap: 16px;
          padding: 0 16px; background: var(--surface);
          border-bottom: 1px solid var(--border-light); }
.titel { font-size: 16px; font-weight: 500; }
.knopf-haupt { margin-left: auto; border: none; background: var(--blue);
               color: #fff; border-radius: 20px; padding: 8px 20px;
               font-size: 14px; cursor: pointer; }

#leinwand { flex: 1; background: var(--bg); touch-action: none; cursor: grab; }
.karte-rahmen { fill: var(--surface); stroke: var(--border); }
.karte.gewaehlt .karte-rahmen { stroke: var(--blue); stroke-width: 2; }
.karte { color: var(--text-secondary); cursor: move; }
.karte-name { font-size: 12px; fill: var(--text); }
.karte-werte { font-size: 10px; fill: var(--text-secondary); }
.port { fill: var(--surface); stroke: var(--text-secondary); }
.port-luft { r: 5; stroke-width: 2; }
.port-signal { stroke-dasharray: 2 2; }
.port.ziel-moeglich { fill: var(--blue); stroke: var(--blue); }
.port.ziel-unmoeglich { opacity: .25; }

.panel { width: 280px; flex-shrink: 0; background: var(--surface);
         border-left: 1px solid var(--border-light); overflow-y: auto;
         padding: 16px; }
```

- [ ] **Step 3: Start the application**

Run: `python3 app.py`, dann im Browser `http://127.0.0.1:5055/anlage/1` öffnen
(die Anlage vorher über `POST /api/anlagen/aus_vorlage` anlegen).

- [ ] **Step 4: Handprüfung**

| Schritt | Erwartetes Verhalten |
|---|---|
| Seite öffnen | Links stehen die sieben Palettengruppen mit allen 31 Symbolen |
| Symbol auf die Leinwand ziehen | Eine Karte erscheint an der Loslassstelle, mit Symbol, Namen und Anschlusspunkten am Rand |
| Karte verschieben | Sie folgt der Maus; nach dem Neuladen der Seite liegt sie an der neuen Stelle |
| Auf leere Fläche ziehen | Die ganze Leinwand verschiebt sich |
| Mausrad | Die Ansicht zoomt zwischen 20 und 300 Prozent |
| Karte anklicken | Sie bekommt einen blauen Rahmen |
| Entf drücken | Die gewählte Karte verschwindet, auch nach dem Neuladen |
| Auf einen Anschlusspunkt zeigen | Ein Kurzhinweis nennt Schlüssel und Rolle |

- [ ] **Step 5: Commit**

```bash
git add static templates routes/pages.py
git commit -m "Editor mit Leinwand, Kartensymbolen und Palette"
```

---

## Task 22: Pfeile und automatische Verdrahtung in der Oberfläche

**Files:**
- Create: `static/js/pfeile.js`
- Modify: `static/css/style.css`
- Test: Handprüfung

**Interfaces:**
- `Pfeile.binde(editor)`, `Pfeile.zeichneAlle(anlage)`,
  `Pfeile.ziehenStarten(karte, ereignis)`

- [ ] **Step 1: Write the implementation**

`static/js/pfeile.js`:

```javascript
/* Pfeile zwischen Karten. Ein Pfeil verbindet KARTEN, nicht Ports - der Server
   ordnet die passenden Anschluesse selbst zu. */

const Pfeile = {
  editor: null,
  ziehen: null,

  binde(editor) {
    this.editor = editor;
    const leinwand = document.getElementById("leinwand");

    leinwand.addEventListener("pointerdown", (e) => {
      const kartenElement = e.target.closest(".karte");
      if (!kartenElement || !e.shiftKey) return;
      e.stopPropagation();
      const id = Number(kartenElement.dataset.id);
      this.ziehenStarten(editor.karteNach(id), e);
    });

    leinwand.addEventListener("dblclick", (e) => {
      const pfeilElement = e.target.closest(".pfeil");
      if (!pfeilElement) return;
      this.loeschen(Number(pfeilElement.dataset.id));
    });
  },

  mitte(karte) {
    return { x: karte.pos_x + 75, y: karte.pos_y + 48 };
  },

  rand(von, nach) {
    /* Ausgang rechts, Eingang links - so laufen die Pfeile wie in der Excel. */
    return {
      a: { x: von.pos_x + 150, y: von.pos_y + 48 },
      b: { x: nach.pos_x, y: nach.pos_y + 48 },
    };
  },

  artDesPfeils(pfeil, anlage) {
    /* Traegt der Pfeil mindestens eine Luftverbindung, wird er dick gezeichnet. */
    const ports = new Map();
    for (const karte of anlage.karten) {
      for (const port of karte.ports) ports.set(port.id, port);
    }
    const hatLuft = pfeil.verbindungen.some(
      (v) => (ports.get(v.von_port_id) || {}).art === "luft"
    );
    return hatLuft ? "luft" : "signal";
  },

  zeichneAlle(anlage) {
    const ebene = document.getElementById("pfeile");
    ebene.textContent = "";
    const NSS = "http://www.w3.org/2000/svg";

    for (const pfeil of anlage.pfeile) {
      const von = anlage.karten.find((k) => k.id === pfeil.von_karte_id);
      const nach = anlage.karten.find((k) => k.id === pfeil.nach_karte_id);
      if (!von || !nach) continue;

      const { a, b } = this.rand(von, nach);
      const mitteX = (a.x + b.x) / 2;
      const bahn = document.createElementNS(NSS, "path");
      bahn.setAttribute(
        "d",
        `M ${a.x} ${a.y} C ${mitteX} ${a.y}, ${mitteX} ${b.y}, ${b.x} ${b.y}`
      );
      bahn.setAttribute("class", `pfeil pfeil-${this.artDesPfeils(pfeil, anlage)}`);
      bahn.setAttribute("data-id", pfeil.id);

      const hinweis = document.createElementNS(NSS, "title");
      hinweis.textContent =
        `${von.name} → ${nach.name} (${pfeil.verbindungen.length} Verbindungen)`;
      bahn.appendChild(hinweis);

      ebene.appendChild(bahn);
    }
  },

  ziehenStarten(karte, ereignis) {
    const NSS = "http://www.w3.org/2000/svg";
    const leinwand = document.getElementById("leinwand");
    const vorschau = document.createElementNS(NSS, "path");
    vorschau.setAttribute("class", "pfeil pfeil-vorschau");
    document.getElementById("pfeile").appendChild(vorschau);

    const start = { x: karte.pos_x + 150, y: karte.pos_y + 48 };
    const sicht = this.editor.sicht;

    const bewegen = (e) => {
      const kasten = leinwand.getBoundingClientRect();
      const x = (e.clientX - kasten.left - sicht.x) / sicht.zoom;
      const y = (e.clientY - kasten.top - sicht.y) / sicht.zoom;
      vorschau.setAttribute("d", `M ${start.x} ${start.y} L ${x} ${y}`);

      const ziel = document.elementFromPoint(e.clientX, e.clientY);
      document.querySelectorAll(".karte.ziel").forEach((g) =>
        g.classList.remove("ziel")
      );
      const zielKarte = ziel && ziel.closest(".karte");
      if (zielKarte && Number(zielKarte.dataset.id) !== karte.id) {
        zielKarte.classList.add("ziel");
      }
    };

    const loslassen = async (e) => {
      window.removeEventListener("pointermove", bewegen);
      window.removeEventListener("pointerup", loslassen);
      vorschau.remove();
      document.querySelectorAll(".karte.ziel").forEach((g) =>
        g.classList.remove("ziel")
      );

      const ziel = document.elementFromPoint(e.clientX, e.clientY);
      const zielKarte = ziel && ziel.closest(".karte");
      if (!zielKarte) return;
      const zielId = Number(zielKarte.dataset.id);
      if (zielId === karte.id) return;

      const antwort = await fetch("/api/pfeile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          anlage_id: this.editor.anlage.id,
          von_karte_id: karte.id,
          nach_karte_id: zielId,
        }),
      });

      if (!antwort.ok) {
        const fehler = await antwort.json();
        this.melde(fehler.fehler || "Verbindung nicht möglich");
        return;
      }
      await this.editor.laden(this.editor.anlage.id);
    };

    window.addEventListener("pointermove", bewegen);
    window.addEventListener("pointerup", loslassen);
  },

  async loeschen(pfeilId) {
    await fetch(`/api/pfeile/${pfeilId}`, { method: "DELETE" });
    await this.editor.laden(this.editor.anlage.id);
  },

  melde(text) {
    const hinweis = document.createElement("div");
    hinweis.className = "hinweis";
    hinweis.textContent = text;
    document.body.appendChild(hinweis);
    setTimeout(() => hinweis.remove(), 4000);
  },
};
```

`static/css/style.css` — ergänzen:

```css
.pfeil { fill: none; stroke: var(--text-secondary); pointer-events: stroke; }
.pfeil-luft { stroke-width: 3; }
.pfeil-signal { stroke-width: 1.2; stroke-dasharray: 5 4; }
.pfeil-vorschau { stroke: var(--blue); stroke-width: 2; stroke-dasharray: 4 4; }
.pfeil:hover { stroke: var(--blue); }
.karte.ziel .karte-rahmen { stroke: var(--blue); stroke-width: 2;
                            fill: var(--blue-tint); }

.hinweis { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
           background: var(--danger); color: #fff; padding: 10px 18px;
           border-radius: 6px; font-size: 13px; box-shadow: 0 2px 8px rgba(0,0,0,.2); }
```

- [ ] **Step 2: Handprüfung**

Anlage aus der Vorlage anlegen und im Browser öffnen.

| Schritt | Erwartetes Verhalten |
|---|---|
| Vorlage öffnen | Alle Pfeile sind gezeichnet: Luftwege dick, Reglerlinien dünn gestrichelt |
| Auf einen Pfeil zeigen | Der Kurzhinweis nennt beide Karten und die Zahl der Verbindungen |
| Zwei Karten mit Umschalt ziehen (Erhitzer → Kühler) | Ein dicker Pfeil entsteht; **ein** Zug genügt, der Luftweg ist verdrahtet |
| Regler auf einen Erhitzer ziehen | Ein dünner Pfeil entsteht; der Kurzhinweis nennt zwei Verbindungen — Stellgröße hin, Istwert zurück |
| Verteiler auf einen zweiten Raum ziehen | Der Pfeil entsteht, obwohl der erste Abgang belegt ist — ein neuer Abgang ist nachgewachsen |
| Zwei unpassende Karten verbinden (Wetterkarte auf Fortluft) | Eine rote Meldung erscheint, es entsteht kein Pfeil |
| Doppelklick auf einen Pfeil | Der Pfeil verschwindet samt seinen Verbindungen, auch nach dem Neuladen |

- [ ] **Step 3: Commit**

```bash
git add static/js/pfeile.js static/css/style.css
git commit -m "Pfeile zwischen Karten mit automatischer Verdrahtung"
```

---

## Task 23: Parameterfenster und Werteanzeige

**Files:**
- Create: `static/js/panel.js`
- Modify: `static/css/style.css`
- Test: Handprüfung

**Interfaces:**
- `Panel.zeige(karte)`, `Panel.leeren()`,
  `Panel.zeigeWerte(werteJeKarte)` — trägt die Ergebnisse in die Karten ein

- [ ] **Step 1: Write the implementation**

`static/js/panel.js`:

```javascript
/* Rechte Spalte: die Parameter der gewaehlten Karte, erzeugt aus ihrer
   Typdeklaration. Jede Aenderung wird sofort gespeichert. */

const Panel = {
  karte: null,

  leeren() {
    this.karte = null;
    document.getElementById("panel").innerHTML =
      '<p class="leerhinweis">Karte auswählen, um ihre Parameter zu sehen.</p>';
  },

  zeige(karte) {
    this.karte = karte;
    const panel = document.getElementById("panel");
    panel.textContent = "";

    const kopf = document.createElement("h2");
    kopf.className = "panel-kopf";
    kopf.textContent = karte.name;
    panel.appendChild(kopf);

    const namensfeld = this.zeileText("Bezeichnung", karte.name, async (wert) => {
      karte.name = wert;
      await this.speichere({ name: wert });
      Editor.zeichne();
    });
    panel.appendChild(namensfeld);

    for (const feld of karte.felder) {
      const wert = karte.parameter[feld.schluessel];
      if (Array.isArray(wert) || (wert && typeof wert === "object")) {
        panel.appendChild(this.zeileListe(feld, wert));
        continue;
      }
      if (feld.auswahl && feld.auswahl.length) {
        panel.appendChild(this.zeileAuswahl(feld, wert));
      } else {
        panel.appendChild(this.zeileZahl(feld, wert));
      }
    }

    const ports = document.createElement("div");
    ports.className = "panel-ports";
    ports.innerHTML = "<h3>Anschlüsse</h3>";
    for (const port of karte.ports) {
      const zeile = document.createElement("div");
      zeile.className = `port-zeile port-zeile-${port.art}`;
      zeile.textContent =
        `${port.richtung === "ein" ? "◀" : "▶"} ${port.schluessel} · ${port.rolle}`;
      ports.appendChild(zeile);
    }
    panel.appendChild(ports);
  },

  _huelle(beschriftung, eingabe, einheit) {
    const zeile = document.createElement("label");
    zeile.className = "panel-zeile";
    const text = document.createElement("span");
    text.className = "panel-label";
    text.textContent = einheit ? `${beschriftung} [${einheit}]` : beschriftung;
    zeile.appendChild(text);
    zeile.appendChild(eingabe);
    return zeile;
  },

  zeileText(beschriftung, wert, beiAenderung) {
    const eingabe = document.createElement("input");
    eingabe.type = "text";
    eingabe.value = wert;
    eingabe.addEventListener("change", () => beiAenderung(eingabe.value));
    return this._huelle(beschriftung, eingabe, "");
  },

  zeileZahl(feld, wert) {
    const eingabe = document.createElement("input");
    eingabe.type = "number";
    eingabe.step = "any";
    eingabe.value = wert;
    eingabe.addEventListener("change", async () => {
      const zahl = Number(eingabe.value);
      this.karte.parameter[feld.schluessel] = zahl;
      await this.speichere({ parameter: { [feld.schluessel]: zahl } });
    });
    return this._huelle(feld.label, eingabe, feld.einheit);
  },

  zeileAuswahl(feld, wert) {
    const eingabe = document.createElement("select");
    for (const moeglichkeit of feld.auswahl) {
      const option = document.createElement("option");
      option.value = moeglichkeit;
      option.textContent = moeglichkeit;
      if (moeglichkeit === wert) option.selected = true;
      eingabe.appendChild(option);
    }
    eingabe.addEventListener("change", async () => {
      this.karte.parameter[feld.schluessel] = eingabe.value;
      await this.speichere({ parameter: { [feld.schluessel]: eingabe.value } });
    });
    return this._huelle(feld.label, eingabe, feld.einheit);
  },

  zeileListe(feld, wert) {
    /* Listen und Tabellen - Zeitplaene, Lastgaenge, Ferien - als JSON-Feld.
       Bewusst schlicht: die Werte sind selten und die Struktur ist sichtbar. */
    const eingabe = document.createElement("textarea");
    eingabe.rows = 4;
    eingabe.value = JSON.stringify(wert);
    eingabe.addEventListener("change", async () => {
      try {
        const gelesen = JSON.parse(eingabe.value);
        this.karte.parameter[feld.schluessel] = gelesen;
        await this.speichere({ parameter: { [feld.schluessel]: gelesen } });
        eingabe.classList.remove("fehlerhaft");
      } catch (fehler) {
        eingabe.classList.add("fehlerhaft");
      }
    });
    return this._huelle(feld.label, eingabe, feld.einheit);
  },

  async speichere(felder) {
    await fetch(`/api/karten/${this.karte.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(felder),
    });
  },

  zeigeWerte(werteJeKarte) {
    /* Traegt nach einem Lauf die wichtigsten Groessen in die Karten ein -
       so wie die farbigen Felder in der Excel. */
    for (const karte of Editor.anlage.karten) {
      const ziel = document.querySelector(`[data-werte="${karte.id}"]`);
      if (!ziel) continue;
      const werte = werteJeKarte[karte.id] || {};
      const teile = [];
      if ("T_aus" in werte) teile.push(`${werte.T_aus.toFixed(1)} °C`);
      if ("F_aus" in werte) teile.push(`${werte.F_aus.toFixed(1)} g/kg`);
      if ("T_Raum" in werte) teile.push(`Raum ${werte.T_Raum.toFixed(1)} °C`);
      if ("QH" in werte) teile.push(`${werte.QH.toFixed(1)} kW`);
      if ("QK" in werte) teile.push(`${werte.QK.toFixed(1)} kW`);
      if ("PE" in werte) teile.push(`${werte.PE.toFixed(2)} kW`);
      ziel.textContent = teile.join("  ·  ");
    }
  },
};
```

`static/css/style.css` — ergänzen:

```css
.panel-kopf { font-size: 15px; font-weight: 500; margin: 0 0 12px; }
.panel-zeile { display: flex; flex-direction: column; gap: 3px; margin-bottom: 10px; }
.panel-label { font-size: 11px; color: var(--text-secondary); }
.panel-zeile input, .panel-zeile select, .panel-zeile textarea {
  border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px;
  font-size: 13px; font-family: inherit; width: 100%; }
.panel-zeile textarea.fehlerhaft { border-color: var(--danger); }
.panel-ports { margin-top: 20px; }
.panel-ports h3 { font-size: 11px; text-transform: uppercase;
                  color: var(--text-secondary); margin: 0 0 6px; }
.port-zeile { font-size: 11px; color: var(--text-secondary); padding: 2px 0; }
.port-zeile-luft { color: var(--text); }
.leerhinweis { font-size: 13px; color: var(--text-secondary); }
```

- [ ] **Step 2: Handprüfung**

| Schritt | Erwartetes Verhalten |
|---|---|
| Erhitzer anklicken | Rechts stehen `V_nenn`, `dp_nenn` und `QH_max` mit ihren Einheiten |
| `QH_max` ändern und Feld verlassen | Nach dem Neuladen der Seite steht der neue Wert dort |
| Ventilator anklicken | `FU/DD/-` ist ein Auswahlfeld mit drei Möglichkeiten |
| Wochenzeitplan anklicken | Die Zeiten stehen als Zahlenfelder, das Ferienfeld als JSON-Textfeld |
| Ungültiges JSON eingeben | Das Feld wird rot umrandet, nichts wird gespeichert |
| Bezeichnung ändern | Der Name ändert sich auch auf der Karte in der Leinwand |
| Anschlussliste ansehen | Luft-Ports stehen dunkler als Signal-Ports, mit Richtungspfeil und Rolle |

- [ ] **Step 3: Commit**

```bash
git add static/js/panel.js static/css/style.css
git commit -m "Parameterfenster und Werteanzeige auf den Karten"
```

---

## Task 24: Simulation starten und Jahresbilanz zeigen

**Files:**
- Create: `static/js/simulation.js`, `templates/_bilanz.html`
- Modify: `templates/editor.html`, `static/css/style.css`, `routes/pages.py`
- Test: `tests/test_bilanzansicht.py`, Handprüfung

**Interfaces:**
- `Simulation.dialogOeffnen()`, `Simulation.starten(wetterId, von, bis)`,
  `Simulation.zeigeBilanz(simulationId)`
- HTTP: `GET /api/anlagen/<id>/simulationen` — die Läufe einer Anlage
- Die Schnellwahlen entsprechen den Excel-Schaltflächen (Anlage!Tabelle1):
  ganzes Jahr `0–8760`, kalter Tag `815–839`, heißer Tag `5855–5879`,
  feuchter Tag `5375–5399`, eigener Zeitraum

- [ ] **Step 1: Write the failing test**

`tests/test_bilanzansicht.py`:

```python
from datetime import datetime

import pytest

from app import create_app
from core import anlagen, database, ergebnisse, solver
from core.vorlagen import ax_sim_2_1
from core.wetter import speicher


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def test_simulationen_einer_anlage_werden_gelistet(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = speicher.datensatz_anlegen(
            "Test", "upload",
            [{"zeitpunkt": datetime(2024, 1, 1, 0), "t_au": 0.0, "x_au": 4.0,
              "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0}],
        )
        lauf = solver.Lauf(
            stunden=[{}],
            bilanz={"strom_ht": 0.0, "strom_nt": 1000.0, "waerme": 0.0,
                    "kaelte": 0.0, "wasser": 0.0},
            warnungen=[],
        )
        ergebnisse.speichere(anlage, wetter, 0, 1, lauf, dauer=0.1)

    antwort = app.test_client().get(f"/api/anlagen/{anlage}/simulationen")
    assert antwort.status_code == 200
    liste = antwort.get_json()
    assert len(liste) == 1
    assert liste[0]["wetter_name"] == "Test"
    assert liste[0]["kosten_gesamt"] == pytest.approx(150.0)


def test_schnellwahlen_treffen_die_richtigen_stunden(app):
    """Die Bereiche entsprechen den Schaltflaechen der Excel (Tabelle1)."""
    from routes.simulation import SCHNELLWAHL

    assert SCHNELLWAHL["jahr"] == (0, 8760)
    assert SCHNELLWAHL["kalter_tag"] == (815, 839)
    assert SCHNELLWAHL["heisser_tag"] == (5855, 5879)
    assert SCHNELLWAHL["feuchter_tag"] == (5375, 5399)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bilanzansicht.py -v`
Expected: FAIL mit `ImportError: cannot import name 'SCHNELLWAHL'`

- [ ] **Step 3: Write the implementation**

`routes/simulation.py` — ergänzen:

```python
# Die Bereiche der Excel-Schaltflaechen. Dort zaehlen die Datenzeilen ab 5,
# hier ab 0 - daher jeweils 5 abgezogen (Anlage!Tabelle1: 820/843, 5860/5883,
# 5380/5403, 5/8765).
SCHNELLWAHL = {
    "jahr": (0, 8760),
    "kalter_tag": (815, 839),
    "heisser_tag": (5855, 5879),
    "feuchter_tag": (5375, 5399),
}


@bp.get("/schnellwahl")
def schnellwahl():
    return jsonify(
        {name: {"von": von, "bis": bis} for name, (von, bis) in SCHNELLWAHL.items()}
    )
```

`routes/anlagen.py` — ergänzen:

```python
from core.database import get_db


@bp.get("/anlagen/<int:anlage_id>/simulationen")
def simulationen(anlage_id):
    db = get_db()
    zeilen = db.execute(
        "SELECT s.*, w.name AS wetter_name, "
        "       (SELECT SUM(b.kosten) FROM bilanz b WHERE b.simulation_id = s.id) "
        "         AS kosten_gesamt "
        "FROM simulation s JOIN wetterdatensatz w ON w.id = s.wetterdatensatz_id "
        "WHERE s.anlage_id = ? ORDER BY s.id DESC",
        (anlage_id,),
    ).fetchall()
    return jsonify(
        [
            {
                "id": z["id"], "wetter_name": z["wetter_name"],
                "von_stunde": z["von_stunde"], "bis_stunde": z["bis_stunde"],
                "status": z["status"], "gestartet_am": z["gestartet_am"],
                "dauer_s": z["dauer_s"],
                "kosten_gesamt": z["kosten_gesamt"] or 0.0,
            }
            for z in zeilen
        ]
    )
```

`static/js/simulation.js`:

```javascript
/* Simulationsdialog, Fortschritt und Jahresbilanz. */

const BESCHRIFTUNG = {
  jahr: "ganzes Jahr",
  kalter_tag: "kalter Tag",
  heisser_tag: "heißer Tag",
  feuchter_tag: "feuchter Tag",
};

const GROESSEN = {
  strom_ht: "Strom HT",
  strom_nt: "Strom NT",
  waerme: "Wärme",
  kaelte: "Kälte",
  wasser: "Wasser",
};

const Simulation = {
  kennung: null,

  async dialogOeffnen() {
    const wetter = await (await fetch("/api/wetter")).json();
    const bereiche = await (await fetch("/api/simulation/schnellwahl")).json();

    const dialog = document.createElement("div");
    dialog.className = "dialog-huelle";
    dialog.innerHTML = `
      <div class="dialog">
        <h2>Simulation starten</h2>
        <label class="panel-zeile">
          <span class="panel-label">Wetterdatensatz</span>
          <select id="wahl-wetter">
            ${wetter
              .map((w) => `<option value="${w.id}">${w.name} (${w.stunden} h)</option>`)
              .join("")}
          </select>
        </label>
        <label class="panel-zeile">
          <span class="panel-label">Zeitraum</span>
          <select id="wahl-bereich">
            ${Object.keys(bereiche)
              .map((n) => `<option value="${n}">${BESCHRIFTUNG[n] || n}</option>`)
              .join("")}
          </select>
        </label>
        <div class="dialog-knoepfe">
          <button id="btn-abbrechen">Abbrechen</button>
          <button class="knopf-haupt" id="btn-los">Los</button>
        </div>
      </div>`;
    document.body.appendChild(dialog);

    dialog.querySelector("#btn-abbrechen").onclick = () => dialog.remove();
    dialog.querySelector("#btn-los").onclick = () => {
      const wetterId = Number(dialog.querySelector("#wahl-wetter").value);
      const bereich = bereiche[dialog.querySelector("#wahl-bereich").value];
      dialog.remove();
      this.starten(wetterId, bereich.von, bereich.bis);
    };
  },

  async starten(wetterId, von, bis) {
    const antwort = await fetch("/api/simulation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        anlage_id: Editor.anlage.id,
        wetterdatensatz_id: wetterId,
        von,
        bis,
      }),
    });
    this.kennung = (await antwort.json()).kennung;
    this.zeigeFortschritt();
    this.beobachte();
  },

  zeigeFortschritt() {
    const balken = document.createElement("div");
    balken.className = "fortschritt-huelle";
    balken.innerHTML = `
      <div class="fortschritt">
        <div class="fortschritt-text" id="fortschritt-text">Simulation läuft …</div>
        <div class="fortschritt-schiene"><div id="fortschritt-balken"></div></div>
        <button id="btn-lauf-abbrechen">Abbrechen</button>
      </div>`;
    document.body.appendChild(balken);
    balken.querySelector("#btn-lauf-abbrechen").onclick = () =>
      fetch(`/api/simulation/${this.kennung}/abbrechen`, { method: "POST" });
  },

  async beobachte() {
    const huelle = document.querySelector(".fortschritt-huelle");
    while (true) {
      const stand = await (await fetch(`/api/simulation/${this.kennung}`)).json();
      const anteil = stand.gesamt ? stand.fertig / stand.gesamt : 0;
      const balken = document.getElementById("fortschritt-balken");
      if (balken) balken.style.width = `${(anteil * 100).toFixed(1)}%`;
      const text = document.getElementById("fortschritt-text");
      if (text) {
        text.textContent =
          `Simulation läuft … ${stand.fertig || 0} von ${stand.gesamt || 0} Stunden`;
      }

      if (["fertig", "abgebrochen", "fehler"].includes(stand.status)) {
        if (huelle) huelle.remove();
        if (stand.status === "fehler") {
          Pfeile.melde(`Simulation fehlgeschlagen: ${stand.fehler}`);
          return;
        }
        await this.zeigeBilanz(stand.simulation_id, stand.warnungen);
        return;
      }
      await new Promise((r) => setTimeout(r, 300));
    }
  },

  async zeigeBilanz(simulationId, warnungen) {
    const daten = await (
      await fetch(`/api/simulation/${simulationId}/bilanz`)
    ).json();

    const zeilen = daten.bilanz
      .map(
        (z) => `<tr>
          <td>${GROESSEN[z.groesse] || z.groesse}</td>
          <td class="zahl">${z.menge.toFixed(3)}</td>
          <td>${z.einheit}</td>
          <td class="zahl">${z.preis.toFixed(2)}</td>
          <td class="zahl">${z.kosten.toFixed(2)} EUR</td>
        </tr>`
      )
      .join("");
    const summe = daten.bilanz.reduce((s, z) => s + z.kosten, 0);

    const fenster = document.createElement("div");
    fenster.className = "dialog-huelle";
    fenster.innerHTML = `
      <div class="dialog dialog-breit">
        <h2>Jahresbilanz</h2>
        <table class="bilanz">
          <thead><tr><th>Größe</th><th class="zahl">Menge</th><th>Einheit</th>
                     <th class="zahl">Preis</th><th class="zahl">Kosten</th></tr></thead>
          <tbody>${zeilen}</tbody>
          <tfoot><tr><td colspan="4">Summe</td>
                     <td class="zahl">${summe.toFixed(2)} EUR</td></tr></tfoot>
        </table>
        ${warnungen ? `<p class="warnhinweis">${warnungen} Stunden ohne Konvergenz</p>` : ""}
        <div class="dialog-knoepfe">
          <button class="knopf-haupt" id="btn-schliessen">Schließen</button>
        </div>
      </div>`;
    document.body.appendChild(fenster);
    fenster.querySelector("#btn-schliessen").onclick = () => fenster.remove();
  },
};

window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btn-simulieren").onclick = () =>
    Simulation.dialogOeffnen();
});
```

`templates/editor.html` — `simulation.js` nach `editor.js` einbinden.

`static/css/style.css` — ergänzen:

```css
.dialog-huelle { position: fixed; inset: 0; background: rgba(0,0,0,.35);
                 display: flex; align-items: center; justify-content: center; }
.dialog { background: var(--surface); border-radius: var(--radius);
          padding: 24px; min-width: 340px; box-shadow: 0 8px 32px rgba(0,0,0,.2); }
.dialog-breit { min-width: 560px; }
.dialog h2 { margin: 0 0 16px; font-size: 16px; font-weight: 500; }
.dialog-knoepfe { display: flex; gap: 8px; justify-content: flex-end;
                  margin-top: 20px; }
.dialog-knoepfe button { border: 1px solid var(--border); background: var(--surface);
                         border-radius: 20px; padding: 8px 18px; cursor: pointer; }

.fortschritt-huelle { position: fixed; inset: 0; background: rgba(0,0,0,.35);
                      display: flex; align-items: center; justify-content: center; }
.fortschritt { background: var(--surface); border-radius: var(--radius);
               padding: 24px; min-width: 380px; text-align: center; }
.fortschritt-schiene { height: 6px; background: var(--border-light);
                       border-radius: 3px; margin: 14px 0; overflow: hidden; }
.fortschritt-schiene div { height: 100%; width: 0; background: var(--blue);
                           transition: width .2s; }

.bilanz { width: 100%; border-collapse: collapse; font-size: 13px; }
.bilanz th, .bilanz td { padding: 7px 10px; border-bottom: 1px solid var(--border-light);
                         text-align: left; }
.bilanz th { font-size: 11px; text-transform: uppercase;
             color: var(--text-secondary); }
.bilanz .zahl { text-align: right; font-variant-numeric: tabular-nums; }
.bilanz tfoot td { font-weight: 500; border-top: 2px solid var(--border); }
.warnhinweis { color: var(--danger); font-size: 12px; margin-top: 12px; }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bilanzansicht.py -v`
Expected: 2 passed

- [ ] **Step 5: Handprüfung**

Zuerst die TRY-Datei hochladen:

```bash
curl -F "datei=@referenz/RLTSimulation_Vorlage_AX_SIM_2.1.xls" \
     -F "name=TRY04" http://127.0.0.1:5055/api/wetter/upload
```

| Schritt | Erwartetes Verhalten |
|---|---|
| „Simulieren" anklicken | Ein Fenster mit Wetterdatensatz und Zeitraum erscheint |
| „kalter Tag" wählen und starten | Der Fortschrittsbalken läuft durch, danach erscheint die Bilanz |
| „ganzes Jahr" starten | Der Balken läuft in Schritten; „Abbrechen" beendet den Lauf sofort |
| Bilanz ansehen | Fünf Zeilen mit Menge, Einheit, Preis und Kosten sowie die Summe |
| Nach dem Lauf auf die Leinwand sehen | Jede Karte zeigt ihre Werte unter dem Namen |

- [ ] **Step 6: Commit**

```bash
git add static/js/simulation.js routes/simulation.py routes/anlagen.py templates static/css/style.css tests/test_bilanzansicht.py
git commit -m "Simulationsdialog mit Fortschritt und Jahresbilanz"
```

---

## Abschluss von Stufe 1

- [ ] **Alle Tests laufen lassen**

Run: `pytest -v`
Expected: alle Tests bestanden, einschließlich des Jahresabgleichs aus Task 20

- [ ] **README ergänzen**

Abschnitte über die Kartentypen, die Vorlage, das Hochladen von Wetterdaten und den
Abgleich gegen die Excel. Der Hinweis auf `referenz/` bleibt bestehen.

- [ ] **Abschluss-Commit**

```bash
git add README.md
git commit -m "Stufe 1 abgeschlossen: Rechenkern, Editor und Jahresbilanz"
```

## Was danach kommt (Stufe 2, eigener Plan)

Open-Meteo-Import mit Jahresvergleich, Diagramme, Varianten-Gegenüberstellung,
HTML- und PDF-Bericht mit ReportLab sowie die Ausgabe nach CSV und Excel.
