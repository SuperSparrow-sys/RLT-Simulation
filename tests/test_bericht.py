"""core/bericht.py und routes/bericht.py - der Ergebnisbericht.

Baut Testlaeufe wie tests/test_ergebnisse.py und tests/test_bilanzansicht.py:
ein synthetischer core.solver.Lauf statt eines echten (minutenlangen)
Solver-Durchlaufs - core.ergebnisse.speichere() speichert ihn genauso wie
einen echten."""

import math
import re
import time
from pathlib import Path
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


def _karte_id(graph, typ):
    return next(k.id for k in graph.karten.values() if k.typ == typ)


def _lauf_mit_logger_speichern(app, anzahl_stunden=48):
    """Wie _lauf_speichern(), zusaetzlich mit bestueckter Datenlogger-Karte
    (ax_sim_2_1 hat vier benannte Spalten: 'WRG'/'T_ZU WRG'/'T Raum'/
    'F Raum') - fuer Tests der Reihen-Auswahl, die auch Datenlogger-Spalten
    einschliessen soll."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_id = ax_sim_2_1.baue(projekt, "A")
        wetter_id = _wetter_anlegen(anzahl_stunden)
        graph = anlagen.lade_graph(anlage_id)
        bilanz_karte_id = _karte_id(graph, "bilanz")
        logger_id = _karte_id(graph, "datenlogger")

        stunden = [
            {
                bilanz_karte_id: {
                    "waerme": float(10 + n), "kaelte": float(n % 3),
                    "strom_ht": 1.0, "strom_nt": 0.5, "wasser": 0.2,
                },
                logger_id: {
                    "wert_1": float(n), "wert_2": 20.0 + n * 0.1,
                    "wert_3": 21.0, "wert_4": 6.0,
                },
            }
            for n in range(anzahl_stunden)
        ]
        lauf = solver.Lauf(
            stunden=stunden,
            bilanz={
                "waerme": sum(s[bilanz_karte_id]["waerme"] for s in stunden),
                "kaelte": sum(s[bilanz_karte_id]["kaelte"] for s in stunden),
                "strom_ht": anzahl_stunden * 1.0, "strom_nt": anzahl_stunden * 0.5,
                "wasser": anzahl_stunden * 0.2,
            },
            warnungen=[],
        )
        simulation_id = ergebnisse.speichere(
            anlage_id, wetter_id, 0, anzahl_stunden, lauf, graph, dauer=1.5
        )
    return anlage_id, simulation_id


def _lauf_im_zeitraum_speichern(app, von_stunde, anzahl_stunden, jahr=2023):
    """Wie _lauf_speichern(), aber mit einem Wetterdatensatz fuer das ganze
    Jahr und einem Lauf, der erst bei 'von_stunde' beginnt - fuer Tests, die
    einen bestimmten Kalenderausschnitt (z.B. Ende April bis Anfang Juni)
    treffen muessen, was mit dem immer bei Stunde 0 (= 1. Januar)
    beginnenden _lauf_speichern() nicht geht."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_id = ax_sim_2_1.baue(projekt, "A")
        wetter_id = _wetter_anlegen(8760, jahr=jahr)
        graph = anlagen.lade_graph(anlage_id)
        bilanz_karte_id = _bilanz_karte_id(graph)

        stunden = [
            {
                bilanz_karte_id: {
                    "waerme": float(10 + n), "kaelte": float(n % 3),
                    "strom_ht": 1.0, "strom_nt": 0.5, "wasser": 0.2,
                }
            }
            for n in range(anzahl_stunden)
        ]
        lauf = solver.Lauf(
            stunden=stunden,
            bilanz={
                "waerme": sum(s[bilanz_karte_id]["waerme"] for s in stunden),
                "kaelte": sum(s[bilanz_karte_id]["kaelte"] for s in stunden),
                "strom_ht": anzahl_stunden * 1.0, "strom_nt": anzahl_stunden * 0.5,
                "wasser": anzahl_stunden * 0.2,
            },
            warnungen=[],
        )
        simulation_id = ergebnisse.speichere(
            anlage_id, wetter_id, von_stunde, von_stunde + anzahl_stunden, lauf, graph, dauer=1.0
        )
    return anlage_id, simulation_id


def _jahr_lauf_speichern(app, jahr=2023):
    """Ein kuenstlicher, aber realistisch geformter Volljahreslauf (8760
    Stunden, 2023 - kein Schaltjahr) fuer die Jahresdiagramme in
    Stundenaufloesung: Waerme hoch im Winter, Kaelte hoch im Sommer, Strom
    mit taeglichem Gang plus vereinzelten Lastspitzen, dieselbe Kurvenform
    wie im Excel-Vorbild des Benutzers (treppenfoermig fuer Waerme/Kaelte,
    stark gezackt fuer eine Lueftungs-Groesse). Kein echter Solver-Lauf (der
    braeuchte acht Minuten) - core.ergebnisse.speichere() speichert das
    genauso wie einen echten Lauf."""
    anzahl_stunden = 8760
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage_id = ax_sim_2_1.baue(projekt, "Jahresanlage")
        wetter_id = _wetter_anlegen(anzahl_stunden, jahr=jahr)
        graph = anlagen.lade_graph(anlage_id)
        bilanz_karte_id = _karte_id(graph, "bilanz")
        logger_id = _karte_id(graph, "datenlogger")

        stunden = []
        for n in range(anzahl_stunden):
            jahreszeit = math.cos(2 * math.pi * (n - 30 * 24) / anzahl_stunden)  # +1 im Winter
            tagesgang = math.sin(2 * math.pi * (n % 24) / 24)
            waerme = max(0.0, 220.0 * jahreszeit) + (150.0 if n % 733 == 0 else 0.0)
            kaelte = max(0.0, -180.0 * jahreszeit) + (140.0 if n % 611 == 0 else 0.0)
            strom = 40.0 + 25.0 * max(0.0, tagesgang) + (60.0 if n % 401 == 0 else 0.0)
            aussentemperatur = 10.0 + 12.0 * jahreszeit + 3.0 * tagesgang
            stunden.append({
                bilanz_karte_id: {
                    "waerme": waerme, "kaelte": kaelte,
                    "strom_ht": strom * 0.6, "strom_nt": strom * 0.4, "wasser": 0.1,
                },
                logger_id: {
                    "wert_1": aussentemperatur, "wert_2": 20.0 + tagesgang,
                    "wert_3": 21.0, "wert_4": 6.0,
                },
            })
        lauf = solver.Lauf(
            stunden=stunden,
            bilanz={
                "waerme": sum(s[bilanz_karte_id]["waerme"] for s in stunden),
                "kaelte": sum(s[bilanz_karte_id]["kaelte"] for s in stunden),
                "strom_ht": sum(s[bilanz_karte_id]["strom_ht"] for s in stunden),
                "strom_nt": sum(s[bilanz_karte_id]["strom_nt"] for s in stunden),
                "wasser": anzahl_stunden * 0.1,
            },
            warnungen=[],
        )
        simulation_id = ergebnisse.speichere(
            anlage_id, wetter_id, 0, anzahl_stunden, lauf, graph, dauer=5.0
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


# ---------------------------------------------------------------------------
# Jahresverlauf in Stundenwerten: Einhuellende, Monatsmarken, Auswahl
# ---------------------------------------------------------------------------

def test_einhuellende_punkte_unterhalb_ziel_gibt_alle_werte():
    punkte = bericht._einhuellende_punkte([1.0, 2.0, 3.0], spalten=100)
    assert len(punkte) == 3


def test_einhuellende_punkte_leer():
    assert bericht._einhuellende_punkte([]) == []


def test_einhuellende_punkte_haelt_spitzen_die_eine_mittelung_verschlucken_wuerde():
    """Der Kern der Entscheidung fuer Minimum/Maximum statt Mittelung: eine
    einzelne Lastspitze inmitten vieler Nullen bleibt im Diagramm sichtbar -
    _downsample_mittel() wuerde denselben Verlauf zu einer flachen Linie
    nahe 0 mitteln."""
    werte = [0.0] * 3000 + [500.0] + [0.0] * 2999  # eine Spitze unter 6000 Nullen
    punkte = bericht._einhuellende_punkte(werte, spalten=300)
    assert max(v for _, v in punkte) == 500.0
    # Zur Gegenprobe: die Mittelung im selben Fenster verschluckt die Spitze.
    gemittelt = bericht._downsample_mittel(werte, ziel=300)
    assert max(v for _, v in gemittelt) < 500.0


def test_einhuellende_punkte_bleibt_innerhalb_der_spaltenzahl():
    werte = [float(i % 17) for i in range(8760)]
    punkte = bericht._einhuellende_punkte(werte, spalten=300)
    assert len(punkte) <= 600  # hoechstens 2 Punkte je Spalte
    x_werte = [x for x, _ in punkte]
    assert x_werte == sorted(x_werte)
    assert min(x_werte) >= 0.0 and max(x_werte) <= 1.0


def test_monatsmarken_eine_marke_je_kalendermonat():
    zeitpunkte = (
        [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(31 * 24)]
        + [datetime(2024, 2, 1) + timedelta(hours=i) for i in range(5 * 24)]
    )
    marken = bericht._monatsmarken(zeitpunkte)
    assert [text for _, text in marken] == ["Jan", "Feb"]
    assert marken[0][0] == 0.0
    assert 0.0 < marken[1][0] < 1.0


def test_monatsmarken_leer():
    assert bericht._monatsmarken([]) == []


def test_gemeinsame_einheit_bei_gleicher_einheit():
    reihen = [{"einheit": "kW"}, {"einheit": "kW"}]
    assert bericht._gemeinsame_einheit(reihen) == "kW"


def test_gemeinsame_einheit_bei_gemischten_einheiten_ist_leer():
    reihen = [{"einheit": "kW"}, {"einheit": "°C"}]
    assert bericht._gemeinsame_einheit(reihen) == ""


def test_reihen_auswaehlen_none_gibt_standardauswahl():
    alle = [
        {"schluessel": "waerme"}, {"schluessel": "kaelte"}, {"schluessel": "strom"},
        {"schluessel": "logger-1-0"},
    ]
    ausgewaehlt = bericht._reihen_auswaehlen(alle, None)
    assert [r["schluessel"] for r in ausgewaehlt] == ["waerme", "kaelte", "strom"]


def test_reihen_auswaehlen_eigene_auswahl():
    alle = [{"schluessel": "waerme"}, {"schluessel": "kaelte"}, {"schluessel": "logger-1-0"}]
    ausgewaehlt = bericht._reihen_auswaehlen(alle, ["logger-1-0"])
    assert [r["schluessel"] for r in ausgewaehlt] == ["logger-1-0"]


def test_reihen_auswaehlen_leere_liste_ist_eine_ausdrueckliche_leere_auswahl():
    """Eine leere Liste ist NICHT dasselbe wie None - None bedeutet 'noch
    keine eigene Auswahl', eine leere Liste 'der Benutzer hat alles
    abgehakt'."""
    alle = [{"schluessel": "waerme"}]
    assert bericht._reihen_auswaehlen(alle, []) == []


def test_bilanzgroessen_stunden_farbe_und_muster_je_reihe_unterschiedlich():
    """Waerme/Kaelte/Strom muessen sich auch ohne Farbwahrnehmung
    unterscheiden lassen - Farbe UND Strichmuster duerfen sich darum
    zwischen den drei Reihen nicht ueberschneiden."""
    farben = [f for _, _, _, f, _ in bericht.BILANZGROESSEN_STUNDEN]
    muster = [m for _, _, _, _, m in bericht.BILANZGROESSEN_STUNDEN]
    assert len(set(farben)) == len(farben)
    assert len(set(muster)) == len(muster)


def test_weitere_reihen_stil_bleibt_ueber_13_reihen_eindeutig():
    """5 Farben x 4 Muster = 20 Kombinationen - mehr als die hoechstens 10
    Datenlogger-Spalten plus 3 Bilanzgroessen, die gleichzeitig zur Auswahl
    stehen koennen."""
    kombinationen = {bericht._weitere_reihen_stil(i) for i in range(13)}
    assert len(kombinationen) == 13


def test_vier_monats_fenster_deckt_alle_zwoelf_monate_ohne_ueberlappung():
    monate_gesamt = []
    for von, bis, _ in bericht._VIER_MONATS_FENSTER:
        monate_gesamt.extend(range(von, bis + 1))
    assert sorted(monate_gesamt) == list(range(1, 13))


def test_vier_monats_ausschnitte_liefert_drei_fenster_fuer_ein_volles_jahr():
    zeitpunkte = [datetime(2023, 1, 1) + timedelta(hours=i) for i in range(8760)]
    reihen = [{"schluessel": "waerme", "label": "Wärme", "einheit": "kW",
               "farbe": zeichnung.FARBE_WAERME, "muster": None,
               "werte": [float(i % 24) for i in range(8760)]}]
    ausschnitte = bericht._vier_monats_ausschnitte(reihen, zeitpunkte)
    assert len(ausschnitte) == 3


def test_vier_monats_ausschnitte_ohne_daten_in_einem_fenster_bleibt_es_aus():
    # Nur die ersten drei Monate vorhanden - das dritte Fenster (Sep-Dez)
    # bekommt keine Daten und darf nicht als leere Leinwand auftauchen.
    # 150 Tage ab 1. Januar 2023 reichen bis in den Mai (Jan 31 + Feb 28 +
    # Mrz 31 + Apr 30 = 120, plus 30 weitere Tage) - das erste Fenster
    # (Jan-Apr) ist so voll gedeckt, das zweite (Mai-Aug) nur teilweise, das
    # dritte (Sep-Dez) bleibt ganz ohne Daten.
    zeitpunkte = [datetime(2023, 1, 1) + timedelta(hours=i) for i in range(150 * 24)]
    reihen = [{"schluessel": "waerme", "label": "Wärme", "einheit": "kW",
               "farbe": zeichnung.FARBE_WAERME, "muster": None,
               "werte": [1.0] * len(zeitpunkte)}]
    ausschnitte = bericht._vier_monats_ausschnitte(reihen, zeitpunkte)
    assert len(ausschnitte) == 2  # Jan-Apr und Mai-Aug, nicht Sep-Dez


def test_vier_monats_ausschnitte_kurzer_lauf_komplett_in_einem_fenster_bleibt_aus():
    """Ein kurzer Lauf, der ganz in ein einziges Vier-Monats-Fenster faellt
    (hier: 30 Stunden im August) - genau der Fall beim Ausprobieren mit
    einem kurzen Lauf. Der Ausschnitt zeigt dann Punkt fuer Punkt dieselbe
    Kurve wie der Jahresverlauf selbst und bringt nichts - er bleibt aus."""
    zeitpunkte = [datetime(2023, 8, 10) + timedelta(hours=i) for i in range(30)]
    reihen = [{"schluessel": "waerme", "label": "Wärme", "einheit": "kW",
               "farbe": zeichnung.FARBE_WAERME, "muster": None,
               "werte": [float(i) for i in range(30)]}]
    ausschnitte = bericht._vier_monats_ausschnitte(reihen, zeitpunkte)
    assert ausschnitte == []


def test_vier_monats_ausschnitte_lauf_ueber_zwei_fenster_bleiben_beide_erhalten():
    """Ein Lauf, der die Grenze zwischen zwei Fenstern ueberschreitet (hier:
    20. April bis 4. Juni) deckt in KEINEM einzelnen Fenster den gesamten
    Lauf ab - beide Ausschnitte zeigen darum etwas, was der Jahresverlauf
    allein nicht auflöst, und bleiben erhalten."""
    zeitpunkte = [datetime(2023, 4, 20) + timedelta(hours=i) for i in range(45 * 24)]
    reihen = [{"schluessel": "waerme", "label": "Wärme", "einheit": "kW",
               "farbe": zeichnung.FARBE_WAERME, "muster": None,
               "werte": [float(i % 24) for i in range(len(zeitpunkte))]}]
    ausschnitte = bericht._vier_monats_ausschnitte(reihen, zeitpunkte)
    assert len(ausschnitte) == 2


def test_daten_fuer_kurzer_lauf_in_einem_fenster_hat_jahresverlauf_aber_keinen_ausschnitt(app):
    """Ende-zu-Ende-Variante: ein 30-Stunden-Lauf (Standardwetter beginnt am
    1. Januar, faellt also komplett ins Fenster Januar-April) bekommt einen
    Jahresverlauf, aber keinen (redundanten) Ausschnitt."""
    _anlage_id, simulation_id = _lauf_speichern(app, anzahl_stunden=30)
    with app.app_context():
        daten = bericht.daten_fuer(simulation_id)
    diagramme = daten["diagramme"]
    assert diagramme["jahr_stunden"] is not None
    assert diagramme["vier_monats_ausschnitte"] == []


def test_daten_fuer_lauf_ueber_zwei_fenster_behaelt_beide_ausschnitte(app):
    # 20. April bis 4. Juni 2023 - ueberschreitet die Grenze zwischen den
    # Fenstern Januar-April und Mai-August.
    _anlage_id, simulation_id = _lauf_im_zeitraum_speichern(
        app, von_stunde=(31 + 28 + 31 + 19) * 24, anzahl_stunden=45 * 24
    )
    with app.app_context():
        daten = bericht.daten_fuer(simulation_id)
    assert len(daten["diagramme"]["vier_monats_ausschnitte"]) == 2


def test_daten_fuer_baut_jahresverlauf_in_stundenwerten_mit_standardauswahl(app):
    _anlage_id, simulation_id = _lauf_speichern(app, anzahl_stunden=72)
    with app.app_context():
        daten = bericht.daten_fuer(simulation_id)
    diagramme = daten["diagramme"]
    assert {r["schluessel"] for r in diagramme["stunden_reihen"]} >= {"waerme", "kaelte", "strom"}
    assert set(diagramme["stunden_ausgewaehlt"]) == {"waerme", "kaelte", "strom"}
    assert diagramme["jahr_stunden"] is not None
    svg = diagramme["jahr_stunden"].als_svg()
    assert "Wärme" in svg and "Kälte" in svg and "Strom" in svg


def test_daten_fuer_mit_eigener_auswahl_zeigt_nur_die_gewaehlten_reihen(app):
    _anlage_id, simulation_id = _lauf_mit_logger_speichern(app, anzahl_stunden=72)
    with app.app_context():
        daten = bericht.daten_fuer(simulation_id, ausgewaehlte_reihen=["waerme"])
    diagramme = daten["diagramme"]
    assert diagramme["stunden_ausgewaehlt"] == ["waerme"]
    svg = diagramme["jahr_stunden"].als_svg()
    assert "Wärme" in svg
    assert "Kälte" not in svg and "Strom" not in svg


def test_daten_fuer_mit_datenlogger_spalte_in_der_auswahl(app):
    _anlage_id, simulation_id = _lauf_mit_logger_speichern(app, anzahl_stunden=72)
    with app.app_context():
        daten = bericht.daten_fuer(simulation_id)
        logger_reihen = [
            r for r in daten["diagramme"]["stunden_reihen"] if r["gruppe"] == "Datenlogger"
        ]
        assert logger_reihen  # die Vorlage hat vier benannte Spalten
        schluessel = logger_reihen[0]["schluessel"]
        daten = bericht.daten_fuer(simulation_id, ausgewaehlte_reihen=[schluessel])
    assert daten["diagramme"]["stunden_ausgewaehlt"] == [schluessel]
    assert daten["diagramme"]["jahr_stunden"] is not None


def test_daten_fuer_mit_leerer_auswahl_baut_kein_stundendiagramm(app):
    _anlage_id, simulation_id = _lauf_speichern(app, anzahl_stunden=72)
    with app.app_context():
        daten = bericht.daten_fuer(simulation_id, ausgewaehlte_reihen=[])
    diagramme = daten["diagramme"]
    assert diagramme["stunden_ausgewaehlt"] == []
    assert diagramme["jahr_stunden"] is None
    assert diagramme["vier_monats_ausschnitte"] == []


# ---------------------------------------------------------------------------
# routes/bericht.py - Auswahl per Query-String, HTML wie PDF
# ---------------------------------------------------------------------------

def _kaestchen_angehakt(html, schluessel):
    """Ob das Auswahlkaestchen mit diesem Schluessel 'checked' traegt - das
    'checked' steht im Template (siehe templates/bericht.html) wegen der
    Jinja-Bedingung auf einer eigenen Zeile, darum kein simpler Substring-Test."""
    treffer = re.search(rf'value="{re.escape(schluessel)}"\s*(checked)?>', html)
    assert treffer, f"Kaestchen fuer {schluessel!r} nicht gefunden"
    return treffer.group(1) == "checked"


def test_route_html_ohne_auswahl_zeigt_standardauswahl(app):
    anlage_id, simulation_id = _lauf_speichern(app, anzahl_stunden=72)
    antwort = app.test_client().get(f"/anlage/{anlage_id}/lauf/{simulation_id}/bericht")
    html = antwort.get_data(as_text=True)
    assert "Jahresverlauf in Stundenwerten" in html
    assert _kaestchen_angehakt(html, "waerme")
    assert _kaestchen_angehakt(html, "kaelte")
    assert _kaestchen_angehakt(html, "strom")


def test_route_html_mit_auswahl_zeigt_nur_gewaehlte_reihe(app):
    anlage_id, simulation_id = _lauf_speichern(app, anzahl_stunden=72)
    antwort = app.test_client().get(
        f"/anlage/{anlage_id}/lauf/{simulation_id}/bericht?auswahl=1&reihe=kaelte"
    )
    html = antwort.get_data(as_text=True)
    assert _kaestchen_angehakt(html, "kaelte")
    assert not _kaestchen_angehakt(html, "waerme")
    # Der PDF-Knopf muss dieselbe Auswahl weitertragen (& als &amp; escaped,
    # weil pdf_href in einem href-Attribut steht - siehe templates/bericht.html).
    assert (
        f"/anlage/{anlage_id}/lauf/{simulation_id}/bericht.pdf?auswahl=1&amp;reihe=kaelte"
        in html
    )


def test_route_html_mit_leerer_auswahl_zeigt_hinweis_statt_diagramm(app):
    anlage_id, simulation_id = _lauf_speichern(app, anzahl_stunden=72)
    antwort = app.test_client().get(
        f"/anlage/{anlage_id}/lauf/{simulation_id}/bericht?auswahl=1"
    )
    html = antwort.get_data(as_text=True)
    assert "Keine Reihen ausgewählt." in html


def test_route_pdf_mit_auswahl_enthaelt_nur_die_gewaehlte_reihe(app):
    anlage_id, simulation_id = _lauf_speichern(app, anzahl_stunden=72)
    antwort = app.test_client().get(
        f"/anlage/{anlage_id}/lauf/{simulation_id}/bericht.pdf?auswahl=1&reihe=strom"
    )
    assert antwort.status_code == 200
    inhalt = antwort.data
    assert b"Jahresverlauf in Stundenwerten" in inhalt
    assert b"Ausgew\xe4hlte Reihen: Strom." in inhalt  # WinAnsi-kodiert (siehe core/pdf.py)


def test_route_pdf_ohne_reihen_meldet_das_statt_leer_zu_bleiben(app):
    anlage_id, simulation_id = _lauf_speichern(app, anzahl_stunden=72)
    antwort = app.test_client().get(
        f"/anlage/{anlage_id}/lauf/{simulation_id}/bericht.pdf?auswahl=1"
    )
    assert antwort.status_code == 200
    assert "Keine Reihen ausgewählt.".encode("cp1252") in antwort.data


# ---------------------------------------------------------------------------
# Volljahr in Stundenaufloesung: gemessene Folgen (Zeichenbefehle, PDF-
# Groesse, Dauer) - siehe _jahr_lauf_speichern() und das Berichtsdokument
# der Aufgabe (diagramme-report.md) fuer die eingeordneten Zahlen.
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_jahresdiagramme_bei_8760_stunden_bleiben_schnell_und_kompakt(app):
    _anlage_id, simulation_id = _jahr_lauf_speichern(app)
    with app.app_context():
        begonnen = time.time()
        daten = bericht.daten_fuer(simulation_id)
        rohdaten = bericht.baue_pdf(daten)
        dauer = time.time() - begonnen

    diagramme = daten["diagramme"]
    assert diagramme["jahr_stunden"] is not None
    assert len(diagramme["vier_monats_ausschnitte"]) == 3

    # Zeichenbefehle: Einhuellende statt Rohwerte - siehe _einhuellende_punkte().
    # Gemessen (drei Bilanzgroessen, ganzes Jahr): rund 1800, deutlich unter
    # den 3*8760 Punkten, die eine ungekuerzte Kurve haette.
    jahr_ops = len(diagramme["jahr_stunden"].als_pdf_operatoren().ops)
    assert jahr_ops < 3000

    _pdf_grundpruefung(rohdaten)
    # Gemessen: rund 185 KB fuer das ganze Bericht-PDF (7 Seiten, inkl. der
    # bestehenden Diagramme UND Datenlogger-Charts) - hier grosszuegig auf
    # 320 KB begrenzt, damit die Pruefung nicht bei jeder kleinen Aenderung an
    # Text oder Layout knapp wird. Siehe diagramme-report.md fuer die
    # eingeordneten Zahlen (auch ohne die neuen Stundendiagramme, zum
    # Vergleich).
    assert len(rohdaten) < 320_000
    # Gemessen: rund 0,1 s fuer daten_fuer() + baue_pdf() zusammen auf der
    # Entwicklungsmaschine - 10 s lassen reichlich Luft fuer eine langsamere
    # Maschine, ohne dass die Pruefung ihren Zweck (eine Regression zu einer
    # spuerbar langsamen Berichtserzeugung zu erkennen) verliert.
    assert dauer < 10.0



def test_keine_zahl_im_angezeigten_text_traegt_einen_punkt():
    """Deutsche Schreibweise gilt auch für Zahlen, die in einem Satz stecken.

    Aufgefallen ist es an der Konvergenzwarnung im Bericht: „größte Änderung
    100.0000" - ein Punkt, während die Bilanztabelle daneben Kommas zeigte.
    Dieselbe Sache wie in der Oberfläche (static/js/zahlen.js).

    Ausgenommen sind Formatierungen, die KEIN angezeigter Text sind: die
    Koordinaten in core/pdf.py und core/zeichnung.py müssen Punkte tragen,
    sonst versteht sie weder ein PDF-Leser noch ein Browser. Sie stehen
    deshalb hier namentlich.
    """
    wurzel = Path(__file__).resolve().parent.parent
    erlaubt = {"core/pdf.py", "core/zeichnung.py"}
    verstoesse = []
    for datei in sorted((wurzel / "core").rglob("*.py")) + sorted((wurzel / "routes").glob("*.py")):
        rel = datei.relative_to(wurzel).as_posix()
        if rel in erlaubt:
            continue
        for nummer, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r":,?\.[1-9]f\}", zeile) and "replace" not in zeile:
                verstoesse.append(f"{rel}:{nummer}: {zeile.strip()}")
    assert not verstoesse, "\n".join(verstoesse)
