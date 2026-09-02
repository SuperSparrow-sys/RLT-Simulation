import csv
import json
from pathlib import Path

DATEN = Path(__file__).parent / "daten"


def test_wetterdaten_haben_8760_stunden():
    with open(DATEN / "wetterdaten_try04.csv", encoding="utf-8") as f:
        zeilen = list(csv.DictReader(f))
    assert len(zeilen) == 8760
    assert float(zeilen[0]["t_au"]) == 2.5
    assert float(zeilen[0]["x_au"]) == 4.4


def test_jahreslauf_hat_8760_stunden():
    with open(DATEN / "ergebnis_jahreslauf.csv", encoding="utf-8") as f:
        zeilen = list(csv.DictReader(f))
    assert len(zeilen) == 8760
    assert float(zeilen[0]["t_raum"]) == 15.0


def test_jahresbilanz_entspricht_der_excel():
    bilanz = json.loads((DATEN / "jahresbilanz.json").read_text(encoding="utf-8"))
    assert bilanz["strom_nt_mwh"] == 85.04562246648032
    assert bilanz["waerme_mwh"] == 328.9201998669775
    assert bilanz["kaelte_mwh"] == 45.4806315625887
    assert bilanz["wasser_m3"] == 111.63868300163553
