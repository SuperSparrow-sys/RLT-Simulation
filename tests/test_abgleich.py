import json
from pathlib import Path

import pytest

from app import create_app
from core import database
from werkzeuge import abgleich

DATEN = Path(__file__).parent / "daten"
# Nur diese beiden Groessen werden gegen die Excel geprueft; zur Begruendung
# siehe den Befund am Anfang dieser Aufgabe.
TOLERANZ = {"strom": 0.02, "kaelte": 0.02}

# Kennwerte des eigenen Laufs, nicht der Excel. Gemessen am 2026-09-02 ueber das
# Referenzjahr (tests/daten/wetterdaten_try04.csv, 8760 Stunden), nachdem der
# Solver einen Grenzzyklus erkennt und das Mittel beider Zustaende ausweist,
# statt den zuletzt gerechneten Durchgang zu nehmen (core/solver.py). Vorher
# hing das Ergebnis daran, ob MAX_ITERATIONEN gerade oder ungerade ist - der
# taktende Befeuchtungskreis wurde jede Stunde ganz an oder ganz aus gerechnet.
#
# Der Stand davor lag bei 436,66 MWh und 702,06 m3; zum Vergleich der
# Excel-Lauf: Waerme 328,92 MWh, Wasser 111,64 m3. Die Waerme ist damit von
# 32,8 auf 8,5 Prozent Abweichung gefallen.
STAND_WAERME_MWH = 300.8150
STAND_WASSER_M3 = 421.2367


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "rlt.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


@pytest.fixture(scope="module")
def referenzjahr(tmp_path_factory, protokoll_pfad):
    """Rechnet AX_SIM 2.1 EINMAL ueber das Referenzjahr; beide Vergleiche
    teilen sich das Ergebnis.

    Der Lauf ist der teuerste des ganzen Testbestands - AX_SIM 2.1 erreicht in
    fast jeder Stunde die Iterationsgrenze (siehe core/config.py). Ihn zweimal
    zu rechnen, um zweimal dieselben Zahlen anzusehen, kostete rund acht
    Minuten fuer nichts. Der dritte Vergleich unten legt die
    Befeuchtungsregelung stillt und braucht deshalb einen eigenen Lauf.

    Der Protokollpfad kommt aus conftest.py (sitzungsweit) und wird hier
    ausdruecklich gesetzt: Eine modulweite Vorrichtung laeuft VOR den
    funktionsweiten, ruft create_app() also noch bevor _protokoll_umbiegen
    greift. app.create_app() entdoppelt seine Protokoll-Handler nach PFAD - ein
    eigener Pfad hinterliesse deshalb einen zusaetzlichen Handler am
    gemeinsamen Logger, und tests/test_app.py, das genau diese Handler zaehlt,
    fiele fehl. Auffaellig wird das nur im vollen Lauf, denn der schnelle
    Durchgang laesst diese Vorrichtungen aus.
    """
    import core.config

    pfad = tmp_path_factory.mktemp("abgleich") / "rlt.db"
    alt = core.config.DB_PATH
    core.config.DB_PATH = pfad
    core.config.LOG_FILE = protokoll_pfad
    try:
        anwendung = create_app()
        with anwendung.app_context():
            database.init_db()
        yield abgleich.rechne_referenzjahr(anwendung)
    finally:
        core.config.DB_PATH = alt


@pytest.mark.slow
def test_strom_und_kaelte_stimmen_mit_der_excel_ueberein(referenzjahr):
    """Die beiden Groessen, deren Regelkreise sich einpendeln.

    Waerme und Wasser haengen am schwingenden Befeuchtungskreis und werden
    getrennt behandelt; die Begruendung steht im Kopf dieser Aufgabe.
    """
    excel = json.loads((DATEN / "jahresbilanz.json").read_text(encoding="utf-8"))
    eigene = referenzjahr

    abweichungen = abgleich.vergleiche(eigene["bilanz"], excel)
    schlimmste = [
        a for a in abweichungen
        if a["groesse"] in TOLERANZ and a["relativ"] > TOLERANZ[a["groesse"]]
    ]
    assert not schlimmste, abgleich.als_text(abweichungen)


@pytest.mark.slow
def test_waerme_und_wasser_bleiben_auf_ihrem_gemessenen_stand(referenzjahr):
    """Kennwerttest, keine Validierung gegen die Excel.

    Beide Groessen haengen am Befeuchtungskreis, der in beiden Werkzeugen schwingt.
    Ihre Excel-Werte sind Momentaufnahmen einer abgebrochenen Iteration und taugen
    nicht als Ziel. Dieser Test haelt stattdessen den eigenen Stand fest, damit eine
    spaetere Aenderung an der Physik oder der Verdrahtung auffaellt.

    Vorgehen beim Umsetzen: den Jahreslauf einmal rechnen, die beiden Werte ablesen
    und hier als STAND_WAERME_MWH und STAND_WASSER_M3 eintragen, mit dem Datum der
    Messung im Kommentar. Toleranz 5 Prozent - genug fuer Rundungsunterschiede,
    eng genug, um eine echte Verschiebung zu zeigen.
    """
    eigene = referenzjahr
    for groesse, stand in (("waerme", STAND_WAERME_MWH), ("wasser", STAND_WASSER_M3)):
        ist = eigene["bilanz"][groesse]
        assert abs(ist - stand) / stand < 0.05, (
            f"{groesse}: {ist:.2f} statt {stand:.2f} - der Stand hat sich verschoben"
        )


# Ein Signal, das je Durchgang zwischen 0 und 100 Prozent kippt, hinterlaesst eine
# Restabweichung von 100. Alles unterhalb dieser Schwelle ist eine Rechnung, die sich
# einem Wert naehert, statt um ihn zu springen.
SCHWINGT_AB = 1.0


@pytest.mark.slow
def test_ohne_den_befeuchtungskreis_schwingt_nichts_mehr(app):
    """Grenzt die Schwingung auf den Befeuchtungskreis ein.

    Es sind zwei verschiedene Dinge, die man auseinanderhalten muss, und dieser Test
    tut genau das.

    Mit den Zweipunktreglern der Luftwaescher kippt deren Ausgang in jedem Durchgang
    zwischen 0 und 100: Der Waescher hebt die Raumfeuchte um mehrere g/kg, die
    Schaltdifferenz betraegt aber nur 0,1 g/kg, also schaltet er sofort wieder ab.
    Das ist ein Grenzzyklus - er loest sich durch keine Iterationszahl auf. Gemessen:
    bei 100 wie bei 2000 Durchgaengen bleibt die Restabweichung bei 100,0, und die
    Jahreszahlen verschieben sich nur um zwei Prozent, beim Wasser sogar weg von der
    Excel.

    Werden die beiden Regler stillgelegt, bleibt eine Rechnung uebrig, die sich einem
    Wert naehert - nur langsamer, als hundert Durchgaenge schaffen. Die Restabweichung
    liegt dann bei Bruchteilen (gemessen 0,0018 bis 0,44 gegen eine Schwelle von
    0,001), nicht bei 100. Genau darauf prueft dieser Test.

    Schlaegt er an, schwingt etwas ausserhalb der Befeuchtung - und das waere ein
    echter Befund. Auf "gar keine Warnung" laesst er sich nicht stellen, denn der
    langsam konvergente Rest braucht mehr Durchgaenge, als die Vorgabe erlaubt; eine
    hoehere Grenze kostet das Zwanzigfache an Rechenzeit und ist kein Fortschritt.
    """
    eigene = abgleich.rechne_referenzjahr(app, ohne_befeuchtungsregelung=True)
    schwingend = [
        w for w in eigene["warnungen"]
        if w["stunde"] > 1 and w["abweichung"] >= SCHWINGT_AB
    ]
    assert not schwingend, schwingend[:5]
