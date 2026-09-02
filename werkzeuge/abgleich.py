"""Rechnet die Vorlage mit den TRY-Daten der Excel und vergleicht die Ergebnisse.

Aufruf von Hand:  python3 werkzeuge/abgleich.py
Dann werden die Abweichungen je Bilanzgroesse und die erste stark abweichende
Stunde ausgegeben - das ist der Einstiegspunkt zur Fehlersuche.

Befund vor der Umsetzung dieses Werkzeugs: Der aufgezeichnete Excel-Lauf ist keine
fertig gerechnete Loesung. Beweis: Anlage!C38 ist als =AH46 definiert; in der
gespeicherten Mappe steht in C38 der Wert 5.331254463695608, in AH46 dagegen
2.885138971629036. Eine Zelle, die nichts weiter tut als eine andere zu spiegeln,
traegt eine andere Zahl - Excel rechnet die Mappe wegen der Zirkelbezuege iterativ
und bricht an seiner Iterationsgrenze ab, einzelne Zellen hinken dabei um eine oder
mehrere Iterationen nach. Ursache ist der Befeuchtungskreis: Der Zweipunktregler
regelt auf die Raumfeuchte, die sein eigener Luftwaescher um mehrere g/kg anhebt -
bei einer Schaltdifferenz von nur 0,1 g/kg. Dieser Kreis schwingt in beiden
Werkzeugen. Waerme und Wasser haengen daran (der Erhitzer waermt nach, was der
Waescher adiabat abkuehlt) und sind deshalb keine reproduzierbaren Zielwerte - sie
werden hier nur gemessen und festgehalten, nicht gegen die Excel geprueft. Strom und
Kaelte pendeln sich dagegen schnell ein und werden mit 2 % Toleranz geprueft.
"""

import csv
import json
from datetime import datetime, timedelta
import pathlib
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DATEN = WURZEL / "tests" / "daten"

# Zuordnung Bilanzschluessel -> Schluessel in jahresbilanz.json.
# Strom steht als Summe, weil die Excel den gesamten Verbrauch im Niedertarif
# bucht: die Zelle AP4, die das Tariffenster oeffnet, ist nie gefuellt worden,
# und WEEKDAY(0) faellt auf einen Samstag. Der Nachbau trennt die Tarife richtig,
# nur die Summe ist deshalb vergleichbar.
ZUORDNUNG = {
    "strom": ("strom_ht_mwh", "strom_nt_mwh"),
    "waerme": ("waerme_mwh",),
    "kaelte": ("kaelte_mwh",),
    "wasser": ("wasser_m3",),
}


def lade_wetterstunden():
    stunden = []
    start = datetime(2000, 1, 1, 0)
    with open(DATEN / "wetterdaten_try04.csv", encoding="utf-8") as datei:
        for nummer, zeile in enumerate(csv.DictReader(datei)):
            stunden.append(
                {
                    "zeitpunkt": start + timedelta(hours=nummer),
                    "t_au": float(zeile["t_au"]),
                    "x_au": float(zeile["x_au"]),
                    "str_s": float(zeile["str_s"]),
                    "str_o": float(zeile["str_o"]),
                    "str_w": float(zeile["str_w"]),
                    "str_n": float(zeile["str_n"]),
                    "str_h": float(zeile["str_h"]),
                }
            )
    return stunden


def lade_excel_stunden():
    with open(DATEN / "ergebnis_jahreslauf.csv", encoding="utf-8") as datei:
        return list(csv.DictReader(datei))


def rechne_referenzjahr(app, ohne_befeuchtungsregelung=False):
    """Rechnet die Vorlage ueber das Referenzjahr.

    Mit ``ohne_befeuchtungsregelung`` werden die beiden Zweipunktregler der
    Luftwaescher stillgelegt: ihre Sollwertleitung wird getrennt und Soll- wie
    Istwert auf null gesetzt, sodass der Ausgang auf null stehen bleibt und die
    Waescher aus sind. Das bricht den einzigen bekannten Schwingkreis auf und
    zeigt, ob der uebrige Anlagenverbund ruhig laeuft.
    """
    from core import anlagen, graph as graph_modul, solver
    from core.vorlagen import ax_sim_2_1

    with app.app_context():
        projekt = anlagen.projekt_anlegen("Abgleich")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        graph = anlagen.lade_graph(anlage)
        if ohne_befeuchtungsregelung:
            graph = _ohne_befeuchtungsregelung(graph, graph_modul)
        lauf = solver.Solver(graph).starte(lade_wetterstunden())

    bilanz = {
        # Die Excel bucht alles im Niedertarif (siehe ZUORDNUNG), darum die Summe.
        "strom": (lauf.bilanz["strom_ht"] + lauf.bilanz["strom_nt"]) / 1000.0,
        "waerme": lauf.bilanz["waerme"] / 1000.0,
        "kaelte": lauf.bilanz["kaelte"] / 1000.0,
        "wasser": lauf.bilanz["wasser"] / 1000.0,
    }
    return {"bilanz": bilanz, "stunden": lauf.stunden, "warnungen": lauf.warnungen}


def _ohne_befeuchtungsregelung(graph, graph_modul):
    """Legt die Zweipunktregler der Luftwaescher stumm und baut den Graph neu.

    Der Graph merkt sich seine Reihenfolge, sobald sie einmal berechnet wurde;
    deshalb wird ein neuer gebaut statt der vorhandene veraendert.

    In der Vorlage traegt der "sollwert"-Port des Reglers die live gemessene
    Raumfeuchte (Anlage!AB55/AB66), waehrend "istwert" ein fester Schwellwert-
    Parameter ist (Anlage!AB56/AB67) - keine Verbindung. Getrennt wird deshalb
    die Verbindung auf "sollwert"; beide Parameter werden zusaetzlich auf null
    gesetzt, damit istwert > sollwert + hysterese/2 nie zutrifft und der Ausgang
    bei seinem Anfangswert null stehen bleibt.
    """
    regler = {
        kennung for kennung, karte in graph.karten.items()
        if karte.typ == "hysterese_regler"
    }
    verbindungen = [
        v for v in graph.verbindungen
        if not (
            v.nach_port.karte_id in regler and v.nach_port.schluessel == "sollwert"
        )
    ]
    for kennung in regler:
        graph.karten[kennung].parameter["sollwert"] = 0.0
        graph.karten[kennung].parameter["istwert"] = 0.0
    return graph_modul.Anlagengraph(graph.karten, verbindungen)


def vergleiche(eigene, excel):
    ergebnis = []
    for schluessel, excel_schluessel in ZUORDNUNG.items():
        meins = eigene.get(schluessel, 0.0)
        seins = sum(float(excel.get(name, 0.0)) for name in excel_schluessel)
        nenner = abs(seins) if abs(seins) > 1e-9 else 1.0
        ergebnis.append(
            {
                "groesse": schluessel,
                "eigene": meins,
                "excel": seins,
                "differenz": meins - seins,
                "relativ": abs(meins - seins) / nenner,
            }
        )
    return ergebnis


def als_text(abweichungen):
    zeilen = [f"{'Groesse':12} {'eigene':>14} {'Excel':>14} {'Abw. %':>9}"]
    for a in abweichungen:
        zeilen.append(
            f"{a['groesse']:12} {a['eigene']:14.4f} {a['excel']:14.4f} "
            f"{a['relativ'] * 100:8.2f}%"
        )
    return "\n".join(zeilen)


def erste_abweichende_stunde(eigene_stunden, excel_stunden, spalte="waerme", grenze=0.5):
    """Findet die erste Stunde, in der eine Groesse deutlich abweicht."""
    for nummer, (meine, seine) in enumerate(zip(eigene_stunden, excel_stunden)):
        summe = 0.0
        for werte in meine.values():
            if spalte in werte:
                summe += float(werte[spalte])
        seins = float(seine.get(spalte, 0.0))
        if abs(summe - seins) > grenze:
            return {
                "stunde": nummer,
                "zeitpunkt": seine.get("datum"),
                "eigene": summe,
                "excel": seins,
            }
    return None


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(WURZEL))

    # In eine Wegwerfdatenbank rechnen. Sonst legt jeder Aufruf von Hand ein
    # Projekt "Abgleich" samt Anlage in der Datenbank des laufenden Dienstes an -
    # der Benutzer findet dort Reste, die er nie erzeugt hat.
    import tempfile

    import core.config as config

    config.DB_PATH = pathlib.Path(tempfile.mkdtemp()) / "abgleich.db"

    from app import create_app
    from core import database

    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()

    excel = json.loads((DATEN / "jahresbilanz.json").read_text(encoding="utf-8"))
    eigene = rechne_referenzjahr(anwendung)

    print(als_text(vergleiche(eigene["bilanz"], excel)))
    print(f"\nKonvergenzwarnungen: {len(eigene['warnungen'])}")
    for warnung in eigene["warnungen"][:5]:
        print("  ", warnung["text"])

    treffer = erste_abweichende_stunde(eigene["stunden"], lade_excel_stunden())
    if treffer:
        print("\nErste deutlich abweichende Stunde:", treffer)
