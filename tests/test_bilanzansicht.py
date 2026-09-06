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


def wetter_anlegen(anzahl):
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


def test_simulationen_einer_anlage_werden_gelistet(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(1)
        graph = anlagen.lade_graph(anlage)
        lauf = solver.Lauf(
            stunden=[{}],
            bilanz={"strom_ht": 0.0, "strom_nt": 1000.0, "waerme": 0.0,
                    "kaelte": 0.0, "wasser": 0.0},
            warnungen=[],
        )
        ergebnisse.speichere(anlage, wetter, 0, 1, lauf, graph, dauer=0.1)

    antwort = app.test_client().get(f"/api/anlagen/{anlage}/simulationen")
    assert antwort.status_code == 200
    liste = antwort.get_json()
    assert len(liste) == 1
    assert liste[0]["wetter_name"] == "Test"
    assert liste[0]["kosten_gesamt"] == pytest.approx(150.0)


def test_simulationen_liste_kennzeichnet_einen_laufenden_eintrag(app, monkeypatch):
    """Randfall aus der Aufgabenstellung: 'Fruehere Laeufe' zeigt jetzt auch
    laufende Eintraege - status und kennung muessen das erkennbar machen,
    statt wie ein Lauf mit Nullwerten fertig auszusehen (das Aussehen selbst
    ist Sache von static/js/simulation.js._fruehereLaeufeHtml)."""
    original = solver.Solver._rechne_stunde

    def langsamer(self, *args, **kwargs):
        time.sleep(0.05)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(solver.Solver, "_rechne_stunde", langsamer)

    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(50)

    antwort = klient.post(
        "/api/simulation",
        json={"anlage_id": anlage, "wetterdatensatz_id": wetter, "von": 0, "bis": 50},
    )
    kennung = antwort.get_json()["kennung"]

    liste = klient.get(f"/api/anlagen/{anlage}/simulationen").get_json()
    assert len(liste) == 1
    assert liste[0]["status"] == "laeuft"
    assert liste[0]["kennung"] == kennung
    # Noch keine Bilanz vorhanden - kosten_gesamt faellt auf 0.0 zurueck, aber
    # status+kennung sagen dem Client, dass das "0.00 EUR" nicht bedeutet.
    assert liste[0]["kosten_gesamt"] == 0.0

    for _ in range(400):
        if klient.get(f"/api/simulation/{kennung}").get_json()["status"] in (
            "fertig", "abgebrochen", "fehler",
        ):
            break
        time.sleep(0.05)

    liste = klient.get(f"/api/anlagen/{anlage}/simulationen").get_json()
    assert liste[0]["status"] == "fertig"


def test_laufende_simulation_endpunkt_ohne_lauf_meldet_null(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")

    antwort = app.test_client().get(f"/api/anlagen/{anlage}/laufende_simulation")
    assert antwort.status_code == 200
    assert antwort.get_json() is None


def test_laufende_simulation_endpunkt_deckt_die_ganze_wiederaufnahme_ab(app, monkeypatch):
    """Genau der Ablauf aus der Aufgabenstellung: Lauf starten, Zeile lesen
    (hier ueber den Endpunkt, den die Editorseite nach einem Neuladen
    abfragt), Abbruch ueber die Schnittstelle, Endstand pruefen."""
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

    start = klient.post(
        "/api/simulation",
        json={"anlage_id": anlage, "wetterdatensatz_id": wetter, "von": 0, "bis": 2000},
    )
    kennung = start.get_json()["kennung"]

    # "Laeuft fuer diese Anlage gerade etwas, und unter welchem Schluessel?"
    laufend = klient.get(f"/api/anlagen/{anlage}/laufende_simulation").get_json()
    assert laufend is not None
    assert laufend["kennung"] == kennung
    assert laufend["status"] == "laeuft"
    assert laufend["gesamt"] == 2000

    abbruch = klient.post(f"/api/simulation/{kennung}/abbrechen")
    assert abbruch.status_code == 200

    stand = {}
    for _ in range(400):
        stand = klient.get(f"/api/simulation/{kennung}").get_json()
        if stand["status"] in ("fertig", "abgebrochen", "fehler"):
            break
        time.sleep(0.05)
    assert stand["status"] == "abgebrochen", stand
    assert stand["fertig"] < 2000

    # Endstand: die Zeile ist nicht mehr 'laeuft', der Endpunkt meldet wieder
    # 'null' fuer diese Anlage - und die Bilanz (ueber die simulation_id aus
    # dem letzten stand()) ist trotz des Abbruchs abrufbar.
    assert klient.get(f"/api/anlagen/{anlage}/laufende_simulation").get_json() is None
    bilanz = klient.get(f"/api/simulation/{stand['simulation_id']}/bilanz")
    assert bilanz.status_code == 200


def test_schnellwahlen_treffen_die_richtigen_stunden(app):
    """Die Bereiche entsprechen den Schaltflaechen der Excel (Tabelle1)."""
    from routes.simulation import SCHNELLWAHL

    assert SCHNELLWAHL["jahr"] == (0, 8760)
    assert SCHNELLWAHL["kalter_tag"] == (815, 839)
    assert SCHNELLWAHL["heisser_tag"] == (5855, 5879)
    assert SCHNELLWAHL["feuchter_tag"] == (5375, 5399)


def test_schnellwahl_endpunkt_liefert_die_bereiche(app):
    antwort = app.test_client().get("/api/simulation/schnellwahl")
    assert antwort.status_code == 200
    daten = antwort.get_json()
    assert daten["jahr"] == {"von": 0, "bis": 8760}
    assert daten["kalter_tag"] == {"von": 815, "bis": 839}


def test_bilanz_endpunkt_liefert_warnungen_und_kartenwerte(app):
    """Die Bilanz-Antwort traegt Zahl+Beispiele der Konvergenzwarnungen (nie
    die volle Liste - siehe core/ergebnisse.lade_warnungen) sowie die letzten
    Kartenwerte, damit die Leinwand sie nach dem Lauf anzeigen kann."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(3)
        graph = anlagen.lade_graph(anlage)
        warnungen = [
            {"stunde": n, "zeitpunkt": "", "abweichung": 1.0, "text": f"Warnung {n}"}
            for n in range(1, 21)
        ]
        lauf = solver.Lauf(
            stunden=[{1: {"T_aus": float(n)}} for n in range(3)],
            bilanz={"strom_ht": 0.0, "strom_nt": 0.0, "waerme": 0.0,
                    "kaelte": 0.0, "wasser": 0.0},
            warnungen=warnungen,
        )
        sim = ergebnisse.speichere(anlage, wetter, 0, 3, lauf, graph, dauer=0.1)

    antwort = app.test_client().get(f"/api/simulation/{sim}/bilanz")
    assert antwort.status_code == 200
    daten = antwort.get_json()

    assert daten["warnungen"]["anzahl"] == 20
    # Nie die volle Liste an den Client - ergebnisse.lade_warnungen() begrenzt
    # auf 5 Beispiele, egal wie viele Warnungen es insgesamt gibt.
    assert len(daten["warnungen"]["beispiele"]) == 5
    assert all("text" in w for w in daten["warnungen"]["beispiele"])

    assert daten["werte"]["1"]["T_aus"] == pytest.approx(2.0)


def test_bilanz_ohne_warnungen_meldet_zahl_null(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(1)
        graph = anlagen.lade_graph(anlage)
        lauf = solver.Lauf(
            stunden=[{}],
            bilanz={"strom_ht": 0.0, "strom_nt": 0.0, "waerme": 0.0,
                    "kaelte": 0.0, "wasser": 0.0},
            warnungen=[],
        )
        sim = ergebnisse.speichere(anlage, wetter, 0, 1, lauf, graph, dauer=0.1)

    daten = app.test_client().get(f"/api/simulation/{sim}/bilanz").get_json()
    # Konvergenzwarnungen und taktende Stunden, je mit Zahl und Stichprobe,
    # dazu die Zahl der gemittelten Stundenwerte (core/ergebnisse.py,
    # lade_warnungen).
    assert daten["warnungen"] == {
        "anzahl": 0, "beispiele": [], "takte": 0, "takt_beispiele": [],
        "gemittelt": 0,
    }


def test_abbrechen_liefert_weniger_stunden_als_angefordert(app, monkeypatch):
    """Kern der Handpruefung: 'Abbrechen' beendet den Lauf wirklich, statt nur
    ein Merkmal zu setzen, das erst am Ende beachtet wird.

    Ohne Verlangsamung waere dieser Test auf einer schnellen Maschine
    unzuverlaessig: der 3000-Stunden-Lauf koennte fertig werden, bevor die
    Abbrechen-Anfrage greift, und der Test wuerde ohne echte Pruefung gruen
    durchlaufen. Jede Stunde bekommt daher 10ms Wartezeit dazu - bei 3000
    Stunden waeren das 30s, wenn nie abgebrochen wuerde; der Abbruch greift
    aber schon nach der ersten oder zweiten Stunde, weil core/solver.py den
    Abbruch-Merker vor jeder Stunde prueft. Das macht den Test deterministisch
    mit sehr grossem Sicherheitsabstand, ohne die Anwendung selbst zu aendern."""
    original = solver.Solver._rechne_stunde

    def langsamer(self, *args, **kwargs):
        time.sleep(0.01)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(solver.Solver, "_rechne_stunde", langsamer)

    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen(3000)

    antwort = klient.post(
        "/api/simulation",
        json={"anlage_id": anlage, "wetterdatensatz_id": wetter, "von": 0, "bis": 3000},
    )
    kennung = antwort.get_json()["kennung"]

    abbruch = klient.post(f"/api/simulation/{kennung}/abbrechen")
    assert abbruch.status_code == 200

    stand = {}
    for _ in range(400):
        stand = klient.get(f"/api/simulation/{kennung}").get_json()
        if stand["status"] in ("fertig", "abgebrochen", "fehler"):
            break
        time.sleep(0.05)

    assert stand["status"] == "abgebrochen", stand
    assert stand["fertig"] < 3000
