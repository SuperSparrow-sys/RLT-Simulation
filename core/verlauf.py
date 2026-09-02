"""Rueckgaengig und Wiederholen: vollstaendige Momentaufnahmen einer Anlage.

Der Entwurf steht in docs/superpowers/plans/2026-09-02-rueckgaengig.md. Die
beiden Entscheidungen, aus denen alles Weitere folgt:

1. **Ganze Zustaende statt einzelner Umkehrungen.** Nach jeder Aenderung wird
   der gesamte Zustand der Anlage (Name, Notiz, Karten, Anschluesse, Pfeile,
   Verbindungen) als gzip-JSON abgelegt. Der vollstaendige Zustand von Anlage
   75 (42 Karten, 61 Pfeile, 369 Anschluesse) misst 69,6 KiB, komprimiert
   7,3 KiB - fuenfzig Schritte kosten damit rund 370 KiB je Anlage. Eine
   Umkehrung je Vorgangsart waere sparsamer, muesste aber fuer jeden der 34
   Kartentypen und jede kuenftige Beziehung einzeln richtig sein. Was hier
   nicht im Zustand steht, gehoert auch nicht dazu; unvollstaendig sein kann
   das Verfahren nicht.

2. **Die Kennungen bleiben erhalten.** Wiederhergestellt wird nicht "eine
   Karte gleichen Typs an gleicher Stelle", sondern dieselbe Karte mit
   derselben `id`. Die Zeitreihen gespeicherter Simulationslaeufe verweisen
   ueber `zeitreihe.karte_id` darauf (core/ergebnisse.py); eine neu vergebene
   Kennung machte die Ergebnisse aller frueheren Laeufe stumm. SQLite laesst
   das Einfuegen mit ausdruecklicher Kennung zu, und der Zaehler von
   AUTOINCREMENT (sqlite_sequence) merkt sich seinen Hoechststand - neu
   angelegte Karten bekommen also auch nach einer Wiederherstellung keine
   schon einmal vergebene Kennung.

Nicht Teil eines Zustands sind Simulationslaeufe, ihre Zeitreihen und
Bilanzen, Wetterdaten und das Projekt: ein Rueckgaengig darf ein
Rechenergebnis nicht vernichten.
"""

import gzip
import json
from datetime import datetime, timezone

from core.database import get_db

# Wie viele Zustaende je Anlage aufgehoben werden. Der aelteste faellt weg,
# der ERSTE (der Ausgangszustand, siehe _grundzustand_sichern) bleibt immer
# erhalten, damit sich an den Anfang zurueckgehen laesst.
GRENZE = 50

# Zwei aufeinanderfolgende Aenderungen mit demselben Buendelschluessel
# (dieselbe Karte verschoben, dasselbe Parameterfeld getippt) innerhalb
# dieser Spanne werden zu EINEM Schritt zusammengefasst - siehe
# _festhalten(). Massstab: ein Schritt ist, was die Anwenderin als eine
# Handlung erlebt.
BUENDEL_FENSTER_S = 5.0

ZEITFORMAT = "%Y-%m-%d %H:%M:%S"


class Leer(LookupError):
    """Es gibt nichts zurueckzunehmen bzw. nichts zu wiederholen."""


def _jetzt():
    """Aktuelle Zeit in UTC - dieselbe Zeitbasis wie SQLites datetime('now'),
    das die uebrigen Tabellen dieses Programms benutzen. Eigene Funktion,
    damit Tests das Buendelfenster ohne echtes Warten pruefen koennen."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# -- Ein Zustand ----------------------------------------------------------

def momentaufnahme(anlage_id):
    """Der vollstaendige Zustand einer Anlage als einfaches dict.

    Die Reihenfolge jeder Liste ist ueber die Kennung festgelegt, damit zwei
    gleiche Zustaende auch byteweise gleich sind (Pruefung 4 des Plans:
    zehn Aenderungen, zehnmal zurueck, byteweise derselbe Zustand).
    Zeitstempel (erstellt_am/geaendert_am) gehoeren ausdruecklich nicht dazu -
    sie beschreiben nicht den Zustand, sondern wann zuletzt daran gearbeitet
    wurde."""
    db = get_db()
    anlage = db.execute(
        "SELECT name, notiz FROM anlage WHERE id = ?", (anlage_id,)
    ).fetchone()
    if anlage is None:
        raise KeyError(f"Anlage {anlage_id} gibt es nicht")

    karten = [
        {"id": z["id"], "typ": z["typ"], "name": z["name"], "pos_x": z["pos_x"],
         "pos_y": z["pos_y"], "parameter": z["parameter"]}
        for z in db.execute(
            "SELECT * FROM karte WHERE anlage_id = ? ORDER BY id", (anlage_id,)
        )
    ]
    ports = [
        {"id": z["id"], "karte_id": z["karte_id"], "schluessel": z["schluessel"],
         "basis": z["basis"], "art": z["art"], "richtung": z["richtung"],
         "rolle": z["rolle"], "nummer": z["nummer"]}
        for z in db.execute(
            "SELECT p.* FROM port p JOIN karte k ON k.id = p.karte_id "
            "WHERE k.anlage_id = ? ORDER BY p.id",
            (anlage_id,),
        )
    ]
    pfeile = [
        {"id": z["id"], "von_karte_id": z["von_karte_id"],
         "nach_karte_id": z["nach_karte_id"], "stuetzpunkte": z["stuetzpunkte"],
         "mehrdeutig": z["mehrdeutig"]}
        for z in db.execute(
            "SELECT * FROM pfeil WHERE anlage_id = ? ORDER BY id", (anlage_id,)
        )
    ]
    verbindungen = [
        {"id": z["id"], "pfeil_id": z["pfeil_id"], "von_port_id": z["von_port_id"],
         "nach_port_id": z["nach_port_id"]}
        for z in db.execute(
            "SELECT v.* FROM verbindung v JOIN pfeil p ON p.id = v.pfeil_id "
            "WHERE p.anlage_id = ? ORDER BY v.id",
            (anlage_id,),
        )
    ]

    return {
        "name": anlage["name"],
        "notiz": anlage["notiz"],
        "karten": karten,
        "ports": ports,
        "pfeile": pfeile,
        "verbindungen": verbindungen,
    }


def _packe(zustand):
    """JSON, komprimiert. mtime=0, damit derselbe Zustand denselben Blob
    ergibt - ohne das traegt gzip die aktuelle Uhrzeit im Kopf und zwei
    gleiche Zustaende waeren nie byteweise gleich."""
    roh = json.dumps(zustand, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return gzip.compress(roh, compresslevel=6, mtime=0)


def _entpacke(blob):
    return json.loads(gzip.decompress(blob).decode("utf-8"))


# -- Einspielen -----------------------------------------------------------

def _einspielen(db, anlage_id, zustand):
    """Spielt einen Zustand ein - ohne commit(), der Aufrufer entscheidet.

    Erst von innen nach aussen loeschen, dann von aussen nach innen
    einfuegen: sonst scheitert entweder ein Fremdschluessel oder es bleibt
    beim ersten Fehler eine halbe Anlage stehen. Der Aufrufer klammert das
    Ganze in EINE Transaktion (siehe zurueck()/vor()/einspielen())."""
    db.execute(
        "DELETE FROM verbindung WHERE pfeil_id IN "
        "(SELECT id FROM pfeil WHERE anlage_id = ?)",
        (anlage_id,),
    )
    db.execute("DELETE FROM pfeil WHERE anlage_id = ?", (anlage_id,))
    db.execute(
        "DELETE FROM port WHERE karte_id IN "
        "(SELECT id FROM karte WHERE anlage_id = ?)",
        (anlage_id,),
    )
    db.execute("DELETE FROM karte WHERE anlage_id = ?", (anlage_id,))

    for k in zustand["karten"]:
        db.execute(
            "INSERT INTO karte (id, anlage_id, typ, name, pos_x, pos_y, parameter) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (k["id"], anlage_id, k["typ"], k["name"], k["pos_x"], k["pos_y"],
             k["parameter"]),
        )
    for p in zustand["ports"]:
        db.execute(
            "INSERT INTO port (id, karte_id, schluessel, basis, art, richtung, "
            "rolle, nummer) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (p["id"], p["karte_id"], p["schluessel"], p["basis"], p["art"],
             p["richtung"], p["rolle"], p["nummer"]),
        )
    for p in zustand["pfeile"]:
        db.execute(
            "INSERT INTO pfeil (id, anlage_id, von_karte_id, nach_karte_id, "
            "stuetzpunkte, mehrdeutig) VALUES (?, ?, ?, ?, ?, ?)",
            (p["id"], anlage_id, p["von_karte_id"], p["nach_karte_id"],
             p["stuetzpunkte"], p["mehrdeutig"]),
        )
    for v in zustand["verbindungen"]:
        db.execute(
            "INSERT INTO verbindung (id, pfeil_id, von_port_id, nach_port_id) "
            "VALUES (?, ?, ?, ?)",
            (v["id"], v["pfeil_id"], v["von_port_id"], v["nach_port_id"]),
        )

    db.execute(
        "UPDATE anlage SET name = ?, notiz = ?, geaendert_am = datetime('now') "
        "WHERE id = ?",
        (zustand["name"], zustand["notiz"], anlage_id),
    )


def einspielen(anlage_id, zustand):
    """Spielt einen Zustand ein und schreibt ihn fest. Erzeugt selbst KEINEN
    neuen Verlaufseintrag - sonst wuechse der Verlauf bei jedem
    Zuruecknehmen."""
    db = get_db()
    try:
        _einspielen(db, anlage_id, zustand)
        db.commit()
    except Exception:
        db.rollback()
        raise


# -- Der Verlauf ----------------------------------------------------------

def _zeiger(db, anlage_id):
    zeile = db.execute(
        "SELECT verlauf_stand FROM anlage WHERE id = ?", (anlage_id,)
    ).fetchone()
    return None if zeile is None else zeile["verlauf_stand"]


def _oberster(db, anlage_id):
    return db.execute(
        "SELECT * FROM zustand WHERE anlage_id = ? ORDER BY nummer DESC LIMIT 1",
        (anlage_id,),
    ).fetchone()


def _grundzustand_sichern(db, anlage_id):
    """Legt, falls der Verlauf dieser Anlage noch leer ist, den Zustand VOR
    der ersten aufgezeichneten Aenderung ab.

    Ohne diesen Eintrag gaebe es zur ersten Aenderung nichts, wohin
    zurueckgenommen werden koennte - der Verlauf begaenne erst hinter ihr.
    Wird bewusst sofort festgeschrieben (commit): schlaegt die eigentliche
    Aenderung danach fehl und nimmt ihr Aufrufer sie mit rollback() zurueck
    (siehe core/anlagen.py, karte_anlegen), soll der Ausgangszustand
    trotzdem stehen bleiben - er beschreibt dann genau die unveraenderte
    Wirklichkeit."""
    if db.execute(
        "SELECT 1 FROM zustand WHERE anlage_id = ? LIMIT 1", (anlage_id,)
    ).fetchone() is not None:
        return
    db.execute(
        "INSERT INTO zustand (anlage_id, nummer, beschreibung, buendel, zeitpunkt, "
        "daten) VALUES (?, 1, ?, NULL, ?, ?)",
        (anlage_id, "Ausgangszustand", _jetzt().strftime(ZEITFORMAT),
         _packe(momentaufnahme(anlage_id))),
    )
    db.execute("UPDATE anlage SET verlauf_stand = 1 WHERE id = ?", (anlage_id,))
    db.commit()


def _grenze_wahren(db, anlage_id):
    """Haelt den Verlauf bei GRENZE Eintraegen: der erste bleibt immer
    erhalten, dazu die juengsten GRENZE-1. Die Luecke, die dabei entsteht,
    stoert nicht - zurueck() und vor() suchen den naechsten VORHANDENEN
    Eintrag, nicht stur nummer±1."""
    nummern = [
        z["nummer"]
        for z in db.execute(
            "SELECT nummer FROM zustand WHERE anlage_id = ? ORDER BY nummer",
            (anlage_id,),
        )
    ]
    if len(nummern) <= GRENZE:
        return
    zu_viel = len(nummern) - GRENZE
    weg = nummern[1:1 + zu_viel]
    db.executemany(
        "DELETE FROM zustand WHERE anlage_id = ? AND nummer = ?",
        [(anlage_id, n) for n in weg],
    )


def festhalten(anlage_id, beschreibung, buendel=None):
    """Haelt den JETZIGEN Zustand der Anlage als neuen Schritt fest.

    Wird nach einer Aenderung aufgerufen (siehe schritt()). Steht der Zeiger
    nicht am Ende - es wurde also etwas zurueckgenommen und danach neu
    geaendert -, faellt alles hinter dem Zeiger weg: das uebliche und das
    einzige Verhalten, das niemanden ueberrascht."""
    db = get_db()
    stand = _zeiger(db, anlage_id)
    if stand is None:
        return  # Anlage gibt es nicht (mehr) - nichts festzuhalten
    daten = _packe(momentaufnahme(anlage_id))

    # Eine Aenderung, die nichts geaendert hat, ist kein Schritt. Der Editor
    # schickt ein PATCH schon beim blossen Anwaehlen einer Karte (das Ziehen
    # endet immer mit einem Speichern der Position, auch wenn die Karte
    # keinen Pixel weit bewegt wurde), und das Parameterfenster speichert
    # beim Verlassen eines Feldes auch dann, wenn niemand etwas getippt hat.
    # Ohne diese Pruefung fuellte sich der Verlauf mit Schritten, die beim
    # Zuruecknehmen sichtbar NICHTS tun - der schlimmste Fall fuer einen
    # Rueckgaengig-Knopf: er tut so, als haette er gewirkt. Vor dem
    # Wegwerfen des Vorwaertsverlaufs geprueft: eine folgenlose Anfrage darf
    # auch nichts wegwerfen.
    geltender = db.execute(
        "SELECT daten FROM zustand WHERE anlage_id = ? AND nummer = ?",
        (anlage_id, stand),
    ).fetchone()
    if geltender is not None and geltender["daten"] == daten:
        return

    db.execute(
        "DELETE FROM zustand WHERE anlage_id = ? AND nummer > ?", (anlage_id, stand)
    )
    jetzt = _jetzt()

    oberster = _oberster(db, anlage_id)
    if _darf_buendeln(db, anlage_id, oberster, buendel, jetzt):
        db.execute(
            "UPDATE zustand SET daten = ?, beschreibung = ?, zeitpunkt = ? WHERE id = ?",
            (daten, beschreibung, jetzt.strftime(ZEITFORMAT), oberster["id"]),
        )
        db.commit()
        return

    nummer = (oberster["nummer"] if oberster else 0) + 1
    db.execute(
        "INSERT INTO zustand (anlage_id, nummer, beschreibung, buendel, zeitpunkt, "
        "daten) VALUES (?, ?, ?, ?, ?, ?)",
        (anlage_id, nummer, beschreibung, buendel, jetzt.strftime(ZEITFORMAT), daten),
    )
    db.execute(
        "UPDATE anlage SET verlauf_stand = ? WHERE id = ?", (nummer, anlage_id)
    )
    _grenze_wahren(db, anlage_id)
    db.commit()


def _darf_buendeln(db, anlage_id, oberster, buendel, jetzt):
    """Gehoert die neue Aenderung zum obersten Schritt statt hinter ihn?

    Ja, wenn beide denselben Buendelschluessel tragen (dieselbe Karte
    verschoben, dasselbe Parameterfeld geaendert) und dazwischen weniger als
    BUENDEL_FENSTER_S liegen. Eine Karte dreimal hintereinander zurechtzu-
    ruecken ist EINE Handlung; dieselbe Karte zehn Minuten spaeter noch
    einmal zu verschieben ist eine zweite. Der Ausgangszustand
    (der einzige Eintrag) wird nie ueberschrieben - sonst gaebe es hinterher
    nichts mehr, wohin man zurueckkoennte."""
    if not buendel or oberster is None or oberster["buendel"] != buendel:
        return False
    # Nicht buendeln, wenn der oberste Eintrag der einzige ist (er ist dann
    # der Ausgangszustand) oder der Zeiger woanders steht.
    if oberster["nummer"] != _zeiger(db, anlage_id) or oberster["nummer"] <= 1:
        return False
    try:
        vorher = datetime.strptime(oberster["zeitpunkt"], ZEITFORMAT)
    except (TypeError, ValueError):
        return False
    return 0 <= (jetzt - vorher).total_seconds() <= BUENDEL_FENSTER_S


class schritt:
    """Klammert eine Aenderung an einer Anlage: Ausgangszustand sichern,
    Aenderung ausfuehren lassen, neuen Zustand festhalten.

        with verlauf.schritt(anlage_id, "Karte 'Erhitzer' gelöscht"):
            db.execute("DELETE FROM karte WHERE id = ?", (karte_id,))

    Scheitert die Aenderung, wird nichts festgehalten. `anlage_id` darf None
    sein (die betroffene Zeile gibt es nicht mehr) - dann tut die Klammer
    gar nichts, statt den Aufrufer mit einem Sonderfall zu belasten."""

    def __init__(self, anlage_id, beschreibung, buendel=None):
        self.anlage_id = anlage_id
        self.beschreibung = beschreibung
        self.buendel = buendel

    def __enter__(self):
        if self.anlage_id is not None:
            _grundzustand_sichern(get_db(), self.anlage_id)
        return self

    def __exit__(self, art, wert, spur):
        if art is None and self.anlage_id is not None:
            festhalten(self.anlage_id, self.beschreibung, self.buendel)
        return False


def _nachbar(db, anlage_id, stand, richtung):
    if richtung < 0:
        return db.execute(
            "SELECT * FROM zustand WHERE anlage_id = ? AND nummer < ? "
            "ORDER BY nummer DESC LIMIT 1",
            (anlage_id, stand),
        ).fetchone()
    return db.execute(
        "SELECT * FROM zustand WHERE anlage_id = ? AND nummer > ? "
        "ORDER BY nummer LIMIT 1",
        (anlage_id, stand),
    ).fetchone()


def _gehe(anlage_id, richtung):
    db = get_db()
    stand = _zeiger(db, anlage_id)
    if stand is None:
        raise KeyError(f"Anlage {anlage_id} gibt es nicht")
    ziel = _nachbar(db, anlage_id, stand, richtung)
    if ziel is None:
        raise Leer(
            "Es gibt nichts zurückzunehmen"
            if richtung < 0
            else "Es gibt nichts zu wiederholen"
        )
    try:
        _einspielen(db, anlage_id, _entpacke(ziel["daten"]))
        db.execute(
            "UPDATE anlage SET verlauf_stand = ? WHERE id = ?",
            (ziel["nummer"], anlage_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return stand_lesen(anlage_id)


def zurueck(anlage_id):
    """Einen Schritt zurueck. Gibt den neuen Stand des Verlaufs zurueck."""
    return _gehe(anlage_id, -1)


def vor(anlage_id):
    """Einen Schritt vor (wiederholen). Gibt den neuen Stand zurueck."""
    return _gehe(anlage_id, +1)


def stand_lesen(anlage_id):
    """Was die beiden Knoepfe im Editor wissen muessen: ob es etwas
    zurueckzunehmen bzw. zu wiederholen gibt, und wie das jeweils heisst."""
    db = get_db()
    stand = _zeiger(db, anlage_id)
    if stand is None:
        raise KeyError(f"Anlage {anlage_id} gibt es nicht")

    # 'Rueckgaengig' nennt die Aenderung, die dadurch verschwindet - das ist
    # die Beschreibung des AKTUELLEN Zustands, nicht die des Ziels.
    aktuell = db.execute(
        "SELECT beschreibung FROM zustand WHERE anlage_id = ? AND nummer = ?",
        (anlage_id, stand),
    ).fetchone()
    frueher = _nachbar(db, anlage_id, stand, -1)
    spaeter = _nachbar(db, anlage_id, stand, +1)

    return {
        "stand": stand,
        "schritte": db.execute(
            "SELECT COUNT(*) AS n FROM zustand WHERE anlage_id = ?", (anlage_id,)
        ).fetchone()["n"],
        "kann_zurueck": frueher is not None,
        "kann_vor": spaeter is not None,
        "zurueck_text": aktuell["beschreibung"] if frueher is not None and aktuell else "",
        "vor_text": spaeter["beschreibung"] if spaeter is not None else "",
    }
