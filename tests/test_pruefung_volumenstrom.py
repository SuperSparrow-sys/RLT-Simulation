"""Ein verdrahteter Luftweg, durch den nichts strömt, muss gemeldet werden.

Der Fall ist beim Bauen einer Anlage mit Abluftwäscher aufgefallen: Raum ->
Wäscher -> Wärmerückgewinnung -> Fortluft war lückenlos verdrahtet, die
Rechnung lief durch, der Wäscher meldete eine Austrittstemperatur von 20,5 °C
- und bewegte null Kubikmeter, weil im Abluftstrang kein Ventilator saß. Kein
Wasserverbrauch, keine Rückgewinnung, keine Meldung. Genau die Sorte Fehler,
für die core/pruefung.py da ist: Die Zahlen sehen aus wie Zahlen.

_luftweg_offen() findet das nicht, weil jeder Anschluss belegt ist.
"""

import pytest

from app import create_app
from core import anlagen, database, pruefung


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def baue(app, mit_abluftventilator):
    from core.vorlagen.bauhilfe import Bauplatz

    with app.app_context():
        projekt = anlagen.projekt_anlegen("Strom")
        with Bauplatz(projekt, f"Anlage {mit_abluftventilator}") as b:
            wetter = b.karte("wetter", 0, 0, "Wetter")
            aussen = b.karte("aussenluft", 0, 100, "Außenluft")
            zuvent = b.karte("ventilator", 200, 100, "Zuluftventilator")
            raum = b.karte("einfacher_raum", 400, 100, "Raum")
            waescher = b.karte(
                "luftwaescher", 400, 250, "Abluftwäscher", rolle="abluft",
            )
            fort = b.karte("fortluft", 0, 250, "Fortluft")

            b.pfeil(wetter, aussen)
            b.pfeil(wetter, raum)
            b.verbinde(aussen, "luft_aus", zuvent, "luft_ein")
            b.verbinde(zuvent, "luft_aus", raum, "zuluft_ein_1")
            b.verbinde(raum, "abluft_aus_1", waescher, "luft_ein")
            if mit_abluftventilator:
                abvent = b.karte(
                    "ventilator", 200, 250, "Abluftventilator", rolle="abluft",
                )
                b.verbinde(waescher, "luft_aus", abvent, "luft_ein")
                b.verbinde(abvent, "luft_aus", fort, "luft_ein")
            else:
                b.verbinde(waescher, "luft_aus", fort, "luft_ein")
        return anlagen.lade_graph(b.anlage), waescher


def test_ein_strang_ohne_ventilator_wird_gemeldet(app):
    graph, waescher = baue(app, mit_abluftventilator=False)
    meldungen = pruefung.pruefe(graph)

    # Der offene Luftweg ist es nicht - alles ist verbunden.
    assert not [m for m in meldungen if m["art"] == "luft_offen"]

    ohne_strom = [m for m in meldungen if m["art"] == "kein_volumenstrom"]
    assert ohne_strom, "der stromlose Abluftstrang wird nicht gemeldet"
    assert waescher in {m["karte_id"] for m in ohne_strom}
    assert "Ventilator" in ohne_strom[0]["text"]


def test_mit_abluftventilator_bleibt_es_still(app):
    """Dieselbe Anlage, ein Ventilator mehr - keine Meldung."""
    graph, _ = baue(app, mit_abluftventilator=True)
    assert not [
        m for m in pruefung.pruefe(graph) if m["art"] == "kein_volumenstrom"
    ]


def test_eine_anlage_ganz_ohne_ventilator_meldet_das_einmal(app):
    """Sonst stünde an jeder Karte einer Anlage im Bau derselbe Hinweis."""
    from core.vorlagen.bauhilfe import Bauplatz

    with app.app_context():
        projekt = anlagen.projekt_anlegen("Bau")
        with Bauplatz(projekt, "Ohne Ventilator") as b:
            aussen = b.karte("aussenluft", 0, 0, "Außenluft")
            erhitzer = b.karte("erhitzer", 200, 0, "Erhitzer")
            kuehler = b.karte("kuehler", 400, 0, "Kühler")
            raum = b.karte("einfacher_raum", 600, 0, "Raum")
            fort = b.karte("fortluft", 800, 0, "Fortluft")
            wetter = b.karte("wetter", 0, 200, "Wetter")
            b.pfeil(aussen, erhitzer)
            b.pfeil(erhitzer, kuehler)
            # Zuluft darf nicht unmittelbar zur Fortluft - dazwischen gehoert
            # ein Raum (core/graph.py, VERBOTEN).
            b.verbinde(kuehler, "luft_aus", raum, "zuluft_ein_1")
            b.verbinde(raum, "abluft_aus_1", fort, "luft_ein")
            b.pfeil(wetter, aussen)
            b.pfeil(wetter, raum)
        meldungen = [
            m for m in pruefung.pruefe(anlagen.lade_graph(b.anlage))
            if m["art"] == "kein_volumenstrom"
        ]

    assert len(meldungen) == 1
    assert "keinen Ventilator" in meldungen[0]["text"]


def test_eine_raumforderung_ohne_abnehmer_wird_gemeldet(app):
    """Der Raum meldet, wieviel eine statische Heizung beisteuern müsste -
    hängt dort kein Pfeil, hält er den Sollwert trotzdem, und die Energie
    dafür steht in keiner Bilanz. Neun von zehn Anlagenvorlagen liefen so."""
    from core.vorlagen.bauhilfe import Bauplatz

    with app.app_context():
        projekt = anlagen.projekt_anlegen("Forderung")
        with Bauplatz(projekt, "Ohne Heizung") as b:
            wetter = b.karte("wetter", 0, 0, "Wetter")
            aussen = b.karte("aussenluft", 0, 100, "Außenluft")
            vent = b.karte("ventilator", 200, 100, "Zuluftventilator")
            raum = b.karte("einfacher_raum", 400, 100, "Raum",
                           spez_transmission=1.0, sollwert_stat=20.0)
            fort = b.karte("fortluft", 600, 100, "Fortluft")
            b.pfeil(wetter, aussen)
            b.pfeil(wetter, raum)
            b.verbinde(aussen, "luft_aus", vent, "luft_ein")
            b.verbinde(vent, "luft_aus", raum, "zuluft_ein_1")
            b.verbinde(raum, "abluft_aus_1", fort, "luft_ein")
        meldungen = [
            m for m in pruefung.pruefe(anlagen.lade_graph(b.anlage))
            if m["art"] == "forderung_ohne_abnehmer"
        ]
        assert len(meldungen) == 1
        assert "QH_stat" in meldungen[0]["text"]

        # Mit angeschlossener Heizung ist es still.
        with Bauplatz(projekt, "Mit Heizung") as b2:
            wetter = b2.karte("wetter", 0, 0, "Wetter")
            aussen = b2.karte("aussenluft", 0, 100, "Außenluft")
            vent = b2.karte("ventilator", 200, 100, "Zuluftventilator")
            raum = b2.karte("einfacher_raum", 400, 100, "Raum",
                            spez_transmission=1.0, sollwert_stat=20.0)
            fort = b2.karte("fortluft", 600, 100, "Fortluft")
            heizung = b2.karte("statische_heizung", 400, 300, "Heizung",
                               QH_nenn=35.0)
            b2.pfeil(wetter, aussen)
            b2.pfeil(wetter, raum)
            b2.verbinde(aussen, "luft_aus", vent, "luft_ein")
            b2.verbinde(vent, "luft_aus", raum, "zuluft_ein_1")
            b2.verbinde(raum, "abluft_aus_1", fort, "luft_ein")
            b2.verbinde(raum, "QH_stat", heizung, "QH_stat")
        assert not [
            m for m in pruefung.pruefe(anlagen.lade_graph(b2.anlage))
            if m["art"] == "forderung_ohne_abnehmer"
        ]


def test_eine_nicht_vorhandene_kuehlflaeche_wird_nicht_angemahnt(app):
    """sollwert_kuehl = 0 heißt: Es gibt keine Kühlfläche. Dann ist der
    unbelegte Anschluss kein vergessener Pfeil, sondern das Angebot der Karte."""
    from core.vorlagen.bauhilfe import Bauplatz

    with app.app_context():
        projekt = anlagen.projekt_anlegen("Ohne Kühlfläche")
        with Bauplatz(projekt, "A") as b:
            raum = b.karte("einfacher_raum", 0, 0, "Raum", sollwert_stat=0.0)
        assert not [
            m for m in pruefung.pruefe(anlagen.lade_graph(b.anlage))
            if m["art"] == "forderung_ohne_abnehmer"
        ]
