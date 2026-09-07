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
# Der Wetterteil der Oberflaeche - er stand bis zur Aufteilung des
# gemeinsamen Moduls in static/js/start.js, das Start- UND Wetterseite in
# voller Laenge luden.
WETTER_JS = (WURZEL / "static" / "js" / "wetter.js").read_text()
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
    """Die Wetterseite (templates/wetter.html).

    Der Wetterbereich stand bis zu diesem Umbau auf der Startseite - dort
    nahmen seine beiden Formulare den meisten Platz ein, waehrend die Projekte
    darueber in zwei Zeilen abgehandelt waren. Er hat jetzt eine eigene Seite;
    die Vorrichtung heisst der Kuerze halber weiter 'startseite'.
    """
    return app.test_client().get("/wetter").get_data(as_text=True)


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

def test_wetter_js_kennt_die_lesbaren_endungen_und_nicht_pdf():
    treffer = re.search(r"const WETTER_ENDUNGEN = \[(.*?)\]", WETTER_JS, re.S)
    assert treffer, "Liste der lesbaren Endungen fehlt"
    endungen = treffer.group(1)
    for erwartet in (".dat", ".xls", ".xlsx", ".csv"):
        assert erwartet in endungen
    assert ".pdf" not in endungen, "das Handbuch darf nicht mitgeschickt werden"


def test_wetter_js_filtert_die_gewaehlten_dateien_ueber_diese_liste():
    """Sonst ginge das Handbuch-PDF mit hoch - zwei Megabyte fuer nichts."""
    assert "WETTER_ENDUNGEN.some" in WETTER_JS or "WETTER_ENDUNGEN.includes" in WETTER_JS


def test_wetter_js_liest_den_standort_aus_dem_ordnernamen():
    assert "webkitRelativePath" in WETTER_JS


def test_wetter_js_beschriftet_try_dateien_mit_jahr_und_art():
    """Aus TRY2015_..._Somm.dat muss '2015 - extremer Sommer' werden, sonst
    steht in der Ankreuzliste sechsmal fast derselbe Dateiname."""
    assert "extremer Sommer" in WETTER_JS
    assert "extremer Winter" in WETTER_JS
    assert "mittleres Jahr" in WETTER_JS


def test_wetter_js_schickt_den_standort_mit():
    assert re.search(r'append\(\s*"ort"', WETTER_JS)


def test_wetter_js_schickt_nur_die_angehakten_dateien():
    treffer = re.search(r"async wetterHochladen\(.*?\n  \},", WETTER_JS, re.S)
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


def test_wetterseite_gruppiert_die_liste_nach_standort(app):
    """Seit dem Umbau der Oberflaeche buendelt der Server (routes/pages.py:
    _nach_standort) - geprueft wird deshalb das ausgelieferte HTML, nicht mehr
    der Wortlaut von start.js."""
    from core.wetter import speicher

    stunde = {
        "zeitpunkt": __import__("datetime").datetime(2024, 1, 1, 0),
        "t_au": 0.0, "x_au": 4.0,
        "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
    }
    with app.app_context():
        speicher.datensatz_anlegen("Erstes", "upload", [stunde], ort="Pirna")
        speicher.datensatz_anlegen("Zweites", "upload", [stunde], ort="Pirna")

    html = app.test_client().get("/wetter").get_data(as_text=True)
    assert html.count("wetter-standort-zeile") == 1
    assert "Pirna" in html


def test_editorseite_bindet_die_gemeinsame_auswahl_ein(app):
    """Ohne das Skript-Tag ist wetterAuswahlFelder auf der Seite unbekannt und
    der Simulationsdialog bliebe leer. Nur noch die Editorseite: Start- und
    Wetterseite brauchen die Auswahlfelder nicht."""
    from core import anlagen

    klient = app.test_client()
    with app.app_context():
        projekt_id = anlagen.projekt_anlegen("Probe")
        anlage_id = anlagen.anlage_anlegen(projekt_id, "Probe")

    antwort = klient.get(f"/anlage/{anlage_id}")
    assert antwort.status_code == 200
    assert "js/wetterauswahl.js" in antwort.get_data(as_text=True)


def _skript_stelle(html, datei):
    """Position des Skript-Tags - nicht die einer beilaeufigen Erwaehnung im
    Kommentar, von denen es in editor.html eine gibt."""
    stelle = html.find(f"filename='{datei}'")
    assert stelle != -1, datei
    return stelle


def test_gemeinsame_auswahl_wird_vor_ihren_nutzern_geladen():
    """Beide Dateien sind klassische Skripte ohne Modulauflösung - laedt die
    Seite sie in falscher Reihenfolge, ist die Funktion beim Aufruf noch nicht
    da.

    Nur noch die Editorseite: Start- und Wetterseite brauchen die Buendelung
    nach Standort nicht mehr, seit die Wetterliste fertig gebuendelt vom
    Server kommt (routes/pages.py: wetter()).
    """
    html = (WURZEL / "templates" / "editor.html").read_text()
    assert _skript_stelle(html, "js/wetterauswahl.js") < _skript_stelle(html, "js/simulation.js")


def test_start_und_wetterseite_laden_die_auswahl_nicht_mehr():
    """Ein Skript, das eine Seite nicht braucht, laedt sie auch nicht - sonst
    steht in ihrem Quelltext eine Abhaengigkeit, die es nicht gibt."""
    for seite in ("index.html", "wetter.html"):
        html = (WURZEL / "templates" / seite).read_text()
        assert "js/wetterauswahl.js" not in html, seite


def test_standort_zwischenzeile_spannt_die_ganze_tabelle():
    """Die Ortsspalte ist mit der Gruppierung entfallen - bleibt das colspan
    auf dem alten Wert, ragt die Zwischenzeile über die Tabelle hinaus.

    Geprueft wird die Vorlage, nicht mehr start.js: Die Tabelle entsteht seit
    dem Umbau der Oberflaeche auf dem Server (routes/pages.py: wetter()).
    """
    vorlage = (WURZEL / "templates" / "wetter.html").read_text()
    kopf = re.search(r"<thead>.*?</thead>", vorlage, re.S).group()
    # <th[ >] statt <th - sonst zaehlt das umschliessende <thead> als Spalte mit.
    spalten = len(re.findall(r"<th[ >]", kopf))
    zwischenzeile = re.search(r'wetter-standort-zeile.*?colspan="(\d+)"', vorlage, re.S)
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
    treffer = re.search(r"const WETTER_ENDUNGEN = \[(.*?)\]", WETTER_JS, re.S)
    assert ".zip" not in treffer.group(1)


def test_wetter_js_erklaert_ein_archiv_statt_es_zu_verschlucken():
    """Ein .zip faellt beim Filtern durch. Ohne eigenen Hinweis bekaeme der
    Nutzer nur 'Bitte eine Datei auswählen' zu sehen, obwohl er gerade eine
    ausgewaehlt hat."""
    assert "entpack" in WETTER_JS.lower()


# --- Erklaertexte an anderer Stelle ---------------------------------------

def test_bausteine_seite_beschreibt_den_ordnerweg(app):
    """Die Seite 'Bausteine' erklaert unter 'An Wetterdaten kommen', wie man
    zu einem Datensatz kommt. Blieb sie beim alten Wortlaut stehen, verspricht
    sie ausdruecklich nur .xls, .xlsx und .csv - also das Gegenteil dessen,
    was das Formular auf der Wetterseite anbietet."""
    html = app.test_client().get("/bausteine").get_data(as_text=True)
    abschnitt = re.search(
        r"<h3>An Wetterdaten kommen</h3>.*?</article>", html, re.S
    ).group()
    assert ".dat" in abschnitt
    assert "Ordner" in abschnitt


def test_vorauswahl_haengt_nicht_an_der_festen_zahl_2045():
    """Das Zukunfts-TRJ ist heute mit Schlüsseljahr 2045 ausgezeichnet. Wird
    die Vorauswahl daran festgemacht, muss der Code angefasst werden, sobald
    der DWD einen weiteren Zukunftsdatensatz herausgibt."""
    assert "2045" not in re.search(
        r"function wetterIstZukunftsjahr.*?\n\}", WETTER_JS, re.S
    ).group(), "Vergleich mit dem laufenden Jahr statt mit einer festen Zahl"
    assert "new Date().getFullYear()" in WETTER_JS
