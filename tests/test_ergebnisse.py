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
