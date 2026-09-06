"""Ändert ein Parameter die Anschlüsse einer Karte, müssen sie sich mitändern.

Der Ventilator trägt seit jeher einen Parameter "Einbau im Zuluft- oder
Abluftstrang", und core/graph.py fragt über ports_fuer() danach. Gewirkt hat er
trotzdem nie: Die Anschlüsse werden einmal beim Anlegen der Karte in die
Datenbank geschrieben, und karte_aendern() hat sie nie nachgezogen. Die Route
POST /karten reicht auch keine Parameter durch, legt also immer die Vorgabe an.
Wer im Parameterfenster auf "Abluft" stellte, bekam eine Karte, die "Abluft"
behauptete und Zuluft-Anschlüsse trug - und an die kein Pfeil aus dem
Abluftstrang passte, weil (Abluft -> Zuluft) in core/graph.py verboten ist.

Der Fehler ist stumm: Weder die Karte noch der Editor sagen etwas. Sichtbar
wird er erst daran, dass ein Pfeil, der offensichtlich passen müsste, mit
"kein freier Anschluss passt zusammen" abgewiesen wird.
"""

import pytest

from app import create_app
from core import anlagen, database
from core.bausteine import basis


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def luftrollen(karte_id):
    return {
        z["schluessel"]: z["rolle"]
        for z in database.get_db().execute(
            "SELECT schluessel, rolle FROM port WHERE karte_id = ? AND art = 'luft'",
            (karte_id,),
        )
    }


def test_rollenwechsel_zieht_die_anschluesse_nach(app):
    with app.app_context():
        anlage = anlagen.anlage_anlegen(anlagen.projekt_anlegen("Rollen"), "A")
        ventilator = anlagen.karte_anlegen(anlage, "ventilator", 0, 0)
        assert luftrollen(ventilator) == {
            "luft_ein": basis.ZULUFT, "luft_aus": basis.ZULUFT,
        }

        anlagen.karte_aendern(ventilator, parameter={"rolle": "abluft"})
        assert luftrollen(ventilator) == {
            "luft_ein": basis.ABLUFT, "luft_aus": basis.ABLUFT,
        }


def test_ein_abluftventilator_nimmt_den_pfeil_aus_dem_raum_an(app):
    """Die Probe aufs Exempel: Erst nach dem Wechsel passt der Strang."""
    with app.app_context():
        anlage = anlagen.anlage_anlegen(anlagen.projekt_anlegen("Rollen"), "A")
        raum = anlagen.karte_anlegen(anlage, "einfacher_raum", 0, 0)
        ventilator = anlagen.karte_anlegen(anlage, "ventilator", 200, 0)

        with pytest.raises(ValueError, match="kein freier Anschluss"):
            anlagen.pfeil_anlegen(anlage, raum, ventilator)

        anlagen.karte_aendern(ventilator, parameter={"rolle": "abluft"})
        pfeil = anlagen.pfeil_anlegen(anlage, raum, ventilator)
        assert pfeil is not None


def test_ein_wechsel_zerreisst_keine_bestehende_verdrahtung(app):
    """Hängt die Karte schon im Zuluftstrang, wird der Wechsel abgewiesen.

    Die Anschlüsse still umzurollen hieße, bestehende Pfeile zu Verbindungen zu
    machen, die core/graph.py selbst als verboten ansieht - die Anlage sähe
    heil aus und wäre es nicht. Sie stattdessen wortlos zu löschen, wäre der
    Verlust von Arbeit, um die niemand gebeten hat. Also sagt die Karte, was im
    Weg steht, und der Anwender löst den Pfeil selbst.
    """
    with app.app_context():
        anlage = anlagen.anlage_anlegen(anlagen.projekt_anlegen("Rollen"), "A")
        aussen = anlagen.karte_anlegen(anlage, "aussenluft", 0, 0)
        ventilator = anlagen.karte_anlegen(anlage, "ventilator", 200, 0)
        anlagen.pfeil_anlegen(anlage, aussen, ventilator)

        with pytest.raises(ValueError, match="Pfeil"):
            anlagen.karte_aendern(ventilator, parameter={"rolle": "abluft"})

        # Nichts halb getan: Die Karte steht unveraendert da.
        assert luftrollen(ventilator) == {
            "luft_ein": basis.ZULUFT, "luft_aus": basis.ZULUFT,
        }
        graph = anlagen.lade_graph(anlage)
        assert graph.karten[ventilator].parameter["rolle"] == "zuluft"


def test_ein_rollenwechsel_laesst_sich_zuruecknehmen(app):
    """Der Verlauf muss die Anschlüsse mitnehmen, nicht nur den Parameter.

    verlauf.schritt sichert den Ausgangszustand beim Betreten der Klammer.
    Stünde das Umschreiben der Anschlüsse davor, holte ein Zurücknehmen den
    alten Parameterwert zurück und ließe die Anschlüsse umgestellt stehen - die
    Karte behauptete dann wieder "Zuluft" und trüge Abluft-Anschlüsse. Genau
    der Zustand, den dieser ganze Test-Satz beseitigt.
    """
    from core import verlauf

    with app.app_context():
        anlage = anlagen.anlage_anlegen(anlagen.projekt_anlegen("Rollen"), "A")
        ventilator = anlagen.karte_anlegen(anlage, "ventilator", 0, 0)
        anlagen.karte_aendern(ventilator, parameter={"rolle": "abluft"})
        assert luftrollen(ventilator) == {
            "luft_ein": basis.ABLUFT, "luft_aus": basis.ABLUFT,
        }

        verlauf.zurueck(anlage)
        graph = anlagen.lade_graph(anlage)
        assert graph.karten[ventilator].parameter["rolle"] == "zuluft"
        assert luftrollen(ventilator) == {
            "luft_ein": basis.ZULUFT, "luft_aus": basis.ZULUFT,
        }
