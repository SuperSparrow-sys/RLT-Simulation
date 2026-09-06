"""Rechnet die Testanlage einmal ueber ein Jahr und prueft das Ergebnis.

Anders als tests/test_abgleich.py (Task 20) wird hier NICHT gegen Zahlen aus
der Excel-Mappe verglichen - core/vorlagen/testanlage.py ist keine Nachbildung
der Mappe, sondern eine zweite, eigenstaendige Anlage, die bewusst die
Kartentypen einsetzt, die AX_SIM 2.1 auslaesst (siehe deren Docstring). Geprueft
wird deshalb gegen physikalische Erwartungen: sinnvolle Temperatur- und
Feuchtebaender, Heizen im Winter statt im Sommer, keine negativen Leistungen,
eine Mischkammer, die nicht waermer oder kaelter mischt als ihre beiden
Bestandteile, und eine Jahresbilanz, die zu den Stundenwerten passt.
"""

import pytest

from app import create_app
from core import database
from werkzeuge import plausibilitaet


@pytest.fixture(scope="module")
def ergebnis(tmp_path_factory):
    """Rechnet die Testanlage einmal ueber ein Jahr; alle Pruefungen teilen sie."""
    pfad = tmp_path_factory.mktemp("plausibilitaet") / "rlt.db"
    import core.config

    alt = core.config.DB_PATH
    core.config.DB_PATH = pfad
    try:
        app = create_app()
        with app.app_context():
            database.init_db()
        yield plausibilitaet.rechne_testjahr(app)
    finally:
        core.config.DB_PATH = alt


@pytest.mark.slow
def test_jede_pruefung_besteht(ergebnis):
    ergebnisse = plausibilitaet.pruefungen(ergebnis)
    gescheitert = [p for p in ergebnisse if not p["bestanden"]]
    assert not gescheitert, "\n" + plausibilitaet.als_text(ergebnisse)


# Was die Plausibilitaetspruefung abdeckt - namentlich statt als blosse Zahl.
# Frueher stand hier "== 12", weil die Aufgabenbeschreibung zwoelf Pruefungen
# als Massstab nannte. Als spaeter zwei dazukamen, schlug der Test fehl, ohne
# zu sagen, WELCHE - eine Zahl allein traegt diese Auskunft nicht. Die Liste
# sagt es und ist zugleich das Verzeichnis dessen, was geprueft wird.
ERWARTETE_PRUEFUNGEN = [
    "Alle 8760 Stunden gerechnet",
    "Kein Zweipunktregler taktet",
    "Ab der zweiten Stunde bleibt die Restabweichung klein",
    "Raumtemperatur zwischen 5 und 40 °C",
    "Raumfeuchte nie negativ und nie ueber der Saettigung",
    "Kein Luftzustand der Anlage ist übersättigt",
    "Heizwaerme im Winter groesser als im Sommer",
    "Kaelte im Sommer groesser als im Winter",
    "Heizleistung wird nie negativ",
    "Der Kuehler waermt hoechstens in Ausnahmestunden und kaum",
    "Mischlufttemperatur liegt zwischen ihren beiden Eingängen",
    "Zulufttemperatur zwischen -15 und 45 °C",
    "Summe der Stundenwerte gleich der Jahresbilanz",
    "Im Betrieb wird mehr Strom gezogen als ausserhalb",
    "Spezifischer Heizwaermebedarf zwischen 10 und 400 kWh/(m² a)",
]


@pytest.mark.slow
def test_die_pruefungen_sind_vollstaendig(ergebnis):
    """Keine Pruefung darf still verschwinden - und eine neue soll hier
    eingetragen werden, damit diese Liste das Verzeichnis bleibt."""
    namen = [p["name"] for p in plausibilitaet.pruefungen(ergebnis)]
    assert namen == ERWARTETE_PRUEFUNGEN


@pytest.mark.slow
def test_die_testanlage_nutzt_karten_die_ax_sim_2_1_auslaesst(ergebnis):
    """Sie soll gerade das abdecken, was AX_SIM 2.1 (Task 20) nicht benutzt:

    kein WRG-Plattentauscher, sondern eine Umluft-Mischkammer; kein
    Luftwaescher, sondern ein Dampfbefeuchter; kein einfacher_raum, sondern der
    bauphysikalische Raum mit Wandspeicher; keine p_regler-Ketten mit Umkehr-/
    Maximalglied, sondern eine Kaskade und ein Sequenzregler; dazu
    Verbraucher, die AX_SIM 2.1 gar nicht kennt (Beleuchtung, Heizungspumpen,
    Warmwasser, Zirkulation) sowie Monatsprofil und Enthalpierechner.
    """
    typen = {k.typ for k in ergebnis["graph"].karten.values()}
    assert {
        "mischkammer", "dampfbefeuchter", "raum", "kaskade", "sequenzregler",
        "statische_heizung", "monatsprofil", "enthalpierechner",
        "beleuchtung", "heizungspumpen", "warmwasser", "zirkulation",
    } <= typen
    # Und umgekehrt: die Zweipunktregelung, die bei AX_SIM 2.1 den bekannten
    # Grenzzyklus erzeugt (siehe werkzeuge/abgleich.py), setzt diese Anlage
    # bewusst NICHT ein - siehe core/vorlagen/testanlage.py, "Zur Konvergenz".
    assert "hysterese_regler" not in typen


@pytest.mark.slow
def test_beide_vorlagen_decken_zusammen_die_ganze_bibliothek_ab(ergebnis):
    """Jeder Kartentyp, der in einer ECHTEN Anlage vorkommen kann, muss von
    mindestens einer der beiden GROSSEN Vorlagen (AX_SIM 2.1 oder diese
    Testanlage) tatsaechlich verbaut sein.

    Die urspruengliche Fassung dieser Pruefung zaehlte jeden Kartentyp mit, der
    IRGENDWO in der Anwendung vorkommt - eingeschlossen die 34 winzigen
    Ein-Karten-Beispielanlagen unter core/lehrinhalte/ (Erklaerbereich
    /bausteine), die es inzwischen zu JEDEM Kartentyp gibt. Dadurch war die
    Pruefung trivial erfuellt, ganz gleich, was die beiden grossen Vorlagen
    taten - sie testete nichts mehr. Jetzt zaehlen ausschliesslich die beiden
    grossen Vorlagen (siehe plausibilitaet.rechne_testjahr).

    Ausgenommen sind umkehrglied, faktor und maximalwert (siehe
    plausibilitaet.KEINE_ECHTE_ANLAGENKARTE): das sind reine
    Verdrahtungshelfer ohne Gegenstueck im echten Anlagenbau, die einzig
    bestimmte Excel-Formeln (100-x, ein fester Faktor, MAX(a;b)) als eigene
    Karte ausdruecken. Ob eine Anlage sie braucht, haengt allein von der
    gewaehlten Reglertopologie ab - diese Testanlage druckt dieselbe
    Verriegelung (siehe Kaskade/Sequenzregler) ohne sie aus, waere aber
    physikalisch nicht weniger vollstaendig, wenn sie es nicht taete. Ein
    Umkehrglied oder ein Faktorglied gehoert nicht zwingend in jede Anlage;
    ein Erhitzer, ein Raum oder ein Wochenzeitplan dagegen schon.
    """
    from core.bausteine import basis

    fehlend = plausibilitaet.nicht_abgedeckte_typen(ergebnis)
    assert not fehlend, (
        f"{len(fehlend)} von {len(basis.alle())} Kartentypen werden von "
        f"keiner der beiden grossen Vorlagen tatsaechlich verbaut: "
        f"{sorted(fehlend)}"
    )
