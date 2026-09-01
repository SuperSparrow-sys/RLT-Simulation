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


def test_zeitreihe_wird_als_32bit_werte_gespeichert(app):
    """Ganzzahlige Werte passen verlustfrei; 1/3 nicht - das ist der bewusste
    Kompromiss aus der 32-Bit-Packung (siehe Docstring von core/ergebnisse)."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(6)
        graph = anlagen.lade_graph(anlage)

        eingabe = [0.0, 1.0, 2.0, 3.0, 4.0, 1 / 3]
        lauf = solver.Lauf(
            stunden=[{1: {"T_aus": wert}} for wert in eingabe],
            bilanz={"strom_ht": 0.0, "strom_nt": 1.0, "waerme": 2.0,
                    "kaelte": 3.0, "wasser": 4.0},
            warnungen=[],
        )
        sim = ergebnisse.speichere(anlage, wetter, 0, 6, lauf, graph, dauer=1.0)
        werte = ergebnisse.lade_zeitreihe(sim, 1, "T_aus")

    assert werte[:5] == [0.0, 1.0, 2.0, 3.0, 4.0]
    # Einfache Genauigkeit haelt rund 7 Dezimalstellen, keine 16 - 1/3 kommt
    # also veraendert zurueck, aber innerhalb der Toleranz des Formats.
    assert werte[5] != 1 / 3
    assert werte[5] == pytest.approx(1 / 3, abs=1e-6)


def test_bilanz_wird_mit_preisen_gespeichert(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(5)
        graph = anlagen.lade_graph(anlage)
        lauf = solver.Lauf(
            stunden=[{}],
            bilanz={"strom_ht": 0.0, "strom_nt": 1000.0, "waerme": 2000.0,
                    "kaelte": 0.0, "wasser": 100.0},
            warnungen=[],
        )
        sim = ergebnisse.speichere(anlage, wetter, 0, 5, lauf, graph, dauer=1.0)
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


def test_abbruch_beendet_den_lauf(app, monkeypatch):
    """Ohne Verlangsamung koennte der Lauf fertig werden, bevor der
    Abbruch-Merker geprueft wird - der Test wuerde dann nichts pruefen (siehe
    dieselbe Begruendung bei test_api_abbrechen_stoppt_den_lauf unten)."""
    original = solver.Solver._rechne_stunde

    def langsamer(self, *args, **kwargs):
        time.sleep(0.01)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(solver.Solver, "_rechne_stunde", langsamer)

    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(2000)
        kennung = laeufe.starte(app, anlage, wetter, 0, 2000)
        laeufe.abbrechen(kennung)

        for _ in range(400):
            stand = laeufe.stand(kennung)
            if stand["status"] in ("fertig", "abgebrochen", "fehler"):
                break
            time.sleep(0.05)
    assert stand["status"] == "abgebrochen", stand
    assert stand["fertig"] < 2000


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


def test_api_abbrechen_stoppt_den_lauf(app, monkeypatch):
    """Ohne Verlangsamung ist dieser Test auf einer schnellen Maschine
    unzuverlaessig: der 2000-Stunden-Lauf koennte fertig werden, bevor die
    Abbrechen-Anfrage greift, und der Test wuerde ohne echte Pruefung gruen
    durchlaufen (also 'fertig' statt 'abgebrochen' beobachten, obwohl nie
    getestet wurde, dass der Abbruch wirkt). Jede Stunde bekommt daher 10ms
    Wartezeit dazu; core/solver.py prueft den Abbruch-Merker vor jeder
    Stunde, also greift er schon nach der ersten oder zweiten - weit vor den
    20s, die der volle Lauf ohne Abbruch bei dieser Verlangsamung braeuchte."""
    original = solver.Solver._rechne_stunde

    def langsamer(self, *args, **kwargs):
        time.sleep(0.01)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(solver.Solver, "_rechne_stunde", langsamer)

    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(2000)

    antwort = klient.post(
        "/api/simulation",
        json={"anlage_id": anlage, "wetterdatensatz_id": wetter, "von": 0, "bis": 2000},
    )
    kennung = antwort.get_json()["kennung"]

    abbruch_antwort = klient.post(f"/api/simulation/{kennung}/abbrechen")
    assert abbruch_antwort.status_code == 200
    assert abbruch_antwort.get_json() == {"ok": True}

    for _ in range(400):
        stand = klient.get(f"/api/simulation/{kennung}").get_json()
        if stand["status"] in ("fertig", "abgebrochen", "fehler"):
            break
        time.sleep(0.05)
    assert stand["status"] == "abgebrochen", stand
    assert stand["fertig"] < 2000


def test_api_liefert_die_bilanz(app):
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(24)

    antwort = klient.post(
        "/api/simulation",
        json={"anlage_id": anlage, "wetterdatensatz_id": wetter, "von": 0, "bis": 24},
    )
    kennung = antwort.get_json()["kennung"]

    stand = {}
    for _ in range(200):
        stand = klient.get(f"/api/simulation/{kennung}").get_json()
        if stand["status"] in ("fertig", "fehler"):
            break
        time.sleep(0.05)
    assert stand["status"] == "fertig", stand.get("fehler")

    bilanz_antwort = klient.get(f"/api/simulation/{stand['simulation_id']}/bilanz")
    assert bilanz_antwort.status_code == 200
    daten = bilanz_antwort.get_json()

    groessen = {z["groesse"] for z in daten["bilanz"]}
    assert groessen == {"strom_ht", "strom_nt", "waerme", "kaelte", "wasser"}
    assert len(daten["reihen"]) > 0
    assert {"karte_id", "karte_name", "groesse", "einheit"} <= daten["reihen"][0].keys()


def test_zeile_entsteht_beim_start_nicht_erst_beim_abschluss(app, monkeypatch):
    """Kern der Wiederaufnahme nach einem Neuladen: die 'simulation'-Zeile
    muss schon da sein, waehrend noch gerechnet wird - vorher entstand sie
    erst am Ende (ergebnisse.speichere()), und ein Neuladen waehrend der
    Rechnung fand keine Spur des Laufs."""
    original = solver.Solver._rechne_stunde

    def langsamer(self, *args, **kwargs):
        time.sleep(0.05)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(solver.Solver, "_rechne_stunde", langsamer)

    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(50)
        kennung = laeufe.starte(app, anlage, wetter, 0, 50)

        # Direkt nach starte() - der Hintergrund-Thread rechnet wegen der
        # Verlangsamung garantiert noch, wenn diese Zeile erreicht wird.
        zeile = ergebnisse.laufende_simulation(anlage)
        assert zeile is not None
        assert zeile["kennung"] == kennung
        assert zeile["von_stunde"] == 0
        assert zeile["bis_stunde"] == 50

        db = database.get_db()
        status = db.execute(
            "SELECT status FROM simulation WHERE id = ?", (zeile["id"],)
        ).fetchone()["status"]
        assert status == "laeuft"

        for _ in range(400):
            stand = laeufe.stand(kennung)
            if stand["status"] in ("fertig", "abgebrochen", "fehler"):
                break
            time.sleep(0.05)
        assert stand["status"] == "fertig", stand.get("fehler")

        # Nach dem Abschluss steht der Endstand in derselben Zeile - keine
        # zweite ist entstanden, und laufende_simulation() findet nichts mehr.
        endstatus = db.execute(
            "SELECT status FROM simulation WHERE id = ?", (zeile["id"],)
        ).fetchone()["status"]
        assert endstatus == "fertig"
        assert ergebnisse.laufende_simulation(anlage) is None


def test_laufender_auftrag_ist_je_anlage(app, monkeypatch):
    """Zwei Anlagen rechnen gleichzeitig: laufender_auftrag() einer Anlage
    darf nie den Lauf der jeweils anderen zeigen."""
    original = solver.Solver._rechne_stunde

    def langsamer(self, *args, **kwargs):
        time.sleep(0.05)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(solver.Solver, "_rechne_stunde", langsamer)

    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_a = ax_sim_2_1.baue(projekt, "A")
        anlage_b = ax_sim_2_1.baue(projekt, "B")
        wetter = wetter_anlegen(50)

        kennung_a = laeufe.starte(app, anlage_a, wetter, 0, 50)

        auftrag_a = laeufe.laufender_auftrag(anlage_a)
        assert auftrag_a is not None
        assert auftrag_a["kennung"] == kennung_a
        assert auftrag_a["status"] == "laeuft"
        assert laeufe.laufender_auftrag(anlage_b) is None

        for _ in range(400):
            if laeufe.stand(kennung_a)["status"] in ("fertig", "abgebrochen", "fehler"):
                break
            time.sleep(0.05)


def test_fortschritt_speichern_schreibt_in_die_zeile(app):
    """Die von core.laeufe._laufen() in groesserem Abstand aufgerufene
    Schreibfunktion isoliert getestet, ohne auf den echten Zeitabstand warten
    zu muessen."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(10)
        simulation_id = ergebnisse.beginne(anlage, wetter, 0, 10, "kennung-x")

        ergebnisse.fortschritt_speichern(simulation_id, 4)

        zeile = ergebnisse.laufende_simulation(anlage)
        assert zeile["fortschritt"] == 4


def test_lauf_meldet_fehler_statt_zu_haengen(app):
    """Ein ungueltiger Wetterdatensatz verletzt den FOREIGN-KEY beim Speichern -
    ein echter Fehlerpfad, kein simulierter."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        kennung = laeufe.starte(app, anlage, 999999, 0, 1)

        for _ in range(200):
            stand = laeufe.stand(kennung)
            if stand["status"] in ("fertig", "fehler", "abgebrochen"):
                break
            time.sleep(0.05)

    assert stand["status"] == "fehler"
    assert stand["fehler"]
