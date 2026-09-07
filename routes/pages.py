import json
import os

from flask import Blueprint, current_app, render_template, send_from_directory

from core import anlagen
from core.wetter import speicher

bp = Blueprint("pages", __name__)


@bp.route("/")
def index():
    eigene, lehrmaterial = _projektliste()
    return render_template(
        "index.html",
        projekte=eigene,
        lehrmaterial=lehrmaterial,
        # Schon zugeklappt sagen, wieviele Beispielanlagen drinstecken - eine
        # Klappe ohne Zahl ist eine Frage ohne Antwort.
        lehrmaterial_anzahl=sum(len(p["anlagen"]) for p in lehrmaterial),
        wetter_anzahl=len(speicher.datensaetze()),
    )


@bp.route("/favicon.ico")
def favicon():
    # Browser fragen dieses Pfad ungefragt an, unabhaengig vom <link rel="icon">
    # in den Vorlagen - ohne diese Route lieferte er bislang 404.
    return send_from_directory(
        os.path.join(current_app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


#: Laeufe, zu denen es einen Bericht gibt (core/bericht.py: STATUS_MIT_ERGEBNIS).
STATUS_MIT_BERICHT = ("fertig", "abgebrochen")


def _statuszettel(anlage):
    """Was in der Anlagenzeile ueber ihren letzten Lauf steht.

    Frueher baute static/js/start.js diesen Zettel im Browser, nachdem es fuer
    JEDE Anlage den Status einzeln nachgefragt hatte. Die Seite zeigte bis
    dahin eine leere Flaeche - beim ersten Blick und auf jedem Bildschirmfoto.
    Jetzt steht er im HTML; das Skript kuemmert sich nur noch um den
    Fortschritt eines Laufs, der GERADE rechnet.

    Rueckgabe: (Zustandsklasse, Etikett, Angaben).

    Der Zustand steht als kurzes Etikett fuer sich ("Fertig", "Abgebrochen");
    was dazu zu sagen ist - Kosten, Warnungen, Tag und Wetterjahr - folgt
    daneben in normaler Schrift. Vorher war der ganze Satz eingefaerbt, was
    eine Liste mit mehreren Anlagen unruhig machte.
    """
    lauf = anlage.get("letzter_lauf")
    if lauf is None:
        return ("offen", "Offen", "noch nicht simuliert")
    if lauf["status"] == "laeuft":
        return ("laeuft", "Läuft", "…")

    warnungen = lauf.get("anzahl_warnungen") or 0
    if lauf["status"] == "fertig":
        etikett = "Fertig"
        kopf = f"{lauf['kosten_gesamt']:.2f} EUR".replace(".", ",")
    elif lauf["status"] == "abgebrochen":
        etikett, kopf = "Abgebrochen", ""
    elif lauf["status"] == "fehler":
        etikett, kopf = "Fehler", ""
    else:
        etikett, kopf = lauf["status"].capitalize(), ""

    # Nur der Kalendertag: gestartet_am kommt als "YYYY-MM-DD HH:MM:SS" aus
    # core/database.py (datetime('now'), UTC). Eine Uhrzeit auf die Minute
    # waere mehr Genauigkeit, als die Zeile braucht - und eine Umrechnung in
    # die Ortszeit koennte den Tag verschieben.
    tag = (lauf.get("gestartet_am") or "")[:10]
    if len(tag) == 10:
        tag = f"{tag[8:10]}.{tag[5:7]}.{tag[0:4]}"

    teile = [kopf]
    if warnungen:
        teile.append(f"{warnungen} {'Warnung' if warnungen == 1 else 'Warnungen'}")
    teile += [tag, lauf.get("wetter_name") or ""]

    klasse = ("fertig" if lauf["status"] == "fertig" and not warnungen
              else "warnung" if lauf["status"] == "fertig"
              else "fehler")
    return (klasse, etikett, " · ".join(t for t in teile if t))


def _projektliste():
    """Projekte mit ihren Anlagen - in EINER Abfrage je Tabelle.

    Lehrmaterial (die Ein-Karten-Beispielanlagen aus /bausteine) steht
    getrennt: Es ist kein Arbeitsergebnis der Anwenderin und soll weder den
    Einstiegskasten noch "Noch kein Projekt vorhanden" verfaelschen.
    """
    alle_anlagen = anlagen.anlagen_von()
    nach_projekt = {}
    for anlage in alle_anlagen:
        nach_projekt.setdefault(anlage["projekt_id"], []).append(
            {**anlage, "statuszettel": _statuszettel(anlage),
             "mit_bericht": bool(
                 anlage.get("letzter_lauf")
                 and anlage["letzter_lauf"]["status"] in STATUS_MIT_BERICHT
             )}
        )
    eigene, lehrmaterial = [], []
    for projekt in anlagen.projekte():
        eintrag = {**projekt, "anlagen": nach_projekt.get(projekt["id"], [])}
        (lehrmaterial if projekt["ist_lehrmaterial"] else eigene).append(eintrag)
    return eigene, lehrmaterial


# Woher ein Datensatz stammt, in der Sprache der Oberflaeche. Dieselben zwei
# Woerter stehen in static/js/start.js (WETTER_QUELLE_TEXT) fuer die Zeilen,
# die nach einem Abruf ohne Neuladen dazukommen.
QUELLE_TEXT = {"upload": "Datei-Upload", "open-meteo": "Online-Abruf"}

OHNE_STANDORT = "Ohne Standort"


def _nach_standort(datensaetze):
    """Datensaetze nach Standort buendeln.

    Ein einziger TRY-Ordner bringt sechs Jahre mit, die sonst als sechs
    zusammenhanglose Zeilen dastuenden. Die Reihenfolge der Liste bleibt
    erhalten, damit der zuletzt angelegte Standort oben steht; "Ohne Standort"
    wandert ans Ende, denn es ist kein Standort, sondern dessen Fehlen.

    Gleiche Regel wie wetterNachStandort() in static/js/wetterauswahl.js, die
    dieselbe Buendelung fuer die Auswahlfelder des Editors braucht.
    """
    gruppen = {}
    for eintrag in datensaetze:
        ort = (eintrag.get("ort") or "").strip() or OHNE_STANDORT
        gruppen.setdefault(ort, []).append(eintrag)
    ohne = gruppen.pop(OHNE_STANDORT, None)
    if ohne is not None:
        gruppen[OHNE_STANDORT] = ohne
    return gruppen


@bp.route("/wetter")
def wetter():
    """Die Wetterdaten als eigene Seite.

    Sie standen als groesster Abschnitt auf der Startseite - mit zwei
    Formularen, die dort den meisten Platz einnahmen, waehrend die Projekte
    darueber in zwei Zeilen abgehandelt waren. Wetterdaten sind aber eine
    Voraussetzung fuer einen Lauf, nicht der Zweck der Anwendung; auf der
    Startseite steht jetzt nur noch, ob welche da sind, und der Weg hierher.

    Die Liste kommt fertig aus dieser Route, nicht aus dem Browser. Sie holte
    sich der Seitenaufbau vorher ueber /api/wetter nach - mit der Folge, dass
    der eigentliche Inhalt dieser Seite bis zur Antwort fehlte und dass er in
    keinem Abzug der Seite auftauchte. Dieselbe Umstellung wie bei der
    Projektliste der Startseite (_projektliste).
    """
    datensaetze = speicher.datensaetze()
    return render_template(
        "wetter.html",
        standorte=_nach_standort(datensaetze),
        quelle_text=QUELLE_TEXT,
        anzahl=len(datensaetze),
    )


@bp.route("/anlage/<int:anlage_id>")
def editor(anlage_id):
    """Der Schreibtisch - mit der Anlage und der Palette schon an Bord.

    Beides holte die Seite bis zum Umbau der Oberflaeche erst nach dem Laden
    ueber /api/palette und /api/anlagen/<id>. Bis die zweite Antwort da war,
    stand der Editor als leere Flaeche mit leerer Palette da - und auf keinem
    Abzug der Seite war die Anlage zu sehen. Die Leinwand selbst bleibt ein
    Programm im Browser (sie zeichnet, misst, verschiebt); nur ihre Daten
    kommen jetzt mit der Seite, statt in einer zweiten Runde.

    Ohne die Pruefung unten rendert der Editor fuer JEDE Zahl, auch eine
    Anlage, die es nie gab oder die inzwischen geloescht wurde - er zeigt dann
    "Diese Anlage ist noch leer.", ununterscheidbar von einer echten, frisch
    angelegten Anlage. Eine eigene Seite statt eines stillen Redirects auf die
    Startseite: der Link selbst war falsch oder veraltet, das soll sichtbar
    bleiben statt kommentarlos woanders hinzufuehren.
    """
    if not anlagen.anlage_existiert(anlage_id):
        return render_template("anlage_nicht_gefunden.html", anlage_id=anlage_id), 404
    return render_template(
        "editor.html",
        anlage_id=anlage_id,
        anlage_json=json.dumps(anlagen.als_json(anlage_id), ensure_ascii=False),
        palette_json=json.dumps(anlagen.palette(), ensure_ascii=False),
    )
