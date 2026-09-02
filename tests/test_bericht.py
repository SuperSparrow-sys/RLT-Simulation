"""core/bericht.py und routes/bericht.py - der Ergebnisbericht.

Baut Testlaeufe wie tests/test_ergebnisse.py und tests/test_bilanzansicht.py:
ein synthetischer core.solver.Lauf statt eines echten (minutenlangen)
Solver-Durchlaufs - core.ergebnisse.speichere() speichert ihn genauso wie
einen echten."""

import re
from datetime import datetime, timedelta

import pytest

from app import create_app
from core import anlagen, bericht, database, ergebnisse, pdf as pdfschreiber, solver, zeichnung
from core.vorlagen import ax_sim_2_1
from core.wetter import speicher


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def _wetter_anlegen(anzahl, jahr=2024):
    start = datetime(jahr, 1, 1)
    return speicher.datensatz_anlegen(
        "Testwetter", "upload",
        [
            {
                "zeitpunkt": start + timedelta(hours=i), "t_au": 0.0, "x_au": 4.0,
                "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
            }
            for i in range(anzahl)
        ],
        ort="Musterstadt", jahr=jahr,
    )


def _bilanz_karte_id(graph):
    return next(k.id for k in graph.karten.values() if k.typ == "bilanz")


def _lauf_speichern(app, anzahl_stunden=48, mit_warnung=True):
    """Ein kurzer, synthetischer Lauf mit stundenweise wechselnden
    Bilanzwerten - genug, damit Monatsaggregation, Dauerlinie und
    Warnungsliste des Berichts etwas zu zeigen haben."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_id = ax_sim_2_1.baue(projekt, "A")
        wetter_id = _wetter_anlegen(anzahl_stunden)
        graph = anlagen.lade_graph(anlage_id)
        bilanz_karte_id = _bilanz_karte_id(graph)

        stunden = [
            {
                bilanz_karte_id: {
                    "waerme": float(10 + nummer), "kaelte": float(nummer % 3),
                    "strom_ht": 1.0, "strom_nt": 0.5, "wasser": 0.2,
                }
            }
            for nummer in range(anzahl_stunden)
        ]
        warnungen = (
            [{"stunde": 1, "zeitpunkt": "", "abweichung": 1.0, "text": "nicht konvergiert"}]
            if mit_warnung else []
        )
        lauf = solver.Lauf(
            stunden=stunden,
            bilanz={
                "waerme": sum(s[bilanz_karte_id]["waerme"] for s in stunden),
                "kaelte": sum(s[bilanz_karte_id]["kaelte"] for s in stunden),
                "strom_ht": anzahl_stunden * 1.0, "strom_nt": anzahl_stunden * 0.5,
                "wasser": anzahl_stunden * 0.2,
            },
            warnungen=warnungen,
        )
        simulation_id = ergebnisse.speichere(
            anlage_id, wetter_id, 0, anzahl_stunden, lauf, graph, dauer=1.5
        )
    return anlage_id, simulation_id


# ---------------------------------------------------------------------------
# core.bericht.daten_fuer()
# ---------------------------------------------------------------------------

def test_daten_fuer_unbekannte_simulation_wirft_keyerror(app):
    with app.app_context():
        with pytest.raises(KeyError):
            bericht.daten_fuer(999999)


def test_daten_fuer_laufender_lauf_wirft_nicht_verfuegbar(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_id = ax_sim_2_1.baue(projekt, "A")
        wetter_id = _wetter_anlegen(5)
        simulation_id = ergebnisse.beginne(anlage_id, wetter_id, 0, 5, "kennung-1")
        with pytest.raises(bericht.BerichtNichtVerfuegbar):
            bericht.daten_fuer(simulation_id)


def test_daten_fuer_liefert_kopf_bilanz_und_warnungen(app):
    anlage_id, simulation_id = _lauf_speichern(app)
    with app.app_context():
        daten = bericht.daten_fuer(simulation_id)

    assert daten["anlage"]["id"] == anlage_id
    assert daten["anlage"]["projekt_name"] == "P"
    assert daten["wetter"]["ort"] == "Musterstadt"
    assert daten["stunden_gerechnet"] == 48
    assert daten["status_text"] == "vollständig gerechnet"
    groessen = {z["groesse"] for z in daten["bilanz"]}
    assert groessen == {"waerme", "kaelte", "strom_ht", "strom_nt", "wasser"}
    assert daten["bilanz_summe"] == pytest.approx(
        sum(z["kosten"] for z in daten["bilanz"])
    )
    assert daten["warnungen"]["anzahl"] == 1
    assert daten["karten"]  # die Anlage hat Karten mit Kennwerten
    assert any(k["kennwerte"] for k in daten["karten"])


def test_daten_fuer_baut_monats_und_dauerlinien_diagramm(app):
    _anlage_id, simulation_id = _lauf_speichern(app)
    with app.app_context():
        daten = bericht.daten_fuer(simulation_id)
    diagramme = daten["diagramme"]
    assert diagramme["monat"] is not None
    assert diagramme["dauerlinie"] is not None
    svg = diagramme["monat"].als_svg()
    assert "Jan" in svg and "Wärme" in svg


def test_daten_fuer_ohne_bilanzkarte_liefert_keine_diagramme(app):
    """Eine Anlage ganz ohne Bilanzkarte (z.B. eine, die noch im Aufbau ist)
    darf den Bericht nicht mit einem Fehler abbrechen lassen - nur eben ohne
    Monats-/Dauerliniendiagramm."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_id = anlagen.anlage_anlegen(projekt, "Leer")
        wetter_id = _wetter_anlegen(3)
        graph = anlagen.lade_graph(anlage_id)
        lauf = solver.Lauf(stunden=[{}, {}, {}], bilanz={}, warnungen=[])
        simulation_id = ergebnisse.speichere(anlage_id, wetter_id, 0, 3, lauf, graph, dauer=0.1)
        daten = bericht.daten_fuer(simulation_id)
    assert daten["diagramme"]["monat"] is None
    assert daten["diagramme"]["dauerlinie"] is None
    assert daten["diagramme"]["datenlogger"] == []


# ---------------------------------------------------------------------------
# Hilfsfunktionen: Monatsaggregation, Dauerlinie, Downsampling, Formatierung
# ---------------------------------------------------------------------------

def test_monatswerte_summiert_je_kalendermonat_in_mwh():
    zeitpunkte = [datetime(2024, 1, 1), datetime(2024, 1, 2), datetime(2024, 2, 1)]
    werte = [1000.0, 1000.0, 500.0]  # kWh je Stunde
    monate = bericht._monatswerte(zeitpunkte, werte)
    assert monate[0] == pytest.approx(2.0)  # Januar: 2000 kWh -> 2 MWh
    assert monate[1] == pytest.approx(0.5)  # Februar
    assert sum(monate[2:]) == 0


def test_dauerlinie_punkte_absteigend_sortiert():
    punkte = bericht._dauerlinie_punkte([3.0, 1.0, 5.0, 2.0])
    werte = [w for _, w in punkte]
    assert werte == sorted(werte, reverse=True)
    assert punkte[0] == (0.0, 5.0)
    assert punkte[-1] == (1.0, 1.0)


def test_dauerlinie_punkte_leer():
    assert bericht._dauerlinie_punkte([]) == []


def test_dauerlinie_punkte_stichprobe_bei_vielen_werten():
    werte = list(range(1000))
    punkte = bericht._dauerlinie_punkte(werte, ziel=100)
    assert len(punkte) == 100


def test_downsample_mittel_erhaelt_reihenfolge_und_mittelt():
    werte = [0.0, 10.0, 0.0, 10.0] * 100  # 400 Werte, Mittel bei genuegend grossen Fenstern ~5
    punkte = bericht._downsample_mittel(werte, ziel=10)
    assert len(punkte) == 10
    x_werte = [x for x, _ in punkte]
    assert x_werte == sorted(x_werte)


def test_downsample_mittel_unterhalb_ziel_gibt_alle_werte():
    punkte = bericht._downsample_mittel([1.0, 2.0, 3.0], ziel=100)
    assert len(punkte) == 3


def test_format_zahl_deutsches_format_mit_tausendertrennung():
    assert bericht.format_zahl(1234.5) == "1 234,50"
    assert bericht.format_zahl(0) == "0,00"
    assert bericht.format_zahl(1514.89) == "1 514,89"


# ---------------------------------------------------------------------------
# core.bericht.baue_pdf() - wohlgeformt UND lesbar (nicht nur '%PDF...%%EOF')
# ---------------------------------------------------------------------------

def _pdf_grundpruefung(rohdaten: bytes):
    """Dieselbe Kreuzreferenz-Pruefung wie tests/test_pdf.py, hier bewusst
    knapp gehalten (nur was ein per baue_pdf() erzeugtes Mehrseiten-PDF
    zusaetzlich zu core/pdf.py's eigenen Tests noch beweisen muss: dass am
    Ende wirklich eine gueltige, wiedereinlesbare Datei herauskommt)."""
    assert rohdaten.startswith(b"%PDF-1.4\n")
    assert rohdaten.rstrip().endswith(b"%%EOF")
    treffer = re.search(rb"startxref\s+(\d+)\s+%%EOF", rohdaten)
    assert treffer
    xref_start = int(treffer.group(1))
    assert rohdaten[xref_start : xref_start + 4] == b"xref"
    kopf = re.search(rb"xref\r?\n0 (\d+)\r?\n", rohdaten[xref_start:])
    anzahl = int(kopf.group(1))
    zeilen = rohdaten[xref_start + kopf.end():].splitlines()[:anzahl]
    for nummer, zeile in enumerate(zeilen[1:], start=1):
        offset = int(re.match(rb"(\d{10}) ", zeile).group(1))
        marke = f"{nummer} 0 obj".encode("ascii")
        assert rohdaten[offset : offset + len(marke)] == marke


def test_baue_pdf_erzeugt_lesbares_mehrseiten_pdf(app):
    _anlage_id, simulation_id = _lauf_speichern(app)
    with app.app_context():
        daten = bericht.daten_fuer(simulation_id)
        rohdaten = bericht.baue_pdf(daten)
    _pdf_grundpruefung(rohdaten)
    assert len(rohdaten) > 1000
    # Der Anlagenname und "Jahresbilanz" muessen (WinAnsi-kodiert) im
    # Inhaltsstrom auftauchen - sonst waere nur eine leere Huelle entstanden.
    assert b"Jahresbilanz" in rohdaten


def test_baue_pdf_seitenzahlen_stimmen_mit_seitenzahl_ueberein():
    """dokument.seiten waechst waehrend baue_pdf() - _seitenzahlen_schreiben()
    muss danach mit der ENDGUELTIGEN Seitenzahl schreiben, nicht mit der beim
    jeweiligen Seitenwechsel bekannten."""
    from core.pdf import PDF
    dokument = PDF()
    for _ in range(3):
        dokument.neue_seite()
    bericht._seitenzahlen_schreiben(dokument)
    for seite in dokument.seiten:
        assert any("von 3" in op for op in seite.ops)


def test_zeilen_umbrechen_haelt_zielbreite_grob_ein():
    text = "Wort " * 40
    zeilen = bericht._zeilen_umbrechen(text, max_breite=200, groesse=9)
    assert len(zeilen) > 1
    assert all(zeile.strip() for zeile in zeilen)
    # Nichts geht verloren: alle Woerter kommen wieder vor.
    assert " ".join(zeilen).split() == text.split()


# ---------------------------------------------------------------------------
# routes/bericht.py
# ---------------------------------------------------------------------------

def test_route_html_zeigt_bilanz_und_diagramme(app):
    anlage_id, simulation_id = _lauf_speichern(app)
    antwort = app.test_client().get(f"/anlage/{anlage_id}/lauf/{simulation_id}/bericht")
    assert antwort.status_code == 200
    html = antwort.get_data(as_text=True)
    assert "Jahresbilanz" in html
    assert "<svg" in html  # mindestens ein eingebettetes Diagramm
    assert f"/anlage/{anlage_id}/lauf/{simulation_id}/bericht.pdf" in html


def test_route_pdf_liefert_anwendung_pdf(app):
    anlage_id, simulation_id = _lauf_speichern(app)
    antwort = app.test_client().get(f"/anlage/{anlage_id}/lauf/{simulation_id}/bericht.pdf")
    assert antwort.status_code == 200
    assert antwort.headers["Content-Type"] == "application/pdf"
    assert "attachment" in antwort.headers["Content-Disposition"]
    assert antwort.data.startswith(b"%PDF-1.4")


def test_route_unbekannte_simulation_ist_404(app):
    antwort = app.test_client().get("/anlage/1/lauf/999999/bericht")
    assert antwort.status_code == 404


def test_route_laufender_lauf_ist_409(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_id = ax_sim_2_1.baue(projekt, "A")
        wetter_id = _wetter_anlegen(5)
        simulation_id = ergebnisse.beginne(anlage_id, wetter_id, 0, 5, "kennung-2")
    antwort = app.test_client().get(f"/anlage/{anlage_id}/lauf/{simulation_id}/bericht")
    assert antwort.status_code == 409


def test_route_pdf_dateiname_ohne_sonderzeichen(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_id = anlagen.anlage_anlegen(projekt, 'Anlage "Süd"/Test')
    wetter_id = None
    with app.app_context():
        wetter_id = _wetter_anlegen(2)
        graph = anlagen.lade_graph(anlage_id)
        lauf = solver.Lauf(stunden=[{}, {}], bilanz={}, warnungen=[])
        simulation_id = ergebnisse.speichere(anlage_id, wetter_id, 0, 2, lauf, graph, dauer=0.1)
    antwort = app.test_client().get(f"/anlage/{anlage_id}/lauf/{simulation_id}/bericht.pdf")
    assert antwort.status_code == 200
    dateiname = re.search(r'filename="([^"]+)"', antwort.headers["Content-Disposition"]).group(1)
    assert '"' not in dateiname and "/" not in dateiname


# ---------------------------------------------------------------------------
# core.bericht._wetter_kopfzeile() - Ort/Jahr nicht doppelt nennen, wenn der
# (frei vergebene) Name eines Wetterdatensatzes sie schon enthaelt.
# ---------------------------------------------------------------------------

def test_wetter_kopfzeile_ohne_wetterdatensatz():
    assert bericht._wetter_kopfzeile(None) == "–"
    assert bericht._wetter_kopfzeile({}) == "–"


def test_wetter_kopfzeile_ergaenzt_ort_und_jahr_wenn_sie_im_namen_fehlen():
    zeile = bericht._wetter_kopfzeile(
        {"name": "Testwetter", "ort": "Musterstadt", "jahr": 2024}
    )
    assert zeile == "Testwetter · Musterstadt · 2024"


def test_wetter_kopfzeile_unterdrueckt_ort_und_jahr_wenn_der_name_sie_schon_traegt():
    """Regressionstest: 'Dresden 2023' als Name plus Ort 'Dresden' und Jahr
    2023 ergab vorher 'Dresden 2023 · Dresden · 2023' - dieselbe Angabe
    dreifach."""
    zeile = bericht._wetter_kopfzeile({"name": "Dresden 2023", "ort": "Dresden", "jahr": 2023})
    assert zeile == "Dresden 2023"


def test_wetter_kopfzeile_ergaenzt_nur_den_fehlenden_teil():
    zeile = bericht._wetter_kopfzeile({"name": "Dresden 2023", "ort": "Leipzig", "jahr": 2023})
    assert zeile == "Dresden 2023 · Leipzig"


def test_daten_fuer_liefert_wetter_kopfzeile(app):
    _anlage_id, simulation_id = _lauf_speichern(app)
    with app.app_context():
        daten = bericht.daten_fuer(simulation_id)
    # _wetter_anlegen() legt einen Namen an, der Ort/Jahr nicht enthaelt -
    # beides muss also in der Kopfzeile ergaenzt werden.
    assert daten["wetter_kopfzeile"] == "Testwetter · Musterstadt · 2024"


# ---------------------------------------------------------------------------
# _Schreiber.zwischentitel()/ueberschrift() - eine Ueberschrift darf nicht
# ohne das erste Stueck ihres Inhalts am Seitenende stehen.
# ---------------------------------------------------------------------------

def _schreiber_bei_y(y):
    """Ein frischer _Schreiber mit direkt gesetztem Fuellstand 'y' - praeziser
    als ihn ueber absatz()-Aufrufe anzunaehern, deren Zeilenhoehe die exakte
    Position sonst vom Zufall der letzten Restzeile abhaengig macht."""
    dokument = pdfschreiber.PDF()
    schreiber = bericht._Schreiber(dokument, "Testkopf")
    schreiber.y = y
    return schreiber


# Bei dieser y-Position passt eine Ueberschrift allein noch auf die Seite
# (y + Ueberschrifthoehe <= unterer Rand), eine Ueberschrift plus ein
# Diagramm (oder die Vorgabe-mindest_folgehoehe) aber nicht mehr - genau der
# Grenzfall, an dem eine Ueberschrift ohne ihren Inhalt verwaisen kann.
_Y_KNAPP_VOR_SEITENENDE = 700


def test_zwischentitel_haelt_ueberschrift_mit_erstem_diagramm_zusammen():
    """Regressionstest fuer den gemeldeten Befund: 'Diagramme' stand allein
    am Seitenende, das erste Diagramm kam erst auf der naechsten Seite."""
    schreiber = _schreiber_bei_y(_Y_KNAPP_VOR_SEITENENDE)
    leinwand = zeichnung.Leinwand(200, 180)
    schreiber.zwischentitel("Diagramme", mindest_folgehoehe=leinwand.hoehe + 14)
    seite_der_ueberschrift = schreiber.seite
    schreiber.diagramm(leinwand)
    assert schreiber.seite is seite_der_ueberschrift, (
        "Ueberschrift und ihr erstes Diagramm muessen auf derselben Seite landen"
    )


def test_zwischentitel_ohne_reservierung_laesst_die_ueberschrift_verwaisen():
    """Gegenprobe: OHNE mindest_folgehoehe (der Zustand vor dem Fix) bricht
    die Seite tatsaechlich zwischen Ueberschrift und Inhalt um - das belegt,
    dass der obige Test die Reservierung wirklich prueft und nicht zufaellig
    gruen ist."""
    schreiber = _schreiber_bei_y(_Y_KNAPP_VOR_SEITENENDE)
    schreiber.zwischentitel("Diagramme", mindest_folgehoehe=0)
    seite_der_ueberschrift = schreiber.seite
    leinwand = zeichnung.Leinwand(200, 180)
    schreiber.diagramm(leinwand)
    assert schreiber.seite is not seite_der_ueberschrift


def test_zwischentitel_vorgabewert_haelt_ueberschrift_mit_einem_absatz_zusammen():
    """Ohne ausdruecklich angegebene mindest_folgehoehe (z.B. vor 'Warnungen')
    muss der Vorgabewert (18pt) trotzdem mindestens einen Absatz danach
    sichern. y=745 liegt genau in dem Fenster, in dem eine Ueberschrift ALLEIN
    noch auf die Seite passt (y + 27,5 <= 779,89), Ueberschrift PLUS
    Vorgabewert (y + 45,5) aber nicht mehr - nur die Reservierung verhindert
    hier den Seitenwechsel zwischen Ueberschrift und Absatz."""
    schreiber = _schreiber_bei_y(745)
    schreiber.zwischentitel("Warnungen")
    seite_der_ueberschrift = schreiber.seite
    schreiber.absatz("Alle Stunden konvergiert.")
    assert schreiber.seite is seite_der_ueberschrift


def test_baue_pdf_diagramme_ueberschrift_steht_mit_diagramm_auf_derselben_seite(app):
    """Ende-zu-Ende-Variante des Regressionstests: im tatsaechlich erzeugten
    Bericht darf zwischen der Textzeile 'Diagramme' und dem Beginn des ersten
    Diagramms kein Seitenwechsel liegen."""
    _anlage_id, simulation_id = _lauf_speichern(app, anzahl_stunden=48)
    with app.app_context():
        daten = bericht.daten_fuer(simulation_id)
        # Wie bei _Y_KNAPP_VOR_SEITENENDE: eine y-Position, an der eine
        # Ueberschrift allein noch passt, mitsamt einem Diagramm aber nicht.
        schreiber = _schreiber_bei_y(_Y_KNAPP_VOR_SEITENENDE)
        diagramme = daten["diagramme"]
        erstes_diagramm = diagramme["monat"] or diagramme["dauerlinie"]
        assert erstes_diagramm is not None
        schreiber.zwischentitel("Diagramme", mindest_folgehoehe=erstes_diagramm.hoehe + 14)
        seite_der_ueberschrift = schreiber.seite
        schreiber.diagramm(diagramme["monat"])
        schreiber.diagramm(diagramme["dauerlinie"])
    assert schreiber.seite is seite_der_ueberschrift
