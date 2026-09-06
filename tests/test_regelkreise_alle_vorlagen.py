"""Die Auslegungsregel für Regelkreise, geprüft an jeder Vorlage.

Ein Regelkreis schwingt sich nur ein, wenn sein Stellglied die geregelte Größe
je Schritt um weniger verändert, als sein Proportionalbereich breit ist. Sonst
überschießt er bei jedem Durchgang und kippt zwischen seinen Anschlägen - so
geschehen in der Testanlage, wo die Nachtluft auf 5 % der Nennmenge fiel und
die Autorität des Heizregisters dadurch auf 10,7 K je Prozent Ventilstellung
stieg (Commit 055f86a).

tests/test_testanlage_regelkreise.py hält die Regel für EINE Anlage fest. Hier
gilt sie für alle - und die kleinste Luftmenge wird nicht aus dem Zeitplan
abgeleitet, sondern gemessen: die Anlage wird über zwei Tage gerechnet, und
was dabei tatsächlich durch das Register strömt, zählt.
"""

import pytest

from app import create_app
from core import anlagen, database, solver
from core.bausteine.basis import Luft
from core.vorlagen import VORLAGEN
from werkzeuge.abgleich import lade_wetterstunden

#: Zwei Tage decken Nacht, Tag und Abend ab - mehr braucht es nicht, um die
#: kleinste gefahrene Luftmenge zu finden.
STUNDEN = 48


@pytest.fixture(scope="module")
def app(tmp_path_factory, protokoll_pfad):
    import core.config

    alt = core.config.DB_PATH
    core.config.DB_PATH = tmp_path_factory.mktemp("regelkreise") / "test.db"
    core.config.LOG_FILE = protokoll_pfad
    try:
        anwendung = create_app()
        with anwendung.app_context():
            database.init_db()
        yield anwendung
    finally:
        core.config.DB_PATH = alt


def register_autoritaet(karte, volumenstrom):
    """Kelvin je Prozent Ventilstellung bei dieser Luftmenge - mit der Karte
    selbst gerechnet, nicht mit einer hier zweitgeschriebenen Formel."""
    luft = Luft(V=volumenstrom, T=0.0, x=3.0)

    def austritt(stellgroesse):
        werte, _ = karte.baustein.berechne(
            {"luft_ein": luft, "stellgroesse": stellgroesse}, karte.parameter, {},
        )
        return werte["luft_aus"].T

    return (austritt(100.0) - austritt(0.0)) / 100.0


@pytest.mark.parametrize("kennung", sorted(VORLAGEN))
def test_heizregister_bleibt_bei_der_kleinsten_luftmenge_regelbar(app, kennung):
    with app.app_context():
        projekt = anlagen.projekt_anlegen(f"Regelkreis {kennung}"[:60])
        graph = anlagen.lade_graph(VORLAGEN[kennung].baue(projekt))
        lauf = solver.Solver(graph).starte(lade_wetterstunden()[:STUNDEN])

    erhitzer = [k for k, v in graph.karten.items() if v.typ == "erhitzer"]
    regler = [k for k, v in graph.karten.items()
              if v.typ in ("kaskade", "sequenzregler")]
    if not erhitzer or not regler:
        pytest.skip("kein Heizregister oder kein Sequenzregler in dieser Vorlage")

    # Der schmalste Proportionalbereich unter den Reglern - er entscheidet.
    xp = min(float(graph.karten[k].parameter.get("xp", 5.0)) for k in regler)

    for kid in erhitzer:
        mengen = [
            s[kid]["luft_aus"].V for s in lauf.stunden
            if kid in s and hasattr(s[kid].get("luft_aus"), "V")
            and s[kid]["luft_aus"].V > 0
        ]
        assert mengen, f"{graph.karten[kid].name} führt nie Luft"
        kleinste = min(mengen)
        autoritaet = register_autoritaet(graph.karten[kid], kleinste)
        kreisverstaerkung = autoritaet / xp

        assert kreisverstaerkung < 1.0, (
            f"{graph.karten[kid].name}: bei {kleinste:.0f} m³/h schafft das "
            f"Register {autoritaet:.2f} K je Prozent Ventilstellung, der Regler "
            f"arbeitet mit einem Proportionalbereich von {xp:.1f} K - "
            f"Kreisverstärkung {kreisverstaerkung:.2f}."
        )


@pytest.mark.parametrize("kennung", sorted(VORLAGEN))
def test_die_luftmenge_faellt_nie_auf_null(app, kennung):
    """Bei Volumenstrom null entkoppelt der Raum seine Feuchtebilanz von der
    Zuluft (core/bausteine/raum.py, der Mappe getreu) - der Feuchteregelkreis
    ist dann offen. Jede Vorlage muss eine Grundluftmenge halten."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen(f"Grundluft {kennung}"[:60])
        graph = anlagen.lade_graph(VORLAGEN[kennung].baue(projekt))
        lauf = solver.Solver(graph).starte(lade_wetterstunden()[:STUNDEN])

    zuluft = [
        k for k, v in graph.karten.items()
        if v.typ == "ventilator" and v.parameter.get("rolle") == "zuluft"
    ]
    assert zuluft, "kein Zuluftventilator"
    for kid in zuluft:
        mengen = [s[kid]["luft_aus"].V for s in lauf.stunden if kid in s]
        assert min(mengen) > 0.0, (
            f"{graph.karten[kid].name} steht in mindestens einer Stunde still"
        )
