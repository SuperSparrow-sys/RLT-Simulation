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

from core import anlagen, ergebnisse, pdf as pdfschreiber, vergleich, zeichnung
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

# Bildspalten fuer die Jahres-/Vier-Monats-Stundendiagramme (_einhuellende_punkte)
# - siehe dort fuer die Begruendung, warum hier Minimum UND Maximum je Spalte
# gezeichnet werden statt gemittelt. 300 Spalten sind grob die Plot-Breite
# dieser Diagramme in Punkt (DIAGRAMM_BREITE=500 minus Achsenrand); mehr
# Spalten als Bildpunkte aufzuloesen braechte auf dem Papier keinen weiteren
# Gewinn, nur mehr PDF-Operatoren.
STUNDEN_DIAGRAMM_SPALTEN = 300

STATUS_MIT_ERGEBNIS = ("fertig", "abgebrochen")


# ---------------------------------------------------------------------------
# Auswahl der Reihen fuer die Stundendiagramme (Jahresverlauf + Ausschnitte)
# ---------------------------------------------------------------------------

# Die drei Bilanzgroessen, die (wenn vorhanden) immer zur Auswahl stehen -
# Farbe und Strichmuster nach Bedeutung statt nach Reihenfolge: Waerme warm
# (rot, durchgezogen), Kaelte kalt (blau, gestrichelt), Strom neutral
# unterscheidbar von beiden (grau, gepunktet) - dieselbe Regel wie bei den
# drei Pfeilarten im Editor: Farbe UND Strichmuster, damit die drei Reihen
# auch im Schwarzweissdruck und fuer Rot-Gruen-Farbenblindheit auseinander-
# bleiben (Wärme/Kälte allein ueber Rot/Blau waeren das nicht automatisch -
# aber zusaetzlich durchgezogen/gestrichelt schon).
BILANZGROESSEN_STUNDEN = (
    ("waerme", "Wärme", "kW", zeichnung.FARBE_WAERME, zeichnung.MUSTER_DURCHGEZOGEN),
    ("kaelte", "Kälte", "kW", zeichnung.FARBE_KAELTE, zeichnung.MUSTER_GESTRICHELT),
    ("strom", "Strom", "kW", zeichnung.FARBE_STROM, zeichnung.MUSTER_GEPUNKTET),
)

# Vorbelegte Auswahl, solange der Benutzer noch keine eigene getroffen hat -
# genau die drei Bilanzgroessen, wie im Jahresverlauf in Monatswerten oben.
STANDARD_AUSWAHL_STUNDEN = tuple(schluessel for schluessel, *_ in BILANZGROESSEN_STUNDEN)

# Farb-/Musterpalette fuer weitere, vom Datenlogger stammende Reihen - 5
# Farben mal 4 Strichmuster ergibt 20 unterscheidbare Kombinationen, mehr als
# die hoechstens 10 Spalten, die ein einzelner Datenlogger fuehrt (siehe
# core.bausteine.datenlogger.ANZAHL). _WEITERE_MUSTER faengt bewusst NICHT
# bei "durchgezogen" an, damit die erste weitere Reihe sich im Schwarzweiss-
# druck nicht mit einer durchgezogenen Bilanzgroesse (Waerme) verwechseln
# laesst, obwohl beide zufaellig aehnlich hell erscheinen koennten.
_WEITERE_FARBEN = ["#3f7d5c", "#6a4c93", "#b8860b", "#2f8f8a", "#8a5a2b"]
_WEITERE_MUSTER = [
    zeichnung.MUSTER_GEPUNKTET, zeichnung.MUSTER_GESTRICHELT,
    zeichnung.MUSTER_STRICHPUNKT, zeichnung.MUSTER_DURCHGEZOGEN,
]


def _weitere_reihen_stil(index):
    """Farbe und Strichmuster fuer die 'index'-te weitere (Datenlogger-)
    Reihe - siehe _WEITERE_FARBEN/_WEITERE_MUSTER."""
    farbe = _WEITERE_FARBEN[index % len(_WEITERE_FARBEN)]
    muster = _WEITERE_MUSTER[(index // len(_WEITERE_FARBEN)) % len(_WEITERE_MUSTER)]
    return farbe, muster


def _reihen_auswaehlen(alle_reihen, schluessel):
    """Waehlt aus 'alle_reihen' (siehe _diagramme) diejenigen aus, deren
    Schluessel in 'schluessel' steht. schluessel=None heisst 'noch keine
    eigene Auswahl getroffen' - dann gilt STANDARD_AUSWAHL_STUNDEN. Eine
    (auch leere) Liste ist dagegen die ausdrueckliche Wahl des Benutzers und
    gilt unveraendert, auch wenn sie leer ist (routes/bericht.py
    unterscheidet beide Faelle ueber den Marker-Parameter 'auswahl')."""
    ziel = set(STANDARD_AUSWAHL_STUNDEN) if schluessel is None else set(schluessel)
    return [r for r in alle_reihen if r["schluessel"] in ziel]


class BerichtNichtVerfuegbar(ValueError):
    """Der Lauf ist noch nicht abgeschlossen oder ohne jedes Ergebnis - der
    Bericht braucht eine (und sei es unvollstaendige) Bilanz."""


def _vergleich_fuer(simulation_id):
    """Ist dieser Lauf Teil einer Reihe (core.laeufe.starte_reihe, Vorhaben
    B) mit mindestens einem weiteren Jahr, dann die Gegenueberstellung mit
    den anderen Jahren derselben Reihe (core.vergleich.vergleichsdaten()) -
    sonst None. Ein einzeln gestarteter Lauf hat keine Geschwister und damit
    keinen Vergleich; eine Reihe mit nur diesem einen Jahr (z.B. weil alle
    uebrigen schon beim Start scheiterten) waere kein sinnvoller Vergleich.

    Ergaenzt die Zeilen um dasselbe 'label' wie die Jahresbilanz oben
    (BILANZ_LABEL) - core.vergleich kennt core/bericht.py bewusst nicht
    (siehe dortiger Moduldocstring), die im Bericht gebrauchten Labels
    kommen darum von hier."""
    geschwister = ergebnisse.reihen_geschwister(simulation_id)
    if geschwister is None or len(geschwister) < 2:
        return None
    try:
        daten = vergleich.vergleichsdaten(geschwister)
    except vergleich.VergleichNichtMoeglich:
        # Kann hier eigentlich nicht auftreten (reihen_geschwister() liefert
        # nur Laeufe derselben Anlage), ist aber kein Grund, den ganzen
        # Bericht scheitern zu lassen, falls doch - der Bericht zeigt dann
        # einfach keinen Vergleichsabschnitt.
        return None
    daten["zeilen"] = [
        {**zeile, "label": BILANZ_LABEL.get(zeile["groesse"], zeile["groesse"])}
        for zeile in daten["zeilen"]
    ]
    daten["diesen_lauf_id"] = simulation_id
    return daten


def daten_fuer(simulation_id, ausgewaehlte_reihen=None):
    """Alle Angaben des Berichts zu einem Simulationslauf - Kopf, Bilanz,
    Warnungen, Anlage, Diagramme (als core.zeichnung.Leinwand-Objekte, noch
    nicht in SVG oder PDF ausgegeben).

    'ausgewaehlte_reihen' steuert, welche Groessen im Jahresverlauf in
    Stundenwerten (und seinen Vier-Monats-Ausschnitten) erscheinen - siehe
    _reihen_auswaehlen(). None (Vorgabe) zeigt die drei Bilanzgroessen;
    routes/bericht.py reicht hier die vom Benutzer per Auswahlformular
    gewaehlten Schluessel durch, fuer HTML- und PDF-Fassung gleichermassen,
    damit die Auswahl auch im serverseitig erzeugten PDF ankommt."""
    sim = ergebnisse.lade_simulation(simulation_id)
    if sim["status"] not in STATUS_MIT_ERGEBNIS:
        raise BerichtNichtVerfuegbar(
            f"Lauf {simulation_id} ist noch nicht abgeschlossen (Status "
            f"'{sim['status']}') – der Bericht braucht ein Ergebnis."
        )

    anlage = anlagen.anlage_kopf(sim["anlage_id"])
    wetter = speicher.datensatz(sim["wetterdatensatz_id"])
    graph = anlagen.lade_graph(sim["anlage_id"])
    wetter_kopfzeile = _wetter_kopfzeile(wetter)

    bilanz = ergebnisse.lade_bilanz(simulation_id)
    bilanz_summe = sum(z["kosten"] for z in bilanz)
    warnungen = ergebnisse.lade_warnungen(simulation_id, anzahl=8)
    baustein_warnungen = ergebnisse.lade_baustein_warnungen(simulation_id)
    karten = _karten_uebersicht(graph)
    diagramme = _diagramme(sim, graph, ausgewaehlte_reihen)

    # Vorhaben B: gehoert dieser Lauf zu einer Reihe (core.laeufe.
    # starte_reihe), bekommt der Bericht einen Abschnitt "im Vergleich zu
    # den anderen Jahren dieser Reihe" statt eines eigenen Berichtstyps -
    # dasselbe Diagramm-Vorgehen wie ueberall sonst in diesem Modul: erst
    # eine core.zeichnung.Leinwand bauen, dann je Fassung (HTML/PDF) erst
    # ganz am Schluss in SVG bzw. PDF-Operatoren umsetzen (routes/bericht.py
    # bzw. baue_pdf() unten) - hier bleibt es ein rohes Leinwand-Objekt.
    vergleich_daten = _vergleich_fuer(simulation_id)
    diagramme["vergleich"] = vergleich.diagramm(vergleich_daten) if vergleich_daten else None

    return {
        "simulation_id": simulation_id,
        "anlage": anlage,
        "wetter": wetter,
        "sim": sim,
        "stunden_gerechnet": sim["gerechnete_stunden"],
        "status_text": STATUS_LABEL.get(sim["status"], sim["status"]),
        "wetter_kopfzeile": wetter_kopfzeile,
        "bilanz": [
            {**z, "label": BILANZ_LABEL.get(z["groesse"], z["groesse"])}
            for z in bilanz
        ],
        "bilanz_summe": bilanz_summe,
        "warnungen": warnungen,
        "baustein_warnungen": baustein_warnungen,
        "karten": karten,
        "diagramme": diagramme,
        "vergleich": vergleich_daten,
        "erzeugt_am": datetime.now(),
    }


def _wetter_kopfzeile(wetter):
    """Die eine Kopfzeile 'Name · Ort · Jahr' - ohne Ort/Jahr zu wiederholen,
    wenn der (frei vergebene) Name sie schon enthaelt, z.B. 'Dresden 2023'.
    Sonst stuende dort 'Dresden 2023 · Dresden · 2023' - dieselbe Angabe
    dreifach, nur weil core.wetter.speicher Name, Ort und Jahr getrennt
    fuehrt (siehe core/database.py, Tabelle wetterdatensatz)."""
    if not wetter:
        return "–"
    name = wetter.get("name") or "–"
    name_klein = name.lower()
    teile = [name]
    ort = wetter.get("ort")
    if ort and ort.lower() not in name_klein:
        teile.append(ort)
    jahr = wetter.get("jahr")
    if jahr and str(int(jahr)) not in name:
        teile.append(str(int(jahr)))
    return " · ".join(teile)


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


def _einhuellende_punkte(werte, spalten=STUNDEN_DIAGRAMM_SPALTEN):
    """Minimal- und Maximalwert je Bildspalte, als ein einziger
    zusammenhaengender Linienzug - fuer den Jahresverlauf in Stundenwerten
    und seine Vier-Monats-Ausschnitte.

    8760 Stundenwerte auf rund 300 Bildspalten sind etwa 29 Werte je Spalte;
    wer die alle als Linie zeichnet, bekommt eine schwarze Flaeche (und ein
    unnoetig grosses PDF). Zwei Wege sind ueblich: je Spalte mitteln (glaettet,
    verschluckt aber genau die Lastspitzen, die den Verlauf ausmachen) oder je
    Spalte Minimum UND Maximum verbinden (haelt die Spitzen, wird optisch
    "gezackt" - genau das Bild, das die Vorlage zeigt). Hier also Minimum und
    Maximum, in der Reihenfolge, in der sie innerhalb der Spalte tatsaechlich
    auftreten (nicht immer erst Minimum), das haelt den Linienverlauf naeher
    am tatsaechlichen zeitlichen Auf und Ab als eine feste Reihenfolge.

    Ergebnis: hoechstens 2*spalten Punkte (bei STUNDEN_DIAGRAMM_SPALTEN=300
    also 600) statt bis zu 8760 - siehe core/bericht-report.md fuer die
    gemessenen Folgen (Anzahl Zeichenbefehle, PDF-Groesse, Dauer)."""
    n = len(werte)
    if n == 0:
        return []
    if n <= spalten:
        return [(i / (n - 1) if n > 1 else 0.0, v) for i, v in enumerate(werte)]
    punkte = []
    for spalte in range(spalten):
        start = int(spalte * n / spalten)
        ende = max(start + 1, int((spalte + 1) * n / spalten))
        teil = werte[start:ende]
        x = ((start + ende - 1) / 2) / (n - 1)
        imin = min(range(len(teil)), key=teil.__getitem__)
        imax = max(range(len(teil)), key=teil.__getitem__)
        if imin == imax:
            punkte.append((x, teil[imin]))
        elif imin < imax:
            punkte.append((x, teil[imin]))
            punkte.append((x, teil[imax]))
        else:
            punkte.append((x, teil[imax]))
            punkte.append((x, teil[imin]))
    return punkte


def _monatsmarken(zeitpunkte):
    """(Anteil, Monatskuerzel) fuer jeden Monatsanfang, der in 'zeitpunkte'
    auftaucht - der Anteil bezieht sich auf die Laenge von 'zeitpunkte'
    selbst, ein Ausschnitt bekommt so seine eigenen Marken statt der des
    ganzen Jahres. Funktioniert auch ueber einen Jahreswechsel hinweg (ein
    Lauf muss nicht am 1. Januar beginnen)."""
    n = len(zeitpunkte)
    if n == 0:
        return []
    marken = []
    letzter_monat = None
    for i, zeitpunkt in enumerate(zeitpunkte):
        monatsschluessel = (zeitpunkt.year, zeitpunkt.month)
        if monatsschluessel != letzter_monat:
            marken.append((i / (n - 1) if n > 1 else 0.0, MONATSNAMEN[zeitpunkt.month - 1]))
            letzter_monat = monatsschluessel
    return marken


def _gemeinsame_einheit(reihen):
    """Die eine y-Achsen-Einheit, wenn alle ausgewaehlten Reihen dieselbe
    fuehren (die drei Bilanzgroessen tun das immer: kW) - sonst leer, dann
    traegt jede Reihe ihre Einheit stattdessen in der Legende (siehe
    _stundendiagramm).

    Bewusste Entscheidung, keine offene Frage: eine Bilanzgroesse und eine
    Datenlogger-Spalte anderer Einheit teilen sich dann eine Achse ohne
    Einheitentext dort - der Benutzer entscheidet selbst, was er
    nebeneinanderlegt, die Legende zeigt zuverlaessig, welche Einheit welche
    Reihe hat. Eine zweite y-Achse waere mehr Bauwerk, als der Fall Nutzen
    bringt, solange niemand danach fragt."""
    einheiten = {r["einheit"] for r in reihen if r["einheit"]}
    return einheiten.pop() if len(einheiten) == 1 else ""


def _stundendiagramm(titel, reihen, zeitpunkte, hoehe=260):
    gemeinsam = _gemeinsame_einheit(reihen)
    serien = [
        (
            r["label"] if r["einheit"] in ("", gemeinsam) else f"{r['label']} [{r['einheit']}]",
            r["farbe"], r["muster"], _einhuellende_punkte(r["werte"]),
        )
        for r in reihen
    ]
    return zeichnung.liniendiagramm(
        DIAGRAMM_BREITE, hoehe, titel, serien, y_einheit=gemeinsam,
        x_beschriftungen=_monatsmarken(zeitpunkte), legende_immer=True,
    )


# Die drei Ausschnitte des Jahres, zu je vier Kalendermonaten - die einzige
# Dreiteilung, die zwoelf Monate ohne Rest deckt (4+4+4). Eine Vierteilung in
# Quartale (3+3+3+3) waere vier statt drei Bilder gewesen, eine Zweiteilung
# in Halbjahre (6+6) je Bild wieder fast so dicht wie das ganze Jahr - vier
# Monate je Ausschnitt sind der Punkt, an dem ein Ausschnitt spuerbar mehr
# zeigt als der Jahresueberblick, ohne dass es gleich vier oder mehr Bilder
# braucht.
_VIER_MONATS_FENSTER = [(1, 4, "Januar–April"), (5, 8, "Mai–August"), (9, 12, "September–Dezember")]


def _vier_monats_ausschnitte(reihen, zeitpunkte):
    """Bis zu drei Leinwaende, siehe _VIER_MONATS_FENSTER.

    Zwei Faelle bleiben absichtlich aus, statt eine Leinwand zu zeigen, die
    nichts beitraegt:
    - ein Fenster ohne eigene Daten (ein Lauf, der nicht das volle Jahr
      rechnet), und
    - ein Fenster, das den GESAMTEN Lauf abdeckt (ein kurzer Lauf, der
      komplett in ein einziges Vier-Monats-Fenster faellt - z.B. ein
      30-Stunden-Testlauf im August). Dessen Ausschnitt zeigt Punkt fuer
      Punkt dieselbe Kurve wie der Jahresverlauf selbst (siehe
      _stundendiagramm() oben) - genau der Fall, den jemand beim Ausprobieren
      mit einem kurzen Lauf trifft. 'indizes' deckt in diesem Fall alle
      Zeitpunkte ab (len(indizes) == len(zeitpunkte)); bei einem Lauf, der
      zwei Fenster ueberschreitet, bleibt in jedem einzelnen Fenster ein Rest
      uebrig, der Vergleich schlaegt dort also nicht an - beide Ausschnitte
      bleiben dann zu Recht erhalten.
    """
    ausschnitte = []
    for von_monat, bis_monat, titelteil in _VIER_MONATS_FENSTER:
        indizes = [i for i, zp in enumerate(zeitpunkte) if von_monat <= zp.month <= bis_monat]
        if not indizes or len(indizes) == len(zeitpunkte):
            continue
        start, ende = indizes[0], indizes[-1] + 1
        teil_reihen = [{**r, "werte": r["werte"][start:ende]} for r in reihen]
        ausschnitte.append(_stundendiagramm(
            f"Ausschnitt {titelteil}", teil_reihen, zeitpunkte[start:ende], hoehe=230,
        ))
    return ausschnitte


def _diagramme(sim, graph, ausgewaehlte_reihen=None):
    ergebnis = {
        "monat": None, "dauerlinie": None, "datenlogger": [],
        "stunden_reihen": [], "stunden_ausgewaehlt": [],
        "jahr_stunden": None, "vier_monats_ausschnitte": [],
    }

    stunden = speicher.lade_stunden(
        sim["wetterdatensatz_id"], sim["von_stunde"], sim["bis_stunde"]
    )
    zeitpunkte = [s["zeitpunkt"] for s in stunden]

    alle_reihen = []
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

        rohwerte = {"waerme": waerme, "kaelte": kaelte, "strom": strom}
        for schluessel, label, einheit, farbe, muster in BILANZGROESSEN_STUNDEN:
            werte = rohwerte.get(schluessel) or []
            if any(werte):
                alle_reihen.append({
                    "schluessel": schluessel, "label": label, "einheit": einheit,
                    "gruppe": "Bilanz", "farbe": farbe, "muster": muster, "werte": werte,
                })

    for globaler_index, spalte in enumerate(ergebnisse.lade_protokoll(sim["id"], graph)):
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

        farbe, muster = _weitere_reihen_stil(globaler_index)
        alle_reihen.append({
            "schluessel": f"logger-{spalte['karte_id']}-{globaler_index}",
            "label": f"{spalte['karte_name']} · {spalte['name']}",
            "einheit": spalte["einheit"], "gruppe": "Datenlogger",
            "farbe": farbe, "muster": muster, "werte": spalte["werte"],
        })

    ergebnis["stunden_reihen"] = [
        {k: r[k] for k in ("schluessel", "label", "einheit", "gruppe", "farbe")}
        for r in alle_reihen
    ]
    ausgewaehlt = _reihen_auswaehlen(alle_reihen, ausgewaehlte_reihen)
    ergebnis["stunden_ausgewaehlt"] = [r["schluessel"] for r in ausgewaehlt]
    if ausgewaehlt:
        ergebnis["jahr_stunden"] = _stundendiagramm(
            "Jahresverlauf in Stundenwerten", ausgewaehlt, zeitpunkte,
        )
        ergebnis["vier_monats_ausschnitte"] = _vier_monats_ausschnitte(ausgewaehlt, zeitpunkte)

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

    def ueberschrift(self, text, groesse=15, abstand_davor=6, abstand_danach=14,
                      mindest_folgehoehe=0):
        """'mindest_folgehoehe' ist die Regel gegen eine Ueberschrift allein am
        Seitenende (siehe zwischentitel() fuer die Begruendung): reserviert
        zusammen mit der Ueberschrift selbst, sonst bricht die Seite genau
        zwischen Ueberschrift und ihrem ersten Inhalt um."""
        self.platz_sichern(groesse + abstand_davor + abstand_danach + mindest_folgehoehe)
        self.y += abstand_davor
        self.seite.text(_RAND, self.y + groesse * 0.8, text, groesse=groesse, fett=True)
        self.y += groesse + abstand_danach

    def zwischentitel(self, text, groesse=11.5, mindest_folgehoehe=18):
        """Eine Ueberschrift ohne das erste Stueck ihres Inhalts darunter gehoert
        nicht ans Seitenende - 'mindest_folgehoehe' reserviert darum neben der
        Ueberschrift selbst auch gleich die Hoehe dessen, was direkt folgt
        (der Aufrufer kennt sie: eine Tabelle, ein Diagramm, ein Absatz). Der
        Vorgabewert von 18pt passt fuer eine Ueberschrift vor Fliesstext oder
        einer Liste (siehe absatz()/liste() - eine Zeile plus Abstand); vor
        einem Diagramm oder einer Tabelle gibt der Aufrufer die tatsaechliche
        Hoehe mit."""
        self.platz_sichern(groesse + 16 + mindest_folgehoehe)
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


def _kurz(text, laenge):
    """Kappt einen frei vergebenen Namen (Wetterdatensatz) auf 'laenge'
    Zeichen - eine Tabellenspalte im PDF hat keinen Zeilenumbruch wie eine
    HTML-Zelle, ein langer Name wuerde sonst die Nachbarspalte ueberdecken."""
    text = str(text)
    return text if len(text) <= laenge else text[: laenge - 1].rstrip() + "…"


def _vergleich_pdf(schreiber, vgl, leinwand):
    """Der Vergleich-Abschnitt im PDF - dieselben Daten wie die HTML-Fassung
    (core.bericht._vergleich_fuer(), templates/bericht.html), nur ueber
    schreiber.tabelle()/schreiber.diagramm() statt einer HTML-Tabelle bzw.
    einem eingebetteten SVG gesetzt. 'vgl' ist None, wenn dieser Lauf zu
    keiner Reihe (mit mindestens einem weiteren Jahr) gehoert - dann bleibt
    der Abschnitt ganz aus, wie im HTML."""
    if not vgl:
        return
    diesen_lauf_id = vgl["diesen_lauf_id"]
    laeufe = vgl["laeufe"]

    # 32pt: Tabellenkopf + erste Zeile (dieselbe Reservierung wie bei der
    # Jahresbilanz oben) - die Ueberschrift soll nicht ohne mindestens eine
    # Vergleichszeile am Seitenende stehen.
    schreiber.zwischentitel(
        "Im Vergleich zu den anderen Jahren dieser Reihe", mindest_folgehoehe=32,
    )
    schreiber.absatz(
        f"Abweichung jeweils gegenüber {laeufe[0]['wetter_name']}.",
        groesse=9, farbe=zeichnung.FARBE_TEXT_SCHWACH,
    )

    spalten_breite = (_INHALT_BREITE - 150) / max(len(laeufe), 1)
    spalten = [("Größe", 150, "links")] + [
        (
            _kurz(l["wetter_name"], 20) + (" (dieser)" if l["simulation_id"] == diesen_lauf_id else ""),
            spalten_breite, "rechts",
        )
        for l in laeufe
    ]

    zeilen = []
    for zeile in vgl["zeilen"]:
        werte = []
        for w in zeile["werte"]:
            if w["menge"] is None:
                werte.append("–")
            elif w["abweichung"] is None:
                werte.append(format_zahl(w["menge"], 3))
            else:
                vorzeichen = "+" if w["abweichung"] >= 0 else ""
                werte.append(
                    f"{format_zahl(w['menge'], 3)} "
                    f"({vorzeichen}{format_zahl(w['abweichung'] * 100, 1)} %)"
                )
        zeilen.append([f"{zeile['label']} [{zeile['einheit']}]", *werte])
    zeilen.append([
        "Kosten gesamt",
        *[f"{format_zahl(l['kosten_gesamt'])} EUR" if l["hat_ergebnis"] else "–" for l in laeufe],
    ])
    zeilen.append([
        "Warnungen",
        *[str(l["anzahl_warnungen"]) if l["hat_ergebnis"] else "–" for l in laeufe],
    ])
    schreiber.tabelle(spalten, zeilen)
    schreiber.y += 10
    schreiber.diagramm(leinwand)


def baue_pdf(daten) -> bytes:
    """Baut das Berichts-PDF aus den Daten von daten_fuer() - eine Kopfseite
    mit Bilanz und Warnungen, die Diagramme, zuletzt die Kartenliste."""
    dokument = pdfschreiber.PDF()
    kopftitel = f"Bericht · {daten['anlage']['name']} · Lauf {daten['simulation_id']}"
    schreiber = _Schreiber(dokument, kopftitel)

    schreiber.ueberschrift(f"Ergebnisbericht – {daten['anlage']['name']}", groesse=17)
    kopfzeilen = [
        f"Projekt: {daten['anlage']['projekt_name']}",
        f"Wetterdatensatz: {daten['wetter_kopfzeile']}",
        f"Lauf gestartet: {daten['sim']['gestartet_am']} · "
        f"{daten['status_text']} · {daten['stunden_gerechnet']} Stunden gerechnet "
        f"(Stunde {daten['sim']['von_stunde']}–{daten['sim']['bis_stunde']})",
        f"Bericht erzeugt: {daten['erzeugt_am'].strftime('%d.%m.%Y %H:%M')}",
    ]
    for zeile in kopfzeilen:
        schreiber.absatz(zeile, groesse=9.5, farbe=zeichnung.FARBE_TEXT_SCHWACH)

    # 32pt: Tabellenkopf + erste Zeile (siehe tabelle()) - die Ueberschrift
    # soll nie ohne mindestens eine Bilanzzeile am Seitenende stehen.
    schreiber.zwischentitel("Jahresbilanz", mindest_folgehoehe=32)
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

    diagramme = daten["diagramme"]
    _vergleich_pdf(schreiber, daten.get("vergleich"), diagramme.get("vergleich"))

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

    erstes_diagramm = diagramme["monat"] or diagramme["dauerlinie"]
    if erstes_diagramm is not None:
        # Dieselbe Hoehe, die diagramm() gleich selbst fuer das erste
        # Diagramm reservieren wird (Leinwand plus Abstand) - die
        # Ueberschrift soll nicht ohne ihr erstes Diagramm am Seitenende
        # stehen (siehe zwischentitel()).
        schreiber.zwischentitel("Diagramme", mindest_folgehoehe=erstes_diagramm.hoehe + 14)
        schreiber.diagramm(diagramme["monat"])
        schreiber.diagramm(diagramme["dauerlinie"])

    if diagramme["stunden_reihen"]:
        # Das PDF hat keine Auswahlkaestchen (die HTML-Fassung schon, siehe
        # templates/bericht.html) - die getroffene Auswahl steht hier
        # stattdessen als Text, damit auch im PDF nachvollziehbar bleibt,
        # welche Reihen gezeigt werden. Beide Fassungen lesen dieselbe
        # Auswahl aus derselben Anfrage (core.bericht.daten_fuer()).
        schreiber.zwischentitel(
            "Jahresverlauf in Stundenwerten",
            mindest_folgehoehe=(diagramme["jahr_stunden"].hoehe + 14) if diagramme["jahr_stunden"]
            else 14,
        )
        ausgewaehlte_labels = [
            r["label"] for r in diagramme["stunden_reihen"]
            if r["schluessel"] in diagramme["stunden_ausgewaehlt"]
        ]
        schreiber.absatz(
            f"Ausgewählte Reihen: {', '.join(ausgewaehlte_labels)}."
            if ausgewaehlte_labels else
            "Keine Reihen ausgewählt.",
            groesse=9, farbe=zeichnung.FARBE_TEXT_SCHWACH,
        )
        schreiber.diagramm(diagramme["jahr_stunden"])
        for ausschnitt in diagramme["vier_monats_ausschnitte"]:
            schreiber.diagramm(ausschnitt)

    for eintrag in diagramme["datenlogger"]:
        schreiber.diagramm(eintrag["leinwand"])

    # 14pt: dieselbe Hoehe, die je Karte unten reserviert wird (Name-/Typ-
    # Zeile) - die Ueberschrift soll nicht ohne die erste Karte am
    # Seitenende stehen.
    schreiber.zwischentitel("Die Anlage", mindest_folgehoehe=14)
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
