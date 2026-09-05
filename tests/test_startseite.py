"""Tests fuer die ueberarbeitete Eingangsseite (templates/index.html,
static/js/start.js, static/css/start.css) - eigene Datei statt Erweiterung
von tests/test_pages.py, weil dort parallel am Editor gearbeitet wird und
diese Datei ausschliesslich den Aufgabenbereich der Eingangsseite abdeckt.

Wie an anderer Stelle im Projekt ueblich (siehe z.B.
tests/test_pages.py::test_palette_js_bewaffnet_nur_bei_finger_nicht_bei_maus)
wird JavaScript-Verhalten, das kein Browser-Test hier ausfuehren kann, durch
Ausschneiden der betreffenden Funktion aus dem Quelltext und Pruefen ihres
Wortlauts abgesichert - kein Ersatz fuer einen echten Browser, aber mehr als
nichts."""

import re
from pathlib import Path

import pytest

from app import create_app
from core import database

START_JS = (Path(__file__).parent.parent / "static" / "js" / "start.js").read_text()
BERICHT_PY = (Path(__file__).parent.parent / "core" / "bericht.py").read_text()


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def test_startseite_bindet_eigenes_stylesheet_ein(app):
    """Ohne dieses Tag bleiben Einstiegskasten, Gewichtung von Projekte vs.
    Wetterdaten und die zweite Statuszeile der Anlage-Karte unformatiert
    (siehe Kommentar in start.css, weshalb es eine eigene Datei statt
    style.css ist)."""
    klient = app.test_client()
    html = klient.get("/").get_data(as_text=True)
    assert "css/start.css" in html


def test_startseite_hat_einen_einstiegs_behaelter(app):
    """start.js fuellt diesen Behaelter nur beim allerersten Besuch (siehe
    Start.zeichneEinstieg()) - ohne ihn in der Vorlage laeuft das Fuellen
    stillschweigend ins Leere."""
    klient = app.test_client()
    html = klient.get("/").get_data(as_text=True)
    assert 'id="start-einstieg"' in html


def test_startseite_stellt_online_abrufen_vor_die_datei_hochladen(app):
    """Online abrufen ist der bequemere, empfohlene Weg (Task, Befund 4) -
    er muss im Markup vor dem Upload-Weg stehen, nicht nur optisch groesser
    wirken, sonst liest ihn eine Vorlesesoftware in der falschen
    Reihenfolge vor."""
    klient = app.test_client()
    html = klient.get("/").get_data(as_text=True)
    # Auf die id statt auf die Beschriftung: der Wortlaut hat sich mit dem
    # Ordner-Upload schon einmal geaendert ("Datei" -> "Dateien"), die
    # Reihenfolge der beiden Wege ist aber genau das, was hier zaehlt.
    assert html.index("Online abrufen") < html.index('id="wetter-upload-details"')


def test_startseite_datei_hochladen_ist_eingeklappt(app):
    """Der Sonderfall (eigene TRY-Datei) sitzt in einem <details>, das ohne
    ausdruecklichen Klick geschlossen bleibt - kein "open"-Attribut auf dem
    Element selbst."""
    klient = app.test_client()
    html = klient.get("/").get_data(as_text=True)
    start = html.index('id="wetter-upload-details"')
    tag_ende = html.index(">", start)
    element_tag = html[max(0, start - 20) : tag_ende]
    assert "open" not in element_tag
    assert 'id="form-wetter-upload"' in html


def test_startseite_enthaelt_weiterhin_das_upload_formular(app):
    """Der Umbau (Online abrufen zuerst, Upload eingeklappt) darf die
    Upload-Felder selbst nicht verlieren - start.js bindet sich weiterhin
    an dieselben ids."""
    klient = app.test_client()
    html = klient.get("/").get_data(as_text=True)
    assert 'id="feld-wetter-datei"' in html
    assert 'id="btn-wetter-hochladen"' in html


def test_startseite_hat_einen_eingeklappten_lehrmaterial_behaelter(app):
    """Beispielanlagen (core.lehrinhalte.beispielanlagen) sind Lehrmaterial,
    kein Arbeitsergebnis des Benutzers (Task-Rueckmeldung) - eigenes,
    serverseitig verstecktes <details>, das start.js erst einblendet, wenn
    es tatsaechlich eine Beispielanlage gibt (siehe zeichneLehrmaterial())."""
    klient = app.test_client()
    html = klient.get("/").get_data(as_text=True)
    start = html.index('id="start-lehrmaterial"')
    tag_ende = html.index(">", start)
    element_tag = html[max(0, start - 20) : tag_ende]
    assert "hidden" in element_tag
    assert 'id="start-lehrmaterial-inhalt"' in html


def test_start_js_einstiegskasten_verschwindet_sobald_ein_projekt_existiert():
    """Der Kasten ist nur fuer den allerersten Besuch gedacht (Task, Befund
    1) - sobald ein Projekt existiert, beantworten die eigentlichen
    Projekt-/Anlagenkarten schon "was ist der naechste Schritt", ein
    dauerhafter Kasten waere nur noch Wiederholung."""
    funktion = START_JS[START_JS.index("zeichneEinstieg() {") :]
    funktion = funktion[: funktion.index("\n  },")]
    assert "if (this.eigeneProjekte().length) return;" in funktion


def test_start_js_einstiegsschritte_stehen_in_der_richtigen_reihenfolge():
    """Wetter vor Anlage vor Rechnen (Task, Befund 1) - unabhaengig davon,
    dass die Abschnitte darunter nach Bedeutung sortiert sind (Projekte vor
    Wetterdaten, siehe static/css/start.css)."""
    funktion = START_JS[START_JS.index("zeichneEinstieg() {") :]
    funktion = funktion[: funktion.index("\n  },")]
    assert (
        funktion.index("Wetterdaten holen")
        < funktion.index("Projekt und Anlage anlegen")
        < funktion.index("Rechnen lassen")
    )


def test_start_js_anlage_karte_zeigt_datum_und_wetterjahr_des_letzten_laufs():
    """Bislang stand bei einem abgeschlossenen Lauf nur der Kostenwert auf
    der Karte (Task, Befund 3: "Eine Anlage sagt nichts ueber sich") - jetzt
    zusaetzlich, wann zuletzt gerechnet wurde und mit welchem
    Wetterdatensatz."""
    funktion = START_JS[START_JS.index("_fuelleStatus(badge, status) {") :]
    funktion = funktion[: funktion.index("\n  },")]
    assert "anlage-status-neben" in funktion
    assert "formatDatum(status.letzter.gestartet_am)" in funktion
    assert "status.letzter.wetter_name" in funktion
    # Ueber textContent gesetzt statt innerHTML - wetter_name ist ein frei
    # vergebener Name (Umbenennen/Abruf), htmlSicher() waere sonst noetig
    # (siehe Kommentar am Kopf von start.js).
    assert ".textContent = `${formatDatum" in funktion


def test_start_js_formatdatum_liest_nur_den_kalendertag_aus():
    """gestartet_am kommt als 'YYYY-MM-DD HH:MM:SS' aus core/database.py
    (datetime('now'), UTC) - formatDatum() darf daraus keinen JS-Date
    bauen, dessen Zeitzonenumrechnung das Datum verschieben koennte."""
    funktion = START_JS[START_JS.index("function formatDatum(") :]
    funktion = funktion[: funktion.index("\n}")]
    assert "new Date(" not in funktion
    # Stichprobe direkt am regulaeren Ausdruck der Funktion.
    assert "(\\d{4})-(\\d{2})-(\\d{2})" in funktion


def test_start_js_berichtlink_nur_bei_laeufen_mit_ergebnis():
    """Ein Bericht ist nur zu einem 'fertig'- oder 'abgebrochen'-Lauf
    verfuegbar (core/bericht.py: STATUS_MIT_ERGEBNIS) - bei 'fehler' oder
    'laeuft' fuehrt der Link ins Leere (core.bericht.BerichtNichtVerfuegbar).
    Diese Liste ist absichtlich dupliziert (wie WETTER_FRUEHESTES_JAHR
    weiter oben in start.js), deshalb hier gegen core/bericht.py
    gegengeprueft, damit ein spaeteres Aendern der einen Seite nicht
    unbemerkt von der anderen abweicht."""
    zeile = START_JS[START_JS.index("const STATUS_MIT_BERICHT = ") :]
    zeile = zeile[: zeile.index(";")]
    js_werte = re.findall(r'"([^"]+)"', zeile)

    py_zeile = BERICHT_PY[BERICHT_PY.index("STATUS_MIT_ERGEBNIS = ") :]
    py_zeile = py_zeile[: py_zeile.index("\n")]
    py_werte = re.findall(r'"([^"]+)"', py_zeile)

    assert js_werte == py_werte
    assert js_werte == ["fertig", "abgebrochen"]


def test_start_js_einstiegskasten_zaehlt_nur_eigene_projekte():
    """Ein Benutzer, der noch nie ein eigenes Projekt angelegt, aber schon
    einmal eine Beispielanlage unter /bausteine geoeffnet hat, soll den
    Einstiegskasten weiterhin sehen - das automatisch entstandene
    "Bausteine"-Projekt zaehlt dafuer nicht als eigenes."""
    funktion = START_JS[START_JS.index("zeichneEinstieg() {") :]
    funktion = funktion[: funktion.index("\n  },")]
    assert "this.eigeneProjekte().length" in funktion


def test_start_js_lehrmaterial_bleibt_versteckt_ohne_beispielanlage():
    funktion = START_JS[START_JS.index("async zeichneLehrmaterial() {") :]
    funktion = funktion[: funktion.index("\n  },")]
    assert "abschnitt.hidden = true" in funktion
    assert "abschnitt.hidden = false" in funktion


def test_start_js_berichtlink_haengt_hinten_an_nicht_vorne():
    """Bei einem Zeilenumbruch der Aktionszeile (Kartenbreite 184px, siehe
    static/css/loeschen.css) soll "Bericht" allein in die zweite Zeile
    rutschen, nicht der gefaehrliche "Loeschen"-Knopf - deshalb ans Ende
    angehaengt statt davorgesetzt."""
    funktion = START_JS[START_JS.index("async anlageKarteElement(anlage) {") :]
    funktion = funktion[: funktion.index("\n  },")]
    assert "aktionen.appendChild(berichtLink)" in funktion
    assert "insertBefore" not in funktion


def test_zahlen_im_text_stehen_in_deutscher_schreibweise():
    """Eine Zahl, die als Text auf der Seite landet, trägt ein Komma.

    Der Bericht (core/bericht.py), die Ausgabe (core/ausgabe.py) und die
    Eingabefelder taten das immer schon - letztere, weil der Browser die
    Schreibweise aus lang="de" übernimmt. Die per JavaScript geschriebenen
    Texte daneben zeigten dagegen einen Punkt: „Letzter Lauf: 136.28 EUR"
    neben einem Feld mit „726,0". Seitdem gibt es dafür eine Stelle
    (static/js/zahlen.js, Zahlen.fest).

    Zwei Ausnahmen bleiben und sind im Code begründet: der Wert eines
    <input type="number"> (mit Komma für den Browser ungültig) und eine
    CSS-Länge. Beide stehen deshalb hier namentlich.
    """
    js_ordner = Path(__file__).resolve().parent.parent / "static" / "js"
    erlaubt = {
        ("zahlen.js", "return zahl.toFixed"),
        ("panel.js", "return zahl.toFixed"),
        ("simulation.js", "style.width"),
    }
    verstoesse = []
    for datei in sorted(js_ordner.glob("*.js")):
        for nummer, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if "toFixed" not in zeile or zeile.lstrip().startswith("//"):
                continue
            if any(datei.name == name and teil in zeile for name, teil in erlaubt):
                continue
            verstoesse.append(f"{datei.name}:{nummer}: {zeile.strip()}")
    assert not verstoesse, "\n".join(verstoesse)


def test_die_fusszeile_einer_anlagenkarte_sitzt_am_kartenboden():
    """Karten in einer Reihe sind gleich hoch, ihr Text aber verschieden lang:
    eine Anlage mit Laufergebnis hat drei Zeilen, eine ohne nur eine. Ohne
    dass der Textteil die überschüssige Höhe aufnimmt, klebt die Knopfreihe
    am Ende des Textes - drei Karten nebeneinander zeigten ihre Knöpfe dann
    auf drei verschiedenen Höhen."""
    css = (
        Path(__file__).resolve().parent.parent / "static" / "css" / "loeschen.css"
    ).read_text(encoding="utf-8")
    stelle = css.index(".anlage-eintrag .anlage-karte {")
    regel = css[stelle:css.index("}", stelle)]
    assert re.search(r"flex:\s*1", regel), regel
