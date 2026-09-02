from pathlib import Path

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


def test_editor_seite_hat_einen_weg_zurueck_zur_startseite(app):
    """Vorher fuehrte aus einer geoeffneten Anlage nur die Adresszeile
    wieder heraus. Links neben dem Anlagennamen, wie im Erklaerbereich
    (.zurueck-knopf) - hier vor <span class="titel anlagenname-zeile">,
    damit es sich gleich anfuehlt."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    html = klient.get(f"/anlage/{anlage}").get_data(as_text=True)
    assert 'class="zurueck-knopf" href="/"' in html
    assert html.index('class="zurueck-knopf"') < html.index('class="titel anlagenname-zeile"')


def test_editor_seite_hat_einen_dauerhaften_bericht_weg_in_der_kopfleiste(app):
    """Vorher stand die Jahresbilanz nur im Dialog - der Bericht war von
    dort nicht erreichbar, und nach dem Schliessen gar nicht mehr. Zu
    Beginn immer abgeblendet (id="link-bericht" mit aria-disabled), erst
    editor.js setzt href, sobald ein Lauf mit Ergebnis vorliegt (siehe
    dortige Tests)."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    html = klient.get(f"/anlage/{anlage}").get_data(as_text=True)
    assert 'id="link-bericht"' in html
    assert 'aria-disabled="true"' in html
    # Vor dem Simulieren-Knopf, dauerhaft in der Kopfleiste (nicht im Dialog).
    assert html.index('id="link-bericht"') < html.index('id="btn-simulieren"')


def test_editor_js_ermittelt_und_setzt_den_bericht_weg(app):
    """Ohne Browserlauf nicht direkt pruefbar (siehe Kommentar bei
    test_entf_taste...) - haelt nur fest, DASS berichtLinkAktualisieren()
    den juengsten Lauf MIT Ergebnis waehlt (status 'fertig'/'abgebrochen',
    core.bericht.STATUS_MIT_ERGEBNIS) und berichtLinkSetzen() href und
    aria-disabled darauf abstimmt."""
    klient = app.test_client()
    js = klient.get("/static/js/editor.js").get_data(as_text=True)

    aktualisieren = js[js.index("async berichtLinkAktualisieren("):]
    aktualisieren = aktualisieren[: aktualisieren.index("\n  },")]
    assert "/api/anlagen/${this.anlage.id}/simulationen" in aktualisieren
    assert '"fertig"' in aktualisieren
    assert '"abgebrochen"' in aktualisieren
    assert "this.berichtLinkSetzen(" in aktualisieren

    setzen = js[js.index("berichtLinkSetzen(simulationId)"):]
    setzen = setzen[: setzen.index("\n  },")]
    assert '/anlage/${this.anlage.id}/lauf/${simulationId}/bericht`' in setzen
    assert 'removeAttribute("aria-disabled")' in setzen
    assert 'setAttribute("aria-disabled", "true")' in setzen


def test_simulation_js_setzt_bericht_link_sofort_bei_laufende_ohne_neuladen(app):
    """Prueft, DASS beobachte() den neu beendeten Lauf sofort an
    Editor.berichtLinkSetzen() meldet, statt dass der Weg erst nach einem
    Neuladen der Seite nutzbar wird - und dass ein fehlgeschlagener Lauf
    (kein Ergebnis) den Weg NICHT setzt."""
    klient = app.test_client()
    js = klient.get("/static/js/simulation.js").get_data(as_text=True)

    block = js[js.index('if (["fertig", "abgebrochen", "fehler"].includes(stand.status)) {'):]
    block = block[: block.index("await this.zeigeBilanz(stand.simulation_id, hinweis);")]
    assert "Editor.berichtLinkSetzen(stand.simulation_id)" in block
    # Der fruehe Ausstieg bei "fehler" liegt VOR dem Setzen des Links.
    assert block.index('stand.status === "fehler"') < block.index(
        "Editor.berichtLinkSetzen(stand.simulation_id)"
    )


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


def test_nur_die_editorseite_traegt_seite_editor(app):
    """.seite-editor setzt html/body auf position:fixed + overflow:hidden
    (siehe style.css) - das darf NUR den Editor treffen. Startseite,
    Bausteine und die Fehlerseite muessen weiterhin ganz normal scrollen
    (siehe dortiger Kommentar in style.css: overscroll-behavior allein
    schaltet nicht die Scrollbarkeit von html/body ab, das war der
    eigentliche Fehler - siehe Bericht)."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    editor_html = klient.get(f"/anlage/{anlage}").get_data(as_text=True)
    assert 'class="seite-editor"' in editor_html
    # Zweimal: einmal auf <html>, einmal auf <body>.
    assert editor_html.count('class="seite-editor"') == 2

    for pfad in ("/", "/bausteine", "/anlage/9999"):
        html = klient.get(pfad).get_data(as_text=True)
        assert "seite-editor" not in html, pfad


def test_style_css_setzt_html_body_auf_der_editorseite_fest(app):
    """position:fixed + overflow:hidden statt sich auf eine Hoehenangabe zu
    verlassen - overflow:hidden allein ist auf iOS Safari nach einer
    Kneifgeste bekannt unzuverlaessig, deshalb beides zusammen ("iOS body
    scroll lock", siehe Kommentar in style.css)."""
    klient = app.test_client()
    css = klient.get("/static/css/style.css").get_data(as_text=True)
    block = css[css.index("html.seite-editor,"):]
    block = block[: block.index("}") + 1]
    assert "position: fixed;" in block
    assert "overflow: hidden;" in block


def test_alle_scrollbaren_flaechen_haben_overscroll_behavior_contain(app):
    """Jede Flaeche mit overflow-y:auto/overflow:auto in style.css muss
    overscroll-behavior:contain tragen - sonst reicht sie einen Wisch, der
    an ihrem eigenen Ende ankommt, an den naechsten Vorfahren weiter (siehe
    Bericht: genau das war die tatsaechliche Fehlerquelle, bevor
    .seite-editor html/body ganz von der Scroll-Wurzel nahm). Bewusst als
    generische Pruefung ueber die ganze Datei, nicht je Klasse einzeln
    aufgezaehlt - eine kuenftig neu hinzukommende Scrollflaeche faellt sonst
    unbemerkt wieder durch dasselbe Loch."""
    klient = app.test_client()
    css = klient.get("/static/css/style.css").get_data(as_text=True)
    bloecke = css.split("}")
    fehlend = []
    for block in bloecke:
        if "overflow-y: auto" not in block and "overflow: auto" not in block:
            continue
        if "overscroll-behavior: contain" not in block:
            fehlend.append(block.strip().splitlines()[-1])
    assert not fehlend, f"Scrollflaeche(n) ohne overscroll-behavior:contain: {fehlend}"


def test_editor_js_verhindert_webkit_gesten_nur_bei_beruehrung(app):
    """gesturestart/-change/-end sind der von Safari selbst dokumentierte
    Weg, das Aufziehen der ganzen Seite zu unterbinden (siehe Bericht) -
    MUSS auf "pointer: coarse" begrenzt sein, sonst traefe es auch das
    Trackpad-Kneifen im Desktop-Safari (Zugaenglichkeit: Zoomen fuer
    schwache Augen muss dort erhalten bleiben)."""
    klient = app.test_client()
    js = klient.get("/static/js/editor.js").get_data(as_text=True)
    for typ in ("gesturestart", "gesturechange", "gestureend"):
        assert f'"{typ}"' in js
    funktion = js[js.index("function nurBeiBeruehrungVerhindern("):]
    funktion = funktion[: funktion.index("\n}") + 2]
    assert 'window.matchMedia("(pointer: coarse)")' in funktion
    assert "ereignis.preventDefault()" in funktion


def test_editor_html_hat_maximum_scale_nur_als_zweite_sicherung(app):
    """maximum-scale/user-scalable wirken nur auf mobile Browser ausserhalb
    von iOS Safari (das ignoriert es seit iOS 10 absichtlich) - eine zweite,
    nicht die tragende Sicherung. Nur auf der Editorseite: Startseite und
    Bausteine sollen sich weiterhin mit zwei Fingern aufziehen lassen."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    editor_html = klient.get(f"/anlage/{anlage}").get_data(as_text=True)
    assert "maximum-scale=1" in editor_html
    assert "user-scalable=no" in editor_html

    for pfad in ("/", "/bausteine", "/anlage/9999"):
        html = klient.get(pfad).get_data(as_text=True)
        assert "maximum-scale" not in html
        assert "user-scalable" not in html


def test_style_css_schliesst_touch_action_luecken_fuer_die_kneifgeste(app):
    """touch-action:pan-y/none auf jeder Flaeche, ueber der sich die Seite
    sonst noch mit zwei Fingern haette aufziehen lassen (siehe Bericht,
    "der zweite Weg") - Minikarte, Legende-Aufklappmenue, sowie (nur auf der
    Editorseite, ueber body.seite-editor abgegrenzt) Dialoge und
    Fehlerleiste, die auch auf anderen, nicht festgesetzten Seiten
    vorkommen."""
    klient = app.test_client()
    css = klient.get("/static/css/style.css").get_data(as_text=True)

    for selektor in (".minikarte-huelle {", ".legende-inhalt {"):
        block = css[css.index(selektor):]
        block = block[: block.index("}") + 1]
        assert "touch-action: none;" in block

    abgegrenzt = css[css.index("body.seite-editor .dialog-huelle,"):]
    abgegrenzt = abgegrenzt[: abgegrenzt.index("}") + 1]
    assert ".fehlermeldung" in abgegrenzt
    assert "touch-action: none;" in abgegrenzt


def test_editor_js_leinwand_zoomt_ueber_webkit_gesten_statt_sie_nur_zu_sperren(app):
    """preventDefault() auf gesturestart/-change bricht in Safari die
    zugehoerige Beruehrungsfolge meist ab (touchcancel) - der
    zeigerbasierte Kneifpfad (_kneifBewegen()) kaeme auf der Leinwand also
    gar nicht mehr zum Zug, wuerde man dort nur pauschal sperren wie
    ueberall sonst. Die Leinwand muss die Geste stattdessen SELBST ueber
    gesturechange (event.scale/clientX/clientY) bedienen. Ohne
    Browserlauf nicht direkt pruefbar (siehe Kommentar bei
    test_entf_taste...) - hier nur festgehalten, DASS die drei
    Lauscher auf der Leinwand sitzen, event.scale/clientX/clientY nutzen,
    stopPropagation() gegen Doppelbehandlung durch die allgemeine Sperre
    aufrufen, und dass sich der zeigerbasierte Pfad waehrend einer
    laufenden Geste zurueckhaelt."""
    klient = app.test_client()
    js = klient.get("/static/js/editor.js").get_data(as_text=True)

    for typ in ("gesturestart", "gesturechange", "gestureend"):
        stelle = js.index(f'leinwand.addEventListener("{typ}"')
        block = js[stelle:]
        block = block[: block.index("{ passive: false });") + 20]
        assert "e.preventDefault();" in block
        assert "e.stopPropagation();" in block

    change = js[js.index('leinwand.addEventListener("gesturechange"'):]
    change = change[: change.index("{ passive: false });")]
    assert "e.scale" in change
    assert "e.clientX" in change and "e.clientY" in change
    assert "this._zoomeUmPunkt(" in change

    # Der zeigerbasierte Pfad haelt sich waehrend einer WebKit-Geste zurueck.
    kneif = js[js.index("_kneifBewegen() {"):]
    kneif = kneif[: kneif.index("\n  },")]
    assert "if (this._gestenAnker) return;" in kneif


def test_editor_js_zoomeumpunkt_bleibt_innerhalb_der_zoomgrenzen(app):
    """_zoomeUmPunkt() (gemeinsam von Zeiger- und Gestenpfad genutzt) muss
    dieselben Grenzen wie das Mausrad einhalten (ZOOM_MIN/ZOOM_MAX) - sonst
    liesse sich per Geste ueber "Einpassen" hinaus heraus- oder in absurde
    Groessen hineinzoomen."""
    klient = app.test_client()
    js = klient.get("/static/js/editor.js").get_data(as_text=True)
    funktion = js[js.index("_zoomeUmPunkt(zoomZiel"):]
    funktion = funktion[: funktion.index("\n  },")]
    assert "this.ZOOM_MAX" in funktion
    assert "this.ZOOM_MIN" in funktion


def test_editor_js_mausrad_zoom_um_zeigerpunkt(app):
    """Fruehere Fassung zoomte ohne festen Bildschirmpunkt - die Anlage zog
    sich beim Herauszoomen zur Ecke (0,0) hin zusammen statt zum Mauszeiger
    (Task-Rueckmeldung, mit einer Messreihe belegt: Weltpunkt unter dem
    Zeiger vor/nach dem Zoomen an fuenf Positionen, Abweichung < 0.15px).
    Das Mausrad nutzt jetzt denselben Weg wie Kneifgeste und WebKit-Geste:
    _zoomeUmPunkt() mit dem Zeigerpunkt (nicht der Fingermitte)."""
    klient = app.test_client()
    js = klient.get("/static/js/editor.js").get_data(as_text=True)
    rad = js[js.index('leinwand.addEventListener("wheel"'):]
    rad = rad[: rad.index("{ passive: false });")]
    assert "this._zoomeUmPunkt(" in rad
    assert "e.clientX" in rad and "e.clientY" in rad

    # Strg+Mausrad bleibt dem Browser ueberlassen (Seitenzoom, eine
    # Zugaenglichkeitsfunktion) - fruehester Ausstieg im Lauscher, VOR dem
    # preventDefault().
    vor_preventdefault = rad[: rad.index("e.preventDefault();")]
    assert "e.ctrlKey" in vor_preventdefault


def test_karte_ziehen_uebersteht_pointercancel_ohne_halben_zustand(app):
    """iOS kann eine Beruehrungsfolge mitten in der Geste abbrechen (siehe
    Bericht - dieselbe Wechselwirkung mit der Gestenerkennung wie beim
    Zoomen, vermuteter Grund, warum sich Karten auf dem echten Geraet nicht
    ziehen liessen). karteGreifen() muss pointercancel genauso behandeln
    wie pointerup (Position speichern, Lauscher entfernen), sonst blieben
    Lauscher haengen und die Karte in einem halben Zustand stehen."""
    klient = app.test_client()
    js = klient.get("/static/js/editor.js").get_data(as_text=True)
    greifen = js[js.index("karteGreifen(ereignis, karte) {"):]
    greifen = greifen[: greifen.index("\n  },\n")]
    assert "gruppe.setPointerCapture(ereignis.pointerId)" in greifen
    assert 'window.addEventListener("pointercancel", loslassen)' in greifen
    assert 'window.removeEventListener("pointercancel", loslassen)' in greifen


def test_pfeile_ziehen_uebersteht_pointercancel(app):
    """Dieselbe Absicherung wie bei karteGreifen() (siehe dort) fuer das
    Ziehen eines Verbindungspfeils - ein abgebrochener Zug raeumt die
    Vorschau sauber weg, statt Lauscher haengen zu lassen."""
    klient = app.test_client()
    js = klient.get("/static/js/pfeile.js").get_data(as_text=True)
    assert 'window.addEventListener("pointercancel", abgebrochen)' in js
    assert 'window.removeEventListener("pointercancel", abgebrochen)' in js


def test_karteauswaehlen_oeffnet_panel_nicht_synchron_im_pointerdown(app):
    """Eine CSS-Klassenaenderung, die eine Schublade mitten in derselben
    Beruehrung verschiebt, ist ein plausibler touchcancel-Ausloeser (siehe
    Bericht) - requestAnimationFrame schiebt sie einen Bildwechsel weiter,
    statt sie synchron im pointerdown-Handler auszufuehren."""
    klient = app.test_client()
    js = klient.get("/static/js/editor.js").get_data(as_text=True)
    auswaehlen = js[js.index("karteAuswaehlen(karte, gruppe) {"):]
    auswaehlen = auswaehlen[: auswaehlen.index("\n  },")]
    assert 'requestAnimationFrame(() => this.seitenbereichOeffnen("panel"))' in auswaehlen


def test_sicht_aktualisierung_waehrend_gesten_gebuendelt_sonst_sofort(app):
    """Der vermutete Grund fuer die kurz aufblitzenden weissen Felder bei
    bestimmten Zoomstufen (siehe Bericht): jedes einzelne Zoom-Ereignis baute
    bisher sofort eine komplette Minikarte neu auf. _sichtAktualisierenGebuendelt()
    muss von den drei haeufig feuernden Pfaden (Kneifzoom/Gestenpfad/Mausrad,
    alle drei ueber _zoomeUmPunkt(), sowie Ein-Finger-Schieben) genutzt
    werden - die
    einmaligen Aktionen (Einpassen, Startansicht, Minikarte anklicken,
    Neuzeichnen der ganzen Anlage) bleiben bei der vollen, sofortigen
    aktualisiereSicht(), dort ist eine sofortige Minikarte wichtiger als das
    Buendeln."""
    klient = app.test_client()
    js = klient.get("/static/js/editor.js").get_data(as_text=True)
    assert "_sichtAktualisierenGebuendelt() {" in js
    assert "requestAnimationFrame(() => {" in js

    zoomen = js[js.index("_zoomeUmPunkt(zoomZiel"):]
    zoomen = zoomen[: zoomen.index("\n  },")]
    assert "this._sichtAktualisierenGebuendelt();" in zoomen

    # Das Mausrad buendelt nicht mehr direkt, sondern ueber _zoomeUmPunkt()
    # (siehe test_editor_js_mausrad_zoom_um_zeigerpunkt) - dessen Koerper ist
    # oben (zoomen) bereits auf "this._sichtAktualisierenGebuendelt();"
    # geprueft, hier reicht der Aufruf.
    rad = js[js.index('leinwand.addEventListener("wheel"'):]
    rad = rad[: rad.index("{ passive: false });")]
    assert "this._zoomeUmPunkt(" in rad

    einpassen = js[js.index("einpassen() {"):]
    einpassen = einpassen[: einpassen.index("\n  },\n")]
    assert "this.aktualisiereSicht();" in einpassen
    assert "_sichtAktualisierenGebuendelt" not in einpassen


def test_aktualisiere_minikarte_kein_fruehausstieg_und_massstab_aus_huelle_plus_sichtfeld(app):
    """Zwei Fehler in einem: (1) ein frueher Ausstieg bei "alles sichtbar"
    liess den Rahmen/Inhalt der letzten Zoomstufe im Baum stehen - beim
    Herauszoomen ueber die ganze Anlage hinaus zeigte die Minikarte darum
    einen zu kleinen, veralteten Rahmen (siehe Bericht, mit einer echten
    Messreihe belegt). (2) der Massstab wurde nur aus der Kartenhuelle
    berechnet - sobald das Sichtfeld groesser als die Anlage ist, liefe der
    Rahmen rechnerisch ueber den Rand der Minikarte hinaus. Beides ohne
    Browserlauf nicht direkt pruefbar (siehe Kommentar bei
    test_entf_taste...) - hier nur festgehalten, DASS kein frueher Ausstieg
    mehr vor dem Neuzeichnen steht und dass der Massstab den gemeinsamen
    Bereich aus Huelle UND Sichtfeld nutzt."""
    klient = app.test_client()
    js = klient.get("/static/js/editor.js").get_data(as_text=True)
    funktion = js[js.index("aktualisiereMinikarte() {"):]
    funktion = funktion[: funktion.index("\n  },\n")]

    # "hidden = komplettSichtbar" muss NACH dem Zeichnen stehen (svg.appendChild
    # der Karten-Rechtecke), nicht davor mit einem return dazwischen.
    stelle_zeichnen = funktion.index("svg.textContent = \"\";")
    stelle_hidden = funktion.index("huelle2.hidden = komplettSichtbar;", stelle_zeichnen)
    assert stelle_hidden > stelle_zeichnen
    # Kein "return" zwischen der komplettSichtbar-Berechnung und dem Zeichnen.
    stelle_komplett = funktion.index("const komplettSichtbar")
    zwischen = funktion[stelle_komplett:stelle_zeichnen]
    assert "return" not in zwischen

    # Massstab aus min/max von huelle UND Sichtfeld, nicht huelle allein.
    assert "Math.min(huelle.minX, sichtX0)" in funktion
    assert "Math.max(huelle.maxX, sichtX1)" in funktion
    assert "Math.min(huelle.minY, sichtY0)" in funktion
    assert "Math.max(huelle.maxY, sichtY1)" in funktion


def test_app_hoehe_reagiert_nur_auf_eine_deutliche_verkleinerung_nicht_waehrend_einer_geste(app):
    """Safari meldet ueber VisualViewport "resize" auch waehrend einer
    laufenden Kneifgeste laufend leicht schwankende Werte - die Gesten-
    erkennung selbst laeuft ja weiter, auch wenn preventDefault() am Ende
    die Seiten-Vergroesserung unterbindet (siehe Bericht: "Sichtfeld wird
    beim Zoomen manchmal kleiner, rechts erscheint grau"). --app-hoehe hat
    GENAU EINEN Zweck (die Bildschirmtastatur) und darf nicht auf jede
    Schwankung reagieren, muss waehrend Editor._gestenAnker komplett
    stillstehen, und muss sich nach Gestenende wieder auf den echten Wert
    einstellen - sonst bleibt ein zu kleiner Stand haengen."""
    klient = app.test_client()
    js = klient.get("/static/js/editor.js").get_data(as_text=True)

    funktion = js[js.index("function aktualisiereAppHoehe() {"):]
    funktion = funktion[: funktion.index("\n}\n")]
    assert "if (Editor._gestenAnker) return;" in funktion
    assert "SCHWELLE_TASTATUR_PX" in funktion
    assert "window.innerHeight - window.visualViewport.height" in funktion
    assert "removeProperty(\"--app-hoehe\")" in funktion

    gestureend = js[js.index('leinwand.addEventListener("gestureend"'):]
    gestureend = gestureend[: gestureend.index("{ passive: false });")]
    assert "this._gestenAnker = null;" in gestureend
    assert "aktualisiereAppHoehe();" in gestureend


def test_leinwand_svg_hat_eigenen_behaelter_statt_flex_auf_dem_svg_selbst(app):
    """Safari berechnet die tatsaechlich bemalte Flaeche eines SVG, dessen
    Groesse allein aus einem Flex-Layout kommt, bekanntermassen abweichend
    von seinem CSS-Kasten (siehe Bericht: eine senkrechte Kante schnitt die
    Leinwand mitten durch ab, vom Benutzer im Bild markiert). #leinwand
    darf deshalb kein flex:1 mehr direkt tragen - ein <div>-Behaelter
    (.leinwand-flaeche, kein "replaced element") spannt sich stattdessen
    zwischen festen Kanten auf, das SVG bekommt darin nur noch
    width/height:100% eines damit bereits eindeutig bemessenen Elternrahmens
    - derselbe Aufbau wie bei #minikarte/.minikarte-huelle."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    html = klient.get(f"/anlage/{anlage}").get_data(as_text=True)
    assert 'class="leinwand-flaeche"' in html
    assert 'id="leinwand" width="100%" height="100%"' in html
    assert 'id="minikarte" viewBox="0 0 168 108" width="168" height="108"' in html

    css = klient.get("/static/css/style.css").get_data(as_text=True)
    flaeche = css[css.index(".leinwand-flaeche {"):]
    flaeche = flaeche[: flaeche.index("}") + 1]
    assert "position: absolute;" in flaeche
    assert "top: 52px;" in flaeche

    leinwand_regel = css[css.index("#leinwand {"):]
    leinwand_regel = leinwand_regel[: leinwand_regel.index("}") + 1]
    assert "flex:" not in leinwand_regel
    assert "position: absolute" not in leinwand_regel
    assert "width: 100%;" in leinwand_regel
    assert "height: 100%;" in leinwand_regel


def test_alle_kopfleisten_sprechen_dieselbe_formensprache(app):
    """Startseite, Erklärbereich und Bericht haben eine Kopfleiste - und
    hatten drei verschiedene Formensprachen: die Startseite einen nackten,
    unterstrichenen Link neben einem eckigen gefüllten Knopf; der Bericht
    einen flachen Textlink neben einem Knopf ganz ohne Klasse, den der
    Browser grau und eckig zeichnete; der Editor die Pillen, die
    style.css beschreibt („Kopfleiste des Editors").

    Es gilt jetzt überall dieselbe Regel: der Weg zurück ist .zurueck-knopf,
    jeder benannte Weg eine Pille (.leiste-knopf), und genau EINE gefüllte
    Pille (.leiste-knopf-haupt) trägt den Zweck der Seite.
    """
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")

    start = klient.get("/").get_data(as_text=True)
    kopf = start[start.index('<header class="leiste">'):start.index("</header>")]
    assert 'class="leiste-knopf" href' in kopf          # Bausteine: benannter Weg
    assert kopf.count("leiste-knopf-haupt") == 1        # + Projekt: der Zweck
    assert 'class="knopf-haupt"' not in kopf         # nicht die alte, eckige Form

    lehre = klient.get("/bausteine").get_data(as_text=True)
    assert 'class="zurueck-knopf"' in lehre
    assert "lehre-zurueck" not in lehre

    # Der Bericht braucht einen gerechneten Lauf; hier reicht die Vorlage der
    # Seite selbst, deshalb nur die Klassen im Quelltext der Vorlage.
    vorlage = (
        Path(__file__).resolve().parent.parent / "templates" / "bericht.html"
    ).read_text(encoding="utf-8")
    kopf = vorlage[vorlage.index('<header class="bericht-kopfleiste">'):vorlage.index("</header>")]
    assert 'class="zurueck-knopf"' in kopf
    assert 'class="leiste-knopf" type="button"' in kopf or 'class="leiste-knopf" id' in kopf
    assert kopf.count("leiste-knopf-haupt") == 1
