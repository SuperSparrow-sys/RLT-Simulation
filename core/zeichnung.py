"""Die Zeichenschicht des Berichts: Diagramme einmal beschrieben, in der
HTML-Fassung als SVG und im PDF als Inhaltsoperatoren ausgegeben (siehe
core/pdf.py fuer den PDF-Schreiber).

Ein Diagramm entsteht als 'Leinwand': eine Liste einfacher Zeichenbefehle
(Linie, Rechteck, Vieleck, Linienzug, Text) in einem eigenen Koordinatensystem
mit (0, 0) oben links, y nach unten - wie ein Bildschirm, wie SVG. Die beiden
Ausgabefunktionen (als_svg, als_pdf_operatoren) lesen dieselbe Befehlsliste;
ein Diagramm sieht darum in beiden Fassungen gleich aus, ohne zweimal
geschrieben zu werden.

Die Bau-Funktionen unten (balkendiagramm, liniendiagramm) setzen aus diesen
Befehlen komplette Diagramme mit Achsen, Gitter, Legende und Titel zusammen -
core/bericht.py ruft nur noch sie auf, nie die Leinwand-Primitiven direkt.

Farben sind eine eigene, druckfeste Palette (FARBE_*) statt der
CSS-Variablen der Anwendung: die sind fuer Bildschirme gedacht und im
Schwarzweissdruck teils kaum zu unterscheiden. Jede Reihe bekommt zusaetzlich
ein eigenes Strichmuster bzw. eine eigene Fuellart (siehe MUSTER_*), damit sie
sich auch ganz ohne Farbe auseinanderhalten laesst.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field

from core.pdf import Flaeche

# -- Druckfeste Berichtspalette --------------------------------------------
# Getrennt von den CSS-Variablen der Anwendung (static/css/style.css) - siehe
# Moduldocstring. Je Groesse eine dunkle, gut unterscheidbare Farbe, dazu ein
# Strichmuster fuer Liniendiagramme.
FARBE_WAERME = "#b3282a"
FARBE_KAELTE = "#2c5f8a"
FARBE_STROM = "#4a4a4a"
FARBE_WASSER = "#3f7d5c"
FARBE_ACHSE = "#333333"
FARBE_GITTER = "#d0d0d0"
FARBE_TEXT = "#222222"
FARBE_TEXT_SCHWACH = "#555555"

# Durchgezogen, gestrichelt, gepunktet, Strich-Punkt - je nach
# [Strichlaenge, Luecke, ...] in Leinwand-Einheiten (beliebig viele Paare,
# nicht nur zwei - siehe MUSTER_STRICHPUNKT); None bedeutet durchgezogen.
# Dieselben vier Muster wie fuer die drei Pfeilarten und die Vorschau im
# Editor (siehe static/css/style.css, .pfeil-luft/-signal/-energie/-vorschau)
# - eine Reihe bleibt so nach demselben, im Projekt schon eingefuehrten
# Verfahren auch ohne Farbe unterscheidbar (Schwarzweissdruck, Farbenblindheit).
MUSTER_DURCHGEZOGEN = None
MUSTER_GESTRICHELT = (6, 3)
MUSTER_GEPUNKTET = (1.5, 2.5)
MUSTER_STRICHPUNKT = (9, 3, 1.5, 3)


def _svg_text(text) -> str:
    return html.escape(str(text), quote=True)


# ---------------------------------------------------------------------------
# Leinwand: Befehlsliste plus die zwei Ausgaben
# ---------------------------------------------------------------------------

@dataclass
class Leinwand:
    breite: float
    hoehe: float
    _ops: list = field(default_factory=list)

    # -- Primitiven ---------------------------------------------------------

    def linie(self, x1, y1, x2, y2, farbe=FARBE_ACHSE, breite=1.0, muster=None):
        self._ops.append(("linie", x1, y1, x2, y2, farbe, breite, muster))

    def rechteck(self, x, y, w, h, fuellfarbe=None, randfarbe=None, randbreite=1.0):
        self._ops.append(("rechteck", x, y, w, h, fuellfarbe, randfarbe, randbreite))

    def vieleck(self, punkte, fuellfarbe=None, randfarbe=None, randbreite=1.0):
        self._ops.append(("vieleck", list(punkte), fuellfarbe, randfarbe, randbreite))

    def linienzug(self, punkte, farbe=FARBE_ACHSE, breite=1.5, muster=None):
        self._ops.append(("linienzug", list(punkte), farbe, breite, muster))

    def text(self, x, y, inhalt, groesse=10, farbe=FARBE_TEXT, anker="start", fett=False):
        if inhalt == "" or inhalt is None:
            return
        self._ops.append(("text", x, y, str(inhalt), groesse, farbe, anker, fett))

    # -- Ausgabe: SVG ---------------------------------------------------------

    def als_svg(self, css_klasse="diagramm") -> str:
        teile = [
            f'<svg class="{css_klasse}" viewBox="0 0 {_z(self.breite)} {_z(self.hoehe)}" '
            f'role="img" xmlns="http://www.w3.org/2000/svg">'
        ]
        for op in self._ops:
            teile.append(_svg_op(op))
        teile.append("</svg>")
        return "".join(teile)

    # -- Ausgabe: PDF-Operatoren ----------------------------------------------

    def als_pdf_operatoren(self, ox=0.0, oy=0.0) -> list:
        """Die Befehle dieser Leinwand als PDF-Operatoren, verschoben um
        (ox, oy) - core/bericht.py haengt das Ergebnis in eine Seite ein
        (core.pdf.Flaeche.einfuegen)."""
        ziel = Flaeche(breite=self.breite, hoehe=self.hoehe, ox=ox, oy=oy)
        for op in self._ops:
            art = op[0]
            if art == "linie":
                _, x1, y1, x2, y2, farbe, breite, muster = op
                ziel.linie(x1, y1, x2, y2, farbe=farbe, breite=breite, gestrichelt=muster)
            elif art == "rechteck":
                _, x, y, w, h, fuellfarbe, randfarbe, randbreite = op
                ziel.rechteck(x, y, w, h, fuellfarbe=fuellfarbe, randfarbe=randfarbe,
                               randbreite=randbreite)
            elif art == "vieleck":
                _, punkte, fuellfarbe, randfarbe, randbreite = op
                ziel.vieleck(punkte, fuellfarbe=fuellfarbe, randfarbe=randfarbe,
                              randbreite=randbreite)
            elif art == "linienzug":
                _, punkte, farbe, breite, muster = op
                ziel.linienzug(punkte, farbe=farbe, breite=breite, gestrichelt=muster)
            elif art == "text":
                _, x, y, inhalt, groesse, farbe, anker, fett = op
                schrift = "Helvetica-Bold" if fett else "Helvetica"
                ziel.text(x, y, inhalt, groesse=groesse, farbe=farbe, schrift=schrift,
                           anker=anker)
        return ziel


def _z(wert) -> str:
    gerundet = round(float(wert), 2)
    if gerundet == int(gerundet):
        return str(int(gerundet))
    return f"{gerundet:.2f}"


def _muster(muster) -> str:
    """'muster' fuer SVG stroke-dasharray - beliebig viele Zahlen, nicht nur
    ein Paar (MUSTER_STRICHPUNKT braucht vier)."""
    return " ".join(_z(m) for m in muster)


def _svg_op(op) -> str:
    art = op[0]
    if art == "linie":
        _, x1, y1, x2, y2, farbe, breite, muster = op
        strich = f' stroke-dasharray="{_muster(muster)}"' if muster else ""
        return (
            f'<line x1="{_z(x1)}" y1="{_z(y1)}" x2="{_z(x2)}" y2="{_z(y2)}" '
            f'stroke="{farbe}" stroke-width="{_z(breite)}"{strich}/>'
        )
    if art == "rechteck":
        _, x, y, w, h, fuellfarbe, randfarbe, randbreite = op
        fill = fuellfarbe or "none"
        rand = f' stroke="{randfarbe}" stroke-width="{_z(randbreite)}"' if randfarbe else ""
        return (
            f'<rect x="{_z(x)}" y="{_z(y)}" width="{_z(w)}" height="{_z(h)}" '
            f'fill="{fill}"{rand}/>'
        )
    if art == "vieleck":
        _, punkte, fuellfarbe, randfarbe, randbreite = op
        pkt = " ".join(f"{_z(x)},{_z(y)}" for x, y in punkte)
        fill = fuellfarbe or "none"
        rand = f' stroke="{randfarbe}" stroke-width="{_z(randbreite)}"' if randfarbe else ""
        return f'<polygon points="{pkt}" fill="{fill}"{rand}/>'
    if art == "linienzug":
        _, punkte, farbe, breite, muster = op
        pkt = " ".join(f"{_z(x)},{_z(y)}" for x, y in punkte)
        strich = f' stroke-dasharray="{_muster(muster)}"' if muster else ""
        return (
            f'<polyline points="{pkt}" fill="none" stroke="{farbe}" '
            f'stroke-width="{_z(breite)}" stroke-linejoin="round" '
            f'stroke-linecap="round"{strich}/>'
        )
    if art == "text":
        _, x, y, inhalt, groesse, farbe, anker, fett = op
        svg_anker = {"start": "start", "middle": "middle", "end": "end"}.get(anker, "start")
        gewicht = ' font-weight="bold"' if fett else ""
        return (
            f'<text x="{_z(x)}" y="{_z(y)}" font-size="{_z(groesse)}" fill="{farbe}" '
            f'text-anchor="{svg_anker}"{gewicht}>{_svg_text(inhalt)}</text>'
        )
    raise ValueError(f"Unbekannter Zeichenbefehl: {art!r}")


# ---------------------------------------------------------------------------
# Achsenrahmen: gemeinsamer Unterbau der beiden Diagrammarten unten
# ---------------------------------------------------------------------------

def _tick_werte(minimum, maximum, anzahl=5):
    """Runde y-Achsenwerte, die 0 und das Maximum sicher einschliessen - kein
    Anspruch auf 'schoene' 1-2-5-Schritte, nur gleichmaessig und lesbar."""
    if maximum <= 0:
        maximum = 1.0
    schritt = maximum / (anzahl - 1)
    return [schritt * i for i in range(anzahl)]


def _format_zahl(wert, nachkommastellen=0):
    text = f"{wert:,.{nachkommastellen}f}"
    return text.replace(",", " ").replace(".", ",") if "," in text or "." in text else text


def _achsenrahmen(leinwand, plot_x, plot_y, plot_w, plot_h, y_max, y_einheit,
                   nachkommastellen=0):
    """Zeichnet y-Gitter, y-Achsenbeschriftung und die Achsenlinien; liefert
    eine Funktion, die einen Datenwert auf die Pixel-y-Koordinate abbildet."""
    ticks = _tick_werte(0, y_max)
    y_max_tick = ticks[-1] or 1.0

    def skala(wert):
        anteil = wert / y_max_tick if y_max_tick else 0
        return plot_y + plot_h - anteil * plot_h

    for tick in ticks:
        y = skala(tick)
        leinwand.linie(plot_x, y, plot_x + plot_w, y, farbe=FARBE_GITTER, breite=0.75)
        leinwand.text(
            plot_x - 8, y + 3.5, _format_zahl(tick, nachkommastellen),
            groesse=8.5, farbe=FARBE_TEXT_SCHWACH, anker="end",
        )
    if y_einheit:
        leinwand.text(
            plot_x - 8, plot_y - 10, y_einheit, groesse=8.5, farbe=FARBE_TEXT_SCHWACH,
            anker="end",
        )
    leinwand.linie(plot_x, plot_y, plot_x, plot_y + plot_h, farbe=FARBE_ACHSE, breite=1.2)
    leinwand.linie(
        plot_x, plot_y + plot_h, plot_x + plot_w, plot_y + plot_h,
        farbe=FARBE_ACHSE, breite=1.2,
    )
    return skala


def _legende(leinwand, x, y, eintraege):
    """eintraege: Liste von (name, farbe, muster) - ein Strich- oder
    Flaechenmuster je Reihe, damit die Legende auch ohne Farbe eindeutig
    bleibt (Schwarzweissdruck)."""
    kx = x
    for name, farbe, muster in eintraege:
        breite_name = 7.5 * len(name) + 34
        leinwand.linienzug([(kx, y), (kx + 20, y)], farbe=farbe, breite=3, muster=muster)
        leinwand.text(kx + 26, y + 3.5, name, groesse=9, farbe=FARBE_TEXT)
        kx += breite_name


# ---------------------------------------------------------------------------
# Diagrammbau
# ---------------------------------------------------------------------------

def balkendiagramm(breite, hoehe, titel, x_beschriftungen, serien, y_einheit="",
                    nachkommastellen=0):
    """Gruppiertes Balkendiagramm - fuer den Jahresverlauf in Monatswerten.

    serien: Liste von (name, farbe, muster_ist_schraffiert, werte); 'werte'
    gleich lang wie x_beschriftungen. 'muster_ist_schraffiert' unterscheidet
    Reihen zusaetzlich zur Farbe ueber eine Schraffur statt vollflaechig -
    im Schwarzweissdruck bleiben die Reihen so auch ohne Farbe auseinanderzuhalten.
    """
    leinwand = Leinwand(breite, hoehe)
    leinwand.text(breite / 2, 18, titel, groesse=12.5, farbe=FARBE_TEXT, anker="middle",
                   fett=True)

    plot_x, plot_y = 46, 34
    plot_w, plot_h = breite - plot_x - 14, hoehe - plot_y - 46
    alle_werte = [w for _, _, _, werte in serien for w in werte]
    y_max = max(alle_werte) if alle_werte else 1.0
    skala = _achsenrahmen(leinwand, plot_x, plot_y, plot_w, plot_h, y_max, y_einheit,
                           nachkommastellen)

    anzahl_gruppen = len(x_beschriftungen)
    anzahl_serien = len(serien)
    gruppen_breite = plot_w / max(anzahl_gruppen, 1)
    balken_breite = gruppen_breite * 0.7 / max(anzahl_serien, 1)

    for g, label in enumerate(x_beschriftungen):
        gx = plot_x + g * gruppen_breite + gruppen_breite * 0.15
        for s, (name, farbe, schraffiert, werte) in enumerate(serien):
            wert = werte[g] if g < len(werte) else 0.0
            bx = gx + s * balken_breite
            by = skala(wert)
            bh = plot_y + plot_h - by
            if bh > 0.3:
                leinwand.rechteck(
                    bx, by, balken_breite * 0.88, bh,
                    fuellfarbe=None if schraffiert else farbe,
                    randfarbe=farbe, randbreite=1.2,
                )
                if schraffiert:
                    _schraffieren(leinwand, bx, by, balken_breite * 0.88, bh, farbe)
        leinwand.text(
            gx + gruppen_breite * 0.35, plot_y + plot_h + 14, label,
            groesse=8.5, farbe=FARBE_TEXT_SCHWACH, anker="middle",
        )

    _legende(
        leinwand, plot_x, hoehe - 8,
        [(n, f, MUSTER_DURCHGEZOGEN) for n, f, _, _ in serien],
    )
    return leinwand


def _schraffieren(leinwand, x, y, w, h, farbe, abstand=4.0):
    """Diagonale Schraffurlinien innerhalb eines Rechtecks - eine Reihe ohne
    Fuellfarbe bleibt so auch als Graustufe von einer vollflaechigen
    unterscheidbar. Ohne echtes Clipping gezeichnet: die Linien werden am
    Rechteck selbst abgeschnitten, indem nur ihr innenliegender Abschnitt
    berechnet wird."""
    diagonale = w + h
    versatz = -h
    while versatz < w:
        x1, y1 = x + versatz, y + h
        x2, y2 = x + versatz + h, y
        # Auf das Rechteck [x, x+w] x [y, y+h] kappen.
        if x1 < x:
            y1 -= (x - x1)
            x1 = x
        if x2 > x + w:
            y2 += (x2 - (x + w))
            x2 = x + w
        if x1 < x2:
            leinwand.linie(x1, y1, x2, y2, farbe=farbe, breite=0.9)
        versatz += abstand


def liniendiagramm(breite, hoehe, titel, serien, y_einheit="", x_beschriftungen=None,
                    nachkommastellen=0, flaeche=False, legende_immer=False):
    """Liniendiagramm mit gemeinsamer x-Achse 0..1 (schon normiert) - fuer die
    Jahresdauerlinie und Zeitreihen des Datenloggers.

    serien: Liste von (name, farbe, muster, punkte) mit punkte=[(x, y), ...],
    x bereits auf [0, 1] normiert (core/bericht.py entscheidet, was x
    bedeutet: Stundenanteil oder Anteil der sortierten Dauerlinie).
    'flaeche': fuellt die erste Reihe unter der Kurve (Dauerlinie) leicht ein.
    'legende_immer': zeigt die Legende auch bei nur einer Reihe - fuer ein
    Diagramm wie den Jahresverlauf in Stundenwerten, dessen Titel (anders als
    bei den Datenlogger-Einzelcharts) nicht schon den Reihennamen traegt, weil
    er sich je nach Auswahl des Benutzers aendert.
    """
    leinwand = Leinwand(breite, hoehe)
    leinwand.text(breite / 2, 18, titel, groesse=12.5, farbe=FARBE_TEXT, anker="middle",
                   fett=True)

    plot_x, plot_y = 46, 34
    plot_w, plot_h = breite - plot_x - 14, hoehe - plot_y - 46
    alle_werte = [y for _, _, _, punkte in serien for _, y in punkte]
    y_max = max(alle_werte) if alle_werte else 1.0
    skala = _achsenrahmen(leinwand, plot_x, plot_y, plot_w, plot_h, y_max, y_einheit,
                           nachkommastellen)

    if x_beschriftungen:
        # Senkrechte Gitterlinien nur fuer Marken INNERHALB der Flaeche (0
        # und 1 fallen ohnehin mit dem schon gezeichneten Achsenrahmen
        # zusammen) - bei der Dauerlinie/den Datenlogger-Charts sind das
        # ohnehin nur die beiden Randmarken, hier aendert sich also nichts;
        # bei den Monatsmarken des Stundendiagramms macht sie erst lesbar,
        # welcher Bildbereich zu welchem Monat gehoert. Vor den Kurven
        # gezeichnet, damit die Kurven immer obenauf bleiben.
        for anteil, _ in x_beschriftungen:
            if 0 < anteil < 1:
                x = plot_x + anteil * plot_w
                leinwand.linie(x, plot_y, x, plot_y + plot_h, farbe=FARBE_GITTER, breite=0.6)

    for i, (name, farbe, muster, punkte) in enumerate(serien):
        if not punkte:
            continue
        pixel = [(plot_x + x * plot_w, skala(y)) for x, y in punkte]
        if flaeche and i == 0:
            boden = plot_y + plot_h
            umriss = [(pixel[0][0], boden)] + pixel + [(pixel[-1][0], boden)]
            leinwand.vieleck(umriss, fuellfarbe=_transparent(farbe))
        leinwand.linienzug(pixel, farbe=farbe, breite=1.6, muster=muster)

    if x_beschriftungen:
        # Am linken/rechten Rand linksbuendig bzw. rechtsbuendig ausrichten
        # statt zentriert - eine am Rand zentrierte Beschriftung wuerde zur
        # Haelfte ueber die Leinwand hinausragen (und im PDF ueber die Seite).
        for anteil, text in x_beschriftungen:
            anker = "start" if anteil <= 0 else "end" if anteil >= 1 else "middle"
            leinwand.text(
                plot_x + anteil * plot_w, plot_y + plot_h + 14, text,
                groesse=8.5, farbe=FARBE_TEXT_SCHWACH, anker=anker,
            )

    if len(serien) > 1 or (legende_immer and serien):
        _legende(leinwand, plot_x, hoehe - 8, [(n, f, m) for n, f, m, _ in serien])
    return leinwand


def _transparent(hexfarbe):
    """Eine helle Mischfarbe fuer Flaechen unter einer Kurve - kein echtes
    Alpha (das PDF-Content-Stream-Grundgeruest hier kennt keine
    Deckkraft-Ressourcen), sondern eine fest gegen Weiss aufgehellte
    Volltonfarbe; sieht in SVG und PDF gleich aus."""
    hexfarbe = hexfarbe.lstrip("#")
    r, g, b = (int(hexfarbe[i:i + 2], 16) for i in (0, 2, 4))
    mischung = 0.85
    r2 = round(r + (255 - r) * mischung)
    g2 = round(g + (255 - g) * mischung)
    b2 = round(b + (255 - b) * mischung)
    return f"#{r2:02x}{g2:02x}{b2:02x}"
