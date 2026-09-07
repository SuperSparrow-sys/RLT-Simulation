"""Der Aufbau der Oberflaeche: Dateien, Doppelungen, Breitenstufen.

Diese Tests pruefen nicht, wie etwas aussieht - das entscheidet ein Blick auf
den Bildschirm. Sie halten fest, was beim Umbau der Oberflaeche als Regel
vereinbart wurde und was ohne Test unbemerkt zurueckkehrt:

  * Jede Seite bindet die drei gemeinsamen Stylesheets ein und hoechstens ein
    eigenes. Vorher band die Wetterseite die Datei mit den kleinen
    Aktionsknoepfen nicht ein - dort war "Loeschen" weder rot noch stand es
    rechts in seiner Spalte, und niemand merkte es.
  * Eine Klasse wird an genau einer Stelle beschrieben. Es gab
    .wetter-hinzufuegen zweimal: der zweite Satz gewann, der erste blieb als
    Rahmen darum stehen.
  * Kein Farbwert ausserhalb der Tokenliste.
  * Die Anlagenzeile ist ein Raster mit festen Spalten, und sie hat drei
    Breitenstufen.
  * Die Kopfleiste des Schreibtischs misst sich selbst und verschiebt ihre
    Knoepfe, statt sie zu verdoppeln.
"""

import re
from pathlib import Path

import pytest

from app import create_app
from core import anlagen, database
from core.vorlagen import ax_sim_2_1

WURZEL = Path(__file__).resolve().parent.parent
CSS = WURZEL / "static" / "css"
JS = WURZEL / "static" / "js"
VORLAGEN = WURZEL / "templates"

GEMEINSAM = ("grundlage.css", "bedienelemente.css", "listen.css")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def _ohne_kommentare(text):
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


# ---------- Was jede Seite einbindet ---------------------------------------

def test_jede_seite_bindet_die_drei_gemeinsamen_dateien_ein(app):
    """In dieser Reihenfolge - einige Regeln gewinnen nur, weil sie spaeter
    stehen (in den Dateien jeweils am Ort vermerkt)."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    for pfad in ("/", "/anlagen", "/wetter", "/bausteine", f"/anlage/{anlage}"):
        html = klient.get(pfad).get_data(as_text=True)
        stellen = [html.find(f"css/{name}") for name in GEMEINSAM]
        assert all(s != -1 for s in stellen), (pfad, stellen)
        assert stellen == sorted(stellen), pfad


def test_keine_seite_bindet_mehr_als_ein_eigenes_stylesheet_ein(app):
    """Die Aufteilung soll die Seiten leichter machen, nicht die Zahl der
    Dateien vermehren: drei gemeinsame plus hoechstens eine eigene."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    for pfad in ("/", "/anlagen", "/wetter", "/bausteine", f"/anlage/{anlage}"):
        html = klient.get(pfad).get_data(as_text=True)
        dateien = re.findall(r"css/([a-z-]+\.css)", html)
        eigene = [d for d in dateien if d not in GEMEINSAM]
        assert len(eigene) <= 1, (pfad, eigene)


def test_keine_seite_bindet_die_editordatei_ein_ausser_dem_editor(app):
    """editor.css ist mit 44 kB die groesste der fuenf - vor der Aufteilung
    luden alle Seiten sie mit, weil alles in einer Datei stand."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    klient = app.test_client()
    for pfad in ("/", "/anlagen", "/wetter", "/bausteine"):
        assert "css/editor.css" not in klient.get(pfad).get_data(as_text=True), pfad
    assert "css/editor.css" in klient.get(f"/anlage/{anlage}").get_data(as_text=True)


# ---------- Nichts doppelt --------------------------------------------------

def _klassen_definitionen(text):
    """Klassen, die in diesem Text als schlichtes ".name {" beschrieben werden.

    Nur der blanke Fall auf oberster Ebene zaehlt als Beschreibung. ".a .b"
    oder ".a:hover" verfeinern eine anderswo beschriebene Klasse und duerfen
    ueberall stehen; dasselbe gilt fuer eine Regel INNERHALB einer
    Medienabfrage - die aendert eine vorhandene Beschreibung, sie ist keine
    zweite.
    """
    text = _ohne_kommentare(text)
    gefunden = []
    tiefe = 0
    puffer = ""
    for zeichen in text:
        if zeichen == "{":
            if tiefe == 0:
                # Nur ein ALLEIN stehender Selektor beschreibt eine Klasse.
                # Eine Gruppe mit Komma (".a, .b { padding }") teilt eine
                # Eigenschaft unter mehreren - das ist keine zweite
                # Beschreibung, sondern gerade die Vermeidung einer.
                teil = puffer.strip()
                if re.fullmatch(r"\.[a-zA-Z][\w-]*", teil):
                    gefunden.append(teil[1:])
            tiefe += 1
            puffer = ""
        elif zeichen == "}":
            tiefe = max(0, tiefe - 1)
            puffer = ""
        else:
            puffer += zeichen
    return gefunden


@pytest.mark.parametrize("datei", sorted(p.name for p in CSS.glob("*.css")))
def test_keine_klasse_wird_in_einer_datei_zweimal_beschrieben(datei):
    namen = _klassen_definitionen((CSS / datei).read_text())
    doppelt = {n for n in namen if namen.count(n) > 1}
    assert not doppelt, f"{datei}: {sorted(doppelt)}"


def test_keine_klasse_wird_in_zwei_dateien_beschrieben():
    """Eine Klasse gehoert genau einer Datei. Stand sie in zweien, gewann die
    spaeter eingebundene, und die fruehere blieb als Rest stehen - so war es
    bei .wetter-hinzufuegen, wo ein voll breiter Kasten um eine Pille herum
    stehen blieb."""
    heimat = {}
    doppelt = {}
    for pfad in sorted(CSS.glob("*.css")):
        for name in _klassen_definitionen(pfad.read_text()):
            if name in heimat and heimat[name] != pfad.name:
                doppelt.setdefault(name, {heimat[name]}).add(pfad.name)
            heimat.setdefault(name, pfad.name)
    assert not doppelt, {k: sorted(v) for k, v in doppelt.items()}


def test_kein_farbwert_ausserhalb_der_tokenliste():
    """Alle Farben stehen als Variablen in grundlage.css. Ein Zahlenwert
    anderswo laesst sich nicht mitaendern und faellt beim naechsten
    Farbabgleich durchs Raster - das Etikett "Fertig" trug so ein
    hartes Gruen, weil es fuer "hat geklappt" keinen Namen gab."""
    for pfad in sorted(CSS.glob("*.css")):
        if pfad.name == "grundlage.css":
            continue
        treffer = re.findall(r"#[0-9a-fA-F]{3,8}\b", _ohne_kommentare(pfad.read_text()))
        assert not treffer, f"{pfad.name}: {treffer}"


# ---------- Die Anlagenzeile ------------------------------------------------

def _regel(datei, selektor):
    text = (CSS / datei).read_text()
    stelle = text.index(selektor + " {")
    return text[stelle:text.index("}", stelle)]


def test_anlagenzeile_ist_ein_raster_mit_festen_spalten():
    """Der Grund fuer Zeilen statt Kacheln: In einer Kachel stand jede Angabe
    an einer anderen senkrechten Stelle. Das gilt nur mit festen Spalten - als
    Flexbox schrumpfte jede nach ihrem eigenen Inhalt, und bei 820 Punkten
    stand "42 Karten" 13 Punkte weiter rechts als "31 Karten"."""
    regel = _regel("listen.css", ".anlage-zeile")
    assert "display: grid" in regel
    assert "grid-template-columns" in regel
    assert "grid-template-areas" in regel


def test_anlagenzeile_hat_drei_breitenstufen():
    """Voll, gestapelt, schmal - und in jeder gibt zuerst das Beiwerk nach.
    Vorher behielten drei Knoepfe ihre volle Breite, waehrend der Anlagenname
    auf "AX_" zusammengeschnitten wurde."""
    text = (CSS / "listen.css").read_text()
    schwellen = re.findall(r"@media \(max-width: (\d+)px\)", text)
    assert "899" in schwellen and "619" in schwellen, schwellen
    # In der schmalen Stufe bekommen die Knoepfe eine eigene Zeile und duerfen
    # umbrechen (Variante A - kein verstecktes Menue).
    schmal = text[text.index("@media (max-width: 619px)"):]
    assert "aktionen aktionen" in schmal
    assert "flex-wrap: wrap" in schmal


def test_ueberfahren_faerbt_die_zeile_nicht_blau():
    """Blau ist in dieser Oberflaeche die Farbe der Handlung. Als
    Ueberfahr-Zustand war sie zu laut, und die weissen Knoepfe standen als
    Loecher in einem blauen Balken."""
    regel = _regel("listen.css", ".anlage-zeile:hover")
    assert "--surface-alt" in regel
    assert "blue" not in regel


def test_tabellen_streifen_nicht_mehr():
    """Die Wettertabelle traegt Zwischenzeilen je Standort; die zaehlten beim
    Streifenmuster mit, und nach jeder Gruppe kippte es."""
    text = _ohne_kommentare((CSS / "listen.css").read_text())
    assert ".bilanz tbody tr:nth-child(even)" not in text
    assert ".bilanz tbody tr:hover" in text
    # Das Stundenprotokoll streift weiter: 8760 Zeilen ohne Zwischenzeilen,
    # dort ordnet das Muster wirklich.
    assert ".protokoll tbody tr:nth-child(even)" in text


# ---------- Die Kopfleiste des Schreibtischs --------------------------------

LEISTE_JS = (JS / "editor-leiste.js").read_text()


def test_leiste_misst_sich_selbst_statt_das_fenster():
    """Die Leiste ist so breit wie die Buehne, nicht wie das Fenster: Bei 820
    Punkten Fensterbreite nahmen Palette und Parameterfenster 460 davon. Eine
    Regel nach Fensterbreite maesse eine Zahl, die sie nicht betrifft."""
    assert "window.innerWidth" not in LEISTE_JS
    assert "this.leiste.clientWidth" in LEISTE_JS
    assert "ResizeObserver" in LEISTE_JS


def test_leiste_verschiebt_ihre_knoepfe_statt_sie_zu_verdoppeln():
    """Ein Knopf, den es zweimal gaebe - einmal in der Leiste, einmal im
    Menue -, muesste zweimal verdrahtet und zweimal freigeschaltet werden."""
    assert "cloneNode" not in LEISTE_JS
    assert "appendChild(eintrag.element)" in LEISTE_JS
    assert "insertBefore(eintrag.element" in LEISTE_JS


def test_jeder_knopf_der_leiste_weicht_statt_zu_schrumpfen():
    """Ein Knopf wird nie schmaler als sein eigenes Wort - sonst stand
    "Parameter" als "Pa" da, waehrend "Bericht" darueber lag. Nur der
    Anlagenname gibt nach, und der hat einen Boden."""
    text = (CSS / "editor.css").read_text()
    assert "flex-shrink: 0" in text
    boden = _regel("editor.css", ".app .leiste .anlagenname-zeile")
    assert re.search(r"min-width:\s*\d+px", boden), boden


def test_die_stufen_stehen_nur_an_einer_stelle():
    """Die Stufe kommt aus dem Skript (data-stufe). Eigene Medienabfragen im
    Stylesheet waeren ein zweiter Weg zu derselben Entscheidung."""
    text = _ohne_kommentare((CSS / "editor.css").read_text())
    verdaechtig = re.findall(
        r"@media \(max-width: \d+px\)[^{]*\{[^}]*?(\.leiste[\w-]*)\b", text
    )
    assert not verdaechtig, verdaechtig
    assert 'data-stufe' in text


def test_ausweichmenue_ist_leer_und_versteckt_wenn_alles_passt(app):
    """Ein leeres Menue ist ein Knopf, hinter dem nichts steht."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    html = app.test_client().get(f"/anlage/{anlage}").get_data(as_text=True)
    stelle = html.index('id="werkzeugmenue"')
    tag = html[html.rindex("<", 0, stelle):html.index(">", stelle)]
    assert "hidden" in tag, tag
    assert 'id="werkzeugmenue-inhalt"' in html
    assert "hidden" in LEISTE_JS  # das Skript blendet es ein, sobald etwas einzieht


def test_schmale_leinwand_passt_die_anlage_beim_oeffnen_ein():
    """Der verankerte Ausschnitt zeigt auf einem Tablett zwei Karten und einen
    Pfeil, der ins Nichts laeuft. Von zwei schlechten Ansichten ist die
    vollstaendige die brauchbarere."""
    sicht = (JS / "editor-sicht.js").read_text()
    karten = (JS / "editor-karten.js").read_text()
    assert "SCHMALE_LEINWAND" in karten
    stelle = sicht.index("  startAnsicht() {")
    block = sicht[stelle:sicht.index("\n  },", stelle)]
    assert "SCHMALE_LEINWAND" in block


# ---------- Die Beispielanlagen ---------------------------------------------

def test_beispielanlagen_nennen_ihre_zahl_schon_zugeklappt(app):
    """Eine Klappe ohne Zahl ist eine Frage ohne Antwort."""
    from core.lehrinhalte import beispielanlagen

    with app.app_context():
        projekt_id = beispielanlagen.projekt_bausteine()
        beispielanlagen.baue_beispiel("erhitzer", projekt_id)

    html = app.test_client().get("/").get_data(as_text=True)
    stelle = html.index("nebenbereich-zaehler")
    assert ">1<" in html[stelle:stelle + 60], html[stelle:stelle + 60]


def test_beispielanlagen_benutzen_dieselben_zeilen_wie_ein_projekt(app):
    """Ein zweites Kartenformat fuer technisch gleiche Dinge waere nur eine
    Doppelung mehr."""
    from core.lehrinhalte import beispielanlagen

    with app.app_context():
        projekt_id = beispielanlagen.projekt_bausteine()
        beispielanlagen.baue_beispiel("erhitzer", projekt_id)

    html = app.test_client().get("/").get_data(as_text=True)
    inhalt = html[html.index('id="start-lehrmaterial-inhalt"'):]
    assert "anlage-zeile" in inhalt
    assert "projekt-block" in inhalt


# ---------- Der Schreibtisch bringt seine Daten mit --------------------------

def test_editorseite_liefert_anlage_und_palette_mit(app):
    """Beides holte die Seite bis zum Umbau erst nach dem Laden ueber
    /api/palette und /api/anlagen/<id>. Bis die zweite Antwort da war, stand
    der Editor als leere Flaeche mit leerer Palette da - beim ersten Blick und
    auf jedem Bildschirmfoto."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    html = app.test_client().get(f"/anlage/{anlage}").get_data(as_text=True)
    assert 'id="anlage-daten"' in html
    assert 'id="palette-daten"' in html

    import json

    for kennung in ("anlage-daten", "palette-daten"):
        anfang = html.index(f'id="{kennung}"')
        anfang = html.index(">", anfang) + 1
        daten = json.loads(html[anfang:html.index("</script>", anfang)])
        assert daten, kennung
    # Die Anlage steht mit ihren Karten da, nicht nur als Huelle.
    anfang = html.index('id="anlage-daten"')
    anfang = html.index(">", anfang) + 1
    anlage_daten = json.loads(html[anfang:html.index("</script>", anfang)])
    assert anlage_daten["name"] == "AX_SIM 2.1"
    assert len(anlage_daten["karten"]) > 10


def test_die_daten_stehen_als_json_nicht_als_javascript(app):
    """<script type="application/json"> wird nie ausgefuehrt - ein Anlagenname
    mit </script> darin kann also nichts anrichten."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")

    html = app.test_client().get(f"/anlage/{anlage}").get_data(as_text=True)
    for kennung in ("anlage-daten", "palette-daten"):
        stelle = html.index(f'id="{kennung}"')
        tag = html[html.rindex("<", 0, stelle):html.index(">", stelle)]
        assert 'type="application/json"' in tag, tag


def test_editor_zeichnet_ohne_zweite_runde():
    """Die mitgelieferten Daten muessen auch benutzt werden - sonst holt der
    Editor sie trotzdem und die Seite bleibt bis dahin leer."""
    editor = (JS / "editor.js").read_text()
    palette = (JS / "palette.js").read_text()
    assert 'getElementById("anlage-daten")' in editor
    assert 'getElementById("palette-daten")' in palette
    # Nach einer Aenderung ist die Fassung in der Seite veraltet - dann wird
    # wieder gefragt. Der Weg ueber die Schnittstelle bleibt also bestehen.
    assert "/api/anlagen/${anlageId}" in editor
    assert 'fetch("/api/palette")' in palette


def test_die_einpassschwelle_liegt_dort_wo_die_seitenbereiche_weichen():
    """Ein Bildschirm, auf dem neben der Leinwand kein Platz fuer Palette und
    Parameterfenster ist, ist einer, auf dem man zuerst die Uebersicht
    braucht. Zwei verschiedene Zahlen waeren zwei Antworten auf dieselbe
    Frage."""
    karten = (JS / "editor-karten.js").read_text()
    treffer = re.search(r"SCHMALE_LEINWAND:\s*(\d+)", karten)
    assert treffer, "SCHMALE_LEINWAND fehlt"

    css = _ohne_kommentare((CSS / "editor.css").read_text())
    schwelle = re.search(
        r"@media \(max-width: (\d+)px\)[^{]*\{[^}]*knopf-seitenbereich", css
    )
    assert schwelle, "die Schwelle der Seitenbereiche steht nicht mehr in editor.css"
    assert treffer.group(1) == schwelle.group(1), (treffer.group(1), schwelle.group(1))
