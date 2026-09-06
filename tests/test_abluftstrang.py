"""Luftbehandlungskarten müssen auch in den Abluftstrang passen.

Erhitzer, Kühler, Luftwäscher und Dampfbefeuchter trugen fest verdrahtete
Zuluft-Anschlüsse. Weil (Abluft -> Zuluft) in core/graph.py unter VERBOTEN
steht, nahm keine von ihnen einen Pfeil aus dem Abluftstrang an - der Editor
wies ihn mit "kein freier Anschluss passt zusammen" ab. Damit war die adiabate
Abluftkühlung nicht baubar: ein Wäscher in der Abluft, der die Abluft
verdunstungskühlt, damit die Wärmerückgewinnung im Sommer die Zuluft kühlt
statt wärmt. Das ist kein Sonderfall, sondern das übliche Verfahren der
indirekten Verdunstungskühlung und in jeder Ausschreibung zu finden.

Seit die fünf Luftbehandlungskarten ihren Einbauort als Parameter tragen
(core/bausteine/basis.py, strangparameter), geht es. Die Rolle bleibt streng
statt neutral: Ein Erhitzer sitzt fast immer in der Zuluft, und ein neutraler
Anschluss hinge ebenso bereitwillig im falschen Strang.
"""

import pytest

from app import create_app
from core import anlagen, database


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


BEHANDLUNGSKARTEN = [
    "erhitzer", "kuehler", "luftwaescher", "dampfbefeuchter", "ventilator",
]


@pytest.mark.parametrize("typ", BEHANDLUNGSKARTEN)
def test_jede_behandlungskarte_passt_in_den_abluftstrang(app, typ):
    """Raum -> Karte -> Fortluft, mit der Karte auf Abluft gestellt."""
    with app.app_context():
        anlage = anlagen.anlage_anlegen(anlagen.projekt_anlegen("Abluft"), "A")
        raum = anlagen.karte_anlegen(anlage, "einfacher_raum", 0, 0)
        karte = anlagen.karte_anlegen(anlage, typ, 200, 0)
        fort = anlagen.karte_anlegen(anlage, "fortluft", 400, 0)

        # Vor der Umstellung passt der Strang nicht - das war der ganze Fehler.
        with pytest.raises(ValueError, match="kein freier Anschluss"):
            anlagen.pfeil_anlegen(anlage, raum, karte)

        anlagen.karte_aendern(karte, parameter={"rolle": "abluft"})
        anlagen.pfeil_anlegen(anlage, raum, karte)
        anlagen.pfeil_anlegen(anlage, karte, fort)

        graph = anlagen.lade_graph(anlage)
        wege = {
            (graph.karten[v.von_port.karte_id].typ,
             graph.karten[v.nach_port.karte_id].typ)
            for v in graph.verbindungen
            if v.von_port.art == "luft"
        }
        assert ("einfacher_raum", typ) in wege
        assert (typ, "fortluft") in wege


@pytest.mark.parametrize("typ", BEHANDLUNGSKARTEN)
def test_der_zuluftstrang_bleibt_die_vorgabe(app, typ):
    """Ohne Zutun sitzt die Karte weiter in der Zuluft.

    Der neue Parameter darf bestehende Anlagen nicht umdeuten: Wer eine Karte
    anlegt, bekommt eine Zuluftkarte, wie seit jeher.
    """
    with app.app_context():
        anlage = anlagen.anlage_anlegen(anlagen.projekt_anlegen("Zuluft"), "A")
        aussen = anlagen.karte_anlegen(anlage, "aussenluft", 0, 0)
        karte = anlagen.karte_anlegen(anlage, typ, 200, 0)
        anlagen.pfeil_anlegen(anlage, aussen, karte)

        graph = anlagen.lade_graph(anlage)
        rollen = {
            p.rolle for p in graph.karten[karte].ports if p.art == "luft"
        }
        assert rollen == {"zuluft"}


def test_adiabate_abluftkuehlung_kuehlt_die_zuluft(app):
    """Der Zweck der ganzen Übung, an einer laufenden Anlage nachgerechnet.

    Ein Wäscher in der Abluft verdunstet Wasser und kühlt damit die Abluft weit
    unter die Raumtemperatur. Die Wärmerückgewinnung überträgt das auf die
    Zuluft - so kühlt eine Anlage im Sommer ohne Kältemaschine. Vor dieser
    Änderung ließ sich diese Anlage nicht bauen; der Pfeil vom Raum zum Wäscher
    wurde abgewiesen.

    Geprüft wird der Unterschied, den der Wäscher macht, nicht ein absoluter
    Wert: dieselbe Anlage einmal mit laufendem und einmal mit stehendem
    Wäscher, bei sommerlicher Außenluft.
    """
    from core import solver
    from core.vorlagen.bauhilfe import Bauplatz

    stunden = [
        {
            "zeitpunkt": f"2024-07-15 {i:02d}:00", "t_au": 30.0, "x_au": 9.0,
            "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
        }
        for i in range(6)
    ]

    def baue(projekt, waescher_an):
        # Der Hysterese-Regler dient hier als feste Quelle: Istwert über
        # Sollwert heißt dauerhaft 100 %, darunter dauerhaft 0 %.
        with Bauplatz(projekt, f"Adiabat {waescher_an}") as b:
            wetter = b.karte("wetter", 0, 0, "Wetter")
            aussen = b.karte("aussenluft", 0, 100, "Außenluft")
            wrg = b.karte("wrg", 200, 100, "WRG")
            vent = b.karte("ventilator", 400, 100, "Zuluftventilator")
            raum = b.karte("einfacher_raum", 600, 100, "Raum")
            waescher = b.karte(
                "luftwaescher", 400, 250, "Abluftwäscher", rolle="abluft",
            )
            abluftvent = b.karte(
                "ventilator", 100, 250, "Abluftventilator", rolle="abluft",
            )
            fort = b.karte("fortluft", 0, 250, "Fortluft")
            volle_leistung = b.karte(
                "hysterese_regler", 200, 350, "Dauerbefehl",
                istwert=1.0 if waescher_an else -1.0, sollwert=0.0,
            )
            wrg_auf = b.karte(
                "hysterese_regler", 200, 420, "WRG dauerhaft an",
                istwert=1.0, sollwert=0.0,
            )

            b.pfeil(wetter, aussen)
            b.pfeil(wetter, raum)
            b.verbinde(aussen, "luft_aus", wrg, "zuluft_ein")
            b.verbinde(wrg, "zuluft_aus", vent, "luft_ein")
            b.verbinde(vent, "luft_aus", raum, "zuluft_ein_1")
            b.verbinde(raum, "abluft_aus_1", waescher, "luft_ein")
            b.verbinde(waescher, "luft_aus", wrg, "abluft_ein")
            # Ohne Abluftventilator strömt im Abluftstrang nichts, und der
            # Wäscher verdunstet nichts - er ist selbst eine Abluftkarte.
            b.verbinde(wrg, "abluft_aus", abluftvent, "luft_ein")
            b.verbinde(abluftvent, "luft_aus", fort, "luft_ein")
            b.verbinde(volle_leistung, "ausgang", waescher, "stellgroesse")
            b.verbinde(wrg_auf, "ausgang", wrg, "stellgroesse")
        return b.anlage, wrg, waescher

    with app.app_context():
        projekt = anlagen.projekt_anlegen("Adiabat")
        ergebnis = {}
        for an in (False, True):
            anlage, wrg, waescher = baue(projekt, an)
            lauf = solver.Solver(anlagen.lade_graph(anlage)).starte(stunden)
            letzte = lauf.stunden[-1]
            ergebnis[an] = (letzte[wrg]["T_ZU"], letzte[waescher]["wasser"])

    ohne_t, ohne_wasser = ergebnis[False]
    mit_t, mit_wasser = ergebnis[True]

    assert ohne_wasser == pytest.approx(0.0), "stehender Wäscher verbraucht Wasser"
    assert mit_wasser > 0.0, "der Wäscher in der Abluft verdunstet nichts"
    assert mit_t < ohne_t - 1.0, (
        f"Die Abluftkühlung senkt die Zulufttemperatur nicht: {ohne_t:.2f} °C "
        f"ohne, {mit_t:.2f} °C mit Wäscher"
    )
