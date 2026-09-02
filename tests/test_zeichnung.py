"""core/zeichnung.py - die Zeichenschicht der Diagramme.

Die zentrale Eigenschaft, die hier zaehlt: dieselbe Leinwand liefert eine
wohlgeformte SVG-Fassung UND eine PDF-Operatorenliste aus derselben
Befehlsliste - beide Ausgaben werden gegen die Zahl der Zeichenbefehle
geprueft, nicht nur einzeln fuer sich."""

import xml.dom.minidom as minidom

from core import zeichnung
from core.pdf import Flaeche


def test_als_svg_ist_wohlgeformtes_xml():
    leinwand = zeichnung.Leinwand(100, 50)
    leinwand.linie(0, 0, 10, 10)
    leinwand.rechteck(0, 0, 5, 5, fuellfarbe="#ff0000")
    leinwand.text(10, 10, "Test äöü <script>", anker="middle")
    svg = leinwand.als_svg()
    dokument = minidom.parseString(svg)
    assert dokument.documentElement.tagName == "svg"


def test_svg_text_wird_escaped_gegen_markup_einschleusung():
    leinwand = zeichnung.Leinwand(100, 50)
    leinwand.text(0, 0, "<script>alert(1)</script>")
    svg = leinwand.als_svg()
    assert "<script>alert" not in svg
    assert "&lt;script&gt;" in svg
    minidom.parseString(svg)  # bleibt trotzdem wohlgeformt


def test_als_pdf_operatoren_liefert_eine_flaeche_mit_versatz():
    leinwand = zeichnung.Leinwand(100, 50)
    leinwand.linie(0, 0, 10, 10)
    flaeche = leinwand.als_pdf_operatoren(ox=20, oy=30)
    assert isinstance(flaeche, Flaeche)
    assert any("20 30 m" in op for op in flaeche.ops)  # 0+20, 0+30


def test_svg_und_pdf_stammen_aus_derselben_befehlsliste():
    """Kein direkter Bytevergleich (SVG- und PDF-Operatoren sehen naturgemaess
    verschieden aus) - aber beide Ausgaben muessen dieselbe Anzahl an
    Zeichenelementen enthalten, weil sie exakt dieselbe Leinwand ablesen."""
    leinwand = zeichnung.Leinwand(200, 100)
    leinwand.linie(0, 0, 10, 10)
    leinwand.linie(10, 10, 20, 20)
    leinwand.rechteck(0, 0, 5, 5, fuellfarbe="#000000")
    leinwand.text(5, 5, "A")
    leinwand.text(6, 6, "B")

    svg = leinwand.als_svg()
    assert svg.count("<line") == 2
    assert svg.count("<rect") == 1
    assert svg.count("<text") == 2

    pdf_ops = leinwand.als_pdf_operatoren().ops
    # Jede Linie endet auf ein 'S' (stroke), jeder Text traegt genau ein 'Tj'.
    assert sum(op.endswith(" S") for op in pdf_ops) == 2
    assert sum("Tj" in op for op in pdf_ops) == 2


def test_gestrichelte_linie_traegt_strichmuster_in_beiden_ausgaben():
    leinwand = zeichnung.Leinwand(100, 50)
    leinwand.linienzug([(0, 0), (10, 10)], muster=zeichnung.MUSTER_GESTRICHELT)
    svg = leinwand.als_svg()
    assert "stroke-dasharray" in svg
    pdf_ops = leinwand.als_pdf_operatoren().ops
    assert any(op.startswith("[") and "] 0 d" in op for op in pdf_ops)


def test_balkendiagramm_zeichnet_eine_gruppe_je_monat():
    leinwand = zeichnung.balkendiagramm(
        400, 200, "Titel", ["Jan", "Feb", "Mär"],
        [
            ("Wärme", zeichnung.FARBE_WAERME, False, [10, 5, 0]),
            ("Kälte", zeichnung.FARBE_KAELTE, True, [0, 2, 8]),
        ],
        y_einheit="MWh",
    )
    svg = leinwand.als_svg()
    # 3 Monate * (Waerme-Balken, evtl. Schraffurlinien fuer Kaelte) - hier
    # zaehlt nur, dass fuer beide Reihen ueberhaupt Rechtecke entstanden sind.
    assert svg.count("<rect") >= 3  # mindestens die Waerme-Balken


def test_balkendiagramm_ohne_werte_erzeugt_kein_rechteck_unter_der_schwelle():
    leinwand = zeichnung.balkendiagramm(
        400, 200, "Titel", ["Jan"], [("A", "#000000", False, [0.0])],
    )
    svg = leinwand.als_svg()
    assert "<rect" not in svg


def test_liniendiagramm_x_beschriftung_am_rand_ragt_nicht_ueber_die_leinwand():
    """Regressionstest: eine am Rand zentrierte Beschriftung ('anker=middle')
    ragt zur Haelfte ueber die Leinwand hinaus - am linken Rand gehoert
    'anker=start', am rechten 'anker=end'."""
    leinwand = zeichnung.liniendiagramm(
        300, 150, "Titel", [("A", "#000000", None, [(0.0, 1.0), (1.0, 2.0)])],
        x_beschriftungen=[(0.0, "0 h"), (0.5, "Mitte"), (1.0, "Ende")],
    )
    svg = leinwand.als_svg()
    assert 'text-anchor="start">0 h<' in svg
    assert 'text-anchor="end">Ende<' in svg
    assert 'text-anchor="middle">Mitte<' in svg


def test_dauerlinie_flaeche_fuellt_unter_der_ersten_reihe():
    leinwand = zeichnung.liniendiagramm(
        300, 150, "Titel",
        [("A", zeichnung.FARBE_WAERME, None, [(0.0, 10.0), (1.0, 0.0)])],
        flaeche=True,
    )
    svg = leinwand.als_svg()
    assert "<polygon" in svg


def test_transparent_hellt_eine_farbe_gegen_weiss_auf():
    hell = zeichnung._transparent("#000000")
    assert hell != "#000000"
    r = int(hell[1:3], 16)
    assert r > 0  # naeher an Weiss als reines Schwarz


def test_format_zahl_deutsche_dezimaltrennung():
    assert zeichnung._format_zahl(3, nachkommastellen=1) == "3,0"
    assert zeichnung._format_zahl(0, nachkommastellen=0) == "0"
