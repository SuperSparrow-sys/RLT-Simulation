"""Der Ergebnisbericht eines Simulationslaufs: Daten sammeln (daten_fuer) und
daraus ein PDF bauen (baue_pdf). Die HTML-Fassung braucht keinen eigenen
Aufbereitungsschritt - routes/bericht.py reicht daten_fuer() direkt an die
Vorlage weiter und ruft fuer die Diagramme nur noch .als_svg() auf.

Datenbankzugriff bleibt an seinem angestammten Ort: core.anlagen fuer die
Anlage, core.ergebnisse fuer den Lauf, core.wetter.speicher fuer den
Wetterdatensatz - dieses Modul fragt nur diese drei, nie die Tabellen
selbst.
"""

from __future__ import annotations

from datetime import datetime

from core import anlagen, ergebnisse, pdf as pdfschreiber, zeichnung
from core.bausteine import basis
from core.wetter import speicher

MONATSNAMEN = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
               "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

# Breite jedes Diagramms - an die Druckseite angelehnt (A4, 42pt Rand je
# Seite: pdfschreiber.SEITE_A4_BREITE - 2*pdfschreiber.RAND = 511pt), damit
# dasselbe Diagramm im PDF ohne Beschneiden auf die Seite passt; in der
# HTML-Fassung skaliert es ueber sein viewBox ohnehin responsiv (siehe
# static/css/bericht.css, svg.diagramm { width: 100% }) - dieselbe Breite
# gilt dort nur als Seitenverhaeltnis, nicht als Pixelmass.
DIAGRAMM_BREITE = 500

BILANZ_LABEL = {
    "strom_ht": "Strom Hochtarif", "strom_nt": "Strom Niedertarif",
    "waerme": "Wärme", "kaelte": "Kälte", "wasser": "Wasser",
}

STATUS_LABEL = {
    "fertig": "vollständig gerechnet", "abgebrochen": "abgebrochen",
    "fehler": "fehlgeschlagen", "laeuft": "läuft noch",
}

# Wie viele Punkte ein Liniendiagramm hoechstens bekommt, bevor Datenpunkte zu
# Zeitfenstern gemittelt werden (_downsample_mittel) - ein Jahreslauf haette
# sonst 8760 einzelne Linien-Segmente je Diagramm, in SVG wie im PDF weit mehr,
# als ein Blatt Papier oder ein Tablet-Bildschirm zeigen kann.
MAX_DIAGRAMMPUNKTE = 300

STATUS_MIT_ERGEBNIS = ("fertig", "abgebrochen")


class BerichtNichtVerfuegbar(ValueError):
    """Der Lauf ist noch nicht abgeschlossen oder ohne jedes Ergebnis - der
    Bericht braucht eine (und sei es unvollstaendige) Bilanz."""


def daten_fuer(simulation_id):
    """Alle Angaben des Berichts zu einem Simulationslauf - Kopf, Bilanz,
    Warnungen, Anlage, Diagramme (als core.zeichnung.Leinwand-Objekte, noch
    nicht in SVG oder PDF ausgegeben)."""
    sim = ergebnisse.lade_simulation(simulation_id)
    if sim["status"] not in STATUS_MIT_ERGEBNIS:
        raise BerichtNichtVerfuegbar(
            f"Lauf {simulation_id} ist noch nicht abgeschlossen (Status "
            f"'{sim['status']}') - der Bericht braucht ein Ergebnis."
        )

    anlage = anlagen.anlage_kopf(sim["anlage_id"])
    wetter = speicher.datensatz(sim["wetterdatensatz_id"])
    graph = anlagen.lade_graph(sim["anlage_id"])

    bilanz = ergebnisse.lade_bilanz(simulation_id)
    bilanz_summe = sum(z["kosten"] for z in bilanz)
    warnungen = ergebnisse.lade_warnungen(simulation_id, anzahl=8)
    baustein_warnungen = ergebnisse.lade_baustein_warnungen(simulation_id)
    karten = _karten_uebersicht(graph)
    diagramme = _diagramme(sim, graph)

    return {
        "simulation_id": simulation_id,
        "anlage": anlage,
        "wetter": wetter,
        "sim": sim,
        "stunden_gerechnet": sim["gerechnete_stunden"],
        "status_text": STATUS_LABEL.get(sim["status"], sim["status"]),
        "bilanz": [
            {**z, "label": BILANZ_LABEL.get(z["groesse"], z["groesse"])}
            for z in bilanz
        ],
        "bilanz_summe": bilanz_summe,
        "warnungen": warnungen,
        "baustein_warnungen": baustein_warnungen,
        "karten": karten,
        "diagramme": diagramme,
        "erzeugt_am": datetime.now(),
    }


def format_zahl(wert, nachkommastellen=2):
    """Deutsche Zahlendarstellung mit Komma und geschuetztem Leerzeichen als
    Tausendertrenner - fuer die Bilanztabelle in beiden Fassungen, damit
    Bericht und Bilanzdialog nicht unterschiedlich runden."""
    text = f"{float(wert):,.{nachkommastellen}f}"
    vorkomma, _, nachkomma = text.partition(".")
    vorkomma = vorkomma.replace(",", " ")
    return f"{vorkomma},{nachkomma}" if nachkomma else vorkomma


# ---------------------------------------------------------------------------
# Die Anlage: Kartenliste mit Kennwerten
# ---------------------------------------------------------------------------

_ANZEIGBARE_DARSTELLUNGEN = (basis.ZAHL, basis.PROZENT, basis.UHRZEIT, basis.AUSWAHL)


def _karten_uebersicht(graph):
    """Jede Karte der Anlage mit ihren skalaren Parametern (Zahl, Prozent,
    Uhrzeit, Auswahl) - Listenparameter (Zeitreihen, Monatswerte, Zeitraeume,
    Spaltennamen) sind fuers Nachvollziehen der Rechnung zu kleinteilig fuer
    diese Uebersicht und bleiben aussen vor; wer sie braucht, oeffnet dafuer
    weiterhin das Parameterfenster der Karte selbst."""
    ergebnis = []
    for karte in sorted(graph.karten.values(), key=lambda k: k.id):
        klasse = basis.hole(karte.typ)
        kennwerte = []
        for feld in klasse.PARAMETER:
            if feld.darstellung not in _ANZEIGBARE_DARSTELLUNGEN:
                continue
            wert = karte.parameter.get(feld.schluessel, feld.vorgabe)
            kennwerte.append({"label": feld.label, "text": _parameterwert_text(feld, wert)})
        ergebnis.append({
            "name": karte.name, "typ_name": klasse.NAME, "gruppe": klasse.GRUPPE,
            "kennwerte": kennwerte,
        })
    return ergebnis


def _parameterwert_text(feld, wert):
    if feld.darstellung == basis.UHRZEIT:
        return basis.uhrzeit_anzeigen(float(wert))
    if feld.darstellung == basis.PROZENT:
        return f"{float(wert):.0f} %"
    if feld.darstellung == basis.AUSWAHL:
        for eintrag in feld.auswahl:
            if eintrag["wert"] == wert:
                return eintrag["label"]
        return str(wert)
    text = format_zahl(wert, feld.dezimalstellen)
    return f"{text} {feld.einheit}".strip()


# ---------------------------------------------------------------------------
# Diagramme
# ---------------------------------------------------------------------------

def _bilanz_karte_id(graph):
    for karte in graph.karten.values():
        if karte.typ == "bilanz":
            return karte.id
    return None


def _monatswerte(zeitpunkte, werte):
    """Stundenwerte (kWh je Stunde, wie sie die Bilanzkarte je Stunde
    ausgibt) zu 12 Monatssummen in MWh gebuendelt - derselbe Umrechnungsfaktor
    1/1000 wie in core.ergebnisse.BILANZ fuer die Jahressumme."""
    summen = [0.0] * 12
    for zeitpunkt, wert in zip(zeitpunkte, werte):
        summen[zeitpunkt.month - 1] += wert
    return [s / 1000.0 for s in summen]


def _dauerlinie_punkte(werte, ziel=MAX_DIAGRAMMPUNKTE):
    """Absteigend sortierte Stundenwerte, x auf [0, 1] normiert - die
    klassische Jahresdauerlinie. Die Kurve ist nach dem Sortieren monoton,
    darum genuegt fuer mehr als 'ziel' Stunden eine gleichmaessige Stichprobe
    statt einer Mittelung je Fenster (die wuerde hier nichts zusaetzlich
    gluetten, nur Rechenzeit kosten)."""
    sortiert = sorted(werte, reverse=True)
    n = len(sortiert)
    if n == 0:
        return []
    if n <= ziel:
        return [(i / (n - 1) if n > 1 else 0.0, v) for i, v in enumerate(sortiert)]
    return [
        (i / (ziel - 1), sortiert[round(i * (n - 1) / (ziel - 1))])
        for i in range(ziel)
    ]


def _downsample_mittel(werte, ziel=MAX_DIAGRAMMPUNKTE):
    """Werte in zeitlicher Reihenfolge zu 'ziel' Fenstermittelwerten
    gebuendelt - anders als bei der Dauerlinie ist die Reihenfolge hier
    bedeutsam (ein Tagesgang, eine Anfahrkurve), Mittelung je Fenster erhaelt
    den Verlauf, eine reine Stichprobe wuerde ihn verrauschen."""
    n = len(werte)
    if n == 0:
        return []
    if n <= ziel:
        return [(i / (n - 1) if n > 1 else 0.0, v) for i, v in enumerate(werte)]
    punkte = []
    for fenster in range(ziel):
        start = int(fenster * n / ziel)
        ende = max(start + 1, int((fenster + 1) * n / ziel))
        teil = werte[start:ende]
        mitte_index = (start + ende - 1) / 2
        punkte.append((mitte_index / (n - 1), sum(teil) / len(teil)))
    return punkte


def _diagramme(sim, graph):
    ergebnis = {"monat": None, "dauerlinie": None, "datenlogger": []}

    bilanz_karte_id = _bilanz_karte_id(graph)
    if bilanz_karte_id is not None:
        waerme = ergebnisse.lade_zeitreihe(sim["id"], bilanz_karte_id, "waerme")
        kaelte = ergebnisse.lade_zeitreihe(sim["id"], bilanz_karte_id, "kaelte")
        strom_ht = ergebnisse.lade_zeitreihe(sim["id"], bilanz_karte_id, "strom_ht")
        strom_nt = ergebnisse.lade_zeitreihe(sim["id"], bilanz_karte_id, "strom_nt")
        strom = (
            [a + b for a, b in zip(strom_ht, strom_nt)] if strom_ht and strom_nt else []
        )

        if waerme or kaelte or strom:
            stunden = speicher.lade_stunden(
                sim["wetterdatensatz_id"], sim["von_stunde"], sim["bis_stunde"]
            )
            zeitpunkte = [s["zeitpunkt"] for s in stunden]
            ergebnis["monat"] = zeichnung.balkendiagramm(
                DIAGRAMM_BREITE, 290, "Jahresverlauf in Monatswerten", MONATSNAMEN,
                [
                    ("Wärme", zeichnung.FARBE_WAERME, False, _monatswerte(zeitpunkte, waerme)),
                    ("Kälte", zeichnung.FARBE_KAELTE, True, _monatswerte(zeitpunkte, kaelte)),
                    ("Strom", zeichnung.FARBE_STROM, False, _monatswerte(zeitpunkte, strom)),
                ],
                y_einheit="MWh", nachkommastellen=1,
            )

        # Die Dauerlinie zeigt Waerme und Kaelte als Leistung (kW) - die
        # beiden thermischen Groessen, fuer die eine Jahresdauerlinie bei
        # Lueftungsanlagen ueblich ist (Auslegung von Erhitzer/Kuehler).
        # Strom bleibt hier aussen vor: seine Groessenordnung liegt meist so
        # weit unter Waerme/Kaelte, dass er in derselben Achse nur als
        # flache Linie am Boden erschiene.
        serien = []
        if any(waerme):
            serien.append(
                ("Wärme", zeichnung.FARBE_WAERME, zeichnung.MUSTER_DURCHGEZOGEN,
                 _dauerlinie_punkte(waerme))
            )
        if any(kaelte):
            serien.append(
                ("Kälte", zeichnung.FARBE_KAELTE, zeichnung.MUSTER_GESTRICHELT,
                 _dauerlinie_punkte(kaelte))
            )
        if serien:
            stundenzahl = max(len(waerme), len(kaelte))
            ergebnis["dauerlinie"] = zeichnung.liniendiagramm(
                DIAGRAMM_BREITE, 260, "Jahresdauerlinie Wärme/Kälte", serien, y_einheit="kW",
                x_beschriftungen=[(0.0, "0 h"), (1.0, f"{stundenzahl} h")],
                flaeche=True,
            )

    for spalte in ergebnisse.lade_protokoll(sim["id"], graph):
        titel = spalte["name"] + (f" [{spalte['einheit']}]" if spalte["einheit"] else "")
        chart = zeichnung.liniendiagramm(
            DIAGRAMM_BREITE, 210, titel,
            [(spalte["name"], zeichnung.FARBE_STROM, zeichnung.MUSTER_DURCHGEZOGEN,
              _downsample_mittel(spalte["werte"]))],
            y_einheit=spalte["einheit"],
            x_beschriftungen=[(0.0, "Stunde 1"), (1.0, f"Stunde {len(spalte['werte'])}")],
        )
        ergebnis["datenlogger"].append({
            "titel": f"{spalte['karte_name']} · {spalte['name']}", "leinwand": chart,
        })

    return ergebnis


# ---------------------------------------------------------------------------
# PDF-Fassung
# ---------------------------------------------------------------------------

_RAND = pdfschreiber.RAND
_INHALT_BREITE = pdfschreiber.SEITE_A4_BREITE - 2 * _RAND


def _zeilen_umbrechen(text, max_breite, groesse):
    """Text wortweise auf 'max_breite' Punkt umbrechen - dieselbe grobe
    Zeichenbreiten-Schaetzung wie core.pdf._textbreite_schaetzung (dort fuer
    zentrierten/rechtsbuendigen Text, hier fuer den Umbruch der
    Kennwerte-Zeile je Karte, die je nach Kartentyp beliebig lang wird)."""
    zeichenbreite = groesse * pdfschreiber._DURCHSCHNITT_BREIT
    zeichen_je_zeile = max(15, int(max_breite / zeichenbreite))
    zeilen, aktuell = [], ""
    for wort in text.split(" "):
        kandidat = f"{aktuell} {wort}".strip()
        if len(kandidat) > zeichen_je_zeile and aktuell:
            zeilen.append(aktuell)
            aktuell = wort
        else:
            aktuell = kandidat
    if aktuell:
        zeilen.append(aktuell)
    return zeilen


class _Schreiber:
    """Fuehrt beim Aufbau des Berichts-PDF Buch, wo auf der Seite als
    Naechstes gezeichnet wird, und legt bei Bedarf automatisch eine neue
    Seite an (mit Kopf- und Fusszeile) - core.bericht.baue_pdf() ruft nur
    noch dessen Methoden auf, nie core.pdf direkt."""

    def __init__(self, dokument: pdfschreiber.PDF, kopftitel):
        self.dokument = dokument
        self.kopftitel = kopftitel
        self.seite = None
        self.y = 0.0
        self._neue_seite()

    def _neue_seite(self):
        self.seite = self.dokument.neue_seite()
        self.y = _RAND
        if len(self.dokument.seiten) > 1:
            self.seite.text(_RAND, self.y, self.kopftitel, groesse=8.5,
                             farbe=zeichnung.FARBE_TEXT_SCHWACH)
            self.y += 16
        self._seitenzahl_platzhalter = len(self.dokument.seiten)

    def platz_sichern(self, hoehe):
        if self.y + hoehe > pdfschreiber.SEITE_A4_HOEHE - _RAND - 20:
            self._neue_seite()

    def ueberschrift(self, text, groesse=15, abstand_davor=6, abstand_danach=14):
        self.platz_sichern(groesse + abstand_davor + abstand_danach)
        self.y += abstand_davor
        self.seite.text(_RAND, self.y + groesse * 0.8, text, groesse=groesse, fett=True)
        self.y += groesse + abstand_danach

    def zwischentitel(self, text, groesse=11.5):
        self.platz_sichern(groesse + 16)
        self.y += 10
        self.seite.text(_RAND, self.y + groesse * 0.8, text, groesse=groesse, fett=True)
        self.y += groesse + 6

    def absatz(self, text, groesse=9.5, farbe=zeichnung.FARBE_TEXT):
        self.platz_sichern(groesse + 6)
        self.seite.text(_RAND, self.y + groesse * 0.8, text, groesse=groesse, farbe=farbe)
        self.y += groesse + 6

    def liste(self, zeilen, groesse=9.0):
        for zeile in zeilen:
            self.platz_sichern(groesse + 5)
            self.seite.text(_RAND + 10, self.y + groesse * 0.8, f"– {zeile}", groesse=groesse)
            self.y += groesse + 5

    def tabelle(self, spalten, zeilen, zeilenhoehe=16, kopf=True):
        """spalten: Liste von (titel, breite, ausrichtung) - ausrichtung
        'links' oder 'rechts'; zeilen: Liste von Listen mit einem Text je
        Spalte."""
        self.platz_sichern(zeilenhoehe * (2 if kopf else 1))
        x = _RAND
        spalten_x = []
        for _, breite, _ in spalten:
            spalten_x.append(x)
            x += breite

        # Innenabstand je Zelle, auf beiden Seiten der Spaltengrenze - ohne
        # ihn stossen ein rechtsbuendiger und ein linksbuendiger Nachbar
        # (z.B. "Menge" und "Einheit") an derselben Stelle direkt aneinander
        # und verschmelzen optisch zu einem Wort.
        polster = 6

        if kopf:
            for (titel, breite, ausrichtung), sx in zip(spalten, spalten_x):
                anker = "end" if ausrichtung == "rechts" else "start"
                tx = sx + breite - polster if ausrichtung == "rechts" else sx + polster
                self.seite.text(tx, self.y + 9, titel, groesse=8.5, fett=True,
                                 farbe=zeichnung.FARBE_TEXT_SCHWACH, anker=anker)
            self.y += 12
            self.seite.linie(_RAND, self.y, _RAND + sum(b for _, b, _ in spalten), self.y,
                              farbe=zeichnung.FARBE_ACHSE, breite=0.8)
            self.y += 4

        for zeilen_index, zeile in enumerate(zeilen):
            self.platz_sichern(zeilenhoehe)
            if zeilen_index % 2 == 1:
                self.seite.rechteck(
                    _RAND, self.y - 2, sum(b for _, b, _ in spalten), zeilenhoehe,
                    fuellfarbe="#f5f5f5",
                )
            for wert, (titel, breite, ausrichtung), sx in zip(zeile, spalten, spalten_x):
                anker = "end" if ausrichtung == "rechts" else "start"
                tx = sx + breite - polster if ausrichtung == "rechts" else sx + polster
                self.seite.text(tx, self.y + zeilenhoehe - 5, str(wert), groesse=9,
                                 anker=anker)
            self.y += zeilenhoehe

    def diagramm(self, leinwand):
        if leinwand is None:
            return
        self.platz_sichern(leinwand.hoehe + 14)
        self.seite.einfuegen(leinwand.als_pdf_operatoren(ox=_RAND, oy=self.y))
        self.y += leinwand.hoehe + 14


def baue_pdf(daten) -> bytes:
    """Baut das Berichts-PDF aus den Daten von daten_fuer() - eine Kopfseite
    mit Bilanz und Warnungen, die Diagramme, zuletzt die Kartenliste."""
    dokument = pdfschreiber.PDF()
    kopftitel = f"Bericht · {daten['anlage']['name']} · Lauf {daten['simulation_id']}"
    schreiber = _Schreiber(dokument, kopftitel)

    schreiber.ueberschrift(f"Ergebnisbericht – {daten['anlage']['name']}", groesse=17)
    wetter = daten["wetter"] or {}
    kopfzeilen = [
        f"Projekt: {daten['anlage']['projekt_name']}",
        f"Wetterdatensatz: {wetter.get('name', '–')}"
        + (f" · {wetter['ort']}" if wetter.get("ort") else "")
        + (f" · {int(wetter['jahr'])}" if wetter.get("jahr") else ""),
        f"Lauf gestartet: {daten['sim']['gestartet_am']} · "
        f"{daten['status_text']} · {daten['stunden_gerechnet']} Stunden gerechnet "
        f"(Stunde {daten['sim']['von_stunde']}–{daten['sim']['bis_stunde']})",
        f"Bericht erzeugt: {daten['erzeugt_am'].strftime('%d.%m.%Y %H:%M')}",
    ]
    for zeile in kopfzeilen:
        schreiber.absatz(zeile, groesse=9.5, farbe=zeichnung.FARBE_TEXT_SCHWACH)

    schreiber.zwischentitel("Jahresbilanz")
    spalten = [
        ("Größe", 150, "links"), ("Menge", 90, "rechts"), ("Einheit", 55, "links"),
        ("Preis", 90, "rechts"), ("Kosten", 90, "rechts"),
    ]
    zeilen = [
        [
            z["label"], format_zahl(z["menge"]), z["einheit"],
            format_zahl(z["preis"]), f"{format_zahl(z['kosten'])} EUR",
        ]
        for z in daten["bilanz"]
    ]
    schreiber.tabelle(spalten, zeilen)
    schreiber.y += 4
    schreiber.seite.text(
        _RAND + sum(b for _, b, _ in spalten[:-1]) + spalten[-1][1], schreiber.y + 9,
        f"Summe: {format_zahl(daten['bilanz_summe'])} EUR", groesse=9.5, fett=True,
        anker="end",
    )
    schreiber.y += 20

    schreiber.zwischentitel("Warnungen")
    warnungen = daten["warnungen"]
    if warnungen["anzahl"] == 0:
        schreiber.absatz("Alle Stunden konvergiert.")
    else:
        schreiber.absatz(f"{warnungen['anzahl']} Stunden ohne Konvergenz, u. a.:")
        schreiber.liste([f"Stunde {b['stunde']}: {b['text']}" for b in warnungen["beispiele"]])
    if not daten["baustein_warnungen"]:
        schreiber.absatz("Keine Warnungen aus Bausteinen.")
    else:
        schreiber.liste([
            f"{w['karte_name']}: {w['text']} — {w['anzahl']} "
            f"Stunde{'n' if w['anzahl'] != 1 else ''}"
            for w in daten["baustein_warnungen"]
        ])

    diagramme = daten["diagramme"]
    if diagramme["monat"] or diagramme["dauerlinie"]:
        schreiber.zwischentitel("Diagramme")
        schreiber.diagramm(diagramme["monat"])
        schreiber.diagramm(diagramme["dauerlinie"])
    for eintrag in diagramme["datenlogger"]:
        schreiber.diagramm(eintrag["leinwand"])

    schreiber.zwischentitel("Die Anlage")
    for karte in daten["karten"]:
        schreiber.platz_sichern(14)
        schreiber.seite.text(_RAND, schreiber.y + 9, karte["name"], groesse=9.5, fett=True)
        schreiber.seite.text(
            _RAND + 220, schreiber.y + 9, f"{karte['typ_name']} · {karte['gruppe']}",
            groesse=9, farbe=zeichnung.FARBE_TEXT_SCHWACH,
        )
        schreiber.y += 13
        if karte["kennwerte"]:
            text = " · ".join(f"{k['label']}: {k['text']}" for k in karte["kennwerte"])
            for zeile in _zeilen_umbrechen(text, _INHALT_BREITE - 10, groesse=8.3)[:3]:
                schreiber.platz_sichern(12)
                schreiber.seite.text(_RAND + 10, schreiber.y + 8, zeile, groesse=8.3,
                                      farbe=zeichnung.FARBE_TEXT_SCHWACH)
                schreiber.y += 12
        schreiber.y += 4

    _seitenzahlen_schreiben(dokument)
    return dokument.schreibe()


def _seitenzahlen_schreiben(dokument):
    gesamt = len(dokument.seiten)
    for nummer, seite in enumerate(dokument.seiten, start=1):
        seite.text(
            pdfschreiber.SEITE_A4_BREITE - _RAND, pdfschreiber.SEITE_A4_HOEHE - 22,
            f"Seite {nummer} von {gesamt}", groesse=8, farbe=zeichnung.FARBE_TEXT_SCHWACH,
            anker="end",
        )
