"""Die Regelkreise der Testanlage muessen einschwingen koennen.

core/vorlagen/testanlage.py ist der Massstab, an dem werkzeuge/plausibilitaet.py
die Rechenkette prueft. Eine Anlage, deren Regelkreise rechnerisch nicht
konvergieren, taugt dafuer nicht - dann misst die Pruefung ihren eigenen
Konstruktionsfehler statt der Physik.

Der Fund, der zu diesen Tests fuehrte: Die Luftmenge fiel ausserhalb der
Betriebszeit auf 5 % der Nennmenge (250 von 5000 m3/h). Bei so wenig Luft
erwaermt dasselbe Heizregister die Luft je Prozent Ventilstellung zwanzigmal
staerker als bei Auslegungsmenge - aus 0,54 K/% werden 10,7 K/%. Jeder
Temperaturregler im Luftweg bekommt damit eine Kreisverstaerkung weit ueber
eins, und die Iteration kippt zwischen den Anschlaegen des Stellglieds hin und
her, statt sich einzupendeln. 5,85 kW erzeugten so 72 Grad Zuluft.

Diese Tests halten beides fest: die Auslegungsregel (Test 1), damit der Fehler
nicht durch eine spaetere Parameteraenderung zurueckkommt, und das Verhalten
(Test 2), damit er auffaellt, falls er auf einem anderen Weg wiederkehrt.
"""

from pathlib import Path

import pytest

from app import create_app
from core import anlagen, database, solver
from core.bausteine.basis import Luft
from core.vorlagen import testanlage
from werkzeuge.abgleich import lade_wetterstunden


@pytest.fixture
def graph(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    app = create_app()
    with app.app_context():
        database.init_db()
        projekt = anlagen.projekt_anlegen("Regelkreise")
        yield anlagen.lade_graph(testanlage.baue(projekt, testanlage.NAME))


def karte_mit(graph, typ, im_namen=None):
    for k in graph.karten.values():
        if k.typ == typ and (im_namen is None or im_namen in (k.name or "")):
            return k
    raise AssertionError(f"Karte '{typ}' nicht in der Testanlage")


def kleinste_luftmenge(graph):
    """Die Luftmenge, auf die die Anlage ausserhalb der Betriebszeit zurueckfaellt.

    Sie entsteht aus dem Tageslastprofil (nie null, unabhaengig von
    Wochenzeitplan und Ferien) mal dem Faktor der Nachtluft-Grundlast, begrenzt
    auf 100 Prozent - siehe core/vorlagen/testanlage.py.
    """
    profil = karte_mit(graph, "tageslastprofil")
    faktor = karte_mit(graph, "faktor", "Nachtluft")
    anteil = min(profil.parameter["lastgang_1"]) * faktor.parameter["faktor"]
    anteil = max(0.0, min(anteil, 100.0)) / 100.0
    return karte_mit(graph, "erhitzer").parameter["V_nenn"] * anteil


def heizautoritaet(graph, volumenstrom):
    """Wieviel Kelvin das Heizregister je Prozent Ventilstellung schafft.

    Gerechnet mit der Karte selbst, nicht mit einer hier zweitgeschriebenen
    Formel - sonst prueft der Test seine eigene Kopie statt des Bausteins.
    """
    karte = karte_mit(graph, "erhitzer")
    ein_luft = Luft(V=volumenstrom, T=0.0, x=5.0)

    def austritt(stellgroesse):
        werte, _ = karte.baustein.berechne(
            {"luft_ein": ein_luft, "stellgroesse": stellgroesse},
            karte.parameter, {},
        )
        return werte["luft_aus"].T

    return (austritt(100.0) - austritt(0.0)) / 100.0


def test_heizregister_bleibt_auch_bei_kleinster_luftmenge_regelbar(graph):
    """Die Auslegungsregel: Aendert das Register die Temperatur je Prozent
    Ventilstellung um mehr, als der Proportionalbereich des Reglers breit ist,
    ueberschreitet der Regelkreis bei jedem Durchgang sein Ziel und die
    Iteration kippt zwischen den Anschlaegen - der Rechengang findet dann
    keinen Wert, egal wie viele Durchgaenge er bekommt.
    """
    v_min = kleinste_luftmenge(graph)
    autoritaet = heizautoritaet(graph, v_min)
    xp = karte_mit(graph, "kaskade").parameter["xp"]
    kreisverstaerkung = autoritaet / xp

    assert kreisverstaerkung < 1.0, (
        f"Bei {v_min:.0f} m³/h schafft das Register {autoritaet:.2f} K je Prozent "
        f"Ventilstellung, der Regler arbeitet aber mit einem Proportionalbereich "
        f"von {xp:.1f} K - Kreisverstärkung {kreisverstaerkung:.2f}. Entweder die "
        f"kleinste Luftmenge anheben oder den Proportionalbereich verbreitern."
    )


@pytest.mark.parametrize("stunden_zahl", [24 * 14])
def test_die_ersten_tage_schwingen_ein(graph, stunden_zahl):
    """Verhaltensprobe zur Auslegungsregel oben - dieselbe Aussage wie die
    Jahrespruefung in werkzeuge/plausibilitaet.py, nur schnell genug fuer die
    normale Testreihe. Der Massstab ist derselbe: kein Takt, und keine
    grenzzyklus-grosse Restabweichung nach der ersten Stunde.
    """
    GRENZZYKLUS_SCHWELLE = 2.0
    lauf = solver.Solver(graph).starte(lade_wetterstunden()[:stunden_zahl])

    takte = [t for t in lauf.takte if t["stunde"] > 1]
    assert not takte, f"{len(takte)} taktende Stunden, erste: {takte[0]['text']}"

    gross = [
        w for w in lauf.warnungen
        if w["stunde"] > 1 and w["abweichung"] > GRENZZYKLUS_SCHWELLE
    ]
    assert not gross, f"{len(gross)} Stunden mit großer Restabweichung, erste: {gross[0]['text']}"
