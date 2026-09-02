import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture(scope="session")
def _protokoll_pfad(tmp_path_factory):
    return tmp_path_factory.mktemp("protokoll") / "rlt.log"


@pytest.fixture(autouse=True)
def _protokoll_umbiegen(_protokoll_pfad, monkeypatch):
    """Biegt den Protokollpfad fuer die gesamte Testreihe auf eine
    voruebergehende, gemeinsame Datei um - so wie core.config.DB_PATH es in
    den einzelnen Testdateien schon tut (dort bewusst je Test neu, weil jeder
    Test eine eigene, isolierte Datenbank braucht), nur zentral hier statt in
    jeder Testdatei einzeln. Ohne dies wuerde jeder Test, der create_app()
    aufruft, in die echte rlt.log des Projekts schreiben statt in eine
    wegwerfbare Datei.

    Bewusst ein einziger Pfad fuer die ganze Sitzung (statt je Test ein
    frischer wie bei tmp_path): create_app() haengt seinen Protokoll-Handler
    an app.logger, einen ueber logging.getLogger(app.name) von allen
    create_app()-Aufrufen geteilten Logger - ein je Test wechselnder Pfad
    wuerde ueber die Testreihe hinweg einen Handler je Test anhaeufen, statt
    genau den einen, den app.py fuer denselben Pfad wiederverwendet."""
    monkeypatch.setattr("core.config.LOG_FILE", _protokoll_pfad)
