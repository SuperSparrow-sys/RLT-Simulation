"""Die zehn mitgelieferten Anlagen - Zusammenbau und eine kurze Rechenprobe.

Der vollständige Nachweis läuft über werkzeuge/anlagenpruefung.py: zehn
Jahresläufe, rund eine Stunde. Für die normale Testreihe ist das zu viel.
Hier steht deshalb die schnelle Fassung - jede Anlage wird gebaut, auf stille
Verdrahtungsfehler geprüft und über eine Winterwoche gerechnet.

Was hier grün ist, kann im Jahreslauf noch auffallen; was hier rot ist, ist
mit Sicherheit kaputt.
"""

import pytest

from app import create_app
from core import anlagen, database, pruefung, solver
from core.vorlagen import VORLAGEN
from core.vorlagen import anlagen as vorlagen_anlagen
from werkzeuge.abgleich import lade_wetterstunden

#: Grenze, ab der eine Restabweichung als Grenzzyklus gilt - derselbe Maßstab
#: wie in werkzeuge/plausibilitaet.py.
GRENZZYKLUS_SCHWELLE = 2.0

MODULE = vorlagen_anlagen.alle()


@pytest.fixture(scope="module")
def app(tmp_path_factory, protokoll_pfad):
    """Eine Anwendung für das ganze Modul - jede der zehn Anlagen einzeln
    aufzubauen kostet Sekunden, und es sind über dreißig Prüfungen.

    Der Protokollpfad kommt aus conftest.py (_protokoll_pfad, sitzungsweit)
    und wird hier ausdrücklich gesetzt: Eine modulweite Vorrichtung läuft VOR
    den funktionsweiten, ruft create_app() also noch bevor _protokoll_umbiegen
    greift. app.create_app() entdoppelt seine Protokoll-Handler nach PFAD -
    ein eigener Pfad hinterließe deshalb einen zusätzlichen Handler am
    gemeinsamen Logger, und tests/test_app.py, das genau diese Handler zählt,
    fiele fehl. Derselbe Pfad für die ganze Sitzung, derselbe eine Handler.
    """
    import core.config

    alt_db = core.config.DB_PATH
    core.config.DB_PATH = tmp_path_factory.mktemp("vorlagen") / "test.db"
    core.config.LOG_FILE = protokoll_pfad
    try:
        anwendung = create_app()
        with anwendung.app_context():
            database.init_db()
        yield anwendung
    finally:
        core.config.DB_PATH = alt_db


@pytest.fixture(scope="module")
def wetterwoche():
    return lade_wetterstunden()[:168]


def baue(app, modul):
    with app.app_context():
        projekt = anlagen.projekt_anlegen(f"Test {modul.NAME}"[:60])
        return anlagen.lade_graph(modul.baue(projekt))


@pytest.mark.parametrize("kennung", sorted(MODULE))
def test_anlage_ist_ohne_stille_verdrahtungsfehler(app, kennung):
    """core/pruefung.py meldet vergessene Pfeile, wirkungslose Regler und
    Karten, deren Stellgröße nirgends herkommt."""
    graph = baue(app, MODULE[kennung])
    meldungen = pruefung.pruefe(graph)
    assert not meldungen, "\n".join(m["text"] for m in meldungen)


@pytest.mark.parametrize("kennung", sorted(MODULE))
def test_anlage_rechnet_eine_woche_ohne_grenzzyklus(app, wetterwoche, kennung):
    graph = baue(app, MODULE[kennung])
    with app.app_context():
        lauf = solver.Solver(graph).starte(wetterwoche)

    takte = [t for t in lauf.takte if t["stunde"] > 1]
    assert not takte, f"{len(takte)} taktende Stunden, erste: {takte[0]['text']}"

    gross = [
        w for w in lauf.warnungen
        if w["stunde"] > 1 and w["abweichung"] > GRENZZYKLUS_SCHWELLE
    ]
    assert not gross, f"{len(gross)} Stunden mit großer Restabweichung: {gross[0]['text']}"


@pytest.mark.parametrize("kennung", sorted(MODULE))
def test_raumtemperatur_bleibt_in_einem_moeglichen_band(app, wetterwoche, kennung):
    """Keine Anlage darf ihren Raum einfrieren oder kochen lassen."""
    graph = baue(app, MODULE[kennung])
    with app.app_context():
        lauf = solver.Solver(graph).starte(wetterwoche)
    raeume = [k for k, v in graph.karten.items()
              if v.typ in ("raum", "einfacher_raum")]
    assert raeume, "die Anlage hat gar keinen Raum"
    for kid in raeume:
        werte = [s[kid]["T_Raum"] for s in lauf.stunden if kid in s]
        assert werte, f"{graph.karten[kid].name} liefert keine Temperatur"
        assert 5.0 < min(werte) and max(werte) < 45.0, (
            f"{graph.karten[kid].name}: {min(werte):.1f} bis {max(werte):.1f} °C"
        )


def test_jede_anlage_traegt_ihre_erwartungsbaender():
    """Ohne Bänder prüft werkzeuge/anlagenpruefung.py an dieser Anlage nur die
    Rechnung, nicht die Zahlen - das soll nicht unbemerkt passieren."""
    for kennung, modul in MODULE.items():
        erwartung = getattr(modul, "ERWARTUNG", None)
        assert erwartung, f"{kennung} hat kein ERWARTUNG"
        assert "heizwaerme_kwh_m2a" in erwartung, kennung
        assert getattr(modul, "FLAECHE_M2", 0) > 0, f"{kennung} nennt keine Fläche"
        assert getattr(modul, "HOEHE_M", 0) > 0, f"{kennung} nennt keine Raumhöhe"


def test_alle_anlagen_sind_als_vorlage_waehlbar():
    """Sie sollen sich im Programm öffnen lassen, nicht nur im Prüfstand."""
    for kennung in MODULE:
        assert kennung in VORLAGEN, f"{kennung} fehlt in core/vorlagen"


def test_die_zehn_anlagen_decken_alle_kartentypen_ab(app):
    """Der Sinn der Auswahl: Was keine Anlage benutzt, prüft auch niemand."""
    from core.bausteine import lade_alle
    from core.bausteine.basis import _REGISTER

    lade_alle()
    benutzt = set()
    for modul in MODULE.values():
        benutzt |= {k.typ for k in baue(app, modul).karten.values()}

    fehlend = set(_REGISTER) - benutzt
    assert not fehlend, f"von keiner der zehn Anlagen benutzt: {sorted(fehlend)}"
