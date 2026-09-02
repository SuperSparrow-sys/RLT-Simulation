import pytest

from app import create_app
from core import anlagen, database
from core.vorlagen import ax_sim_2_1


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def test_editor_seite_laedt_eine_anlage(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    antwort = klient.get(f"/anlage/{anlage}")
    assert antwort.status_code == 200


def test_editor_seite_unbekannte_anlage_meldet_404(app):
    """Vorher rendierte /anlage/<id> fuer JEDE Zahl den Editor, ununterscheidbar
    von einer echten, leeren Anlage (siehe core.anlagen.anlage_existiert()) -
    eine falsche oder veraltete Adresse muss als solche erkennbar sein."""
    klient = app.test_client()
    antwort = klient.get("/anlage/9999")
    assert antwort.status_code == 404
    html = antwort.get_data(as_text=True)
    assert "gibt es nicht" in html
    assert 'id="anlagenname"' not in html  # nicht der Editor selbst


def test_editor_seite_bindet_pfeile_js_vor_editor_js_ein(app):
    """Ohne dieses Script-Tag existiert 'Pfeile' nicht und editor.js' Aufrufe
    von Pfeile.zeichneAlle()/Pfeile.binde() brechen mit einem ReferenceError
    ab - das faellt in keinem Python-Test auf, deshalb hier absichern."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    html = klient.get(f"/anlage/{anlage}").get_data(as_text=True)

    assert "js/pfeile.js" in html
    assert html.index("js/pfeile.js") < html.index("js/editor.js")


def test_editor_seite_bindet_editor_js_fuer_palette_js_ein(app):
    """palette.js ruft zeigeFehler() auf, das nicht in palette.js selbst,
    sondern in editor.js definiert ist (siehe Kommentare in beiden Dateien) -
    ohne editor.js auf derselben Seite waere das ein ReferenceError, sobald
    das Laden der Palette fehlschlaegt. Das faellt in keinem Python-Test auf,
    deshalb hier absichern."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    html = klient.get(f"/anlage/{anlage}").get_data(as_text=True)

    assert "js/palette.js" in html
    assert "js/editor.js" in html


def test_entf_taste_greift_nicht_im_eingabefeld_und_fragt_nach(app):
    """Zwei Befunde in einem Lauscher, beide ohne JS-Testlauf nicht pruefbar.

    Der Entf-Lauscher haengt am window (die Auswahl bleibt auch bestehen,
    waehrend der Fokus im Parameterfenster liegt) und muss deshalb selbst
    pruefen, wo der Fokus steht - sonst loeschte Entf beim Tippen im Feld
    "Bezeichnung" die ganze Karte samt ihren Pfeilen. Und Loeschen braucht
    dieselbe Rueckfrage wie ueberall sonst.

    Die Pruefung liest die ausgelieferte Datei, weil es im Projekt keinen
    JS-Testlauf gibt; nachgestellt wurde beides im Browser. Sie haelt nur
    fest, DASS Fokuspruefung und Rueckfrage im Lauscher stehen - nicht, wie
    sie formuliert sind.
    """
    klient = app.test_client()
    quelle = klient.get("/static/js/editor.js").get_data(as_text=True)

    assert "function istTexteingabe(" in quelle
    lauscher = quelle[quelle.index('window.addEventListener("keydown"'):]
    lauscher = lauscher[:lauscher.index("});")]
    assert "istTexteingabe(document.activeElement)" in lauscher
    assert "karteLoeschenDialog" in lauscher

    dialog = quelle[quelle.index("async karteLoeschenDialog("):]
    dialog = dialog[:dialog.index("\n  },")]
    assert "bestaetigenDialog(" in dialog
    # Die Rueckfrage nennt, was mit der Karte verloren geht.
    assert "_verlustHinweis(" in dialog


def test_startseite_antwortet_mit_200(app):
    klient = app.test_client()
    antwort = klient.get("/")
    assert antwort.status_code == 200


def test_startseite_bindet_ihr_eigenes_script_ein(app):
    """Ohne dieses Script-Tag bleibt die Startseite ein leerer Rahmen ohne
    Projekte, Anlagen oder Wetterdaten - das faellt in keinem Python-Test auf,
    deshalb hier absichern."""
    klient = app.test_client()
    html = klient.get("/").get_data(as_text=True)
    assert "js/start.js" in html


def test_startseite_bindet_wetter_abruf_css_ein(app):
    """Das eigene Stylesheet des Wetterabrufs - ohne dieses Tag bleibt das
    Formular unformatiert (siehe Kommentar in wetter-abruf.css, weshalb es
    eine eigene Datei statt style.css ist)."""
    klient = app.test_client()
    html = klient.get("/").get_data(as_text=True)
    assert "css/wetter-abruf.css" in html


def test_startseite_enthaelt_das_abrufformular(app):
    """Formularfelder fuer den Online-Abruf (Ort, Jahr-Mehrfachauswahl,
    Absenden) - ohne sie kann start.js nichts an sie binden und der zweite
    Weg zu Wetterdaten (neben dem Datei-Upload) fehlt stillschweigend."""
    klient = app.test_client()
    html = klient.get("/").get_data(as_text=True)
    assert 'id="form-wetter-abruf"' in html
    assert 'id="feld-wetter-abruf-ort"' in html
    assert 'id="feld-wetter-abruf-jahre"' in html
    assert 'id="btn-wetter-abrufen"' in html
    # mindestens ein vorbelegter Ort und die Option fuer eigene Koordinaten
    assert 'value="Dresden"' in html
    assert 'value="eigene"' in html


def test_startseite_bindet_loeschen_css_ein(app):
    """Das eigene Stylesheet fuer Loeschen/Umbenennen - ohne dieses Tag
    bleiben die neuen Aktionsknoepfe unformatiert (siehe Kommentar in
    loeschen.css, weshalb es eine eigene Datei statt style.css ist)."""
    klient = app.test_client()
    html = klient.get("/").get_data(as_text=True)
    assert "css/loeschen.css" in html


def test_editor_seite_bindet_loeschen_css_ein(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    html = klient.get(f"/anlage/{anlage}").get_data(as_text=True)
    assert "css/loeschen.css" in html


def test_startseite_bindet_kein_editor_script_ein(app):
    """start.js ist eigenstaendig (siehe dortiger Kommentar) - laedt die
    Startseite trotzdem editor.js/panel.js/simulation.js mit, waere das ein
    Zeichen, dass sich eine stille Abhaengigkeit eingeschlichen hat."""
    klient = app.test_client()
    html = klient.get("/").get_data(as_text=True)
    assert "js/editor.js" not in html
    assert "js/panel.js" not in html
    assert "js/simulation.js" not in html
    assert "js/pfeile.js" not in html
    assert "js/palette.js" not in html
