"""Ergebnisse einer Simulation speichern und lesen.

Zeitreihen liegen als Block von 32-Bit-Gleitkommazahlen, eine je Stunde. Ein
Jahr belegt damit rund 35 KB je Groesse; ein Diagramm laedt seine Reihe in einem
einzigen Zugriff, und die Datenbank waechst nicht auf Millionen Zeilen.
"""

import array
import json

from core.bausteine.basis import Luft
from core.database import get_db

# Preisschluessel der Bilanzkarte und die Umrechnung der Stundensummen
BILANZ = {
    "strom_ht": ("MWh", "preis_strom_ht", 1 / 1000.0),
    "strom_nt": ("MWh", "preis_strom_nt", 1 / 1000.0),
    "waerme": ("MWh", "preis_waerme", 1 / 1000.0),
    "kaelte": ("MWh", "preis_kaelte", 1 / 1000.0),
    "wasser": ("m³", "preis_wasser", 1 / 1000.0),
}


def _als_blob(werte):
    return array.array("f", werte).tobytes()


def _aus_blob(rohdaten):
    feld = array.array("f")
    feld.frombytes(rohdaten)
    return list(feld)


def _preise(graph):
    """Die Preise der ersten Bilanzkarte dieser Anlage.

    Liest aus dem bereits geladenen Anlagengraph statt selbst die
    'karte'-Tabelle abzufragen - core/anlagen.py bleibt so die einzige Stelle,
    die das Schema der Karten kennt.
    """
    for karte in graph.karten.values():
        if karte.typ == "bilanz":
            return karte.parameter
    return {}


def speichere(anlage_id, wetterdatensatz_id, von, bis, lauf, graph, dauer, status="fertig"):
    db = get_db()
    cur = db.execute(
        "INSERT INTO simulation (anlage_id, wetterdatensatz_id, von_stunde, "
        "bis_stunde, status, dauer_s, warnungen) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (anlage_id, wetterdatensatz_id, von, bis, status, dauer,
         json.dumps(lauf.warnungen, ensure_ascii=False)),
    )
    simulation_id = cur.lastrowid

    # Alle vorkommenden Groessen einsammeln
    reihen = {}
    for nummer, stunde in enumerate(lauf.stunden):
        for karte_id, werte in stunde.items():
            for groesse, wert in werte.items():
                if isinstance(wert, Luft) or not isinstance(wert, (int, float)):
                    continue
                reihen.setdefault((karte_id, groesse), [0.0] * len(lauf.stunden))
                reihen[(karte_id, groesse)][nummer] = float(wert)

    def _name(karte_id):
        karte = graph.karten.get(karte_id)
        return karte.name if karte is not None else ""

    db.executemany(
        "INSERT INTO zeitreihe (simulation_id, karte_id, karte_name, groesse, werte) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (simulation_id, karte_id, _name(karte_id), groesse, _als_blob(werte))
            for (karte_id, groesse), werte in sorted(reihen.items())
        ],
    )

    preise = _preise(graph)
    zeilen = []
    for groesse, (einheit, preisschluessel, faktor) in BILANZ.items():
        menge = lauf.bilanz.get(groesse, 0.0) * faktor
        preis = float(preise.get(preisschluessel, 0.0))
        zeilen.append((simulation_id, groesse, menge, einheit, preis, menge * preis))
    db.executemany(
        "INSERT INTO bilanz (simulation_id, groesse, menge, einheit, preis, kosten) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        zeilen,
    )

    db.commit()
    return simulation_id


def lade_bilanz(simulation_id):
    db = get_db()
    return [
        dict(z)
        for z in db.execute(
            "SELECT groesse, menge, einheit, preis, kosten FROM bilanz "
            "WHERE simulation_id = ? ORDER BY id",
            (simulation_id,),
        )
    ]


def lade_zeitreihe(simulation_id, karte_id, groesse):
    db = get_db()
    zeile = db.execute(
        "SELECT werte FROM zeitreihe WHERE simulation_id = ? AND karte_id = ? "
        "AND groesse = ?",
        (simulation_id, karte_id, groesse),
    ).fetchone()
    return _aus_blob(zeile["werte"]) if zeile else []


def reihen(simulation_id):
    db = get_db()
    return [
        {"karte_id": z["karte_id"], "karte_name": z["karte_name"],
         "groesse": z["groesse"], "einheit": z["einheit"]}
        for z in db.execute(
            "SELECT karte_id, karte_name, groesse, einheit FROM zeitreihe "
            "WHERE simulation_id = ? ORDER BY karte_name, groesse",
            (simulation_id,),
        )
    ]
