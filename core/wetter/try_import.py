"""Liest Wetterdaten im Format des Excel-Blattes 'Wetterdaten'.

Aufbau dort: Zeile 1 bis 4 Kopf, ab Zeile 5 je Stunde
Datum als Excel-Zahl, Temperatur in °C, absolute Feuchte in g/kg und
die Strahlung auf Sued, Ost, West, Nord und die Horizontale in W/m².
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path

SPALTEN = ("t_au", "x_au", "str_s", "str_o", "str_w", "str_n", "str_h")

# Excel zaehlt Tage ab dem 30.12.1899 (mit dem bekannten Schaltjahrfehler von 1900,
# der fuer Datumsangaben ab 1900 keine Rolle mehr spielt).
EXCEL_NULLPUNKT = datetime(1899, 12, 30)


def excel_datum(zahl, jahr=None):
    zeitpunkt = EXCEL_NULLPUNKT + timedelta(days=float(zahl))
    # Auf volle Stunden runden - die Excel speichert 0,0416666666 statt 1/24
    zeitpunkt += timedelta(seconds=30 * 60)
    zeitpunkt = zeitpunkt.replace(minute=0, second=0, microsecond=0)
    if jahr is not None:
        zeitpunkt = zeitpunkt.replace(year=jahr)
    return zeitpunkt


def _zeilen_aus_xls(pfad):
    import xlrd

    mappe = xlrd.open_workbook(str(pfad))
    blatt = (
        mappe.sheet_by_name("Wetterdaten")
        if "Wetterdaten" in mappe.sheet_names()
        else mappe.sheet_by_index(0)
    )
    for nummer in range(4, blatt.nrows):
        yield blatt.row_values(nummer)[:8]


def _zeilen_aus_xlsx(pfad):
    import openpyxl

    mappe = openpyxl.load_workbook(str(pfad), data_only=True)
    blatt = mappe["Wetterdaten"] if "Wetterdaten" in mappe.sheetnames else mappe.worksheets[0]
    for nummer, zeile in enumerate(blatt.iter_rows(values_only=True), start=1):
        if nummer <= 4:
            continue
        yield list(zeile)[:8]


def _zeilen_aus_csv(pfad):
    with open(pfad, encoding="utf-8-sig", newline="") as datei:
        leser = csv.reader(datei, delimiter=";" if _semikolon(pfad) else ",")
        for nummer, zeile in enumerate(leser, start=1):
            if nummer <= 4:
                continue
            yield zeile[:8]


def _semikolon(pfad):
    with open(pfad, encoding="utf-8-sig") as datei:
        kopf = datei.readline()
    return kopf.count(";") > kopf.count(",")


def lese_datei(pfad, jahr=None):
    pfad = Path(pfad)
    endung = pfad.suffix.lower()
    if endung == ".xls":
        zeilen = _zeilen_aus_xls(pfad)
    elif endung in (".xlsx", ".xlsm"):
        zeilen = _zeilen_aus_xlsx(pfad)
    elif endung == ".csv":
        zeilen = _zeilen_aus_csv(pfad)
    else:
        raise ValueError(f"Format '{endung}' wird nicht unterstuetzt")

    stunden = []
    for zeile in zeilen:
        if not zeile or zeile[0] in ("", None):
            continue
        try:
            zeitpunkt = excel_datum(zeile[0], jahr)
        except (TypeError, ValueError):
            continue
        werte = {"zeitpunkt": zeitpunkt}
        for index, name in enumerate(SPALTEN, start=1):
            wert = zeile[index] if index < len(zeile) else 0.0
            werte[name] = float(wert) if wert not in ("", None) else 0.0
        stunden.append(werte)
    return stunden
