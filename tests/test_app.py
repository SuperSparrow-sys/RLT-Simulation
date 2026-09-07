from logging.handlers import RotatingFileHandler

import pytest

from app import create_app
from core import anlagen, config, database
from core.vorlagen import ax_sim_2_1


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def test_create_app_haengt_protokoll_handler_nur_einmal_an(tmp_path, monkeypatch):
    """Reproduziert den gemeldeten Fehler: dieselbe Warnung dutzendfach mit
    identischem Zeitstempel im Protokoll, weil jeder create_app()-Aufruf
    (die Testreihe allein ruft ihn dutzendfach auf) einen weiteren
    RotatingFileHandler an denselben, nach app.name geteilten Logger
    anhaengte. Zwei Aufrufe duerfen zusammen nur einen Handler und jede
    Meldung nur einmal im Protokoll hinterlassen."""
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")

    app1 = create_app()
    app2 = create_app()

    # Beide Flask-Anwendungen teilen sich denselben, nach Namen aufgeloesten
    # Python-Logger - das ist die eigentliche Ursache der Verdoppelung.
    assert app1.logger is app2.logger

    dateihandler = [
        h for h in app2.logger.handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(dateihandler) == 1

    app2.logger.warning("Testmeldung fuer die Handler-Absicherung")
    inhalt = config.LOG_FILE.read_text(encoding="utf-8")
    assert inhalt.count("Testmeldung fuer die Handler-Absicherung") == 1


# ---------- Cache-Control: HTML-Seiten duerfen nie abgelegt werden ----------
# Reproduziert den gemeldeten Fehler: ohne 'Cache-Control' legt der Browser
# eine HTML-Seite nach eigenem Ermessen ab (heuristische Freischaltung,
# RFC 7234 4.2.2) - beobachtet als eine zwei Tage alte Startseite, die
# wortwoertlich wiederkam, ohne Konsolenfehler und ohne dass 'Neu laden'
# noetig ausgesehen haette. Siehe app.py, _html_nie_ablegen().

def test_alle_vier_seiten_setzen_cache_control_no_store(app):
    """'no-store' statt nur 'no-cache': die Seite darf gar nicht erst
    abgelegt werden - bei vier kleinen Seiten vernachlaessigbarer Preis,
    der Schaden eines veralteten Standes war es nicht (siehe Befund)."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    for pfad in ("/", "/bausteine", f"/anlage/{anlage}", "/anlage/9999"):
        antwort = klient.get(pfad)
        assert antwort.headers.get("Cache-Control") == "no-store", pfad


def test_fehlerseiten_setzen_ebenfalls_cache_control_no_store(app):
    """Nicht nur die vier Hauptseiten - jede HTML-Antwort, auch Flasks
    eigene Fehlerseite fuer abort(...) (hier: /anlage/<id>/lauf/<id>/bericht
    fuer eine unbekannte Simulation-Id, 404)."""
    klient = app.test_client()
    antwort = klient.get("/anlage/1/lauf/9999/bericht")
    assert antwort.status_code == 404
    assert antwort.headers.get("Cache-Control") == "no-store"


def test_statische_dateien_behalten_no_cache_mit_etag(app):
    """Gegenprobe: die Korrektur fuer HTML-Seiten darf statische Dateien
    (Skripte, Formatvorlagen) nicht treffen - die bleiben ueber Flasks
    eigene Auslieferung bei 'no-cache' plus ETag (erzwingt eine Rueckfrage
    beim Server vor jeder Verwendung, siehe Kommentar in app.py, warum das
    hier als ausreichend entschieden wurde statt einer Fassungskennung im
    Dateiverweis)."""
    klient = app.test_client()
    for pfad in ("/static/js/editor.js", "/static/css/grundlage.css"):
        antwort = klient.get(pfad)
        assert antwort.headers.get("Cache-Control") == "no-cache", pfad
        assert antwort.headers.get("ETag"), pfad
