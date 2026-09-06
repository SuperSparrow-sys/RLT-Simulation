"""Die Grenzen der Fixpunkt-Iteration stammen aus der Referenzmappe.

MAX_ITERATIONEN und MAX_AENDERUNG sind keine gegriffenen Zahlen, sondern die
Rechenoptionen, die in RLTSimulation_Vorlage_AX_SIM_2.1.xls gespeichert sind.
Das ist keine Formalie: Weil P- und Hysterese-Regler ueber die Durchgaenge
integrieren (ZUSTAND_UEBER_ITERATION), ist die Zahl der Durchgaenge Teil des
Modells und nicht bloss eine Abbruchbedingung. Wer sie anhebt, rechnet eine
andere Anlage als die Mappe - gemessen aendert sich die Jahresarbeit von
AX_SIM 2.1 dadurch spuerbar. Dieser Test haelt beide Zahlen an ihrer Quelle
fest, damit sie nicht "zur Beschleunigung" oder "fuer bessere Konvergenz"
verstellt werden, ohne dass der Abgleich mit der Mappe neu bewertet wird.

Gelesen wird die .xls unmittelbar. Eine BIFF8-Mappe legt die Rechenoptionen als
zusammenhaengenden Block gleichartig aufgebauter Datensaetze ab - je zwei Byte
Kennzahl, zwei Byte Laenge, dann die Nutzdaten:

    0x000D CALCMODE   16 bit   automatisch / manuell
    0x000C CALCCOUNT  16 bit   Extras > Formeln > Maximale Iterationszahl
    0x000F REFMODE    16 bit   A1- oder Z1S1-Bezuege
    0x0011 ITERATION  16 bit   iterative Berechnung an/aus
    0x0010 DELTA      64 bit   Maximale Aenderung

Gesucht wird der ganze Block, nicht ein einzelner Datensatz: Fuenf lueckenlos
aneinander anschliessende, wohlgeformte Datensaetze in genau dieser Reihenfolge
sind kein Bytemuster, das zufaellig in einem Zellinhalt steht. Ein OLE-Leser
waere hier keine Hilfe - der Workbook-Strom liegt ueber die Sektoren der Datei
verstreut, weshalb ein Durchlaufen der Datensatzkette von vorn nicht ans Ziel
fuehrt; der Block selbst steht aber am Stueck.
"""

import struct
from pathlib import Path

import pytest

from core import config

MAPPE = (
    Path(__file__).resolve().parent.parent
    / "referenz" / "RLTSimulation_Vorlage_AX_SIM_2.1.xls"
)

# Kennzahl und Nutzdatenlaenge, in der Reihenfolge, in der Excel sie schreibt.
RECHENBLOCK = (
    ("calcmode", 0x000D, 2),
    ("calccount", 0x000C, 2),
    ("refmode", 0x000F, 2),
    ("iteration", 0x0011, 2),
    ("delta", 0x0010, 8),
)


def _bloecke(rohdaten):
    """Alle Rechenoptionen-Bloecke der Mappe, entschluesselt.

    Excel schreibt den Block in jeden Blattstrom; die Werte muessen deshalb
    mehrfach vorkommen und uebereinstimmen. Kaeme nur ein einziger Treffer
    zustande, waere das ein Grund, dem Fund zu misstrauen.
    """
    kopf = struct.pack("<HH", *RECHENBLOCK[0][1:])
    gefunden = []
    stelle = rohdaten.find(kopf)
    while stelle >= 0:
        werte, p, heil = {}, stelle, True
        for name, kennzahl, laenge in RECHENBLOCK:
            if struct.unpack("<HH", rohdaten[p:p + 4]) != (kennzahl, laenge):
                heil = False
                break
            nutzdaten = rohdaten[p + 4:p + 4 + laenge]
            werte[name] = struct.unpack("<d" if laenge == 8 else "<H", nutzdaten)[0]
            p += 4 + laenge
        if heil:
            gefunden.append(werte)
        stelle = rohdaten.find(kopf, stelle + 1)
    return gefunden


@pytest.fixture(scope="module")
def rechenoptionen():
    if not MAPPE.exists():
        pytest.skip(f"Referenzmappe fehlt: {MAPPE}")
    bloecke = _bloecke(MAPPE.read_bytes())
    assert bloecke, "kein Rechenoptionen-Block in der Mappe gefunden"
    erster = bloecke[0]
    for weiterer in bloecke[1:]:
        assert weiterer == erster, (
            "Die Blattstroeme der Mappe nennen verschiedene Rechenoptionen - "
            f"{erster} gegen {weiterer}"
        )
    return erster


def test_die_mappe_rechnet_ueberhaupt_iterativ(rechenoptionen):
    """Ohne eingeschaltete Iteration waeren die beiden Grenzen bedeutungslos.

    In referenz/vba-module.txt steht ein aufgezeichnetes Makro, das
    Application.Iteration auf False setzt. Massgeblich ist, was die Mappe
    gespeichert hat - und das ist eingeschaltete Iteration.
    """
    assert rechenoptionen["iteration"] == 1


def test_max_iterationen_ist_die_iterationszahl_der_mappe(rechenoptionen):
    assert rechenoptionen["calccount"] == config.MAX_ITERATIONEN, (
        f"Die Mappe rechnet mit {rechenoptionen['calccount']} Durchgaengen, die "
        f"Simulation mit {config.MAX_ITERATIONEN}. Weil die Regler ueber die "
        "Durchgaenge integrieren, rechnen beide dann nicht mehr dieselbe Anlage."
    )


def test_max_aenderung_ist_die_maximale_aenderung_der_mappe(rechenoptionen):
    assert rechenoptionen["delta"] == pytest.approx(config.MAX_AENDERUNG, rel=1e-12)
