"""Zieht Wetterdaten, Stundenprotokoll und Jahresbilanz aus der Excel-Mappe.

Aufruf:  python3 werkzeuge/referenz_export.py
Ergebnis: drei Dateien unter tests/daten/
"""

import csv
import json
from pathlib import Path

import xlrd

WURZEL = Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "referenz" / "RLTSimulation_Vorlage_AX_SIM_2.1.xls"
ZIEL = WURZEL / "tests" / "daten"


def exportiere():
    ZIEL.mkdir(parents=True, exist_ok=True)
    mappe = xlrd.open_workbook(str(QUELLE))

    wetter = mappe.sheet_by_name("Wetterdaten")
    with open(ZIEL / "wetterdaten_try04.csv", "w", newline="", encoding="utf-8") as f:
        schreiber = csv.writer(f)
        schreiber.writerow(
            ["datum", "t_au", "x_au", "str_s", "str_o", "str_w", "str_n", "str_h"]
        )
        for zeile in range(4, wetter.nrows):
            schreiber.writerow(wetter.row_values(zeile)[:8])

    ergebnis = mappe.sheet_by_name("Ergebnis")
    with open(ZIEL / "ergebnis_jahreslauf.csv", "w", newline="", encoding="utf-8") as f:
        schreiber = csv.writer(f)
        schreiber.writerow(
            [
                "datum", "t_au", "x_au", "strom_ht", "strom_nt",
                "waerme", "kaelte", "wasser", "wrg", "t_raum", "f_raum",
            ]
        )
        for zeile in range(19, ergebnis.nrows):
            werte = ergebnis.row_values(zeile)[:11]
            if werte[0] in ("", None):
                continue
            schreiber.writerow(werte)

    bilanz = {
        "strom_ht_mwh": ergebnis.cell_value(4, 1),
        "strom_nt_mwh": ergebnis.cell_value(5, 1),
        "waerme_mwh": ergebnis.cell_value(11, 1),
        "kaelte_mwh": ergebnis.cell_value(12, 1),
        "wasser_m3": ergebnis.cell_value(13, 1),
        "wrg_mwh": ergebnis.cell_value(15, 8),
        "kosten_gesamt_eur": ergebnis.cell_value(14, 5),
    }
    (ZIEL / "jahresbilanz.json").write_text(
        json.dumps(bilanz, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("geschrieben:", sorted(p.name for p in ZIEL.glob("*")))


if __name__ == "__main__":
    exportiere()
