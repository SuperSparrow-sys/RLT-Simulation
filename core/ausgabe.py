"""Ausgabe der Stundenwerte eines Simulationslaufs als CSV und als
Excel-Mappe (Vorhaben C, docs/superpowers/plans/2026-09-02-rlt-simulation-stufe-2.md).

Der Benutzer will die 8760 Stundenwerte eines Laufs in Excel weiterverarbeiten.
Eine Zeile je Stunde, mit Zeitpunkt, Außentemperatur, Außenfeuchte, den
Bilanzgrößen und allen am Datenlogger benannten Spalten - denselben, die das
Stundenprotokoll im Simulationsdialog zeigt (core.ergebnisse.lade_protokoll).

Kein SQL hier: core.anlagen fuer die Anlage, core.ergebnisse fuer den Lauf und
seine Zeitreihen, core.wetter.speicher fuer den Wetterdatensatz - wie
core/bericht.py fragt dieses Modul nur diese drei, nie die Tabellen selbst.

Zwei Bausteine trennen sich sauber: daten_fuer() baut die Spalten (eine Liste
von Werten je Stunde), csv_bytes()/xlsx_bytes() serialisieren sie in ihr
jeweiliges Format. routes/simulation.py ruft nur noch diese drei Funktionen.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from core import anlagen, ergebnisse
from core.wetter import speicher

# Wie core.bericht.STATUS_MIT_ERGEBNIS: ein Lauf hat erst dann eine
# gespeicherte Zeitreihe, wenn core.ergebnisse.abschliesse() oder .speichere()
# gelaufen ist - das passiert fuer 'fertig' und (mit den bis zum Abbruch
# gerechneten Stunden) fuer 'abgebrochen', nie fuer 'laeuft' oder 'fehler'.
# Absichtlich hier noch einmal definiert statt aus core.bericht importiert -
# die beiden Module sollen unabhaengig voneinander aenderbar bleiben.
STATUS_MIT_ERGEBNIS = ("fertig", "abgebrochen")

# Die fuenf Bilanzgroessen als Stundenwerte: (Schluessel in der Zeitreihe der
# Bilanzkarte, Beschriftung, Einheit). Anders als core.ergebnisse.BILANZ (das
# die ueber alle Stunden aufsummierte Menge in MWh/m3 fuehrt) sind das hier
# die rohen Stundenwerte, wie core.bausteine.bilanz.Bilanz.berechne() sie je
# Stunde ausgibt: kWh fuer Strom/Waerme/Kaelte, Liter fuer Wasser (dieselbe
# Grundeinheit, aus der core.ergebnisse.BILANZ mit dem Faktor 1/1000 die
# Jahressumme in MWh bzw. m3 bildet).
BILANZ_SPALTEN = [
    ("strom_ht", "Strom Hochtarif", "kWh"),
    ("strom_nt", "Strom Niedertarif", "kWh"),
    ("waerme", "Wärme", "kWh"),
    ("kaelte", "Kälte", "kWh"),
    ("wasser", "Wasser", "L"),
]

# Nachkommastellen fuer alle Zahlenspalten - großzügig genug für die
# 32-Bit-Genauigkeit, mit der core.ergebnisse Zeitreihen ablegt (array.array
# 'f', rund 7 gültige Stellen), und dieselbe Stellenzahl wie die Jahresbilanz
# im Dialog (static/js/simulation.js, zeigeBilanz(): z.menge.toFixed(3)).
NACHKOMMASTELLEN = 3


class AusgabeNichtVerfuegbar(ValueError):
    """Der Lauf ist noch nicht abgeschlossen oder hat keine gespeicherte
    Zeitreihe - die Ausgabe braucht ein Ergebnis (siehe STATUS_MIT_ERGEBNIS)."""


def _bilanz_karte_id(graph):
    """Die erste Bilanzkarte der Anlage, wie core.ergebnisse._preise() -
    eine Anlage ohne Bilanzkarte (z.B. noch im Aufbau) bekommt einfach keine
    Bilanzspalten, statt die Ausgabe mit einem Fehler abzubrechen."""
    for karte in graph.karten.values():
        if karte.typ == "bilanz":
            return karte.id
    return None


def _kopfzelle(spalte):
    """'Name [Einheit]', dieselbe Schreibweise wie das Stundenprotokoll im
    Dialog (static/js/simulation.js, _zeigeProtokoll()) - wer beide kennt,
    soll dieselbe Spalte wiedererkennen."""
    if spalte["einheit"]:
        return f"{spalte['name']} [{spalte['einheit']}]"
    return spalte["name"]


def daten_fuer(simulation_id):
    """Kopf (Anlage, Wetterdatensatz, Lauf) und Spalten eines Simulationslaufs
    fuer die Stundenwerte-Ausgabe.

    Jede Spalte ist {'name', 'einheit', 'werte'} mit einem Wert je gerechneter
    Stunde (sim['gerechnete_stunden']) - Zeitpunkt, Außentemperatur,
    Außenfeuchte, die Bilanzgrößen (falls die Anlage eine Bilanzkarte hat) und
    alle am Datenlogger benannten Spalten (core.ergebnisse.lade_protokoll).

    Wirft KeyError fuer eine unbekannte simulation_id (aus
    core.ergebnisse.lade_simulation), AusgabeNichtVerfuegbar fuer einen Lauf
    ohne gespeicherte Zeitreihe.
    """
    sim = ergebnisse.lade_simulation(simulation_id)
    if sim["status"] not in STATUS_MIT_ERGEBNIS:
        raise AusgabeNichtVerfuegbar(
            f"Lauf {simulation_id} ist noch nicht abgeschlossen (Status "
            f"'{sim['status']}') – die Ausgabe braucht ein Ergebnis."
        )

    anlage = anlagen.anlage_kopf(sim["anlage_id"])
    wetter = speicher.datensatz(sim["wetterdatensatz_id"])
    graph = anlagen.lade_graph(sim["anlage_id"])

    # Massgeblich ist die tatsaechlich gerechnete Stundenzahl (kann bei einem
    # abgebrochenen Lauf kleiner sein als von_stunde..bis_stunde) - dieselbe
    # Ueberlegung wie core.ergebnisse.abschliesse(), das fortschritt=
    # len(lauf.stunden) schreibt. Die Wetterstunden werden fuer den vollen
    # angeforderten Zeitraum geladen und dann auf diese Laenge gekappt; sie
    # stehen in derselben Reihenfolge, in der der Solver sie verarbeitet hat.
    anzahl = sim["gerechnete_stunden"]
    wetterstunden = speicher.lade_stunden(
        sim["wetterdatensatz_id"], sim["von_stunde"], sim["bis_stunde"]
    )[:anzahl]

    spalten = [
        {
            "name": "Zeitpunkt", "einheit": "",
            "werte": [s["zeitpunkt"] for s in wetterstunden],
        },
        {
            "name": "Außentemperatur", "einheit": "°C",
            "werte": [s["t_au"] for s in wetterstunden],
        },
        {
            "name": "Außenfeuchte", "einheit": "g/kg",
            "werte": [s["x_au"] for s in wetterstunden],
        },
    ]

    bilanz_karte_id = _bilanz_karte_id(graph)
    if bilanz_karte_id is not None:
        for schluessel, name, einheit in BILANZ_SPALTEN:
            werte = ergebnisse.lade_zeitreihe(simulation_id, bilanz_karte_id, schluessel)
            if werte:
                spalten.append({"name": name, "einheit": einheit, "werte": werte[:anzahl]})

    for eintrag in ergebnisse.lade_protokoll(simulation_id, graph):
        spalten.append(
            {
                "name": eintrag["name"], "einheit": eintrag["einheit"],
                "werte": eintrag["werte"][:anzahl],
            }
        )

    return {"simulation_id": simulation_id, "anlage": anlage, "wetter": wetter,
            "sim": sim, "spalten": spalten}


def dateiname(daten, endung):
    """Ein Dateiname, der erkennen laesst, woher die Datei stammt: Anlage,
    Wetterjahr, Datum des Laufs - z.B. 'stundenwerte-Buero-Nord-2023-20260902.csv'.
    Bereinigt wie routes/bericht.py seinen PDF-Dateinamen (dieselbe Regel:
    nur alphanumerische Zeichen, Bindestrich, Unterstrich, Punkt), damit ein
    frei vergebener Anlagenname die Content-Disposition-Kopfzeile nicht
    verletzt."""
    anlage_name = daten["anlage"]["name"]
    wetterjahr = daten["wetter"].get("jahr") or "unbekannt"
    lauf_datum = str(daten["sim"]["gestartet_am"])[:10].replace("-", "")
    roh = f"stundenwerte-{anlage_name}-{wetterjahr}-{lauf_datum}.{endung}"
    bereinigt = "".join(z for z in roh if z.isalnum() or z in "-_.")
    return bereinigt or f"stundenwerte.{endung}"


def _csv_wert(spalte, index):
    wert = spalte["werte"][index]
    if isinstance(wert, datetime):
        return wert.strftime("%d.%m.%Y %H:%M")
    # Deutsches Dezimalzeichen (Komma) statt des von Python/csv erzeugten
    # Punkts - siehe csv_bytes() fuer die Begruendung des ganzen Formats.
    return f"{wert:.{NACHKOMMASTELLEN}f}".replace(".", ",")


def csv_bytes(daten):
    """Die Stundenwerte als CSV, so dass eine deutsche Excel-Einstellung sie
    ohne Importdialog richtig oeffnet:

    - Semikolon als Feldtrennzeichen und Komma als Dezimalzeichen - die
      deutsche Excel-Standardeinstellung, weil dort das Komma schon als
      Listentrennzeichen der Landeseinstellung gilt (umgekehrt zur
      amerikanischen Vorgabe mit Punkt/Komma). Ein Komma als Dezimalzeichen UND
      als Feldtrennzeichen waere doppeldeutig; das Semikolon vermeidet das.
    - UTF-8 MIT Byte-Reihenfolge-Markierung (BOM, 'utf-8-sig'). Excel unter
      Windows oeffnet eine CSV-Datei per Doppelklick nicht ueber einen
      Importdialog, sondern rät die Kodierung selbst - und faellt ohne BOM auf
      die Systemkodierung (Windows-1252) zurueck. Die Umlaute und das ß in den
      Spaltennamen ('Außentemperatur', 'Wärme', 'Kälte', ...) und in frei
      vergebenen Anlagen-/Datenlogger-Namen wuerden dann als Kauderwelsch
      erscheinen. Die BOM behebt genau das; sie kostet nur drei Byte und
      schadet keinem anderen Programm, das UTF-8 sauber erkennt.
    - CRLF-Zeilenenden (csv.writer-Vorgabe), das von Windows-Excel erwartete
      Format.
    """
    spalten = daten["spalten"]
    anzahl = len(spalten[0]["werte"]) if spalten else 0
    puffer = io.StringIO(newline="")
    schreiber = csv.writer(puffer, delimiter=";")
    schreiber.writerow([_kopfzelle(s) for s in spalten])
    for zeile_nr in range(anzahl):
        schreiber.writerow([_csv_wert(s, zeile_nr) for s in spalten])
    return puffer.getvalue().encode("utf-8-sig")


def xlsx_bytes(daten):
    """Die Stundenwerte als .xlsx: Kopfzeile mit Einheit, Zahlen als echte
    Zahlen (kein Text - Excel soll direkt weiterrechnen koennen), sinnvolle
    Spaltenbreiten, erste Zeile fixiert.

    Im 'write_only'-Modus von openpyxl: bei 8760 Zeilen unkritisch fuer den
    normalen Modus (rund eine Sekunde, siehe ausgabe-report.md), aber
    write_only haelt die Zeilen nicht zusaetzlich als Objektbaum im Speicher,
    sondern schreibt sie sofort in die Zip-Struktur der Mappe - der
    naheliegende Modus fuer eine Tabelle, die nur einmal von vorne nach hinten
    geschrieben und nie wieder gelesen wird. Wichtig dabei: Spaltenbreiten und
    die Fixierung muessen VOR dem ersten append() gesetzt werden - im
    write_only-Modus schreibt openpyxl die Kopfdaten des Arbeitsblatts beim
    ersten append(), eine spaetere Zuweisung geht sonst stillschweigend
    verloren (geprueft beim Bau dieser Funktion).
    """
    spalten = daten["spalten"]
    anzahl = len(spalten[0]["werte"]) if spalten else 0

    arbeitsmappe = Workbook(write_only=True)
    blatt = arbeitsmappe.create_sheet("Stundenwerte")

    # Je Spalte einzeln bemessen, an ihrer eigenen Kopfzelle - eine 'Wärme
    # [kWh]'-Spalte braucht keine so breite Spalte wie 'Zeitpunkt' bekommen
    # wuerde, nur weil irgendeine andere Spalte einen langen Namen hat.
    for index, s in enumerate(spalten, start=1):
        breite = min(30, max(10, len(_kopfzelle(s)) + 2))
        blatt.column_dimensions[get_column_letter(index)].width = breite
    blatt.freeze_panes = "A2"

    fett = Font(bold=True)
    kopfzeile = []
    for s in spalten:
        zelle = WriteOnlyCell(blatt, value=_kopfzelle(s))
        zelle.font = fett
        kopfzeile.append(zelle)
    blatt.append(kopfzeile)

    zahlenformat = "0." + "0" * NACHKOMMASTELLEN
    for zeile_nr in range(anzahl):
        zeile = []
        for s in spalten:
            wert = s["werte"][zeile_nr]
            zelle = WriteOnlyCell(blatt, value=wert)
            zelle.number_format = (
                "DD.MM.YYYY HH:MM" if isinstance(wert, datetime) else zahlenformat
            )
            zeile.append(zelle)
        blatt.append(zeile)

    puffer = io.BytesIO()
    arbeitsmappe.save(puffer)
    return puffer.getvalue()
