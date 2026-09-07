"""Der Anlagenkatalog - die Seite, auf der die Vorlagen überhaupt sichtbar sind.

Zwölf fertig verdrahtete Anlagen liegen dem Programm bei, jede mit einer im
Quelltext vorgerechneten Auslegung und geprüften Erwartungsbändern. Zu finden
waren sie bisher ausschließlich als Auswahlknöpfe in einem Dialog, den man
erst erreicht, wenn man schon ein Projekt angelegt hat - wer die Anwendung zum
ersten Mal öffnete, sah von ihnen nichts und musste im Quelltext nachsehen.

Diese Tests halten fest, dass sie sichtbar bleiben: die Seite selbst, die
Daten dahinter, und der Weg dorthin von jeder anderen Seite aus.
"""

import pytest

from app import create_app
from core import database, vorlagen


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


@pytest.fixture
def klient(app):
    return app.test_client()


def test_die_katalogseite_gibt_es(klient):
    antwort = klient.get("/anlagen")
    assert antwort.status_code == 200
    html = antwort.get_data(as_text=True)
    assert 'id="feld-suche"' in html, "keine Suche"
    assert "js/anlagen.js" in html, "das Verhalten der Seite fehlt"

    # Der Inhalt steht IM HTML, nicht erst nach einem Abruf: Er ist bei jedem
    # Aufruf derselbe, und eine Seite, die erst nach zwei Umläufen etwas
    # zeigt, ist für feststehende Daten der falsche Bau (siehe
    # routes/katalog.py).
    assert html.count('class="katalog-karte"') == len(vorlagen.VORLAGEN)
    assert "Bürogebäude" in html
    assert "Auslegung und geprüfte Bänder" in html


def test_jede_seite_fuehrt_zu_jeder_anderen(klient):
    """Die Hauptnavigation steht auf allen drei Seiten - und zwar überall
    dieselbe. Vorher trug jede Seite ihre eigene Kopfleiste, und von der
    Bausteinseite kam man nur über den Umweg über die Startseite weiter."""
    for pfad in ("/", "/anlagen", "/bausteine"):
        html = klient.get(pfad).get_data(as_text=True)
        assert 'class="hauptweg"' in html, f"{pfad}: keine Hauptnavigation"
        for ziel in ('href="/"', 'href="/anlagen"', 'href="/bausteine"'):
            assert ziel in html, f"{pfad}: Weg zu {ziel} fehlt"


def test_die_seite_sagt_wo_man_ist(klient):
    """Genau ein Eintrag ist hervorgehoben, und er trägt aria-current - sonst
    nennt ein Screenreader ihn nicht als den aktuellen."""
    for pfad, wort in (("/", "Start"), ("/anlagen", "Anlagen"),
                       ("/bausteine", "Bausteine")):
        html = klient.get(pfad).get_data(as_text=True)
        assert html.count("ist-hier") == 1, f"{pfad}: nicht genau ein Eintrag aktiv"
        assert html.count('aria-current="page"') == 1, f"{pfad}: ohne aria-current"
        stelle = html.index("ist-hier")
        assert wort in html[stelle:stelle + 200], f"{pfad}: der falsche Eintrag"


def test_die_auskunft_traegt_alles_was_der_katalog_zeigt(klient):
    daten = klient.get("/api/vorlagen").get_json()
    assert len(daten) == len(vorlagen.VORLAGEN)
    for kennung, v in daten.items():
        for feld in ("name", "gruppe", "beschreibung", "einleitung",
                     "auslegung", "erwartung"):
            assert feld in v, f"{kennung}: {feld} fehlt"


def test_jede_echte_anlage_bringt_ihre_auslegung_mit(klient):
    """Die Auslegung wird aus dem Kopfkommentar gelesen (core/vorlagen/
    __init__.py, _auslegung). Bleibt sie leer, ist entweder der Kommentar
    umgebaut worden oder der Leser kaputt - und die Katalogseite zeigte
    stillschweigend eine leere Klappe."""
    daten = klient.get("/api/vorlagen").get_json()
    ohne = [
        k for k, v in daten.items()
        if v["gruppe"] != "Referenz" and len(v["auslegung"]) < 4
    ]
    assert not ohne, f"ohne (ausreichende) Auslegung: {sorted(ohne)}"

    # Und die Angaben tragen wirklich etwas: Stichwort und mindestens eine Zeile.
    for kennung, v in daten.items():
        for angabe in v["auslegung"]:
            assert angabe["stichwort"], f"{kennung}: Angabe ohne Stichwort"
            assert any(z.strip() for z in angabe["zeilen"]), (
                f"{kennung}/{angabe['stichwort']}: Angabe ohne Inhalt"
            )


def test_die_eckdaten_stimmen_mit_der_anlage_ueberein(klient):
    """Fläche, Luftmenge und der daraus gerechnete Luftwechsel - dieselben
    Zahlen, gegen die werkzeuge/anlagenpruefung.py die Anlage prüft."""
    daten = klient.get("/api/vorlagen").get_json()
    for kennung, v in daten.items():
        if v["gruppe"] == "Referenz":
            continue
        assert v["flaeche_m2"] and v["luftmenge_m3h"] and v["hoehe_m"], kennung
        erwartet = v["luftmenge_m3h"] / (v["flaeche_m2"] * v["hoehe_m"])
        assert v["luftwechsel_1h"] == pytest.approx(erwartet)


def test_jede_anlage_gehoert_zu_einer_gruppe(klient):
    """Zwölf Karten in einer Reihe sind kein Katalog. Die Gruppen bleiben
    wenige - eine Gruppe je Anlage wäre dieselbe Reihe mit Überschriften."""
    daten = klient.get("/api/vorlagen").get_json()
    gruppen = {v["gruppe"] for v in daten.values()}
    assert gruppen, "keine Gruppen"
    assert len(gruppen) <= 5, f"zu viele Gruppen zum Gliedern: {sorted(gruppen)}"
    for kennung, v in daten.items():
        assert v["gruppe"], f"{kennung}: ohne Gruppe"


def test_aus_dem_katalog_laesst_sich_eine_anlage_uebernehmen(klient):
    """Der Weg, um dessentwillen die Seite da ist: Vorlage aussuchen, in ein
    Projekt legen, im Editor weiterbauen."""
    projekt = klient.post("/api/projekte", json={"name": "Katalogprobe"}).get_json()
    antwort = klient.post(
        "/api/anlagen/aus_vorlage",
        json={"projekt_id": projekt["id"], "vorlage": "buero", "name": "Übernommen"},
    )
    assert antwort.status_code in (200, 201), antwort.get_data(as_text=True)
    anlage = antwort.get_json()
    assert klient.get(f"/anlage/{anlage['id']}").status_code == 200

    # Und sie steht wirklich als eigene Anlage im Projekt - eine Kopie, die
    # sich frei ändern lässt; die Vorlage bleibt, wie sie ist.
    anlagen = klient.get(f"/api/anlagen?projekt_id={projekt['id']}").get_json()
    assert [a["name"] for a in anlagen] == ["Übernommen"]
