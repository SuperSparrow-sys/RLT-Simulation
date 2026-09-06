"""Bei Teillast muss die Luftmenge durch die ganze Kette dieselbe sein.

Faehrt der Zuluftventilator gedrosselt - Nachtabsenkung, Bedarfslueftung,
Wochenende -, dann stroemt durch Erhitzer, Kuehler und
Waermerueckgewinnung genau die Menge, die der Ventilator foerdert. Alles
andere waere eine Luftmenge, die nirgends herkommt.

Bis dieser Test entstand, lieferte die Aussenluftkarte immer den NENNstrom.
Vor dem Ventilator lief die Anlage damit auf voller Menge, der Ventilator
drosselte, und die Differenz verschwand: In einer Winternacht erwaermte der
Erhitzer 8000 m3/h auf 25 Grad, wovon 1600 m3/h in den Raum gingen. Vier
Fuenftel der Waerme wurden erzeugt, abgerechnet und weggeworfen.

Aufgefallen ist es nicht frueher, weil beide bisherigen Vorlagen den Fall nicht
zeigen: AX_SIM 2.1 faehrt durchgehend auf Nennmenge (nachgemessen: alle
Luftmengen konstant), und die Testanlage Technikhalle hat eine Mischkammer, die
den Strom auf den tatsaechlichen Bedarf zurechtstutzt und den Fehler damit
verdeckt.
"""

import pytest

from app import create_app
from core import anlagen, database, solver
from core.vorlagen.bauhilfe import Bauplatz
from werkzeuge.abgleich import lade_wetterstunden

V_NENN = 8000.0
WOCHENTAGE = ("montag", "dienstag", "mittwoch", "donnerstag",
              "freitag", "samstag", "sonntag")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def baue_gedrosselte_anlage(projekt_id, stellgroesse):
    """Die kleinste Anlage, die den Fall zeigt: Quelle, Erhitzer, Ventilator,
    Raum - ohne Mischkammer, mit fest gedrosseltem Ventilator."""
    with Bauplatz(projekt_id, f"Teillast {stellgroesse:.0f} %") as b:
        wetter = b.karte("wetter", 0, 0, "Wetter")
        aussen = b.karte("aussenluft", 0, 100, "Außenluft")
        erhitzer = b.karte("erhitzer", 200, 100, "Erhitzer",
                           V_nenn=V_NENN, dp_nenn=150.0, QH_max=70.0)
        vent = b.karte("ventilator", 400, 100, "Zuluftventilator",
                       rolle="zuluft", V_max=V_NENN, dp_max=800.0,
                       dp_konst=800.0, PE_max=3.0, regelart="F",
                       stellgroesse=stellgroesse)
        raum = b.karte("einfacher_raum", 600, 100, "Raum", spez_transmission=1.0)
        # Der Erhitzer braucht eine Ansteuerung, sonst bleibt sein Ventil zu
        # (core/bausteine/erhitzer.py: stellgroesse ohne Quelle ist 0) und der
        # Test saehe nie Heizbetrieb. Fest auf 50 %, ohne Regler - hier geht es
        # um die Luftmenge, nicht um eine Regelung.
        zeitplan = b.karte("wochenzeitplan", 200, 300, "immer an",
                           **{f"von_{tag}": 0.0 for tag in WOCHENTAGE},
                           **{f"bis_{tag}": 1.0 for tag in WOCHENTAGE})
        betrieb = b.karte("anlagenbetrieb", 400, 300, "Betrieb")
        halb = b.karte("faktor", 600, 300, "halbe Leistung", faktor=0.5)

        b.pfeil(wetter, aussen)
        b.pfeil(wetter, raum)
        b.pfeil(aussen, erhitzer)
        b.pfeil(erhitzer, vent)
        b.pfeil(vent, raum)
        b.pfeil(zeitplan, betrieb)
        b.verbinde(betrieb, "stellgrad", halb, "ein")
        b.verbinde(halb, "ausgang", erhitzer, "stellgroesse")
    return b.anlage


def luftmengen(app, stellgroesse):
    with app.app_context():
        projekt = anlagen.projekt_anlegen(f"P{stellgroesse}")
        graph = anlagen.lade_graph(baue_gedrosselte_anlage(projekt, stellgroesse))
        lauf = solver.Solver(graph).starte(lade_wetterstunden()[:24])
    typ = {k: v.typ for k, v in graph.karten.items()}
    def strom(kartentyp):
        kid = next(k for k in graph.karten if typ[k] == kartentyp)
        return [s[kid]["luft_aus"].V for s in lauf.stunden if kid in s]
    return strom("erhitzer"), strom("ventilator"), lauf, graph, typ


def test_bei_voller_stellung_bleibt_alles_beim_nennstrom(app):
    vor, nach, *_ = luftmengen(app, 100.0)
    assert max(vor) == pytest.approx(V_NENN)
    assert max(nach) == pytest.approx(V_NENN)


def test_bei_halber_stellung_stroemt_vor_dem_ventilator_dasselbe(app):
    """Der Kern: kein Sprung der Luftmenge am Ventilator."""
    vor, nach, *_ = luftmengen(app, 50.0)
    assert max(nach) == pytest.approx(V_NENN * 0.5)
    for v, n in zip(vor, nach):
        assert v == pytest.approx(n), (
            f"Vor dem Ventilator strömen {v:.0f} m³/h, dahinter {n:.0f} - "
            f"die Differenz wird beheizt und weggeworfen."
        )


def test_erzeugte_waerme_kommt_auch_an(app):
    """Gegenprobe über die Energie statt über die Luftmenge: Was der Erhitzer
    an Wärme ausweist, muss der Temperaturerhöhung der Luft entsprechen, die
    tatsächlich beim Raum ankommt."""
    _, _, lauf, graph, typ = luftmengen(app, 25.0)
    erhitzer = next(k for k in graph.karten if typ[k] == "erhitzer")
    vent = next(k for k in graph.karten if typ[k] == "ventilator")

    geprueft = 0
    for stunde in lauf.stunden:
        werte = stunde[erhitzer]
        qh = werte.get("QH", 0.0)
        if qh < 1.0:
            continue
        geliefert = stunde[vent]["luft_aus"].V
        # T_aus ist die Austrittstemperatur der Karte (ihre AUSGABEN);
        # T_luft_ein die des Eintritts, vom Solver mitgeschrieben.
        angekommen = (
            geliefert / 3600.0 * 1.2 * 1.007
            * (werte["T_aus"] - werte["T_luft_ein"])
        )
        assert angekommen == pytest.approx(qh, rel=0.02), (
            f"Erhitzer weist {qh:.1f} kW aus, mit der gelieferten Luftmenge "
            f"({geliefert:.0f} m³/h) werden aber nur {angekommen:.1f} kW transportiert"
        )
        geprueft += 1

    # Ohne diese Zeile bestuende der Test auch dann, wenn der Erhitzer nie
    # liefe - eine Pruefung, die nichts ansieht, besteht immer.
    assert geprueft >= 12, f"nur {geprueft} Stunden mit Heizbetrieb geprüft"
