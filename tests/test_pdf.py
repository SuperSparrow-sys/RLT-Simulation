"""core/pdf.py - der handgeschriebene PDF-Schreiber.

Ein von Hand gebautes PDF scheitert fast immer an der Kreuzreferenztabelle
(falsche Byteposition) oder am Seitenbaum - beides prueft dieses Modul durch
Wiedereinlesen, nicht nur durch Vorhandensein von '%PDF' und '%%EOF' (siehe
Auftrag: 'Pruef das Ergebnis, indem du es wieder einliest.')."""

import re

from core.pdf import PDF, Flaeche, SEITE_A4_BREITE, SEITE_A4_HOEHE


def _objekte_und_xref(rohdaten: bytes):
    """Zerlegt eine erzeugte PDF-Datei in ihre Bestandteile und prueft dabei
    genau das, woran selbstgebaute PDFs meistens scheitern: dass jede in der
    Kreuzreferenztabelle eingetragene Byteposition tatsaechlich auf 'N 0 obj'
    zeigt. Gibt {objektnummer: inhalt-bytes} zurueck."""
    assert rohdaten.startswith(b"%PDF-1.4\n")
    assert rohdaten.rstrip().endswith(b"%%EOF")

    treffer = re.search(rb"startxref\s+(\d+)\s+%%EOF", rohdaten)
    assert treffer, "kein startxref vor %%EOF gefunden"
    xref_start = int(treffer.group(1))
    assert rohdaten[xref_start : xref_start + 4] == b"xref", (
        "startxref zeigt nicht auf den Beginn der Kreuzreferenztabelle"
    )

    kopf = re.search(rb"xref\r?\n0 (\d+)\r?\n", rohdaten[xref_start:])
    assert kopf, "Kreuzreferenz-Kopfzeile '0 N' fehlt"
    anzahl = int(kopf.group(1))
    zeilen_start = xref_start + kopf.end()
    zeilen = rohdaten[zeilen_start:].splitlines()[:anzahl]
    assert len(zeilen) == anzahl

    objekte = {}
    # Zeile 0 ist der freie Eintrag ('0000000000 65535 f') - ab Zeile 1
    # zaehlen die Objektnummern 1..anzahl-1 mit.
    for nummer, zeile in enumerate(zeilen[1:], start=1):
        treffer = re.match(rb"(\d{10}) \d{5} n ?", zeile)
        assert treffer, f"Kreuzreferenzzeile fuer Objekt {nummer} missgebildet: {zeile!r}"
        offset = int(treffer.group(1))
        erwartete_marke = f"{nummer} 0 obj".encode("ascii")
        stelle = rohdaten[offset : offset + len(erwartete_marke)]
        assert stelle == erwartete_marke, (
            f"Objekt {nummer}: xref-Offset {offset} zeigt auf {stelle!r}, "
            f"erwartet {erwartete_marke!r}"
        )
        ende = rohdaten.index(b"\nendobj", offset)
        objekte[nummer] = rohdaten[offset + len(erwartete_marke) : ende]

    trailer = re.search(rb"trailer\s*<<(.*?)>>", rohdaten[xref_start:], re.S)
    assert trailer, "trailer-Dictionary fehlt"
    inhalt = trailer.group(1)
    groesse = int(re.search(rb"/Size (\d+)", inhalt).group(1))
    assert groesse == anzahl
    wurzel = int(re.search(rb"/Root (\d+) 0 R", inhalt).group(1))
    assert wurzel in objekte

    return objekte


def test_leeres_pdf_hat_eine_seite_und_gueltige_kreuzreferenz():
    pdf = PDF()
    pdf.neue_seite()
    objekte = _objekte_und_xref(pdf.schreibe())
    assert any(b"/Type /Catalog" in inhalt for inhalt in objekte.values())
    assert any(b"/Type /Pages" in inhalt and b"/Count 1" in inhalt for inhalt in objekte.values())
    assert any(b"/Type /Page" in inhalt and b"/Type /Pages" not in inhalt for inhalt in objekte.values())


def test_mehrere_seiten_werden_alle_eingetragen():
    pdf = PDF()
    for _ in range(4):
        pdf.neue_seite()
    objekte = _objekte_und_xref(pdf.schreibe())
    baum = next(i for i in objekte.values() if b"/Type /Pages" in i)
    assert b"/Count 4" in baum


def test_text_mit_umlauten_und_eurozeichen_uebersteht_die_kodierung():
    pdf = PDF()
    seite = pdf.neue_seite()
    seite.text(50, 50, "Prüfung äöü ß € – Bericht")
    objekte = _objekte_und_xref(pdf.schreibe())
    inhaltsstroeme = [i for i in objekte.values() if b"stream" in i]
    assert inhaltsstroeme
    # cp1252 kodiert Umlaute/ß auf feste Einzelbytes, die als Literalstring-
    # Inhalt zwischen '(' und ')' auftauchen muessen.
    ziel = "Prüfung äöü ß".encode("cp1252")
    assert any(ziel in strom for strom in inhaltsstroeme)


def test_klammern_und_rueckstrich_im_text_werden_escaped():
    """Ein Text mit '(', ')' oder '\\' wuerde ohne Escapen den
    PDF-Literalstring vorzeitig beenden und die Datei unlesbar machen."""
    pdf = PDF()
    seite = pdf.neue_seite()
    seite.text(50, 50, "Karte (Test) \\ Ende")
    rohdaten = pdf.schreibe()
    _objekte_und_xref(rohdaten)  # muss trotzdem eine gueltige Datei bleiben
    assert rb"\(Test\)" in rohdaten
    assert rb"\\" in rohdaten


def test_seitengroesse_im_seitenobjekt():
    pdf = PDF()
    pdf.neue_seite(breite=300, hoehe=400)
    objekte = _objekte_und_xref(pdf.schreibe())
    seite = next(
        i for i in objekte.values() if b"/Type /Page" in i and b"/Type /Pages" not in i
    )
    assert b"/MediaBox [0 0 300 400]" in seite


def test_vorgabe_seitengroesse_ist_a4():
    assert round(SEITE_A4_BREITE) == 595
    assert round(SEITE_A4_HOEHE) == 842


def test_flaeche_verschiebt_koordinaten_um_ox_oy():
    mit_versatz = Flaeche(breite=100, hoehe=100, ox=10, oy=20)
    mit_versatz.linie(0, 0, 5, 5)
    ohne_versatz = Flaeche(breite=100, hoehe=100)
    ohne_versatz.linie(10, 20, 15, 25)
    assert mit_versatz.ops == ohne_versatz.ops


def test_einfuegen_uebernimmt_operatoren_einer_anderen_flaeche():
    seite = Flaeche(breite=200, hoehe=200)
    diagramm = Flaeche(breite=50, hoehe=50, ox=5, oy=5)
    diagramm.rechteck(0, 0, 10, 10, fuellfarbe="#ff0000")
    seite.einfuegen(diagramm)
    assert seite.ops == diagramm.ops
    assert any("re f" in op for op in seite.ops)


def test_rechteck_ohne_farben_zeichnet_nichts():
    flaeche = Flaeche(breite=10, hoehe=10)
    flaeche.rechteck(0, 0, 5, 5)
    assert flaeche.ops == []


def test_gefuelltes_und_umrandetes_rechteck_nutzt_b_operator():
    flaeche = Flaeche(breite=10, hoehe=10)
    flaeche.rechteck(0, 0, 5, 5, fuellfarbe="#ffffff", randfarbe="#000000")
    assert any(op.endswith(" B") for op in flaeche.ops)
