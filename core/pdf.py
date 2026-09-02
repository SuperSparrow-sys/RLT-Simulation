"""Ein PDF von Hand schreiben - ohne Fremdbibliothek.

PDF 1.4, eine der vierzehn Standardschriften (Helvetica/Helvetica-Bold, kein
Einbetten noetig), WinAnsi-Kodierung fuer Umlaute und ß. Jede Seite ist ein
einziger unkomprimierter Inhaltsstrom; core/zeichnung.py liefert die
Zeichenbefehle dafuer (Linien, Rechtecke, Text), core/bericht.py setzt daraus
die Seiten des Berichts zusammen.

Koordinaten sind hier wie ueberall im Bericht "Bildschirm-Art": (0, 0) oben
links, y waechst nach unten. PDF selbst rechnet mit y nach oben - jede Seite
bekommt darum einmal am Anfang ihres Inhaltsstroms die Matrix
'1 0 0 -1 0 H cm', die diesen Unterschied ausgleicht. Text wuerde durch diese
Spiegelung auf dem Kopf stehen; PDF.text() gleicht das aus, indem es die
Textmatrix selbst ein zweites Mal spiegelt (siehe dortiger Kommentar) - das
Ergebnis ist an der richtigen Stelle und seitenrichtig zugleich. Linien und
Rechtecke brauchen diesen Ausgleich nicht: eine Flaeche sieht gespiegelt
gleich aus wie ungespiegelt.

Geprueft wird ein erzeugtes PDF durch Wiedereinlesen - siehe
tests/test_pdf.py: die Kreuzreferenztabelle wird gegen die tatsaechlichen
Bytepositionen der 'N 0 obj'-Marken nachgerechnet, nicht nur auf Anwesenheit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# WinAnsiEncoding (~= Windows-1252) deckt Umlaute und ß direkt ab - kein
# Sonderfall fuer deutschen Text noetig, nur diese eine feste Kodierung.
_KODIERUNG = "cp1252"

SEITE_A4_BREITE = 595.28
SEITE_A4_HOEHE = 841.89

# Rand einer A4-Seite in Punkt (1 pt = 1/72 Zoll) - siehe core/bericht.py.
RAND = 42.0


def _pdf_text(text: str) -> bytes:
    """Ein PDF-Literalstring '(...)' aus deutschem Text - Klammern und
    Rueckstrich werden escaped, alles andere in WinAnsi kodiert. Zeichen
    ausserhalb von WinAnsi (z.B. Emoji) werden ersetzt statt den Bau des
    PDFs scheitern zu lassen - ein Bericht ohne dieses eine Zeichen ist
    besser als gar keiner."""
    rohbytes = text.encode(_KODIERUNG, errors="replace")
    rohbytes = rohbytes.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    return rohbytes


def _zahl(wert: float) -> str:
    """Eine Zahl fuer einen PDF-Operator - ohne unnoetige Nachkommastellen,
    PDF-Leser akzeptieren aber auch 'zu genaue' Zahlen; hier geht es nur
    darum, die Datei nicht unnoetig aufzublaehen."""
    gerundet = round(float(wert), 3)
    if gerundet == int(gerundet):
        return str(int(gerundet))
    return f"{gerundet:.3f}".rstrip("0").rstrip(".")


def _rgb(hexfarbe: str) -> tuple:
    hexfarbe = hexfarbe.lstrip("#")
    return tuple(int(hexfarbe[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


@dataclass
class Flaeche:
    """Eine Zeichenflaeche, die PDF-Inhaltsoperatoren sammelt - eine ganze
    Seite (PDF.neue_seite()) oder, mit 'ox'/'oy' verschoben, ein einzelnes
    Diagramm, das core/zeichnung.py an einer bestimmten Stelle einer Seite
    einbetten will (siehe core.zeichnung.Leinwand.als_pdf_operatoren()) -
    dieselbe Formatierung (Escapen, Strichmuster, Textbreiten-Schaetzung)
    zaehlt dann fuer beide gleich, keine zweite Implementierung noetig."""

    breite: float
    hoehe: float
    ox: float = 0.0
    oy: float = 0.0
    ops: list = field(default_factory=list)

    def _op(self, text):
        self.ops.append(text)

    def linie(self, x1, y1, x2, y2, farbe="#000000", breite=1.0, gestrichelt=None):
        x1, y1, x2, y2 = x1 + self.ox, y1 + self.oy, x2 + self.ox, y2 + self.oy
        r, g, b = _rgb(farbe)
        self._op("q")
        if gestrichelt:
            muster = " ".join(_zahl(m) for m in gestrichelt)
            self._op(f"[{muster}] 0 d")
        self._op(f"{_zahl(r)} {_zahl(g)} {_zahl(b)} RG")
        self._op(f"{_zahl(breite)} w")
        self._op(f"{_zahl(x1)} {_zahl(y1)} m {_zahl(x2)} {_zahl(y2)} l S")
        self._op("Q")

    def rechteck(self, x, y, w, h, fuellfarbe=None, randfarbe=None, randbreite=1.0):
        if fuellfarbe is None and randfarbe is None:
            return
        x, y = x + self.ox, y + self.oy
        self._op("q")
        befehl = ""
        if fuellfarbe is not None:
            r, g, b = _rgb(fuellfarbe)
            self._op(f"{_zahl(r)} {_zahl(g)} {_zahl(b)} rg")
            befehl += "f"
        if randfarbe is not None:
            r, g, b = _rgb(randfarbe)
            self._op(f"{_zahl(r)} {_zahl(g)} {_zahl(b)} RG")
            self._op(f"{_zahl(randbreite)} w")
            befehl += "S"
            if befehl == "fS":
                befehl = "B"
        self._op(f"{_zahl(x)} {_zahl(y)} {_zahl(w)} {_zahl(h)} re {befehl}")
        self._op("Q")

    def vieleck(self, punkte, fuellfarbe=None, randfarbe=None, randbreite=1.0):
        """Geschlossenes Vieleck - fuer die Flaeche unter einer Kurve."""
        if not punkte or (fuellfarbe is None and randfarbe is None):
            return
        punkte = [(x + self.ox, y + self.oy) for x, y in punkte]
        self._op("q")
        befehl = ""
        if fuellfarbe is not None:
            r, g, b = _rgb(fuellfarbe)
            self._op(f"{_zahl(r)} {_zahl(g)} {_zahl(b)} rg")
            befehl += "f"
        if randfarbe is not None:
            r, g, b = _rgb(randfarbe)
            self._op(f"{_zahl(r)} {_zahl(g)} {_zahl(b)} RG")
            self._op(f"{_zahl(randbreite)} w")
            befehl += "S"
            if befehl == "fS":
                befehl = "B"
        x0, y0 = punkte[0]
        self._op(f"{_zahl(x0)} {_zahl(y0)} m")
        for x, y in punkte[1:]:
            self._op(f"{_zahl(x)} {_zahl(y)} l")
        self._op(f"h {befehl}")
        self._op("Q")

    def linienzug(self, punkte, farbe="#000000", breite=1.5, gestrichelt=None):
        if len(punkte) < 2:
            return
        punkte = [(x + self.ox, y + self.oy) for x, y in punkte]
        self._op("q")
        if gestrichelt:
            muster = " ".join(_zahl(m) for m in gestrichelt)
            self._op(f"[{muster}] 0 d")
        r, g, b = _rgb(farbe)
        self._op(f"{_zahl(r)} {_zahl(g)} {_zahl(b)} RG")
        self._op(f"{_zahl(breite)} w 1 J 1 j")
        x0, y0 = punkte[0]
        self._op(f"{_zahl(x0)} {_zahl(y0)} m")
        for x, y in punkte[1:]:
            self._op(f"{_zahl(x)} {_zahl(y)} l")
        self._op("S")
        self._op("Q")

    def text(self, x, y, inhalt, groesse=10, farbe="#000000", schrift="Helvetica",
              anker="start", fett=False):
        """Schreibt Text mit Basislinie bei (x, y) - 'anker' wie bei SVG
        text-anchor: 'start' (Standard), 'middle' oder 'end'. 'fett' ist eine
        Abkuerzung fuer schrift='Helvetica-Bold' (core/bericht.py braucht
        Fettschrift oefter als eine eigene Schriftangabe).

        Die Breite eines Standardfonts liesse sich exakt nur mit seinen
        AFM-Metriken bestimmen; fuer 'middle'/'end' reicht hier eine grobe
        Schaetzung ueber die Zeichenzahl (siehe _textbreite_schaetzung) - der
        Bericht zentriert damit Ueberschriften und rechnet Achsen aus, ohne
        AFM-Tabellen mitzuschleppen. Linksbuendiger Text (der weit
        ueberwiegende Teil des Berichts) ist davon nicht betroffen.
        """
        if not inhalt:
            return
        if fett and schrift == "Helvetica":
            schrift = "Helvetica-Bold"
        x, y = x + self.ox, y + self.oy
        rohbytes = _pdf_text(inhalt)
        verschiebung = 0.0
        if anker != "start":
            breite = _textbreite_schaetzung(inhalt, groesse, schrift)
            verschiebung = breite if anker == "end" else breite / 2.0
        r, g, b = _rgb(farbe)
        self._op("q")
        self._op(f"{_zahl(r)} {_zahl(g)} {_zahl(b)} rg")
        self._op("BT")
        self._op(f"/{schrift} {_zahl(groesse)} Tf")
        # Zweite Spiegelung, siehe Moduldocstring - kompensiert die
        # Seitenmatrix, damit dieser Text aufrecht erscheint statt spiegelverkehrt.
        self._op(f"1 0 0 -1 {_zahl(x - verschiebung)} {_zahl(y)} Tm")
        self._op(f"({rohbytes.decode('latin-1')}) Tj")
        self._op("ET")
        self._op("Q")

    def einfuegen(self, andere: "Flaeche"):
        """Die Operatoren einer anderen Flaeche uebernehmen - so bettet
        core.zeichnung.Leinwand.als_pdf_operatoren() ein Diagramm in eine
        Seite ein: es zeichnet auf eine eigene Flaeche mit passendem
        Versatz (ox/oy) und die Seite haengt deren Operatoren einfach an."""
        self.ops.extend(andere.ops)

    def inhaltsstrom(self):
        kopf = f"q 1 0 0 -1 0 {_zahl(self.hoehe)} cm"
        return "\n".join([kopf, *self.ops, "Q"])


# Breite je Zeichen in 1/1000 em, grob gemittelt aus den AFM-Tabellen von
# Helvetica - genau genug, um eine Ueberschrift zu zentrieren oder eine
# rechtsbuendige Zahl an eine Spalte anzuschlagen; fuer alles andere im
# Bericht wird ohnehin linksbuendig gesetzt.
_DURCHSCHNITT_BREIT = 0.556
_DURCHSCHNITT_FETT = 0.611


def _textbreite_schaetzung(text, groesse, schrift):
    faktor = _DURCHSCHNITT_FETT if "Bold" in schrift else _DURCHSCHNITT_BREIT
    return len(text) * groesse * faktor


class PDF:
    """Ein PDF-Dokument aus mehreren Seiten. Aufruf:

        pdf = PDF()
        seite = pdf.neue_seite()
        seite.text(...); seite.linie(...)
        rohdaten = pdf.schreibe()
    """

    def __init__(self):
        self.seiten = []

    def neue_seite(self, breite=SEITE_A4_BREITE, hoehe=SEITE_A4_HOEHE):
        seite = Flaeche(breite=breite, hoehe=hoehe)
        self.seiten.append(seite)
        return seite

    def schreibe(self) -> bytes:
        """Baut die vollstaendige PDF-Datei: Objekte, Kreuzreferenztabelle mit
        den tatsaechlichen Bytepositionen, Trailer."""
        objekte = []  # Liste von (nummer, inhalt: bytes), nummer ab 1 fortlaufend

        # 1: Katalog, 2: Seitenbaum, 3/4: Schriften, 5..: Seiten und deren
        # Inhaltsstroeme - Nummern werden unten beim Anhaengen vergeben.
        katalog_nr = 1
        seitenbaum_nr = 2
        helvetica_nr = 3
        helvetica_fett_nr = 4

        def anhaengen(inhalt: bytes) -> int:
            objekte.append(inhalt)
            return len(objekte)

        # Platzhalter fuer 1..4, in genau dieser Reihenfolge angehaengt.
        objekte.append(None)  # 1 Katalog
        objekte.append(None)  # 2 Seitenbaum
        objekte.append(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>"
        )  # 3
        objekte.append(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
            b"/Encoding /WinAnsiEncoding >>"
        )  # 4

        seiten_nrn = []
        for seite in self.seiten:
            inhalt = seite.inhaltsstrom().encode("latin-1", errors="replace")
            inhalt_nr = anhaengen(
                b"<< /Length " + str(len(inhalt)).encode("ascii") + b" >>\nstream\n"
                + inhalt + b"\nendstream"
            )
            seiten_nrn.append((seite, inhalt_nr))

        seite_objekt_nrn = []
        for seite, inhalt_nr in seiten_nrn:
            nr = anhaengen(
                (
                    "<< /Type /Page /Parent {parent} 0 R "
                    "/MediaBox [0 0 {b} {h}] "
                    "/Resources << /Font << /Helvetica {f1} 0 R "
                    "/Helvetica-Bold {f2} 0 R >> >> "
                    "/Contents {c} 0 R >>"
                )
                .format(
                    parent=seitenbaum_nr, b=_zahl(seite.breite), h=_zahl(seite.hoehe),
                    f1=helvetica_nr, f2=helvetica_fett_nr, c=inhalt_nr,
                )
                .encode("ascii")
            )
            seite_objekt_nrn.append(nr)

        kids = " ".join(f"{n} 0 R" for n in seite_objekt_nrn)
        objekte[seitenbaum_nr - 1] = (
            f"<< /Type /Pages /Kids [{kids}] /Count {len(seite_objekt_nrn)} >>"
        ).encode("ascii")
        objekte[katalog_nr - 1] = (
            f"<< /Type /Catalog /Pages {seitenbaum_nr} 0 R >>"
        ).encode("ascii")

        # -- Datei zusammensetzen, Byteposition jedes Objekts mitschreiben --
        teile = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
        offset = len(teile[0])
        offsets = []
        for nummer, inhalt in enumerate(objekte, start=1):
            kopf = f"{nummer} 0 obj\n".encode("ascii")
            stueck = kopf + inhalt + b"\nendobj\n"
            offsets.append(offset)
            teile.append(stueck)
            offset += len(stueck)

        xref_start = offset
        xref_zeilen = ["xref", f"0 {len(objekte) + 1}", "0000000000 65535 f "]
        for pos in offsets:
            xref_zeilen.append(f"{pos:010d} 00000 n ")
        xref_text = ("\n".join(xref_zeilen) + "\n").encode("ascii")

        trailer = (
            f"trailer\n<< /Size {len(objekte) + 1} /Root {katalog_nr} 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        ).encode("ascii")

        return b"".join(teile) + xref_text + trailer
