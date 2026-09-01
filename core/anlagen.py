"""Anlagen, Karten, Ports und Pfeile lesen und schreiben."""

import json

from core import graph
from core.bausteine import basis, lade_alle
from core.database import get_db

lade_alle()


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
    cur = db.execute(
        "INSERT INTO anlage (projekt_id, name, notiz) VALUES (?, ?, ?)",
        (projekt_id, name, notiz),
    )
    db.commit()
    return cur.lastrowid


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
    try:
        return _karte_schreiben(db, anlage_id, typ, pos_x, pos_y, werte, name, klasse)
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


def karte_aendern(karte_id, pos_x=None, pos_y=None, parameter=None, name=None):
    db = get_db()
    zeile = db.execute("SELECT * FROM karte WHERE id = ?", (karte_id,)).fetchone()
    if zeile is None:
        raise KeyError(f"Karte {karte_id} gibt es nicht")

    werte = json.loads(zeile["parameter"])
    if parameter:
        werte.update(parameter)

    db.execute(
        "UPDATE karte SET pos_x = ?, pos_y = ?, parameter = ?, name = ? WHERE id = ?",
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
    db = get_db()
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
                f"Die Karte '{karte.name}' gehoert nicht zu dieser Anlage"
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
    db = get_db()
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
                f"Der Anschluss '{zeile['schluessel']}' gehoert nicht zu dieser Anlage"
            )
        ports[port_id] = zeile

    von, nach = ports[von_port_id], ports[nach_port_id]
    if von["richtung"] != "aus" or nach["richtung"] != "ein":
        raise ValueError("Ein Pfeil laeuft von einem Ausgang zu einem Eingang")
    if von["art"] != nach["art"]:
        raise ValueError("Luft laesst sich nicht mit einem Signal verbinden")

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
            f"Der Luftausgang '{von['schluessel']}' fuehrt schon woanders hin - "
            "fuer eine Verzweigung gibt es den Verteiler"
        )

    try:
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
            verbindungen.append(graph.VerbindungInstanz(von_port=von, nach_port=nach))

    return graph.Anlagengraph(karten=karten, verbindungen=verbindungen)


def als_json(anlage_id):
    db = get_db()
    anlage = db.execute("SELECT * FROM anlage WHERE id = ?", (anlage_id,)).fetchone()
    g = lade_graph(anlage_id)

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
                    }
                    for f in klasse.PARAMETER
                ],
                "ports": [
                    {
                        "id": p.id, "schluessel": p.schluessel, "art": p.art,
                        "richtung": p.richtung, "rolle": p.rolle,
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
        "name": anlage["name"] if anlage else "",
        "karten": karten,
        "pfeile": pfeile,
    }


def projekte():
    """Alle Projekte mit der Zahl ihrer Anlagen."""
    db = get_db()
    return [
        {"id": z["id"], "name": z["name"], "beschreibung": z["beschreibung"],
         "anlagen": z["anlagen"], "geaendert_am": z["geaendert_am"]}
        for z in db.execute(
            "SELECT p.*, (SELECT COUNT(*) FROM anlage a WHERE a.projekt_id = p.id) "
            "       AS anlagen "
            "FROM projekt p ORDER BY p.geaendert_am DESC, p.id DESC"
        )
    ]


def anlagen_von(projekt_id=None):
    """Alle Anlagen, wahlweise auf ein Projekt eingegrenzt."""
    db = get_db()
    abfrage = (
        "SELECT a.*, p.name AS projekt_name, "
        "       (SELECT COUNT(*) FROM karte k WHERE k.anlage_id = a.id) AS karten "
        "FROM anlage a JOIN projekt p ON p.id = a.projekt_id"
    )
    werte = []
    if projekt_id is not None:
        abfrage += " WHERE a.projekt_id = ?"
        werte.append(projekt_id)
    abfrage += " ORDER BY a.id"
    return [
        {"id": z["id"], "projekt_id": z["projekt_id"], "projekt_name": z["projekt_name"],
         "name": z["name"], "notiz": z["notiz"], "karten": z["karten"]}
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
