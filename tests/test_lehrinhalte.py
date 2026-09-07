"""Der Erklärbereich: Erklärung je Kartentyp, und die Beispielanlagen müssen
sich bauen lassen und tatsächlich rechnen.
"""

from datetime import datetime, timedelta

import pytest

from app import create_app
from core import anlagen, database, solver
from core.bausteine import basis, lade_alle
from core.lehrinhalte import beispielanlagen
from core.lehrinhalte.erklaerungen import ERKLAERUNGEN

lade_alle()


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def _wetterstunden(anzahl):
    # Montag, 01.01.2024 - Index 8..12 faellt in ein Wochenzeitplan-Fenster
    # (Vorgabe 05:00-22:00 werktags), damit die zeitgesteuerten Beispiele
    # tatsaechlich etwas tun.
    start = datetime(2024, 1, 1, 8)
    return [
        {
            "zeitpunkt": start + timedelta(hours=i),
            "t_au": 2.0, "x_au": 3.0,
            "str_s": 120.0, "str_o": 40.0, "str_w": 40.0, "str_n": 10.0, "str_h": 90.0,
        }
        for i in range(anzahl)
    ]


def test_jeder_kartentyp_hat_eine_erklaerung_und_eine_beispielanlage():
    alle_typen = {klasse.KENNUNG for klasse in basis.alle()}
    assert alle_typen == set(ERKLAERUNGEN)
    assert alle_typen == set(beispielanlagen.BAUPLAENE)


@pytest.mark.parametrize("kennung", sorted(beispielanlagen.BAUPLAENE))
def test_beispielanlage_baut_und_rechnet(app, kennung):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Test")
        anlage_id = beispielanlagen.baue_beispiel(kennung, projekt)
        g = anlagen.lade_graph(anlage_id)

        # Muss sich sortieren lassen - keine losen Enden, kein unaufloesbarer Zyklus.
        assert len(g.reihenfolge()) == len(g.karten)

        # Kein Lufteingang darf ohne Quelle bleiben.
        ohne_eingang = [
            k for k in g.karten.values()
            if any(p.art == "luft" and p.richtung == "ein" for p in k.ports)
            and not g.eingaenge_von(k.id)
        ]
        assert ohne_eingang == [], [k.name for k in ohne_eingang]

        lauf = solver.Solver(g).starte(_wetterstunden(4))

    assert len(lauf.stunden) == 4
    # Kein Grenzzyklus. Eine Restabweichung weit unter einem Kelvin ist kein
    # Rechenfehler: MAX_AENDERUNG steht bei 0,001, und die Anlagenpruefung
    # laesst bei den grossen Vorlagen bis 2,0 zu (werkzeuge/plausibilitaet.py,
    # GRENZZYKLUS_SCHWELLE). Von einer Beispielanlage ueber vier Stunden genau
    # null zu verlangen, waere ein strengerer Massstab als der, den echte
    # Anlagen erfuellen muessen - und er haengt an Tausendsteln, die
    # physikalisch nichts bedeuten.
    gross = [w for w in lauf.warnungen if w["abweichung"] > 0.1]
    assert not gross, gross
    assert not lauf.takte, lauf.takte


def test_baue_beispiel_gibt_bestehende_anlage_zurueck_statt_zu_verdoppeln(app):
    """Vor dieser Absicherung legte jeder Aufruf von baue_beispiel() fuer
    denselben Kartentyp eine weitere, identisch benannte Anlage im Projekt
    "Bausteine" an - im echten Projekt lagen deswegen zeitweise neun
    Anlagen fuer sieben Kartentypen, "Anlagenbetrieb" und "Heizungspumpen"
    je zweimal (siehe .superpowers/sdd-Report)."""
    with app.app_context():
        projekt = beispielanlagen.projekt_bausteine()
        erster_aufruf = beispielanlagen.baue_beispiel("erhitzer", projekt)
        zweiter_aufruf = beispielanlagen.baue_beispiel("erhitzer", projekt)
        dritter_aufruf = beispielanlagen.baue_beispiel("erhitzer", projekt)

        assert erster_aufruf == zweiter_aufruf == dritter_aufruf
        anlagen_im_projekt = anlagen.anlagen_von(projekt)
        assert len(anlagen_im_projekt) == 1


def test_baue_beispiel_erkennt_verschiedene_kartentypen_als_verschieden(app):
    with app.app_context():
        projekt = beispielanlagen.projekt_bausteine()
        erhitzer = beispielanlagen.baue_beispiel("erhitzer", projekt)
        kuehler = beispielanlagen.baue_beispiel("kuehler", projekt)

        assert erhitzer != kuehler
        assert len(anlagen.anlagen_von(projekt)) == 2


def test_baue_beispiel_legt_nach_umbenennen_eine_neue_frische_anlage_an(app):
    """Eine per Umbenennen persoenlich gemachte Beispielanlage wird beim
    naechsten Oeffnen des Beispiels nicht angetastet - stattdessen entsteht
    (wieder erkennbar am Vorgabenamen) eine neue, frische Beispielanlage,
    kein stilles Ueberschreiben der eigenen Aenderung."""
    with app.app_context():
        projekt = beispielanlagen.projekt_bausteine()
        erste = beispielanlagen.baue_beispiel("erhitzer", projekt)
        anlagen.anlage_umbenennen(erste, "Meine Fassung des Erhitzers")

        zweite = beispielanlagen.baue_beispiel("erhitzer", projekt)

        assert zweite != erste
        namen = {a["id"]: a["name"] for a in anlagen.anlagen_von(projekt)}
        assert namen[erste] == "Meine Fassung des Erhitzers"
        assert namen[zweite] == "Erhitzer"


def test_erwarteter_name_stimmt_mit_klasse_name_fuer_jeden_kartentyp_ueberein():
    """_erwarteter_name() ist der Wiedererkennungsschluessel fuer
    baue_beispiel() - fuer jeden Kartentyp muss er mit dem Namen
    uebereinstimmen, den die zugehoerige bau_<typ>()-Funktion tatsaechlich
    vergibt (bei der Einfuehrung einzeln nachgerechnet, siehe Kommentar
    dort). Diese Stichprobe deckt nur die Erwartung gegen core.bausteine.basis
    ab, nicht jede der 34 bau_<typ>()-Funktionen einzeln - das leistet
    test_beispielanlage_baut_und_rechnet bereits pro Kartentyp."""
    namen_je_kennung = {klasse.KENNUNG: klasse.NAME for klasse in basis.alle()}
    for kennung in beispielanlagen.BAUPLAENE:
        assert beispielanlagen._erwarteter_name(kennung) == namen_je_kennung[kennung]


def test_name_projekt_stimmt_mit_core_anlagen_lehrmaterial_konstante_ueberein():
    """core.anlagen.NAME_PROJEKT_LEHRMATERIAL ist absichtlich dupliziert
    (Begruendung dort: Zirkelbezug-Vermeidung) - hier gegengeprueft, damit
    ein spaeteres Umbenennen des Sammelprojekts nicht unbemerkt nur eine
    der beiden Stellen trifft und die Startseite die Beispielanlagen dann
    wieder zwischen die eigenen Projekte des Benutzers mischt."""
    assert anlagen.NAME_PROJEKT_LEHRMATERIAL == beispielanlagen.NAME_PROJEKT


def test_erklaerbereich_zeigt_lesbare_anschluesse_und_die_hinweise_der_karten(app):
    """Der Erklärbereich soll dieselben Beschriftungen zeigen wie das
    Parameterfenster - vorher stand hier der rohe Schlüssel ("QH_S – Signal,
    Eingang"), den nur versteht, wer die Excel-Vorlage kennt. Und der
    Erklärsatz eines Parameters (Param.hinweis) gehört auf beide Seiten,
    damit sie nicht auseinanderlaufen."""
    with app.test_client() as klient:
        antwort = klient.get("/api/lehre/bausteine")
    assert antwort.status_code == 200
    eintraege = {e["kennung"]: e for e in antwort.get_json()}

    raum = eintraege["raum"]
    anschluesse = {p["schluessel"]: p["label"] for p in raum["ports"]}
    assert anschluesse["QH_S"] == "Sonneneinstrahlung Süd (W/m²)"
    assert anschluesse["T_Raum"] == "Raumtemperatur (°C)"
    for port in raum["ports"]:
        assert port["label"] and port["label"] != port["schluessel"]

    lastgang = next(
        p for p in eintraege["tageslastprofil"]["parameter"]
        if p["schluessel"] == "lastgang_1"
    )
    assert lastgang["einheit"] == "Anteil 0–1"
    assert "Nennlast" in lastgang["hinweis"]


# ---------- Die Seite liefert ihren Inhalt selbst aus -----------------------
#
# Sie holte ihre Kacheln bis zum Umbau der Oberflaeche erst nach dem Laden
# ueber /api/lehre/bausteine und baute sie im Browser. Bis die Antwort da war,
# stand dort "Bausteine werden geladen ..." - und auf keinem Abzug der Seite
# war ihr eigentlicher Inhalt zu sehen. Die Tests hier beschreiben, was ohne
# ein einziges Stueck JavaScript dastehen muss.


def test_bausteinseite_zeigt_jeden_kartentyp_ohne_javascript(app):
    html = app.test_client().get("/bausteine").get_data(as_text=True)
    for klasse in basis.alle():
        if klasse.KENNUNG not in ERKLAERUNGEN:
            continue
        assert f'id="baustein-{klasse.KENNUNG}"' in html, klasse.KENNUNG
        assert klasse.NAME in html, klasse.KENNUNG


def test_bausteinseite_zeigt_anschluesse_und_parameter_im_klartext(app):
    """Dieselben Beschriftungen wie im Parameterfenster - sie standen bis zum
    Umbau nur in der JSON-Antwort und wurden im Browser zusammengesetzt."""
    html = app.test_client().get("/bausteine").get_data(as_text=True)
    assert "Sonneneinstrahlung Süd (W/m²) – Signal, Eingang" in html
    assert "Raumtemperatur (°C) – Signal, Ausgang" in html
    # Der Erklaersatz eines Parameters (Param.hinweis).
    assert "Nennlast" in html


def test_bausteinseite_hat_ein_gefuelltes_inhaltsverzeichnis(app):
    """Die Sprungmarken im Verzeichnis muessen zu den Abschnitten passen -
    beide entstehen jetzt an derselben Stelle (routes/lehre.py: _anker)."""
    import re

    html = app.test_client().get("/bausteine").get_data(as_text=True)
    verweise = set(re.findall(r'href="#(gruppe-[^"]+)"', html))
    abschnitte = set(re.findall(r'id="(gruppe-[^"]+)"', html))
    assert verweise
    assert verweise == abschnitte


def test_bausteinseite_deaktiviert_den_knopf_ohne_beispielanlage(app):
    """Ein Knopf, der nur absagen kann, wird gar nicht erst angeboten. Ob es
    eine Beispielanlage gibt, weiss der Server - der Browser musste es
    vorher erst aus der JSON-Antwort erfahren."""
    import re

    html = app.test_client().get("/bausteine").get_data(as_text=True)
    for treffer in re.finditer(
        r'<button class="baustein-beispiel-knopf" data-kennung="([^"]+)"([^>]*)>', html
    ):
        kennung, rest = treffer.group(1), treffer.group(2)
        hat_beispiel = kennung in beispielanlagen.BAUPLAENE
        assert ("disabled" in rest) != hat_beispiel, kennung


def test_bausteine_js_baut_die_kacheln_nicht_mehr_selbst():
    """Zwei Wege zu derselben Darstellung waeren zwei Wege, die
    auseinanderlaufen."""
    from pathlib import Path

    quelle = (Path(__file__).parent.parent / "static" / "js" / "bausteine.js").read_text()
    assert "/api/lehre/bausteine`" not in quelle  # das Anlegen bleibt, das Holen nicht
    assert 'fetch("/api/lehre/bausteine")' not in quelle
    assert "createElement" not in quelle
