"""Vergleich mehrerer Wetterjahre derselben Anlage (Vorhaben B).

Unit-Tests fuer core/vergleich.py legen fertige Ergebnisse direkt per
core.ergebnisse.speichere() an (wie tests/test_bilanzansicht.py) - kein Solver-
Lauf noetig, um Bilanz und Abweichung zu pruefen. Die Reihen-Tests (mehrere
Laeufe nacheinander, Fortschritt, Abbruch, ein scheiterndes Jahr) laufen
dagegen ueber die echten Endpunkte, mit sehr kurzen Wetterdatensaetzen
(wenige Stunden) statt eines Jahreslaufs - siehe Aufgabenstellung: "Prüf die
Reihe mit kurzen Ausschnitten über wenige Stunden; das Verhalten ist
dasselbe." Der Solver wird dafuer wie in test_bilanzansicht.py kuenstlich
verlangsamt, wo ein Test etwas mitten im Lauf abfangen muss (Abbruch,
Wiederaufnahme)."""

import time
from datetime import datetime

import pytest

from app import create_app
from core import anlagen, database, ergebnisse, solver, vergleich
from core.vorlagen import ax_sim_2_1
from core.wetter import speicher


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Eigene tmp_path-Datenbank je Test - derselbe Aufbau wie
    tests/test_bilanzansicht.py."""
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def wetter_anlegen(name, anzahl, t_au=5.0, x_au=4.0):
    return speicher.datensatz_anlegen(
        name, "upload",
        [
            {
                "zeitpunkt": datetime(2024, 1, 1, i % 24), "t_au": t_au, "x_au": x_au,
                "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
            }
            for i in range(anzahl)
        ],
    )


def _lauf_speichern(anlage, wetter, graph, waerme, kaelte, warnungen_anzahl=0):
    lauf = solver.Lauf(
        stunden=[{} for _ in range(3)],
        bilanz={"strom_ht": 10.0, "strom_nt": 5.0, "waerme": waerme,
                "kaelte": kaelte, "wasser": 2.0},
        warnungen=[
            {"stunde": n, "zeitpunkt": "", "abweichung": 1.0, "text": "Warnung"}
            for n in range(warnungen_anzahl)
        ],
    )
    return ergebnisse.speichere(anlage, wetter, 0, 3, lauf, graph, dauer=0.1)


# ---------------------------------------------------------------------------
# core.vergleich.vergleichsdaten() / diagramm() - ohne Hintergrund-Thread
# ---------------------------------------------------------------------------

def test_vergleichsdaten_zeigt_bilanz_und_abweichung_gegenueber_dem_ersten_lauf(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        graph = anlagen.lade_graph(anlage)
        kalt = wetter_anlegen("Kalt", 3)
        mild = wetter_anlegen("Mild", 3)
        sim_kalt = _lauf_speichern(anlage, kalt, graph, waerme=1000.0, kaelte=0.0)
        sim_mild = _lauf_speichern(anlage, mild, graph, waerme=500.0, kaelte=0.0)

        daten = vergleich.vergleichsdaten([sim_kalt, sim_mild])

    assert daten["anlage_id"] == anlage
    assert [l["simulation_id"] for l in daten["laeufe"]] == [sim_kalt, sim_mild]
    assert all(l["hat_ergebnis"] for l in daten["laeufe"])

    waerme_zeile = next(z for z in daten["zeilen"] if z["groesse"] == "waerme")
    # Bilanzwerte in core.ergebnisse.BILANZ sind in MWh, Faktor 1/1000 auf die
    # in kWh uebergebene Rohsumme.
    assert waerme_zeile["werte"][0]["menge"] == pytest.approx(1.0)
    assert waerme_zeile["werte"][0]["abweichung"] == pytest.approx(0.0)
    assert waerme_zeile["werte"][1]["menge"] == pytest.approx(0.5)
    assert waerme_zeile["werte"][1]["abweichung"] == pytest.approx(-0.5)


def test_vergleichsdaten_lehnt_verschiedene_anlagen_ab(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_a = ax_sim_2_1.baue(projekt, "A")
        anlage_b = ax_sim_2_1.baue(projekt, "B")
        graph_a = anlagen.lade_graph(anlage_a)
        graph_b = anlagen.lade_graph(anlage_b)
        wetter = wetter_anlegen("W", 3)
        sim_a = _lauf_speichern(anlage_a, wetter, graph_a, waerme=1.0, kaelte=0.0)
        sim_b = _lauf_speichern(anlage_b, wetter, graph_b, waerme=1.0, kaelte=0.0)

        with pytest.raises(vergleich.VergleichNichtMoeglich):
            vergleich.vergleichsdaten([sim_a, sim_b])


def test_vergleichsdaten_leere_auswahl_lehnt_ab(app):
    with app.app_context():
        with pytest.raises(vergleich.VergleichNichtMoeglich):
            vergleich.vergleichsdaten([])


def test_vergleichsdaten_unbekannte_id_wirft_keyerror(app):
    with app.app_context():
        with pytest.raises(KeyError):
            vergleich.vergleichsdaten([999999])


def test_vergleichsdaten_zeigt_was_da_ist_und_benennt_was_fehlt(app):
    """Ein Lauf ohne Ergebnis (hier: noch 'laeuft') bekommt eine leere Bilanz
    statt die ganze Anfrage abzulehnen - core.laeufe._reihe_laufen erzeugt
    fuer ein noch nicht abgeschlossenes Jahr zwar keine solche Zeile, wohl
    aber core.laeufe.starte() fuer einen einzelnen, noch laufenden Lauf; der
    Vergleich muss also so oder so damit umgehen koennen."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        graph = anlagen.lade_graph(anlage)
        wetter_fertig = wetter_anlegen("Fertig", 3)
        wetter_laeuft = wetter_anlegen("Laeuft", 3)
        sim_fertig = _lauf_speichern(anlage, wetter_fertig, graph, waerme=1.0, kaelte=0.0)
        sim_laeuft = ergebnisse.beginne(anlage, wetter_laeuft, 0, 3, "kennung-laeuft")

        daten = vergleich.vergleichsdaten([sim_fertig, sim_laeuft])

    laeuft_eintrag = next(l for l in daten["laeufe"] if l["simulation_id"] == sim_laeuft)
    assert laeuft_eintrag["hat_ergebnis"] is False
    assert laeuft_eintrag["status"] == "laeuft"
    assert laeuft_eintrag["bilanz"] == {}
    waerme_zeile = next(z for z in daten["zeilen"] if z["groesse"] == "waerme")
    assert waerme_zeile["werte"][1]["menge"] is None
    assert waerme_zeile["werte"][1]["abweichung"] is None
    # Der Basislauf selbst hat ein Ergebnis - dessen eigene Abweichung bleibt 0.
    assert waerme_zeile["werte"][0]["abweichung"] == pytest.approx(0.0)


def test_diagramm_liefert_leinwand_mit_werten(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        graph = anlagen.lade_graph(anlage)
        kalt = wetter_anlegen("Kalt", 3)
        mild = wetter_anlegen("Mild", 3)
        sim_kalt = _lauf_speichern(anlage, kalt, graph, waerme=1000.0, kaelte=0.0)
        sim_mild = _lauf_speichern(anlage, mild, graph, waerme=500.0, kaelte=0.0)
        daten = vergleich.vergleichsdaten([sim_kalt, sim_mild])

        leinwand = vergleich.diagramm(daten)

    assert leinwand is not None
    svg = leinwand.als_svg()
    assert "<svg" in svg
    assert "Kalt" in svg and "Mild" in svg


def test_diagramm_ohne_ergebnis_liefert_none(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = wetter_anlegen("Laeuft", 3)
        sim_laeuft = ergebnisse.beginne(anlage, wetter, 0, 3, "kennung-laeuft")
        daten = vergleich.vergleichsdaten([sim_laeuft])

        assert vergleich.diagramm(daten) is None


# ---------------------------------------------------------------------------
# /api/simulation/vergleich(/diagramm.svg) - ueber die Route
# ---------------------------------------------------------------------------

def test_vergleich_endpunkt_liefert_daten(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        graph = anlagen.lade_graph(anlage)
        kalt = wetter_anlegen("Kalt", 3)
        mild = wetter_anlegen("Mild", 3)
        sim_kalt = _lauf_speichern(anlage, kalt, graph, waerme=1000.0, kaelte=0.0)
        sim_mild = _lauf_speichern(anlage, mild, graph, waerme=500.0, kaelte=0.0)

    antwort = app.test_client().get(f"/api/simulation/vergleich?ids={sim_kalt},{sim_mild}")
    assert antwort.status_code == 200
    daten = antwort.get_json()
    assert len(daten["laeufe"]) == 2


def test_vergleich_endpunkt_ohne_ids_meldet_400(app):
    antwort = app.test_client().get("/api/simulation/vergleich")
    assert antwort.status_code == 400


def test_vergleich_endpunkt_ungueltige_ids_meldet_400(app):
    antwort = app.test_client().get("/api/simulation/vergleich?ids=abc")
    assert antwort.status_code == 400


def test_vergleich_endpunkt_unbekannte_id_meldet_404(app):
    antwort = app.test_client().get("/api/simulation/vergleich?ids=999999")
    assert antwort.status_code == 404


def test_vergleich_diagramm_svg_endpunkt(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        graph = anlagen.lade_graph(anlage)
        kalt = wetter_anlegen("Kalt", 3)
        mild = wetter_anlegen("Mild", 3)
        sim_kalt = _lauf_speichern(anlage, kalt, graph, waerme=1000.0, kaelte=0.0)
        sim_mild = _lauf_speichern(anlage, mild, graph, waerme=500.0, kaelte=0.0)

    antwort = app.test_client().get(
        f"/api/simulation/vergleich/diagramm.svg?ids={sim_kalt},{sim_mild}"
    )
    assert antwort.status_code == 200
    assert antwort.content_type.startswith("image/svg+xml")
    assert b"<svg" in antwort.data


# ---------------------------------------------------------------------------
# Reihen: mehrere Laeufe derselben Anlage nacheinander (core/laeufe.py)
# ---------------------------------------------------------------------------

def test_reihe_rechnet_ein_jahr_je_wetterdatensatz(app):
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        kalt = wetter_anlegen("Kalt", 5, t_au=-10.0)
        mild = wetter_anlegen("Mild", 5, t_au=18.0)
        heiss = wetter_anlegen("Heiß", 5, t_au=32.0)

    start = klient.post(
        "/api/simulation/reihe",
        json={"anlage_id": anlage, "wetterdatensatz_ids": [kalt, mild, heiss],
              "von": 0, "bis": 5},
    )
    assert start.status_code == 202
    reihen_kennung = start.get_json()["reihen_kennung"]

    stand = {}
    for _ in range(400):
        stand = klient.get(f"/api/simulation/reihe/{reihen_kennung}").get_json()
        if stand["status"] in ("fertig", "abgebrochen"):
            break
        time.sleep(0.02)

    assert stand["status"] == "fertig", stand
    assert stand["jahr_gesamt"] == 3
    assert stand["jahr_index"] == 3
    assert len(stand["ergebnisse"]) == 3
    assert all(e["status"] == "fertig" for e in stand["ergebnisse"])
    assert {e["wetterdatensatz_id"] for e in stand["ergebnisse"]} == {kalt, mild, heiss}

    # Jedes Jahr ist eine ganz normale, eigene 'simulation'-Zeile - fuer den
    # Dialog "Fruehere Laeufe" und die Loeschsperre (core.wetter.speicher.
    # datensatz_loeschen) automatisch mit, ohne eigenen Code dafuer.
    liste = klient.get(f"/api/anlagen/{anlage}/simulationen").get_json()
    assert len(liste) == 3

    ids = [e["simulation_id"] for e in stand["ergebnisse"]]
    vergleich_antwort = klient.get(f"/api/simulation/vergleich?ids={','.join(map(str, ids))}")
    assert vergleich_antwort.status_code == 200
    assert len(vergleich_antwort.get_json()["laeufe"]) == 3


def test_reihe_laufend_endpunkt_ermoeglicht_wiederaufnahme(app, monkeypatch):
    """Simuliert ein Neuladen der Seite mitten in der Reihe: die Editorseite
    kennt nach einem Neuladen keine Reihen-Kennung mehr - genau dafuer liest
    /api/simulation/reihe/laufend/<anlage_id> aus der Datenbank, welche Reihe
    gerade laeuft (core.ergebnisse.laufende_reihe/core.laeufe.
    laufende_reihe_auftrag)."""
    original = solver.Solver._rechne_stunde

    def langsamer(self, *args, **kwargs):
        time.sleep(0.03)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(solver.Solver, "_rechne_stunde", langsamer)

    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        j1 = wetter_anlegen("J1", 30)
        j2 = wetter_anlegen("J2", 30)

    # Vor dem Start: kein Neuladen findet eine laufende Reihe.
    assert klient.get(f"/api/simulation/reihe/laufend/{anlage}").get_json() is None

    start = klient.post(
        "/api/simulation/reihe",
        json={"anlage_id": anlage, "wetterdatensatz_ids": [j1, j2], "von": 0, "bis": 30},
    )
    reihen_kennung = start.get_json()["reihen_kennung"]

    laufend = None
    for _ in range(200):
        laufend = klient.get(f"/api/simulation/reihe/laufend/{anlage}").get_json()
        if laufend is not None:
            break
        time.sleep(0.02)
    assert laufend is not None
    assert laufend["reihen_kennung"] == reihen_kennung
    assert laufend["status"] == "laeuft"
    assert laufend["jahr_gesamt"] == 2

    for _ in range(400):
        stand = klient.get(f"/api/simulation/reihe/{reihen_kennung}").get_json()
        if stand["status"] in ("fertig", "abgebrochen"):
            break
        time.sleep(0.02)
    assert stand["status"] == "fertig"

    # Nach dem Ende meldet der Wiederaufnahme-Endpunkt wieder 'null'.
    assert klient.get(f"/api/simulation/reihe/laufend/{anlage}").get_json() is None


def test_reihe_abbruch_verhindert_auch_noch_nicht_begonnene_jahre(app, monkeypatch):
    """Kern der Handpruefung fuer die Reihe: Abbrechen beendet nicht nur das
    laufende Jahr, sondern verhindert auch, dass die Reihe mit dem naechsten
    weitermacht."""
    original = solver.Solver._rechne_stunde

    def langsamer(self, *args, **kwargs):
        time.sleep(0.02)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(solver.Solver, "_rechne_stunde", langsamer)

    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        ids = [wetter_anlegen(f"J{n}", 300) for n in range(3)]

    start = klient.post(
        "/api/simulation/reihe",
        json={"anlage_id": anlage, "wetterdatensatz_ids": ids, "von": 0, "bis": 300},
    )
    reihen_kennung = start.get_json()["reihen_kennung"]

    # Kurz warten, damit das erste Jahr sicher schon laeuft (nicht schon
    # fertig ist - 300 Stunden a 20ms sind 6s, viel Sicherheitsabstand).
    time.sleep(0.2)
    zwischenstand = klient.get(f"/api/simulation/reihe/{reihen_kennung}").get_json()
    assert zwischenstand["status"] == "laeuft"
    assert zwischenstand["jahr_index"] == 1

    abbruch = klient.post(f"/api/simulation/reihe/{reihen_kennung}/abbrechen")
    assert abbruch.status_code == 200

    stand = {}
    for _ in range(400):
        stand = klient.get(f"/api/simulation/reihe/{reihen_kennung}").get_json()
        if stand["status"] in ("fertig", "abgebrochen"):
            break
        time.sleep(0.05)

    assert stand["status"] == "abgebrochen", stand
    # Nur das erste (abgebrochene) Jahr hat ueberhaupt begonnen - Jahr 2 und
    # 3 duerfen keine Spur hinterlassen haben.
    assert len(stand["ergebnisse"]) == 1
    assert stand["ergebnisse"][0]["status"] == "abgebrochen"
    with app.app_context():
        liste = ergebnisse.simulationen_von(anlage)
    assert len(liste) == 1


def test_reihe_ein_scheiterndes_jahr_stoppt_die_uebrigen_nicht(app):
    """'Scheitert ein Jahr, duerfen die uebrigen nicht mit untergehen' -
    ein nicht existierender Wetterdatensatz mitten in der Auswahl darf die
    Reihe nicht abreissen lassen."""
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        j1 = wetter_anlegen("J1", 5)
        j3 = wetter_anlegen("J3", 5)
    unbekannt = 987654321

    start = klient.post(
        "/api/simulation/reihe",
        json={"anlage_id": anlage, "wetterdatensatz_ids": [j1, unbekannt, j3],
              "von": 0, "bis": 5},
    )
    assert start.status_code == 202
    reihen_kennung = start.get_json()["reihen_kennung"]

    stand = {}
    for _ in range(400):
        stand = klient.get(f"/api/simulation/reihe/{reihen_kennung}").get_json()
        if stand["status"] in ("fertig", "abgebrochen"):
            break
        time.sleep(0.02)

    assert stand["status"] == "fertig", stand
    assert len(stand["ergebnisse"]) == 3
    nach_datensatz = {e["wetterdatensatz_id"]: e for e in stand["ergebnisse"]}
    assert nach_datensatz[j1]["status"] == "fertig"
    assert nach_datensatz[j3]["status"] == "fertig"
    assert nach_datensatz[unbekannt]["status"] == "fehler"
    assert nach_datensatz[unbekannt]["simulation_id"] is None
    assert "gibt es nicht" in nach_datensatz[unbekannt]["fehler"]

    # Der Vergleich zeigt, was da ist (die beiden gelungenen Jahre).
    gelungene_ids = [
        e["simulation_id"] for e in stand["ergebnisse"] if e["simulation_id"]
    ]
    assert len(gelungene_ids) == 2
    vergleich_antwort = klient.get(
        f"/api/simulation/vergleich?ids={','.join(map(str, gelungene_ids))}"
    )
    assert vergleich_antwort.status_code == 200
    assert len(vergleich_antwort.get_json()["laeufe"]) == 2


def test_reihe_startet_ohne_wetterdatensaetze_meldet_400(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")

    antwort = app.test_client().post(
        "/api/simulation/reihe", json={"anlage_id": anlage, "wetterdatensatz_ids": []}
    )
    assert antwort.status_code == 400


def test_wetterdatensatz_einer_reihe_laesst_sich_nicht_loeschen(app):
    """Ein Wetterdatensatz, der von einem Lauf benutzt wird, laesst sich
    nicht loeschen (core.wetter.speicher.datensatz_loeschen) - gilt
    unveraendert auch fuer ein Jahr, das ueber eine Reihe entstanden ist:
    jedes Jahr ist eine ganz normale 'simulation'-Zeile (siehe
    test_reihe_rechnet_ein_jahr_je_wetterdatensatz), die Sperre prueft nur
    darauf, nicht auf reihen_kennung."""
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        j1 = wetter_anlegen("J1", 3)
        j2 = wetter_anlegen("J2", 3)

    start = klient.post(
        "/api/simulation/reihe",
        json={"anlage_id": anlage, "wetterdatensatz_ids": [j1, j2], "von": 0, "bis": 3},
    )
    reihen_kennung = start.get_json()["reihen_kennung"]
    for _ in range(400):
        stand = klient.get(f"/api/simulation/reihe/{reihen_kennung}").get_json()
        if stand["status"] in ("fertig", "abgebrochen"):
            break
        time.sleep(0.02)
    assert stand["status"] == "fertig"

    with app.app_context():
        with pytest.raises(ValueError):
            speicher.datensatz_loeschen(j1)
