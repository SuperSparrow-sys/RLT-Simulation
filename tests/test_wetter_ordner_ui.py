"""Oberflaeche fuer den Ordner-Upload und die Auswahl nach Standort.

Wie in tests/test_startseite.py wird JavaScript-Verhalten, das hier kein
Browser ausfuehren kann, ueber den Wortlaut des Quelltextes abgesichert -
kein Ersatz fuer einen Browser-Test, aber mehr als nichts.
"""

import re
from pathlib import Path

import pytest

from app import create_app
from core import database

WURZEL = Path(__file__).parent.parent
START_JS = (WURZEL / "static" / "js" / "start.js").read_text()
SIMULATION_JS = (WURZEL / "static" / "js" / "simulation.js").read_text()
WETTERAUSWAHL_JS = (WURZEL / "static" / "js" / "wetterauswahl.js").read_text()
# Was die Editorseite tatsaechlich ausliefert - die Buendelung nach Standort
# steht in der gemeinsamen Datei, das Dialog-Markup in simulation.js.
EDITOR_JS = SIMULATION_JS + WETTERAUSWAHL_JS


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def startseite(app):
    return app.test_client().get("/").get_data(as_text=True)


# --- Ordnerfeld -----------------------------------------------------------

def test_startseite_bietet_ein_ordnerfeld(app):
    """Ohne webkitdirectory laesst sich kein Ordner waehlen, nur Dateien."""
    html = startseite(app)
    assert "webkitdirectory" in html
    assert 'id="feld-wetter-ordner"' in html


def test_dateifeld_nimmt_jetzt_auch_dat_dateien(app):
    html = startseite(app)
    feld = re.search(r'<input[^>]*id="feld-wetter-datei"[^>]*>', html).group()
    assert ".dat" in feld, "sonst blendet der Dateidialog Testreferenzjahre aus"
    assert "multiple" in feld


def test_startseite_hat_ein_standortfeld_und_eine_auswahlliste(app):
    html = startseite(app)
    assert 'id="feld-wetter-ort"' in html
    assert 'id="wetter-auswahl-liste"' in html


def test_hinweis_erklaert_den_ordnerweg(app):
    html = startseite(app)
    # Es gibt mehrere Hinweiskaesten; gemeint ist der im Upload-Aufklapper.
    block = re.search(
        r'id="wetter-upload-details".*?</details>', html, re.S
    ).group()
    hinweis = re.search(r'<p class="wetter-weg-hinweis">(.*?)</p>', block, re.S).group(1)
    assert "Ordner" in hinweis
    assert ".dat" in hinweis


# --- Filtern im Browser ---------------------------------------------------

def test_start_js_kennt_die_lesbaren_endungen_und_nicht_pdf():
    treffer = re.search(r"const WETTER_ENDUNGEN = \[(.*?)\]", START_JS, re.S)
    assert treffer, "Liste der lesbaren Endungen fehlt"
    endungen = treffer.group(1)
    for erwartet in (".dat", ".xls", ".xlsx", ".csv"):
        assert erwartet in endungen
    assert ".pdf" not in endungen, "das Handbuch darf nicht mitgeschickt werden"


def test_start_js_filtert_die_gewaehlten_dateien_ueber_diese_liste():
    """Sonst ginge das Handbuch-PDF mit hoch - zwei Megabyte fuer nichts."""
    assert "WETTER_ENDUNGEN.some" in START_JS or "WETTER_ENDUNGEN.includes" in START_JS


def test_start_js_liest_den_standort_aus_dem_ordnernamen():
    assert "webkitRelativePath" in START_JS


def test_start_js_beschriftet_try_dateien_mit_jahr_und_art():
    """Aus TRY2015_..._Somm.dat muss '2015 - extremer Sommer' werden, sonst
    steht in der Ankreuzliste sechsmal fast derselbe Dateiname."""
    assert "extremer Sommer" in START_JS
    assert "extremer Winter" in START_JS
    assert "mittleres Jahr" in START_JS


def test_start_js_schickt_den_standort_mit():
    assert re.search(r'append\(\s*"ort"', START_JS)


def test_start_js_schickt_nur_die_angehakten_dateien():
    treffer = re.search(r"async wetterHochladen\(.*?\n  \},", START_JS, re.S)
    assert treffer, "wetterHochladen nicht gefunden"
    rumpf = treffer.group()
    assert "angehakt" in rumpf


# --- Zwei Auswahlfelder im Simulationsdialog ------------------------------

def test_simulation_js_waehlt_erst_den_standort_dann_den_datensatz():
    assert 'id="wahl-wetter-ort"' in SIMULATION_JS
    assert 'id="wahl-wetter"' in SIMULATION_JS


def test_vergleichsdialog_gruppiert_ebenfalls_nach_standort():
    assert 'id="wahl-wetter-ort-reihe"' in SIMULATION_JS
    assert 'id="wahl-wetter-reihe"' in SIMULATION_JS


def test_simulation_js_faengt_datensaetze_ohne_standort_auf():
    """Alle bisher hochgeladenen Datensaetze haben ein leeres Ortsfeld - sie
    duerfen dadurch nicht aus der Auswahl fallen."""
    assert "Ohne Standort" in EDITOR_JS


def test_vergleich_erlaubt_weiterhin_standortuebergreifend():
    """Zwei Wetterjahre verschiedener Orte zu vergleichen war bisher moeglich
    und muss es bleiben."""
    assert "Alle Standorte" in EDITOR_JS


def test_startseite_gruppiert_die_liste_nach_standort():
    assert "wetterNachStandort" in START_JS


def test_beide_seiten_binden_die_gemeinsame_auswahl_ein(app):
    """Ohne das Skript-Tag ist wetterAuswahlFelder auf der Seite unbekannt und
    der Simulationsdialog bliebe leer."""
    from core import anlagen

    klient = app.test_client()
    with app.app_context():
        projekt_id = anlagen.projekt_anlegen("Probe")
        anlage_id = anlagen.anlage_anlegen(projekt_id, "Probe")

    for pfad in ("/", f"/anlage/{anlage_id}"):
        antwort = klient.get(pfad)
        assert antwort.status_code == 200, pfad
        assert "js/wetterauswahl.js" in antwort.get_data(as_text=True), pfad


def _skript_stelle(html, datei):
    """Position des Skript-Tags - nicht die einer beilaeufigen Erwaehnung im
    Kommentar, von denen es in editor.html eine gibt."""
    stelle = html.find(f"filename='{datei}'")
    assert stelle != -1, datei
    return stelle


def test_gemeinsame_auswahl_wird_vor_ihren_nutzern_geladen():
    """Beide Dateien sind klassische Skripte ohne Modulauflösung - laedt die
    Seite sie in falscher Reihenfolge, ist die Funktion beim Aufruf noch nicht
    da."""
    for seite, nutzer in (("index.html", "js/start.js"), ("editor.html", "js/simulation.js")):
        html = (WURZEL / "templates" / seite).read_text()
        assert _skript_stelle(html, "js/wetterauswahl.js") < _skript_stelle(html, nutzer), seite


def test_standort_zwischenzeile_spannt_die_ganze_tabelle():
    """Die Ortsspalte ist mit der Gruppierung entfallen - bleibt das colspan
    auf dem alten Wert, ragt die Zwischenzeile über die Tabelle hinaus."""
    kopf = re.search(r"<thead>.*?</thead>", START_JS, re.S).group()
    # <th[ >] statt <th - sonst zaehlt das umschliessende <thead> als Spalte mit.
    spalten = len(re.findall(r"<th[ >]", kopf))
    zwischenzeile = re.search(r'wetter-standort-zeile.*?colspan="(\d+)"', START_JS, re.S)
    assert int(zwischenzeile.group(1)) == spalten


# --- Echte Ordnerauswahl --------------------------------------------------

def test_ordnerfeld_oeffnet_wirklich_einen_ordnerdialog(app):
    """webkitdirectory macht aus dem Dateidialog einen Ordnerdialog. Ein
    accept-Attribut daneben lassen manche Browser den Ordner wieder als
    Dateiauswahl oeffnen - es darf an diesem Feld also nicht stehen."""
    html = startseite(app)
    feld = re.search(r'<input[^>]*id="feld-wetter-ordner"[^>]*>', html, re.S).group()
    assert "webkitdirectory" in feld
    assert "multiple" in feld
    assert "accept=" not in feld


def test_ordnerfeld_und_dateifeld_sind_getrennt(app):
    """Ein Feld kann nicht beides: mit webkitdirectory waehlt man immer einen
    Ordner, nie eine einzelne Datei. Darum zwei Felder nebeneinander."""
    html = startseite(app)
    datei_feld = re.search(r'<input[^>]*id="feld-wetter-datei"[^>]*>', html, re.S).group()
    assert "webkitdirectory" not in datei_feld


# --- Archive ---------------------------------------------------------------

def test_zip_steht_nicht_unter_den_lesbaren_endungen():
    from core.wetter import einlesen

    assert ".zip" not in einlesen.ENDUNGEN
    treffer = re.search(r"const WETTER_ENDUNGEN = \[(.*?)\]", START_JS, re.S)
    assert ".zip" not in treffer.group(1)


def test_start_js_erklaert_ein_archiv_statt_es_zu_verschlucken():
    """Ein .zip faellt beim Filtern durch. Ohne eigenen Hinweis bekaeme der
    Nutzer nur 'Bitte eine Datei auswählen' zu sehen, obwohl er gerade eine
    ausgewaehlt hat."""
    assert "entpack" in START_JS.lower()


# --- Erklaertexte an anderer Stelle ---------------------------------------

def test_bausteine_seite_beschreibt_den_ordnerweg(app):
    """Die Seite 'Bausteine' erklaert unter 'An Wetterdaten kommen', wie man
    zu einem Datensatz kommt. Blieb sie beim alten Wortlaut stehen, verspricht
    sie ausdruecklich nur .xls, .xlsx und .csv - also das Gegenteil dessen,
    was das Formular auf der Startseite anbietet."""
    html = app.test_client().get("/bausteine").get_data(as_text=True)
    abschnitt = re.search(
        r"<h2>An Wetterdaten kommen</h2>.*?</article>", html, re.S
    ).group()
    assert ".dat" in abschnitt
    assert "Ordner" in abschnitt


def test_vorauswahl_haengt_nicht_an_der_festen_zahl_2045():
    """Das Zukunfts-TRJ ist heute mit Schlüsseljahr 2045 ausgezeichnet. Wird
    die Vorauswahl daran festgemacht, muss der Code angefasst werden, sobald
    der DWD einen weiteren Zukunftsdatensatz herausgibt."""
    assert "2045" not in re.search(
        r"function wetterIstZukunftsjahr.*?\n\}", START_JS, re.S
    ).group(), "Vergleich mit dem laufenden Jahr statt mit einer festen Zahl"
    assert "new Date().getFullYear()" in START_JS
