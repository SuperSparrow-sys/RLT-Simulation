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
