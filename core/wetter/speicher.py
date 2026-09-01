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


def datensaetze():
    db = get_db()
    return [
        {
            "id": z["id"], "name": z["name"], "quelle": z["quelle"], "ort": z["ort"],
            "jahr": z["jahr"], "stunden": z["stunden"],
        }
        for z in db.execute(
            "SELECT w.*, (SELECT COUNT(*) FROM wetterstunde s "
            "             WHERE s.datensatz_id = w.id) AS stunden "
            "FROM wetterdatensatz w ORDER BY w.id DESC"
        )
    ]
