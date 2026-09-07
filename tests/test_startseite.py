"""Tests fuer die Eingangsseite und die Wetterseite.

Der Wetterbereich stand bis zum Umbau der Oberflaeche auf der Startseite -
dort nahmen seine beiden Formulare den meisten Platz ein, waehrend die
Projekte darueber in zwei Zeilen abgehandelt waren. Er hat jetzt eine eigene
Seite (templates/wetter.html); die Tests dazu stehen weiter hier, weil sie
dieselbe Sache pruefen wie vorher.

Urspruenglich: Tests fuer die ueberarbeitete Eingangsseite (templates/index.html,
static/js/start.js, static/css/start.css) - eigene Datei statt Erweiterung
von tests/test_pages.py, weil dort parallel am Editor gearbeitet wird und
diese Datei ausschliesslich den Aufgabenbereich der Eingangsseite abdeckt.

Wie an anderer Stelle im Projekt ueblich (siehe z.B.
tests/test_pages.py::test_palette_js_bewaffnet_nur_bei_finger_nicht_bei_maus)
wird JavaScript-Verhalten, das kein Browser-Test hier ausfuehren kann, durch
Ausschneiden der betreffenden Funktion aus dem Quelltext und Pruefen ihres
Wortlauts abgesichert - kein Ersatz fuer einen echten Browser, aber mehr als
nichts."""

import inspect
import re
from datetime import datetime
from pathlib import Path

import pytest

from app import create_app
from core import database

START_JS = (Path(__file__).parent.parent / "static" / "js" / "start.js").read_text()
WETTER_JS = (Path(__file__).parent.parent / "static" / "js" / "wetter.js").read_text()
DIALOGE_JS = (Path(__file__).parent.parent / "static" / "js" / "dialoge.js").read_text()
BERICHT_PY = (Path(__file__).parent.parent / "core" / "bericht.py").read_text()


def seite_mit_lauf(app, status="fertig", wetter_name="Testjahr"):
    """Eine Startseite mit einem Projekt, einer Anlage und einem Lauf.

    Die Anlagenkarte zeigt ihren letzten Lauf; ohne einen gibt es nichts zu
    pruefen. Gerechnet wird eine einzige Stunde - geprueft wird die
    Darstellung, nicht die Physik.
    """
    from core import anlagen, ergebnisse, solver
    from core.vorlagen import ax_sim_2_1
    from core.wetter import speicher

    stunde = {
        "zeitpunkt": datetime(2024, 1, 1, 0), "t_au": 0.0, "x_au": 4.0,
        "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
    }
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Darstellung")
        anlage = ax_sim_2_1.baue(projekt, "Anlage")
        wetter = speicher.datensatz_anlegen(wetter_name, "upload", [stunde])
        graph = anlagen.lade_graph(anlage)
        lauf = solver.Solver(graph).starte([stunde])
        ergebnisse.speichere(anlage, wetter, 0, 1, lauf, graph, dauer=0.1,
                             status=status)
    return app.test_client().get("/").get_data(as_text=True)



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


def test_wetterseite_stellt_online_abrufen_vor_die_datei_hochladen(app):
    """Online abrufen ist der bequemere, empfohlene Weg (Task, Befund 4) -
    er muss im Markup vor dem Upload-Weg stehen, nicht nur optisch groesser
    wirken, sonst liest ihn eine Vorlesesoftware in der falschen
    Reihenfolge vor."""
    klient = app.test_client()
    html = klient.get("/wetter").get_data(as_text=True)
    # Auf die id statt auf die Beschriftung: der Wortlaut hat sich mit dem
    # Ordner-Upload schon einmal geaendert ("Datei" -> "Dateien"), die
    # Reihenfolge der beiden Wege ist aber genau das, was hier zaehlt.
    assert html.index("Online abrufen") < html.index('id="wetter-upload-details"')


def test_wetterseite_datei_hochladen_ist_eingeklappt(app):
    """Der Sonderfall (eigene TRY-Datei) sitzt in einem <details>, das ohne
    ausdruecklichen Klick geschlossen bleibt - kein "open"-Attribut auf dem
    Element selbst."""
    klient = app.test_client()
    html = klient.get("/wetter").get_data(as_text=True)
    start = html.index('id="wetter-upload-details"')
    tag_ende = html.index(">", start)
    element_tag = html[max(0, start - 20) : tag_ende]
    assert "open" not in element_tag
    assert 'id="form-wetter-upload"' in html


def test_wetterseite_enthaelt_weiterhin_das_upload_formular(app):
    """Der Umbau (Online abrufen zuerst, Upload eingeklappt) darf die
    Upload-Felder selbst nicht verlieren - start.js bindet sich weiterhin
    an dieselben ids."""
    klient = app.test_client()
    html = klient.get("/wetter").get_data(as_text=True)
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
        < funktion.index("Anlage aussuchen")
        < funktion.index("Rechnen lassen")
    )
    # Der zweite Schritt fuehrt in den Anlagenkatalog. Vorher stand dort nur
    # ein Satz ohne Weg - wer noch kein Projekt hat, sollte aber genau dorthin
    # gehen, wo die zwoelf fertigen Anlagen liegen.
    assert "/anlagen" in funktion


def test_anlagenkarte_zeigt_datum_und_wetterjahr_des_letzten_laufs(app):
    """Bislang stand bei einem abgeschlossenen Lauf nur der Kostenwert auf der
    Karte ("Eine Anlage sagt nichts über sich") - jetzt zusätzlich, wann
    zuletzt gerechnet wurde und mit welchem Wetterdatensatz.

    Geprüft wird das gerenderte HTML: Der Zettel entsteht serverseitig
    (routes/pages.py, _statuszettel), seit die Startseite ihre Liste nicht
    mehr im Browser baut."""
    html = seite_mit_lauf(app, status="fertig", wetter_name="Testreferenzjahr")
    assert "Testreferenzjahr" in html
    assert re.search(r"\d{2}\.\d{2}\.\d{4} · Testreferenzjahr", html), "kein Datum"



def test_das_datum_wird_nur_als_kalendertag_gelesen(app):
    """gestartet_am kommt als 'YYYY-MM-DD HH:MM:SS' aus core/database.py
    (datetime('now'), UTC). Daraus darf kein Zeitpunkt mit Zeitzone werden,
    dessen Umrechnung den Tag verschieben könnte - der Zettel schneidet die
    zehn Zeichen vorn ab und dreht sie um."""
    from routes.pages import _statuszettel

    _, _, angaben = _statuszettel({
        "letzter_lauf": {
            "id": 1, "status": "fertig", "gestartet_am": "2026-01-31 23:30:00",
            "kosten_gesamt": 1.0, "wetter_name": "W", "anzahl_warnungen": 0,
        }
    })
    assert "31.01.2026" in angaben, angaben



def test_berichtlink_nur_bei_laeufen_mit_ergebnis():
    """Ein Bericht ist nur zu einem 'fertig'- oder 'abgebrochen'-Lauf
    verfügbar (core/bericht.py: STATUS_MIT_ERGEBNIS) - bei 'fehler' oder
    'laeuft' führte der Link ins Leere. Die Liste steht in routes/pages.py
    noch einmal, weil es dort eine reine Oberflächenfrage ist (den Verweis
    zeigen oder nicht); dieser Test hält beide aneinander."""
    from routes.pages import STATUS_MIT_BERICHT

    py_zeile = BERICHT_PY[BERICHT_PY.index("STATUS_MIT_ERGEBNIS = ") :]
    py_zeile = py_zeile[: py_zeile.index("\n")]
    py_werte = re.findall(r'"([^"]+)"', py_zeile)
    assert sorted(STATUS_MIT_BERICHT) == sorted(py_werte)



def test_start_js_einstiegskasten_zaehlt_nur_eigene_projekte():
    """Ein Benutzer, der noch nie ein eigenes Projekt angelegt, aber schon
    einmal eine Beispielanlage unter /bausteine geoeffnet hat, soll den
    Einstiegskasten weiterhin sehen - das automatisch entstandene
    "Bausteine"-Projekt zaehlt dafuer nicht als eigenes."""
    funktion = START_JS[START_JS.index("zeichneEinstieg() {") :]
    funktion = funktion[: funktion.index("\n  },")]
    assert "this.eigeneProjekte().length" in funktion


def test_lehrmaterial_bleibt_versteckt_ohne_beispielanlage(app):
    """Beispielanlagen entstehen erst, wenn jemand /bausteine öffnet. Bis
    dahin soll kein leerer Abschnitt dastehen."""
    klient = app.test_client()
    html = klient.get("/").get_data(as_text=True)
    stelle = html.index('id="start-lehrmaterial"')
    tag = html[stelle : html.index(">", stelle)]
    assert "hidden" in tag or "hidden" in html[stelle : stelle + 120]



def test_berichtlink_steht_hinter_dem_loeschen_knopf(app):
    """Bei einem Zeilenumbruch der Aktionszeile soll „Bericht" allein in die
    zweite Zeile rutschen, nicht der gefährliche „Löschen"-Knopf - deshalb
    steht er im Markup dahinter."""
    html = seite_mit_lauf(app, status="fertig")
    assert html.index("data-anlage-loeschen") < html.index(">Bericht<")



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


def test_die_anlagenzeile_haelt_feste_spalten():
    """Der Grund fuer den Wechsel von Kacheln zu Zeilen: In einer Kachel stand
    jede Angabe an einer anderen senkrechten Stelle und liess sich zwischen
    zwei Anlagen nicht vergleichen. Das gilt nur, solange Kartenzahl und
    Etikett eine feste Spaltenbreite haben - waechst die Spalte mit ihrem
    Inhalt, stehen die Angaben wieder versetzt."""
    css = (
        Path(__file__).resolve().parent.parent / "static" / "css" / "listen.css"
    ).read_text(encoding="utf-8")
    stelle = css.index(".anlage-zeile {")
    block = css[stelle:css.index("}", stelle)]
    assert "display: grid" in block, block
    # Feste Spalten fuer Kartenzahl und Zustand - waechst eine mit ihrem
    # Inhalt, stehen die Angaben wieder versetzt.
    assert re.search(r"grid-template-columns:.*\b76px\b.*\b96px\b", block), block


def test_der_letzte_lauf_kommt_mit_der_anlage(app):
    """Die Anlagenkarte zeigt den letzten Lauf - und bekommt ihn mitgeliefert.

    Vorher holte die Startseite ihn für JEDE Anlage einzeln nach
    (/api/anlagen/<id>/simulationen): bei zehn Anlagen elf Anfragen für eine
    Liste, die in einer Abfrage steht, und bis sie durch waren, zeigte die
    Seite eine leere Fläche. Jetzt liefert core.anlagen.anlagen_von() ihn mit,
    und die Seite steht schon im HTML.

    Dieser Test hält die beiden Seiten aneinander: Welche Felder der Zettel
    liest, steht in routes/pages.py. Fehlt eines in der Auskunft, bleibt auf
    der Karte stillschweigend eine Lücke - genau das ist beim Umbau zweimal
    passiert (Wetterdatensatz, Warnungszahl).
    """
    from core import anlagen as anlagen_modul
    from routes import pages

    quelle = inspect.getsource(pages._statuszettel)
    gelesen = set(re.findall(r"lauf\[.(\w+).\]", quelle))
    gelesen |= set(re.findall(r"lauf\.get\(.(\w+).", quelle))
    assert gelesen, "der Zettel liest gar nichts - Muster geändert?"

    with app.app_context():
        projekt = anlagen_modul.projekt_anlegen("Statusfelder")
        anlagen_modul.anlage_anlegen(projekt, "A")
        anlage = anlagen_modul.anlagen_von(projekt)[0]
    assert "letzter_lauf" in anlage

    geliefert = {"id", "status", "gestartet_am", "kosten_gesamt",
                 "wetter_name", "anzahl_warnungen"}
    fehlend = gelesen - geliefert
    assert not fehlend, (
        f"der Zettel liest {sorted(fehlend)}, "
        f"core.anlagen.anlagen_von() liefert nur {sorted(geliefert)}"
    )


# ---------- Wetterseite: die Liste kommt vom Server -------------------------
#
# Sie kam bis zum Umbau aus dem Browser: start.js holte sie nach dem Laden
# ueber /api/wetter und baute die Tabelle selbst. Die Folge war, dass der
# einzige Inhalt dieser Seite bis zur Antwort fehlte - auf einem Abzug der
# Seite (Screenshot) war sie ueberhaupt nicht zu sehen. Die Tests hier
# beschreiben deshalb, was ohne ein einziges Stueck JavaScript dastehen muss.


def _wetterdatensatz(app, name, ort="", quelle="upload", jahr=2024):
    from core.wetter import speicher

    stunde = {
        "zeitpunkt": datetime(jahr, 1, 1, 0), "t_au": 0.0, "x_au": 4.0,
        "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
    }
    with app.app_context():
        return speicher.datensatz_anlegen(name, quelle, [stunde], ort=ort)


def test_wetterseite_zeigt_die_datensaetze_ohne_javascript(app):
    """Name, Herkunft, Jahr und Stundenzahl jedes Datensatzes stehen im
    ausgelieferten HTML - nicht erst nach einer zweiten Anfrage."""
    _wetterdatensatz(app, "Mittleres Jahr", ort="Pirna", jahr=2015)
    _wetterdatensatz(app, "Hamburg 2022", ort="Hamburg", quelle="open-meteo",
                     jahr=2022)

    html = app.test_client().get("/wetter").get_data(as_text=True)
    assert "Mittleres Jahr" in html
    assert "Hamburg 2022" in html
    # Die Herkunft in der Sprache der Oberflaeche, nicht als Datenbankwort.
    assert "Datei-Upload" in html
    assert "Online-Abruf" in html
    assert "open-meteo" not in html
    assert "2015" in html and "2022" in html


def test_wetterseite_buendelt_nach_standort(app):
    """Ein TRY-Ordner bringt sechs Jahre desselben Ortes mit; ohne die
    Zwischenzeile stuenden sie als sechs zusammenhanglose Zeilen da."""
    _wetterdatensatz(app, "A", ort="Pirna")
    _wetterdatensatz(app, "B", ort="Pirna")
    _wetterdatensatz(app, "C", ort="")

    html = app.test_client().get("/wetter").get_data(as_text=True)
    assert html.count("wetter-standort-zeile") == 2
    # "Ohne Standort" ist kein Standort, sondern dessen Fehlen - es steht
    # deshalb hinter den echten Orten.
    assert html.index("Pirna") < html.index("Ohne Standort")


def test_wetterseite_ohne_datensaetze_klappt_das_hinzufuegen_auf(app):
    """Ist nichts da, sind die beiden Wege das, was als Naechstes zu tun
    ist - dann steht die Klappe offen. Sobald etwas da ist, zaehlt die Liste
    und die Formulare treten zurueck."""
    html = app.test_client().get("/wetter").get_data(as_text=True)
    assert "open" in _tag_von(html, 'id="wetter-hinzufuegen"')

    _wetterdatensatz(app, "Irgendein Jahr", ort="Pirna")
    html = app.test_client().get("/wetter").get_data(as_text=True)
    assert "open" not in _tag_von(html, 'id="wetter-hinzufuegen"')


def _tag_von(html, kennung):
    """Das oeffnende Tag, in dem die Kennung steht - von "<" bis ">"."""
    stelle = html.index(kennung)
    return html[html.rindex("<", 0, stelle) : html.index(">", stelle)]


def test_wetterseite_sperrt_das_loeschen_eines_benutzten_datensatzes(app):
    """Ein Datensatz, auf den ein Simulationslauf zeigt, laesst sich nicht
    loeschen (core.wetter.speicher.datensatz_loeschen). Der Knopf sagt das
    schon vorher, statt den Benutzer erst in die Absage laufen zu lassen."""
    from core import anlagen, ergebnisse, solver
    from core.vorlagen import ax_sim_2_1
    from core.wetter import speicher

    stunde = {
        "zeitpunkt": datetime(2024, 1, 1, 0), "t_au": 0.0, "x_au": 4.0,
        "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
    }
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "A")
        wetter = speicher.datensatz_anlegen("Benutztes Jahr", "upload", [stunde])
        graph = anlagen.lade_graph(anlage)
        lauf = solver.Solver(graph).starte([stunde])
        ergebnisse.speichere(anlage, wetter, 0, 1, lauf, graph, dauer=0.1)

    html = app.test_client().get("/wetter").get_data(as_text=True)
    zeile = html[html.index("Benutztes Jahr"):]
    zeile = zeile[: zeile.index("</tr>")]
    assert "disabled" in zeile
    assert "Simulationslauf" in zeile


def test_startseite_stellt_die_zahl_der_wetterdatensaetze_ins_markup(app):
    """Der Einstiegskasten hakt seinen ersten Schritt ab, sobald ein
    Datensatz da ist. Die Zahl dafuer steht am Kasten selbst - vorher holte
    die Startseite dafuer die ganze Liste ueber /api/wetter, nur um sie zu
    zaehlen. Einen eigenen Wetterabschnitt hat die Uebersicht nicht mehr: Die
    Wetterseite steht in der Kopfleiste."""
    html = app.test_client().get("/").get_data(as_text=True)
    assert 'data-wetter-anzahl="0"' in html

    _wetterdatensatz(app, "Ein Jahr")
    html = app.test_client().get("/").get_data(as_text=True)
    assert 'data-wetter-anzahl="1"' in html


def test_wetter_js_baut_die_wetterliste_nicht_mehr_selbst():
    """Zwei Wege zu derselben Darstellung waeren zwei Wege, die
    auseinanderlaufen: Die Liste steht in der Vorlage, das Skript verdrahtet
    nur noch. Ein erneuter Griff zu /api/wetter waere der Rueckfall."""
    assert "/api/wetter\"" not in WETTER_JS
    assert "bindeWetter()" in WETTER_JS
    # Nach einer Aenderung wird neu geladen, statt die Liste nachzuziehen.
    quelle = inspect.cleandoc(
        WETTER_JS[WETTER_JS.index("async _wetterListeAktualisieren"):]
    )
    assert "window.location.reload()" in quelle[: quelle.index("},")]


def test_start_und_wetterseite_teilen_sich_kein_gemeinsames_grossmodul():
    """Beide Seiten luden bis zur Aufteilung dasselbe 44-kB-Modul in voller
    Laenge: die Wetterseite bekam die Projektdialoge mitgeliefert, die
    Startseite die Ordnerauswertung des Uploads. Was eine Seite nicht braucht,
    laedt sie auch nicht."""
    assert "wetterHochladen" not in START_JS
    assert "projektAnlegenDialog" not in WETTER_JS
    # Die vier gemeinsamen Bausteine stehen genau einmal.
    for name in ("function zeigeFehler", "function htmlSicher",
                 "function bestaetigenDialog", "function textEingabeDialog"):
        assert name in DIALOGE_JS, name
        assert name not in START_JS, name
        assert name not in WETTER_JS, name
