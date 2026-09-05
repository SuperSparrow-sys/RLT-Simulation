"""Verteiler fuer hochgeladene Wetterdateien.

Waehlt anhand der Endung den zustaendigen Leser und liefert von jedem dieselbe
kanonische Form: eine Liste von Stunden-Dictionaries mit 'zeitpunkt' und den
Feldern aus core.wetter.speicher.SPALTEN. Die Aufrufer - routes/wetter.py und
die Tests - muessen dadurch kein Dateiformat kennen.

- .dat              -> core.wetter.try_dat   (DWD-Testreferenzjahr)
- .xls/.xlsx/.csv   -> core.wetter.tabelle   (Layout des Blattes 'Wetterdaten')
"""

from pathlib import Path

from core.wetter import tabelle, try_dat

#: Endungen, die eine hochgeladene Datei haben darf. Dieselbe Liste steht in
#: templates/index.html im accept-Attribut; hier ist sie die verbindliche.
ENDUNGEN = (".dat", ".xls", ".xlsx", ".xlsm", ".csv")

#: Archive werden bewusst nicht ausgepackt. Ein Hochladen-Endpunkt, der
#: fremde Archive entpackt, muss sich mit Pfadausbruch ("zip slip") und
#: Entpackbomben befassen - fuer einen Weg, den der Ordner-Upload ohnehin
#: ueberfluessig macht. Sie bekommen aber eine eigene Meldung, damit der
#: Nutzer erfaehrt, was zu tun ist, statt nur "wird nicht gelesen".
ARCHIVENDUNGEN = (".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".bz2")

_TRY_ENDUNG = ".dat"


def lese_datei(pfad, jahr=None):
    """Stundenwerte aus einer Wetterdatei, unabhaengig vom Format."""
    if Path(pfad).suffix.lower() == _TRY_ENDUNG:
        return try_dat.lese_datei(pfad, jahr)
    return tabelle.lese_datei(pfad, jahr)


def beschreibung(pfad):
    """Was sich ueber die Datei sagen laesst, ohne sie ganz zu lesen.

    Fuer ein TRY sind das Ort, Jahr und Kopfangaben; fuer eine Tabelle im
    'Wetterdaten'-Layout gibt es nichts dergleichen - dort bleiben die Felder
    leer, statt etwas zu erfinden.
    """
    if Path(pfad).suffix.lower() == _TRY_ENDUNG:
        return try_dat.beschreibung(pfad)
    return {"art": "", "jahr": None, "breite": None, "laenge": None, "notiz": ""}
