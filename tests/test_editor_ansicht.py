"""Kopfleiste und Legende des Editors.

Was hier geprueft wird, ist nicht die Optik - die laesst sich nur im Browser
beurteilen (und wurde dort nachgestellt und ausgemessen) -, sondern das,
woran der Aufbau haengt: dass jedes Bedienelement der Leiste dieselbe
Grundform traegt, dass es genau EINEN Hauptknopf gibt, und dass die Legende
alle Wegarten nennt, die static/js/pfeile.js zeichnen kann. Faellt eines
davon beim naechsten Umbau heraus, faellt es hier auf und nicht erst dem
Benutzer.
"""

import pathlib
import re

import pytest

from app import create_app
from core import anlagen, database


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


@pytest.fixture
def seite(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
    return app.test_client().get(f"/anlage/{anlage}").get_data(as_text=True)


def test_die_kopfleiste_steht_in_gruppen(seite):
    """Ort, Bearbeitung, Ansicht, Ergebnis - vier Gruppen statt einer Reihe
    aus allem, was ueber die Zeit dazukam."""
    assert seite.count('class="leiste-gruppe') >= 3
    assert 'class="leiste-gruppe leiste-ergebnis"' in seite
    assert 'class="leiste-trenner"' in seite


def test_jedes_bedienelement_der_leiste_traegt_dieselbe_grundform(seite):
    """Die Formensprache haengt daran, dass jeder Knopf .leiste-knopf traegt
    (und die beiden Ausnahmen, die keine eigene Klasse haben koennen, in der
    gemeinsamen CSS-Regel mitgenannt sind: .zurueck-knopf und die
    Zusammenfassung der Legende)."""
    kopf = seite[seite.index('<header class="leiste">'):seite.index("</header>")]
    knoepfe = re.findall(r"<(?:button|a)\s[^>]*id=\"([^\"]+)\"[^>]*>", kopf)
    assert set(knoepfe) >= {
        "btn-anlage-umbenennen", "btn-zurueck", "btn-vor", "btn-einpassen",
        "btn-palette-umschalten", "btn-panel-umschalten", "link-bericht",
        "btn-vergleich", "btn-simulieren",
    }
    for kennung in knoepfe:
        stelle = kopf.index(f'id="{kennung}"')
        anfang = kopf.rindex("<", 0, stelle)
        assert "leiste-knopf" in kopf[anfang:stelle + len(kennung) + 60], (
            f"'{kennung}' faellt aus der Formensprache der Kopfleiste"
        )


def test_genau_ein_hauptknopf(seite):
    """'Simulieren' ist der Zweck der Seite und der einzige gefuellte Knopf -
    zwei Hauptknoepfe waeren keiner."""
    assert seite.count("leiste-knopf-haupt") == 1
    stelle = seite.index("leiste-knopf-haupt")
    assert 'id="btn-simulieren"' in seite[stelle:stelle + 120]


def test_runde_knoepfe_nennen_ihre_handlung_auch_ohne_wort(seite):
    """Auf schmalen Geraeten tragen sie nur ihr Zeichen (siehe style.css,
    @media max-width: 1400px) - dann muss der Name in aria-label und title
    stehen, sonst ist der Knopf fuer Vorlesesoftware und fuer die Maus
    stumm."""
    kopf = seite[seite.index('<header class="leiste">'):seite.index("</header>")]
    for kennung in ("btn-anlage-umbenennen", "btn-zurueck", "btn-vor", "btn-einpassen"):
        stelle = kopf.index(f'id="{kennung}"')
        umfeld = kopf[kopf.rindex("<", 0, stelle):stelle + 200]
        assert "aria-label=" in umfeld, kennung
        assert "title=" in umfeld, kennung


def test_die_legende_nennt_alle_fuenf_luftarten(seite):
    """core/bausteine/basis.py unterscheidet Aussenluft, Zuluft, Abluft,
    Fortluft und Umluft; static/js/pfeile.js zeichnet sie seit dieser
    Aenderung verschieden (LUFTROLLEN). Was gezeichnet wird, muss die
    Legende auch erklaeren."""
    for art in ("aussenluft", "zuluft", "abluft", "fortluft", "umluft"):
        assert f"pfeil-luft-{art}" in seite, art
    for wort in ("Außenluft", "Zuluft", "Abluft", "Fortluft", "Umluft"):
        assert wort in seite, wort


def test_die_legende_nennt_auch_die_uebrigen_wegarten(seite):
    for klasse in ("pfeil-signal", "pfeil-energie", "pfeil-protokoll", "pfeil-mehrdeutig"):
        assert klasse in seite, klasse


def test_melde_und_energiewege_lassen_sich_abschalten(seite):
    """Sie laufen aus der ganzen Anlage auf zwei Karten am Rand zu (in
    AX_SIM 2.1 zwoelf der 61 Pfeile) und queren dabei alles. Der Schalter
    steht in der Legende, weil er zu den Wegarten gehoert, die sie
    erklaert - von Haus aus AN (nichts verschwindet ungefragt)."""
    assert 'id="schalter-meldewege"' in seite
    stelle = seite.index('id="schalter-meldewege"')
    assert "checked" in seite[stelle:stelle + 60]
    assert "Energie- und Meldewege anzeigen" in seite


def test_luftarten_sind_nicht_nur_an_der_farbe_zu_unterscheiden():
    """Dieselbe Regel wie bei Luft/Signal/Energie und den Palettengruppen:
    Farbe ist Verstaerkung, nicht der einzige Traeger. Geprueft wird, dass
    jede der fuenf Luftarten ein EIGENES Strichmuster hat - im
    Schwarzweissdruck bleibt nur das uebrig."""
    css = (
        pathlib.Path(__file__).resolve().parent.parent
        / "static" / "css" / "style.css"
    ).read_text(encoding="utf-8")
    muster = {}
    for art in ("zuluft", "abluft", "aussenluft", "fortluft", "umluft"):
        treffer = re.search(rf"\.pfeil-luft-{art}\s*{{([^}}]*)}}", css)
        assert treffer, art
        regel = treffer.group(1)
        strich = re.search(r"stroke-dasharray:\s*([^;]+);", regel)
        muster[art] = strich.group(1).strip() if strich else "durchgezogen"
    assert len(set(muster.values())) == 5, muster


def test_die_oeffnungsansicht_entscheidet_an_einer_eigenen_schwelle():
    """Beim Öffnen gilt eine Regel mit zwei Ausgängen (static/js/editor.js,
    startAnsicht): passt die ganze Anlage in lesbarer Größe hinein, wird
    eingepasst - sonst öffnet der Editor an der Karte, an der der Luftweg
    beginnt. Eine kleine Beispielanlage (core/lehrinhalte/) wurde sonst
    rechts abgeschnitten gezeigt, obwohl alles Platz gehabt hätte.

    Die Schwelle dafür ist bewusst eine eigene und nicht die, ab der eine
    Karte ihre Zusatzzeilen ausblendet: das sind zwei verschiedene Fragen -
    „ist der Name noch lesbar" gegen „stören die Detailzeilen". Wer sie
    wieder zusammenlegt, macht die Einpassung ohne Not strenger; gemessen
    passt eine Beispielanlage bei Zoom 0,72, die Detailschwelle liegt bei
    0,85. Dieser Test hält die Trennung fest.
    """
    js = (
        pathlib.Path(__file__).resolve().parent.parent
        / "static" / "js" / "editor.js"
    ).read_text(encoding="utf-8")

    einstieg = re.search(r"EINSTIEG_ZOOM_MIN:\s*([\d.]+)", js)
    detail = re.search(r"DETAIL_ZOOM_SCHWELLE:\s*([\d.]+)", js)
    assert einstieg and detail
    assert float(einstieg.group(1)) < float(detail.group(1))

    # startAnsicht() muss gegen die Einstiegsschwelle prüfen, nicht gegen die
    # Detailschwelle - und einpassZoom() dafür benutzen statt die Rechnung
    # ein zweites Mal hinzuschreiben.
    stelle = js.index("  startAnsicht() {")
    abschnitt = js[stelle:stelle + 1600]
    assert "EINSTIEG_ZOOM_MIN" in abschnitt
    assert "einpassZoom(" in abschnitt
    assert "DETAIL_ZOOM_SCHWELLE" not in abschnitt


def test_der_anlagenname_steht_auch_dort_wo_er_ganz_zu_lesen_ist():
    """In der Kopfleiste bleibt für den Namen wenig Platz: die Leiste gibt
    ihren Raum zuerst den Wegen zum Ergebnis, sodass auf einem iPad quer nur
    rund sechs Zeichen und ein Auslassungszeichen übrig bleiben (nachgemessen:
    66 Punkte). Das ist eine bewusste Abwägung - aber „in welcher Anlage bin
    ich" muss beantwortbar bleiben. Deshalb setzt der Editor den ganzen Namen
    zusätzlich in den title des Elements und in den Titel der Seite."""
    js = (
        pathlib.Path(__file__).resolve().parent.parent / "static" / "js" / "editor.js"
    ).read_text(encoding="utf-8")
    stelle = js.index("anlagennamenZeigen(name) {")
    abschnitt = js[stelle:stelle + 400]
    assert "feld.title = name" in abschnitt
    assert "document.title" in abschnitt

    # Und niemand setzt den Namen an der Funktion vorbei.
    assert 'getElementById("anlagenname").textContent =' not in js


def test_der_hauptknopf_bleibt_auch_in_einer_knopfreihe_hervorgehoben():
    """In jeder Knopfreihe soll genau ein Knopf gefüllt sein - der, den man
    am Ende drückt. Die Regel für die Nebenknöpfe (.dialog-knoepfe button)
    traf vorher auch .knopf-haupt und gewann gegen dessen Regel weiter oben
    (Spezifität 0,1,1 gegen 0,1,0): In jedem Dialog sah „Los" danach aus wie
    „Abbrechen" daneben. Nachgemessen im Browser: Hintergrund weiß statt
    blau. Das :not() in der Regel ist deshalb tragend und kein Beiwerk."""
    css = (
        pathlib.Path(__file__).resolve().parent.parent
        / "static" / "css" / "style.css"
    ).read_text(encoding="utf-8")
    stelle = css.index(".dialog-knoepfe button")
    abschnitt = css[stelle:stelle + 400]
    assert ":not(.knopf-haupt)" in abschnitt
    assert ":not(.knopf-haupt-gefahr)" in abschnitt
