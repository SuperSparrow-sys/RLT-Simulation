"""Anlagen, Karten, Ports und Pfeile lesen und schreiben."""

import json

from core import graph, verlauf
from core.bausteine import basis, lade_alle
from core.database import get_db

lade_alle()

# Name des Sammelprojekts fuer die Beispielanlagen aus dem Erklaerbereich
# (core.lehrinhalte.beispielanlagen.NAME_PROJEKT) - hier dupliziert statt
# importiert, um core.anlagen nicht von core.lehrinhalte abhaengig zu
# machen (core.lehrinhalte.beispielanlagen importiert bereits core.anlagen;
# ein Import in Gegenrichtung waere ein Zirkelbezug). Nur fuer die Markierung
# in projekte() gebraucht, die die Startseite nutzt, um Lehrmaterial optisch
# von den eigenen Projekten des Benutzers zu trennen.
NAME_PROJEKT_LEHRMATERIAL = "Bausteine"


# -- Projekte und Anlagen -------------------------------------------------

def projekt_anlegen(name, beschreibung=""):
    db = get_db()
    cur = db.execute(
        "INSERT INTO projekt (name, beschreibung) VALUES (?, ?)", (name, beschreibung)
    )
    db.commit()
    return cur.lastrowid


def anlage_anlegen(projekt_id, name, notiz=""):
    db = get_db()
    if db.execute("SELECT 1 FROM projekt WHERE id = ?", (projekt_id,)).fetchone() is None:
        raise KeyError(f"Projekt {projekt_id} gibt es nicht")
    cur = db.execute(
        "INSERT INTO anlage (projekt_id, name, notiz) VALUES (?, ?, ?)",
        (projekt_id, name, notiz),
    )
    db.commit()
    return cur.lastrowid


def projekt_umbenennen(projekt_id, name):
    db = get_db()
    cur = db.execute(
        "UPDATE projekt SET name = ?, geaendert_am = datetime('now') WHERE id = ?",
        (name, projekt_id),
    )
    db.commit()
    if cur.rowcount == 0:
        raise KeyError(f"Projekt {projekt_id} gibt es nicht")


def projekt_loeschen(projekt_id):
    """Loescht ein Projekt mitsamt allen seinen Anlagen.

    ON DELETE CASCADE (core/database.py) reisst dabei jede Anlage mit ihren
    Karten, Pfeilen, Verbindungen und Simulationslaeufen (samt Zeitreihe und
    Bilanz) mit - ein Projekt mit drei Anlagen und zwoelf Laeufen hinterlaesst
    keine einzige Zeile. Ruft vorher laeufe.abbrich_vor_loeschen() nicht selbst
    auf (core/anlagen.py kennt core.laeufe nicht - zirkulaerer Import), das
    macht die aufrufende Route (routes/anlagen.py)."""
    db = get_db()
    db.execute("DELETE FROM projekt WHERE id = ?", (projekt_id,))
    db.commit()


def anlage_umbenennen(anlage_id, name):
    db = get_db()
    if db.execute("SELECT 1 FROM anlage WHERE id = ?", (anlage_id,)).fetchone() is None:
        raise KeyError(f"Anlage {anlage_id} gibt es nicht")
    with verlauf.schritt(anlage_id, f"Anlage in '{name}' umbenannt"):
        db.execute(
            "UPDATE anlage SET name = ?, geaendert_am = datetime('now') WHERE id = ?",
            (name, anlage_id),
        )
        db.commit()


def anlage_loeschen(anlage_id):
    """Loescht eine Anlage mitsamt Karten, Pfeilen, Verbindungen und
    Simulationslaeufen (samt Zeitreihe und Bilanz) - alles ueber ON DELETE
    CASCADE (core/database.py). Ein noch laufender Lauf dieser Anlage wird
    dabei mitgeloescht; dass sein Rechen-Thread davon sauber erfaehrt, regelt
    laeufe.abbrich_vor_loeschen() vor diesem Aufruf (siehe routes/anlagen.py)."""
    db = get_db()
    db.execute("DELETE FROM anlage WHERE id = ?", (anlage_id,))
    db.commit()


# -- Karten ---------------------------------------------------------------

def karte_anlegen(anlage_id, typ, pos_x=0.0, pos_y=0.0, parameter=None, name=None):
    """Legt eine Karte samt ihren Ports an.

    Schlaegt einer der Schreibvorgaenge fehl, werden alle zurueckgenommen. Ohne das
    blieben angefangene Schreibvorgaenge auf der Verbindung stehen und wuerden vom
    naechsten erfolgreichen commit() mit festgeschrieben - im Web faellt das nicht
    auf, weil jede Anfrage ihre eigene Verbindung schliesst, in einem Skript oder
    einer Testsitzung mit mehreren Aufrufen aber sehr wohl.
    """
    klasse = basis.hole(typ)
    werte = klasse.vorgabeparameter()
    werte.update(parameter or {})

    db = get_db()
    if db.execute("SELECT 1 FROM anlage WHERE id = ?", (anlage_id,)).fetchone() is None:
        raise KeyError(f"Anlage {anlage_id} gibt es nicht")
    try:
        with verlauf.schritt(anlage_id, f"Karte '{name or klasse.NAME}' angelegt"):
            return _karte_schreiben(
                db, anlage_id, typ, pos_x, pos_y, werte, name, klasse
            )
    except Exception:
        db.rollback()
        raise


def _karte_schreiben(db, anlage_id, typ, pos_x, pos_y, werte, name, klasse):
    cur = db.execute(
        "INSERT INTO karte (anlage_id, typ, name, pos_x, pos_y, parameter) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (anlage_id, typ, name or klasse.NAME, pos_x, pos_y,
         json.dumps(werte, ensure_ascii=False)),
    )
    karte_id = cur.lastrowid

    for port in graph.erzeuge_ports(klasse, werte, karte_id, ab_id=0):
        db.execute(
            "INSERT INTO port (karte_id, schluessel, basis, art, richtung, rolle, nummer) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (karte_id, port.schluessel, port.basis, port.art, port.richtung,
             port.rolle, port.nummer),
        )
    db.commit()
    return karte_id


class UngueltigeParameter(ValueError):
    """Beim Speichern einer Karte: mindestens ein Parameterwert ist unzulaessig
    (siehe core.bausteine.basis.pruefe_parameter).

    `fehler` traegt eine deutsche Meldung je betroffenem Parameterschluessel,
    damit das Parameterfenster genau das Feld markieren kann, das nicht
    stimmt - nicht nur, dass irgendetwas nicht stimmt (routes/anlagen.py gibt
    beides weiter: eine zusammengefasste Meldung und dieses Dict)."""

    def __init__(self, fehler: dict):
        self.fehler = fehler
        super().__init__("; ".join(fehler.values()))


def _aenderung_an_karte(zeile, pos_x, pos_y, parameter, name):
    """Wie heisst diese Aenderung im Verlauf - und gehoert sie mit der
    vorhergehenden zu EINER Handlung?

    Der zweite Rueckgabewert ist der Buendelschluessel (siehe
    core/verlauf.py, _darf_buendeln): Dieselbe Karte mehrmals kurz
    hintereinander zurechtzuruecken ist eine Handlung, ebenso mehrere
    schnelle Aenderungen desselben Parameterfeldes. Zwei verschiedene Felder
    oder zwei verschiedene Karten bleiben zwei Schritte - deshalb steckt die
    Kennung im Schluessel."""
    name_neu = zeile["name"] if name is None else name
    if name is not None and name != zeile["name"]:
        return f"Karte '{name}' umbenannt", None
    if parameter:
        if len(parameter) == 1:
            schluessel = next(iter(parameter))
            klasse = basis.hole(zeile["typ"])
            feld = next(
                (f for f in klasse.PARAMETER if f.schluessel == schluessel), None
            )
            label = feld.label if feld is not None else schluessel
            return (
                f"'{label}' an Karte '{name_neu}' geändert",
                f"parameter:{zeile['id']}:{schluessel}",
            )
        return f"Parameter an Karte '{name_neu}' geändert", None
    if pos_x is not None or pos_y is not None:
        return f"Karte '{name_neu}' verschoben", f"verschieben:{zeile['id']}"
    return f"Karte '{name_neu}' geändert", None


def karte_aendern(karte_id, pos_x=None, pos_y=None, parameter=None, name=None):
    db = get_db()
    zeile = db.execute("SELECT * FROM karte WHERE id = ?", (karte_id,)).fetchone()
    if zeile is None:
        raise KeyError(f"Karte {karte_id} gibt es nicht")

    werte = json.loads(zeile["parameter"])
    if parameter:
        klasse = basis.hole(zeile["typ"])
        fehlermeldungen = basis.pruefe_parameter(klasse, parameter)
        if fehlermeldungen:
            raise UngueltigeParameter(fehlermeldungen)
        werte.update(parameter)

    beschreibung, buendel = _aenderung_an_karte(zeile, pos_x, pos_y, parameter, name)
    with verlauf.schritt(zeile["anlage_id"], beschreibung, buendel):
        db.execute(
            "UPDATE karte SET pos_x = ?, pos_y = ?, parameter = ?, name = ? "
            "WHERE id = ?",
            (
                zeile["pos_x"] if pos_x is None else pos_x,
                zeile["pos_y"] if pos_y is None else pos_y,
                json.dumps(werte, ensure_ascii=False),
                zeile["name"] if name is None else name,
                karte_id,
            ),
        )
        db.commit()


def karte_loeschen(karte_id):
    """Loescht eine Karte samt ihren Anschluessen und allen Pfeilen, die an
    ihr hingen (ON DELETE CASCADE, core/database.py).

    Der Verlauf haelt vorher den ganzen Zustand fest - zurueckgenommen kommt
    die Karte mit DERSELBEN Kennung wieder, samt Anschluessen, Pfeilen und
    Verbindungen (core/verlauf.py). Gibt es die Karte nicht (mehr), bleibt
    das wie bisher folgenlos; verlauf.schritt(None, ...) tut dann nichts."""
    db = get_db()
    zeile = db.execute(
        "SELECT anlage_id, name FROM karte WHERE id = ?", (karte_id,)
    ).fetchone()
    anlage_id = zeile["anlage_id"] if zeile else None
    with verlauf.schritt(
        anlage_id, f"Karte '{zeile['name']}' gelöscht" if zeile else ""
    ):
        db.execute("DELETE FROM karte WHERE id = ?", (karte_id,))
        db.commit()


# -- Pfeile ---------------------------------------------------------------

def _karte_instanz(zeile, ports):
    klasse = basis.hole(zeile["typ"])
    werte = json.loads(zeile["parameter"])
    return graph.KarteInstanz(
        id=zeile["id"],
        typ=zeile["typ"],
        name=zeile["name"],
        parameter=werte,
        baustein=klasse(),
        ports=[
            graph.PortInstanz(
                id=p["id"], karte_id=p["karte_id"], schluessel=p["schluessel"],
                basis=p["basis"], art=p["art"], richtung=p["richtung"],
                rolle=p["rolle"], nummer=p["nummer"],
            )
            for p in ports
        ],
    )


def _lade_karte(karte_id):
    db = get_db()
    zeile = db.execute("SELECT * FROM karte WHERE id = ?", (karte_id,)).fetchone()
    if zeile is None:
        raise KeyError(f"Karte {karte_id} gibt es nicht")
    ports = db.execute(
        "SELECT * FROM port WHERE karte_id = ? ORDER BY id", (karte_id,)
    ).fetchall()
    karte = _karte_instanz(zeile, ports)
    karte.anlage_id = zeile["anlage_id"]
    return karte


def _belegte_ports(anlage_id):
    db = get_db()
    zeilen = db.execute(
        "SELECT v.von_port_id AS a, v.nach_port_id AS b "
        "FROM verbindung v JOIN pfeil p ON p.id = v.pfeil_id WHERE p.anlage_id = ?",
        (anlage_id,),
    ).fetchall()
    belegt = set()
    for z in zeilen:
        belegt.add(z["a"])
        belegt.add(z["b"])
    return belegt


def pfeil_anlegen(anlage_id, von_karte_id, nach_karte_id):
    if von_karte_id == nach_karte_id:
        raise ValueError("Eine Karte kann nicht mit sich selbst verbunden werden")

    db = get_db()
    von = _lade_karte(von_karte_id)
    nach = _lade_karte(nach_karte_id)

    # Beide Karten muessen zu DIESER Anlage gehoeren. Sonst entstuende ein Pfeil,
    # dessen Verbindungen beim Laden der Anlage stillschweigend verschwinden - der
    # Graph waere unvollstaendig, ohne dass irgendwo etwas gemeldet wuerde.
    for karte in (von, nach):
        if karte.anlage_id != anlage_id:
            raise ValueError(
                f"Die Karte '{karte.name}' gehört nicht zu dieser Anlage"
            )

    belegt = _belegte_ports(anlage_id)

    paare = graph.verdrahte(von, nach, belegt)
    if not paare:
        raise ValueError(
            f"Zwischen '{von.name}' und '{nach.name}' passt kein freier Anschluss "
            "zusammen"
        )

    # Wurde hier geraten? graph.alternativen nennt die verworfenen Moeglichkeiten -
    # gibt es welche, war die Zuordnung nicht die einzig moegliche, und der Editor
    # soll den Pfeil als mehrdeutig kennzeichnen (siehe core/graph.py).
    mehrdeutig = bool(graph.alternativen(von, nach, belegt))

    try:
        with verlauf.schritt(
            anlage_id, f"Pfeil von '{von.name}' nach '{nach.name}' angelegt"
        ):
            return _pfeil_schreiben(
                db, anlage_id, von_karte_id, nach_karte_id, von, nach, paare, belegt,
                mehrdeutig,
            )
    except Exception:
        db.rollback()
        raise


def _pfeil_schreiben(
    db, anlage_id, von_karte_id, nach_karte_id, von, nach, paare, belegt, mehrdeutig,
):
    cur = db.execute(
        "INSERT INTO pfeil (anlage_id, von_karte_id, nach_karte_id, mehrdeutig) "
        "VALUES (?, ?, ?, ?)",
        (anlage_id, von_karte_id, nach_karte_id, int(mehrdeutig)),
    )
    pfeil_id = cur.lastrowid

    verbindungen = []
    for v, n in paare:
        db.execute(
            "INSERT INTO verbindung (pfeil_id, von_port_id, nach_port_id) "
            "VALUES (?, ?, ?)",
            (pfeil_id, v.id, n.id),
        )
        verbindungen.append(
            {
                "von_karte_id": v.karte_id, "von_schluessel": v.schluessel,
                "nach_karte_id": n.karte_id, "nach_schluessel": n.schluessel,
            }
        )

    # dynamische Ports nachwachsen lassen
    neu_belegt = belegt | {v.id for v, _ in paare} | {n.id for _, n in paare}
    for karte in (von, nach):
        for port in graph.fehlende_ports(karte, neu_belegt):
            db.execute(
                "INSERT INTO port (karte_id, schluessel, basis, art, richtung, rolle, "
                "nummer) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (karte.id, port.schluessel, port.basis, port.art, port.richtung,
                 port.rolle, port.nummer),
            )

    db.commit()
    return {"id": pfeil_id, "verbindungen": verbindungen, "mehrdeutig": mehrdeutig}


def pfeil_loeschen(pfeil_id):
    """Loest einen Pfeil samt seinen Verbindungen (ON DELETE CASCADE).

    Die Anschluesse selbst bleiben stehen - nur ihre Verbindung faellt weg.
    Zurueckgenommen zeigt sie wieder auf dieselben Anschluesse (siehe
    core/verlauf.py: auch die 'verbindung'-Zeilen behalten ihre Kennung)."""
    db = get_db()
    zeile = db.execute(
        "SELECT p.anlage_id, v.name AS von_name, n.name AS nach_name FROM pfeil p "
        "JOIN karte v ON v.id = p.von_karte_id "
        "JOIN karte n ON n.id = p.nach_karte_id WHERE p.id = ?",
        (pfeil_id,),
    ).fetchone()
    anlage_id = zeile["anlage_id"] if zeile else None
    beschreibung = (
        f"Pfeil von '{zeile['von_name']}' nach '{zeile['nach_name']}' getrennt"
        if zeile
        else ""
    )
    with verlauf.schritt(anlage_id, beschreibung):
        db.execute("DELETE FROM pfeil WHERE id = ?", (pfeil_id,))
        db.commit()


def port_id(karte_id, schluessel):
    """Anschluss-Id einer Karte ueber ihren Schluessel.

    Fuer Vorlagen, die eine Verbindung ausdruecklich statt automatisch setzen
    wollen (siehe verbindung_anlegen) - core/anlagen.py bleibt so der einzige Ort,
    der Schema-Wissen ueber die Datenbank hat.
    """
    db = get_db()
    zeile = db.execute(
        "SELECT id FROM port WHERE karte_id = ? AND schluessel = ?",
        (karte_id, schluessel),
    ).fetchone()
    if zeile is None:
        raise KeyError(f"Anschluss '{schluessel}' gibt es nicht an Karte {karte_id}")
    return zeile["id"]


def verbindung_anlegen(anlage_id, von_port_id, nach_port_id):
    """Verbindet zwei Anschluesse ausdruecklich, ohne zu raten.

    Die automatische Verdrahtung laesst einen namenlosen Istwert-Anschluss frei,
    wenn die Quelle mehrere Messwerte anbietet - welcher gemeint ist, kann sie nicht
    wissen. Diese Funktion ist der Weg, ihn dann selbst zu setzen. Sie legt einen
    Pfeil mit genau einer Verbindung an, damit er sich wie jeder andere loeschen
    laesst.
    """
    db = get_db()
    ports = {}
    for port_id in (von_port_id, nach_port_id):
        zeile = db.execute(
            "SELECT p.*, k.anlage_id, k.name AS karte_name FROM port p "
            "JOIN karte k ON k.id = p.karte_id WHERE p.id = ?",
            (port_id,),
        ).fetchone()
        if zeile is None:
            raise KeyError(f"Anschluss {port_id} gibt es nicht")
        if zeile["anlage_id"] != anlage_id:
            raise ValueError(
                f"Der Anschluss '{zeile['schluessel']}' gehört nicht zu dieser Anlage"
            )
        ports[port_id] = zeile

    von, nach = ports[von_port_id], ports[nach_port_id]
    if von["richtung"] != "aus" or nach["richtung"] != "ein":
        raise ValueError("Ein Pfeil läuft von einem Ausgang zu einem Eingang")
    if von["art"] != nach["art"]:
        raise ValueError("Luft lässt sich nicht mit einem Signal verbinden")

    belegt = _belegte_ports(anlage_id)
    if nach_port_id in belegt:
        raise ValueError(
            f"Der Anschluss '{nach['schluessel']}' ist schon belegt"
        )
    # Ein Luftausgang fuehrt an genau eine Stelle - auch von Hand darf daran kein
    # zweiter Kanal haengen, sonst umginge diese Funktion die Regel, die die
    # automatische Verdrahtung durchsetzt. Signalausgaenge duerfen dagegen
    # beliebig viele Verbraucher speisen.
    if von["art"] == "luft" and von_port_id in belegt:
        raise ValueError(
            f"Der Luftausgang '{von['schluessel']}' führt schon woanders hin – "
            "für eine Verzweigung gibt es den Verteiler"
        )

    beschreibung = (
        f"'{nach['schluessel']}' an Karte '{nach['karte_name']}' mit "
        f"'{von['karte_name']}' verbunden"
    )
    try:
        with verlauf.schritt(anlage_id, beschreibung):
            cur = db.execute(
                "INSERT INTO pfeil (anlage_id, von_karte_id, nach_karte_id) "
                "VALUES (?, ?, ?)",
                (anlage_id, von["karte_id"], nach["karte_id"]),
            )
            db.execute(
                "INSERT INTO verbindung (pfeil_id, von_port_id, nach_port_id) "
                "VALUES (?, ?, ?)",
                (cur.lastrowid, von_port_id, nach_port_id),
            )
            db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "id": cur.lastrowid,
        "mehrdeutig": False,  # eine von Hand gesetzte Verbindung ist keine Vermutung
        "verbindungen": [
            {"von_karte_id": von["karte_id"], "von_schluessel": von["schluessel"],
             "nach_karte_id": nach["karte_id"], "nach_schluessel": nach["schluessel"]}
        ],
    }


# -- Lesen ----------------------------------------------------------------

def lade_graph(anlage_id):
    db = get_db()
    karten = {}
    for zeile in db.execute(
        "SELECT * FROM karte WHERE anlage_id = ? ORDER BY id", (anlage_id,)
    ):
        ports = db.execute(
            "SELECT * FROM port WHERE karte_id = ? ORDER BY id", (zeile["id"],)
        ).fetchall()
        karten[zeile["id"]] = _karte_instanz(zeile, ports)

    nach_id = {p.id: p for k in karten.values() for p in k.ports}
    verbindungen = []
    for zeile in db.execute(
        "SELECT v.* FROM verbindung v JOIN pfeil p ON p.id = v.pfeil_id "
        "WHERE p.anlage_id = ?",
        (anlage_id,),
    ):
        von = nach_id.get(zeile["von_port_id"])
        nach = nach_id.get(zeile["nach_port_id"])
        if von and nach:
            verbindungen.append(
                graph.VerbindungInstanz(
                    von_port=von, nach_port=nach, pfeil_id=zeile["pfeil_id"],
                )
            )

    return graph.Anlagengraph(karten=karten, verbindungen=verbindungen)


def _messwert_label(karte, schluessel):
    """Menschenlesere Beschriftung eines Ausgangswerts einer Karte.

    Faellt auf den rohen Schluessel zurueck, wenn die Kartenklasse dafuer keine
    eigene Beschriftung in AUSGABE_LABEL hinterlegt hat.
    """
    klasse = basis.hole(karte.typ)
    return getattr(klasse, "AUSGABE_LABEL", {}).get(schluessel, schluessel)


def _port_label(karte, port):
    """Menschenlesbare Beschriftung eines Anschlusses.

    Fuer den Anschluesse-Abschnitt des Parameterfensters (static/js/panel.js,
    bauePortliste), der bisher nur den rohen Schluessel samt Rolle zeigte
    (z.B. 'ausgang_2 · stellgroesse'). Reicht dieselben Beschriftungsquellen
    weiter, die 'Regelt auf' schon benutzt - zuerst AUSGABE_LABEL (siehe
    _messwert_label), dann ein gleichnamiger Parameter (dessen Label die Karte
    ohnehin schon fuer das Eingabefeld traegt), zuletzt die uebersetzte Rolle
    (basis.ROLLEN_LABEL). Kein Kartentyp muss dafuer selbst etwas deklarieren;
    Mehrdeutigkeiten zwischen gleichartigen Anschluessen (mehrere Stellgroessen,
    mehrere Protokollspalten) loest das Parameterfenster selbst ueber die
    laufende Nummer im Schluessel auf.
    """
    klasse = basis.hole(karte.typ)
    label = getattr(klasse, "AUSGABE_LABEL", {}).get(port.basis)
    if label is not None:
        return label
    feld = next((p for p in klasse.PARAMETER if p.schluessel == port.basis), None)
    if feld is not None:
        return feld.label
    return basis.ROLLEN_LABEL.get(port.rolle, port.rolle)


def _ueberschreibung(karte, feld, nach_verbindung, g):
    """Ist `feld` ein 'fest, aber durch eine Verbindung ersetzbarer' Parameter?

    Das erkennt sich rein strukturell: die Karte deklariert einen EINGANGs-Port
    mit demselben Schluessel wie der Parameter (siehe hysterese_regler.istwert,
    p_regler.sollwert_1/istwert_1 usw.) - kein Sonderfall je Kartentyp noetig.
    Ist dieser Port aktuell verbunden, gilt statt des Parameterwerts die
    Verbindung; die Rueckgabe nennt dann, woher der Wert stattdessen kommt.

    Rueckgabe: None, wenn der Parameter keinen gleichnamigen Eingang hat oder
    dieser frei ist. Sonst ein dict mit der Herkunft und der Pfeil-Id, mit der
    sich die Verbindung wieder loesen laesst (DELETE /api/pfeile/<id>).
    """
    passender_port = next(
        (p for p in karte.ports if p.schluessel == feld.schluessel), None
    )
    if passender_port is None or passender_port.richtung != basis.EINGANG:
        return None

    verbindung = nach_verbindung.get(passender_port.id)
    if verbindung is None:
        return None

    quelle = g.karten.get(verbindung.von_port.karte_id)
    return {
        "von_karte_id": verbindung.von_port.karte_id,
        "von_karte_name": quelle.name if quelle else "",
        "von_schluessel": verbindung.von_port.schluessel,
        "von_label": _messwert_label(quelle, verbindung.von_port.basis) if quelle else verbindung.von_port.schluessel,
        "pfeil_id": verbindung.pfeil_id,
    }


def anlage_existiert(anlage_id):
    """Fuer routes/pages.py: die Editorseite einer Anlage, die es nicht (mehr)
    gibt, soll das auch zeigen (siehe templates/anlage_nicht_gefunden.html),
    statt einen leeren Editor zu rendern. Eigene, billige Abfrage statt
    als_json() nur fuer diese Frage aufzurufen - das baut Karten, Ports und
    Pfeile komplett auf, hier reicht eine einzelne Zeile."""
    db = get_db()
    return db.execute("SELECT 1 FROM anlage WHERE id = ?", (anlage_id,)).fetchone() is not None


def als_json(anlage_id):
    db = get_db()
    anlage = db.execute("SELECT * FROM anlage WHERE id = ?", (anlage_id,)).fetchone()
    if anlage is None:
        raise KeyError(f"Anlage {anlage_id} gibt es nicht")
    g = lade_graph(anlage_id)
    nach_verbindung = {v.nach_port.id: v for v in g.verbindungen}

    karten = []
    for zeile in db.execute(
        "SELECT * FROM karte WHERE anlage_id = ? ORDER BY id", (anlage_id,)
    ):
        klasse = basis.hole(zeile["typ"])
        karte = g.karten[zeile["id"]]
        karten.append(
            {
                "id": zeile["id"],
                "typ": zeile["typ"],
                "name": zeile["name"],
                "symbol": klasse.SYMBOL,
                "gruppe": klasse.GRUPPE,
                "pos_x": zeile["pos_x"],
                "pos_y": zeile["pos_y"],
                "parameter": karte.parameter,
                "felder": [
                    {
                        "schluessel": f.schluessel, "label": f.label,
                        "einheit": f.einheit, "auswahl": list(f.auswahl),
                        "darstellung": f.darstellung,
                        "dezimalstellen": f.dezimalstellen,
                        "ueberschrieben_von": _ueberschreibung(
                            karte, f, nach_verbindung, g
                        ),
                    }
                    for f in klasse.PARAMETER
                ],
                "ports": [
                    {
                        "id": p.id, "schluessel": p.schluessel, "art": p.art,
                        "richtung": p.richtung, "rolle": p.rolle,
                        "label": _port_label(karte, p),
                    }
                    for p in karte.ports
                ],
            }
        )

    pfeile = []
    for zeile in db.execute(
        "SELECT * FROM pfeil WHERE anlage_id = ? ORDER BY id", (anlage_id,)
    ):
        verbindungen = db.execute(
            "SELECT * FROM verbindung WHERE pfeil_id = ?", (zeile["id"],)
        ).fetchall()

        pfeile.append(
            {
                "id": zeile["id"],
                "von_karte_id": zeile["von_karte_id"],
                "nach_karte_id": zeile["nach_karte_id"],
                "stuetzpunkte": json.loads(zeile["stuetzpunkte"]),
                # Ob geraten wurde, ist eine Tatsache ueber den Moment, in dem
                # der Pfeil entstand - keine Eigenschaft des heutigen
                # Anlagenzustands. Deshalb wird sie in pfeil_anlegen() einmal
                # berechnet und hier nur gelesen, nicht neu bestimmt: eine
                # Neuberechnung ueber die aktuelle Portbelegung liefert ein
                # anderes Ergebnis, sobald spaeter angelegte Pfeile an der
                # Gegenkarte weitere, zufaellig noch freie Anschluesse
                # nachwachsen lassen.
                "mehrdeutig": bool(zeile["mehrdeutig"]),
                "verbindungen": [
                    {"von_port_id": v["von_port_id"], "nach_port_id": v["nach_port_id"]}
                    for v in verbindungen
                ],
            }
        )

    return {
        "id": anlage_id,
        "name": anlage["name"],
        "karten": karten,
        "pfeile": pfeile,
    }


def messwerte_von(anlage_id):
    """Alle Messwerte, die die Karten dieser Anlage anbieten.

    Das sind die Kandidaten, um einen Istwert oder Sollwert eines Reglers
    gezielt zu verdrahten - jeder Signalausgang mit Rolle MESSWERT, egal ob er
    schon irgendwo angeschlossen ist oder nicht (ein Messwert darf mehrere
    Abnehmer speisen, siehe core.graph._paare). Antwortet auf die Frage 'Wie
    kann ich einen Regler intern auf verschiedene Groessen regeln?':

    Die Oberflaeche bietet je Istwert-/Sollwert-Anschluss einer Reglerkarte
    (Port mit rolle=ISTWERT bzw. SOLLWERT) eine Auswahl aus dieser Liste an -
    'kommt von: <karte_name> -> <label>' - und verbindet die Wahl mit
    POST /api/verbindungen (von_port_id=messwert['port_id'], nach_port_id=der
    Istwert-/Sollwert-Port). Eine bestehende Wahl wird durch DELETE
    /api/pfeile/<pfeil_id> wieder geloest, wobei die Pfeil-Id aus dem
    'ueberschrieben_von' der jeweiligen Karte in als_json() kommt.
    """
    g = lade_graph(anlage_id)
    messwerte = []
    for karte in g.karten.values():
        for port in karte.ports:
            if (
                port.art == basis.SIGNAL
                and port.richtung == basis.AUSGANG
                and port.rolle == basis.MESSWERT
            ):
                messwerte.append(
                    {
                        "port_id": port.id,
                        "karte_id": karte.id,
                        "karte_name": karte.name,
                        "karte_typ": karte.typ,
                        "schluessel": port.schluessel,
                        "label": _messwert_label(karte, port.basis),
                    }
                )
    messwerte.sort(key=lambda m: (m["karte_name"], m["label"]))
    return messwerte


def projekte():
    """Alle Projekte mit der Zahl ihrer Anlagen und Simulationslaeufe.

    Die Laeufe-Zahl zaehlt ueber alle Anlagen des Projekts - sie ist die
    Grundlage der Rueckfrage vor dem Loeschen ('3 Anlagen mit 12
    Simulationslaeufen'), nicht nur eine Zierde der Liste."""
    db = get_db()
    return [
        {"id": z["id"], "name": z["name"], "beschreibung": z["beschreibung"],
         "anlagen": z["anlagen"], "simulationen": z["simulationen"],
         "geaendert_am": z["geaendert_am"],
         "ist_lehrmaterial": z["name"] == NAME_PROJEKT_LEHRMATERIAL}
        for z in db.execute(
            "SELECT p.*, "
            "       (SELECT COUNT(*) FROM anlage a WHERE a.projekt_id = p.id) "
            "         AS anlagen, "
            "       (SELECT COUNT(*) FROM simulation s "
            "        JOIN anlage a2 ON a2.id = s.anlage_id "
            "        WHERE a2.projekt_id = p.id) AS simulationen "
            "FROM projekt p ORDER BY p.geaendert_am DESC, p.id DESC"
        )
    ]


def anlage_kopf(anlage_id):
    """Name, Notiz und Projektzugehoerigkeit einer einzelnen Anlage - fuer den
    Kopf des Berichts (core.bericht), der weder die volle als_json()
    (Karten, Ports, Pfeile) noch anlagen_von() (immer eine Liste) braucht."""
    db = get_db()
    zeile = db.execute(
        "SELECT a.id, a.name, a.notiz, a.projekt_id, p.name AS projekt_name "
        "FROM anlage a JOIN projekt p ON p.id = a.projekt_id WHERE a.id = ?",
        (anlage_id,),
    ).fetchone()
    if zeile is None:
        raise KeyError(f"Anlage {anlage_id} gibt es nicht")
    return dict(zeile)


def anlagen_von(projekt_id=None):
    """Alle Anlagen, wahlweise auf ein Projekt eingegrenzt - mit der Zahl
    ihrer Karten und Simulationslaeufe (letztere fuer dieselbe Rueckfrage vor
    dem Loeschen wie bei projekte())."""
    db = get_db()
    abfrage = (
        "SELECT a.*, p.name AS projekt_name, "
        "       (SELECT COUNT(*) FROM karte k WHERE k.anlage_id = a.id) AS karten, "
        "       (SELECT COUNT(*) FROM simulation s WHERE s.anlage_id = a.id) "
        "         AS simulationen "
        "FROM anlage a JOIN projekt p ON p.id = a.projekt_id"
    )
    werte = []
    if projekt_id is not None:
        abfrage += " WHERE a.projekt_id = ?"
        werte.append(projekt_id)
    abfrage += " ORDER BY a.id"
    return [
        {"id": z["id"], "projekt_id": z["projekt_id"], "projekt_name": z["projekt_name"],
         "name": z["name"], "notiz": z["notiz"], "karten": z["karten"],
         "simulationen": z["simulationen"]}
        for z in db.execute(abfrage, werte)
    ]


def palette():
    """Die Kartentypen nach Gruppen, fuer die Symbolleiste."""
    gruppen = {}
    for klasse in basis.alle():
        gruppen.setdefault(klasse.GRUPPE, []).append(
            {"kennung": klasse.KENNUNG, "name": klasse.NAME, "symbol": klasse.SYMBOL}
        )
    for klassen in gruppen.values():
        klassen.sort(key=lambda k: k["name"])
    return gruppen
