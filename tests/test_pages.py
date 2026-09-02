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


# ---------- iPad: Ueberscrollen, sichere Bereiche, Beruehrung ----------
# Nachgestellt mit Playwright (echtes iPad Pro 11 in Chromium, siehe
# ipad-report.md) - hier nur die billig, ohne Browserlauf pruefbaren
# Voraussetzungen dafuer: die Vorlage traegt viewport-fit=cover, und das
# ausgelieferte CSS schaltet das Gummiband-Ueberscrollen ab.

def test_alle_vier_vorlagen_setzen_viewport_fit_cover(app):
    """Ohne viewport-fit=cover ignoriert iOS env(safe-area-inset-*) komplett
    (siehe style.css/bausteine.css) - die Kopfleiste liefe dann unter einer
    Notch/Rundung durch, ohne dass irgendein Polster das verhindern koennte."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    for pfad in ("/", "/bausteine", f"/anlage/{anlage}", "/anlage/9999"):
        html = klient.get(pfad).get_data(as_text=True)
        assert 'viewport-fit=cover' in html, pfad


def test_style_css_schaltet_das_ueberscrollen_ab(app):
    """overscroll-behavior auf Wurzel UND Koerper (siehe Task, Befund 3) -
    ohne das schiebt sich auf iOS die ganze Seite mit, wenn man ueber den
    Rand eines Bereichs hinaus zieht."""
    klient = app.test_client()
    css = klient.get("/static/css/style.css").get_data(as_text=True)
    block = css[css.index("html, body {"):]
    block = block[:block.index("}")]
    assert "overscroll-behavior: none;" in block


def test_style_css_verwendet_dvh_mit_vh_rueckfallwert(app):
    """100vh zaehlt auf iOS die Hoehe MIT eingefahrener Werkzeugleiste mit
    (siehe Task) - 100dvh muss als zweite, ueberschreibende Deklaration nach
    100vh stehen (Browser ohne dvh-Unterstuetzung ueberspringen die zweite
    Zeile und behalten den vh-Wert)."""
    klient = app.test_client()
    css = klient.get("/static/css/style.css").get_data(as_text=True)
    for regel in (".app {", ".start {"):
        block = css[css.index(regel):]
        block = block[:block.index("}")]
        assert "height: 100vh;" in block
        assert "height: 100dvh;" in block
        assert block.index("height: 100vh;") < block.index("height: 100dvh;")


def test_editor_seite_hat_umschaltknoepfe_fuer_palette_und_panel(app):
    """Auf schmalem Hochformat mit Finger passen drei Spalten nicht
    nebeneinander (siehe Task, Befund 6) - Palette und Parameterfenster
    werden zu Seitenbereichen, die diese zwei Knoepfe umschalten (siehe
    static/js/editor.js, seitenbereichSchalten())."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    html = klient.get(f"/anlage/{anlage}").get_data(as_text=True)
    assert 'id="btn-palette-umschalten"' in html
    assert 'aria-controls="palette"' in html
    assert 'id="btn-panel-umschalten"' in html
    assert 'aria-controls="panel"' in html


def test_palette_js_bewaffnet_nur_bei_finger_nicht_bei_maus(app):
    """Der Zwei-Tipp-Weg (Eintrag antippen, Leinwand antippen - siehe Task)
    darf das bestehende Maus-Drag&Drop nicht anfassen: dragstart bleibt
    bedingungslos, das Bewaffnen prueft ausdruecklich pointerType !== 'mouse'."""
    klient = app.test_client()
    js = klient.get("/static/js/palette.js").get_data(as_text=True)
    assert 'e.pointerType === "mouse"' in js
    assert 'this.armieren(typ.kennung, eintrag)' in js
    # dragstart selbst bleibt unveraendert - keine pointerType-Pruefung davor.
    dragstart = js[js.index('"dragstart"'):]
    dragstart = dragstart[:dragstart.index(");")]
    assert "pointerType" not in dragstart


def test_editor_js_leinwand_beachtet_bewaffnete_palette_und_kneifgeste(app):
    """Zwei Handgriffe, beide ohne Browserlauf nicht direkt pruefbar (siehe
    Kommentar bei test_entf_taste...) - hier nur festgehalten, DASS der
    Leinwand-Lauscher auf eine bewaffnete Palette reagiert (Karte per Tipp
    anlegen) und dass eine Kneifgeste (zwei Zeiger) den Zoom aendert."""
    klient = app.test_client()
    js = klient.get("/static/js/editor.js").get_data(as_text=True)
    assert "if (Palette.bereit)" in js
    assert "_kneifBewegen" in js
    assert "this._zeiger.size >= 2" in js
    # setPointerCapture darf einen synthetischen/inaktiven Zeiger nicht mit
    # einer unbehandelten Ausnahme zum Abbruch bringen (siehe Bericht).
    aufruf = js[js.index("try {\n        leinwand.setPointerCapture"):]
    assert "} catch {" in aufruf[: aufruf.index("this._zeiger.set")]
