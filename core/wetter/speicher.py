"""Wetterdatensaetze in der Datenbank."""

from datetime import datetime

from core.database import get_db

SPALTEN = ("t_au", "x_au", "str_s", "str_o", "str_w", "str_n", "str_h")


def datensatz_anlegen(name, quelle, stunden, ort="", breite=None, laenge=None,
                      jahr=None, notiz=""):
    db = get_db()
    if jahr is None and stunden:
        jahr = stunden[0]["zeitpunkt"].year

    cur = db.execute(
        "INSERT INTO wetterdatensatz (name, quelle, ort, breite, laenge, jahr, notiz) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, quelle, ort, breite, laenge, jahr, notiz),
    )
    datensatz_id = cur.lastrowid

    db.executemany(
        "INSERT INTO wetterstunde "
        "(datensatz_id, stunde, zeitpunkt, t_au, x_au, str_s, str_o, str_w, str_n, str_h) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (datensatz_id, nummer, s["zeitpunkt"].isoformat())
            + tuple(float(s.get(name, 0.0)) for name in SPALTEN)
            for nummer, s in enumerate(stunden)
        ],
    )
    db.commit()
    return datensatz_id


def lade_stunden(datensatz_id, von=None, bis=None):
    db = get_db()
    abfrage = "SELECT * FROM wetterstunde WHERE datensatz_id = ?"
    werte = [datensatz_id]
    if von is not None:
        abfrage += " AND stunde >= ?"
        werte.append(von)
    if bis is not None:
        abfrage += " AND stunde < ?"
        werte.append(bis)
    abfrage += " ORDER BY stunde"

    ergebnis = []
    for zeile in db.execute(abfrage, werte):
        eintrag = {"zeitpunkt": datetime.fromisoformat(zeile["zeitpunkt"])}
        for name in SPALTEN:
            eintrag[name] = zeile[name]
        ergebnis.append(eintrag)
    return ergebnis


def datensatz(datensatz_id):
    """Kopfdaten eines einzelnen Wetterdatensatzes (Name, Ort, Jahr, Quelle) -
    fuer den Kopf des Berichts (core.bericht), der nicht die ganze
    Uebersichtsliste datensaetze() braucht."""
    db = get_db()
    zeile = db.execute(
        "SELECT * FROM wetterdatensatz WHERE id = ?", (datensatz_id,)
    ).fetchone()
    return dict(zeile) if zeile else None


def datensaetze():
    """Alle Wetterdatensaetze - mit Stundenzahl und der Zahl der
    Simulationslaeufe, die auf sie verweisen (letzteres, damit die
    Oberflaeche vor dem Loeschen weiss, ob und warum das verweigert wird,
    statt es erst zu versuchen - siehe datensatz_loeschen())."""
    db = get_db()
    return [
        {
            "id": z["id"], "name": z["name"], "quelle": z["quelle"], "ort": z["ort"],
            "jahr": z["jahr"], "stunden": z["stunden"], "simulationen": z["simulationen"],
        }
        for z in db.execute(
            "SELECT w.*, "
            "       (SELECT COUNT(*) FROM wetterstunde s "
            "        WHERE s.datensatz_id = w.id) AS stunden, "
            "       (SELECT COUNT(*) FROM simulation sim "
            "        WHERE sim.wetterdatensatz_id = w.id) AS simulationen "
            "FROM wetterdatensatz w ORDER BY w.id DESC"
        )
    ]


def datensatz_umbenennen(datensatz_id, name):
    db = get_db()
    cur = db.execute(
        "UPDATE wetterdatensatz SET name = ? WHERE id = ?", (name, datensatz_id)
    )
    db.commit()
    if cur.rowcount == 0:
        raise KeyError(f"Wetterdatensatz {datensatz_id} gibt es nicht")


def datensatz_loeschen(datensatz_id):
    """Loescht einen Wetterdatensatz mitsamt seinen Wetterstunden (ON DELETE
    CASCADE, siehe core/database.py) - aber nur, wenn kein Simulationslauf
    mehr auf ihn verweist. Ein gespeicherter Lauf ohne seinen Wetterdatensatz
    waere nicht mehr nachvollziehbar (welches Wetter fuehrte zu dieser
    Bilanz?); die Spalte simulation.wetterdatensatz_id hat deshalb bewusst
    kein ON DELETE CASCADE und keine Kaskade auf 'setze NULL' - dieselbe
    Fremdschluesselpruefung wuerde den DELETE sonst mit einem rohen
    'FOREIGN KEY constraint failed' verweigern; diese Pruefung hier meldet
    stattdessen, wie viele Laeufe betroffen sind."""
    db = get_db()
    verwendung = db.execute(
        "SELECT COUNT(*) AS n FROM simulation WHERE wetterdatensatz_id = ?",
        (datensatz_id,),
    ).fetchone()["n"]
    if verwendung:
        einheit = "Simulationslauf" if verwendung == 1 else "Simulationsläufen"
        raise ValueError(
            f"Der Wetterdatensatz wird von {verwendung} {einheit} verwendet und "
            "kann nicht gelöscht werden."
        )
    db.execute("DELETE FROM wetterdatensatz WHERE id = ?", (datensatz_id,))
    db.commit()
