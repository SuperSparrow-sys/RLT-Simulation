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


@pytest.mark.slow
def test_es_sind_zwoelf_pruefungen(ergebnis):
    """Die Aufgabenbeschreibung nennt zwoelf Pruefungen als Massstab."""
    assert len(plausibilitaet.pruefungen(ergebnis)) == 12


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
