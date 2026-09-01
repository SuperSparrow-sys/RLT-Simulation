from logging.handlers import RotatingFileHandler

from app import create_app
from core import config


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
