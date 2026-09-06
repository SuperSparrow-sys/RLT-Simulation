"""Der Lauf muss sagen, wie viele Durchgänge er je Stunde gebraucht hat.

Der Solver bricht die Iteration nach MAX_ITERATIONEN ab und weist dann das
Mittel der beiden letzten Durchgänge aus. Wie nah eine Anlage an dieser Grenze
rechnet, war von außen nicht zu sehen: Die Zahl fiel in _rechne_stunde an und
wurde verworfen.

Damit ließ sich weder begründen, warum die Grenze bei 100 steht, noch
erkennen, wenn eine Anlage regelmäßig dagegen läuft - der Unterschied zwischen
"in drei Durchgängen fertig" und "hundert gebraucht und dann gemittelt" ist
der zwischen einem Ergebnis und einer Schätzung.
"""

import pytest

from app import create_app
from core import anlagen, config, database, solver
from core.vorlagen import VORLAGEN
from core.wetter import speicher
from werkzeuge.abgleich import lade_wetterstunden


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def lauf_ueber(app, kennung, stunden=24):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Durchgänge")
        graph = anlagen.lade_graph(VORLAGEN[kennung].baue(projekt))
        return solver.Solver(graph).starte(lade_wetterstunden()[:stunden])


def test_der_lauf_fuehrt_eine_durchgangszahl_je_stunde(app):
    lauf = lauf_ueber(app, "buero")
    assert len(lauf.durchgaenge) == len(lauf.stunden)
    assert all(1 <= d <= config.MAX_ITERATIONEN for d in lauf.durchgaenge)


def test_die_zahl_ist_keine_erfindung(app):
    """Eine Stunde, die konvergiert, braucht weniger als das Maximum."""
    lauf = lauf_ueber(app, "buero")
    assert min(lauf.durchgaenge) < config.MAX_ITERATIONEN


def test_gemittelte_stunden_sind_abzaehlbar(app):
    """Wo gemittelt wurde, ist das Ergebnis keine eingeschwungene Rechnung. Der
    Lauf muss sagen, wie viele Stunden das betrifft - sonst steht eine
    Schätzung ununterscheidbar neben einem Ergebnis.

    Gemittelt wird auf zwei Wegen (core/solver.py, _rechne_stunde): wenn die
    Iterationsgrenze erreicht ist, und wenn ein Zweitakt erkannt wurde. Der
    zweite Weg endet oft weit vor der Grenze, deshalb ist die Zahl der
    gemittelten Stunden mindestens so groß wie die Zahl der Stunden am
    Anschlag - und die Durchgangszahl allein reicht nicht aus, um sie zu
    ermitteln."""
    lauf = lauf_ueber(app, "buero")
    assert len(lauf.gemittelt) == len(lauf.stunden)
    am_anschlag = [d for d in lauf.durchgaenge if d >= config.MAX_ITERATIONEN]
    assert lauf.gemittelte_stunden >= len(am_anschlag)
    # Jede Stunde am Anschlag ist auch eine gemittelte Stunde.
    for durchgaenge, gemittelt in zip(lauf.durchgaenge, lauf.gemittelt):
        if durchgaenge >= config.MAX_ITERATIONEN:
            assert gemittelt


def test_ein_erkannter_takt_zaehlt_als_gemittelte_stunde(app):
    """Ein Zweitakt wird gemittelt, obwohl er die Grenze nie erreicht.

    Würde nur die Durchgangszahl gezählt, blieben diese Stunden unsichtbar -
    gerade die, in denen der ausgewiesene Wert am wenigsten ein Messwert ist.
    """
    lauf = lauf_ueber(app, "ax_sim_2_1", stunden=48)
    takt_stunden = [
        gemittelt
        for durchgaenge, gemittelt in zip(lauf.durchgaenge, lauf.gemittelt)
        if gemittelt and durchgaenge < config.MAX_ITERATIONEN
    ]
    assert takt_stunden, "keine Stunde vor der Grenze gemittelt - Beispiel prüfen"


def test_die_zahl_erreicht_den_bericht(app):
    """Gezählt zu haben genügt nicht - die Zahl muss beim Leser ankommen.

    Sie geht über eine eigene Spalte in die Datenbank und von dort in die
    Bilanzansicht und den Bericht; dieser Test hält den ganzen Weg fest, weil
    ein Verlust unterwegs genau die Verwechslung zurückbrächte, die die
    Zählung verhindern soll.
    """
    from core import ergebnisse

    stunden = lade_wetterstunden()[:48]
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Bericht")
        anlage_id = VORLAGEN["ax_sim_2_1"].baue(projekt)
        graph = anlagen.lade_graph(anlage_id)
        lauf = solver.Solver(graph).starte(stunden)
        wetter = speicher.datensatz_anlegen("Test", "upload", stunden)
        sim = ergebnisse.speichere(
            anlage_id, wetter, 0, len(stunden), lauf, graph, dauer=0.1,
        )
        gelesen = ergebnisse.lade_warnungen(sim)

    assert gelesen["gemittelt"] == lauf.gemittelte_stunden > 0
