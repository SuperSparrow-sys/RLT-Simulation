"""Dynamische Anschluesse muessen auch beim Verdrahten von Hand nachwachsen.

Karten wie Bilanz, Maximalwert und Datenlogger haben Eingaenge, die sich
vermehren: ist 'strom_1' belegt, waechst 'strom_2' nach. Beim automatischen
Verdrahten (anlagen.pfeil_anlegen) geschieht das seit jeher. Beim
ausdruecklichen Verbinden (anlagen.verbindung_anlegen) geschah es nicht - wer
eine Bilanz von Hand verdrahtete, bekam genau einen Anschluss je Sorte und sass
dann fest.

Von Hand verbunden wird gerade dort, wo das Raten nicht genuegt: wenn eine
Quelle mehrere gleichrangige Ausgaenge anbietet. Das trifft die Bilanz und das
Maximalglied besonders oft - beide sammeln von vielen Karten ein.
"""

import pytest

from app import create_app
from core import anlagen, database


@pytest.fixture
def anlage(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    app = create_app()
    with app.app_context():
        database.init_db()
        projekt = anlagen.projekt_anlegen("Dynamik")
        yield anlagen.anlage_anlegen(projekt, "Probe")


def test_maximalglied_nimmt_von_hand_einen_zweiten_eingang(anlage):
    """Zwei Forderungen an dieselbe Stellgroesse ueber ein Maximalglied ist der
    Regelfall - und beide Verbindungen muessen von Hand setzbar sein, weil die
    Quellen mehrere gleichrangige Ausgaenge anbieten."""
    betrieb = anlagen.karte_anlegen(anlage, "anlagenbetrieb", 0, 0, {}, "Betrieb")
    faktor = anlagen.karte_anlegen(anlage, "faktor", 0, 100, {"faktor": 100.0}, "Grundlast")
    maximum = anlagen.karte_anlegen(anlage, "maximalwert", 200, 50, {}, "Stellung")

    anlagen.verbindung_anlegen(
        anlage,
        anlagen.port_id(betrieb, "stellgrad"),
        anlagen.port_id(maximum, "ein_1"),
    )
    # Ohne nachwachsende Anschluesse gibt es 'ein_2' hier gar nicht.
    anlagen.verbindung_anlegen(
        anlage,
        anlagen.port_id(faktor, "ausgang"),
        anlagen.port_id(maximum, "ein_2"),
    )

    assert anlagen.port_id(maximum, "ein_3"), "nach zwei Belegungen muss ein_3 bereitstehen"


def test_bilanz_sammelt_von_hand_mehrere_waermequellen(anlage):
    """Eine Bilanz zaehlt Erhitzer, statische Heizung und Warmwasser zusammen -
    drei Waermequellen an einer Karte."""
    erhitzer = anlagen.karte_anlegen(anlage, "erhitzer", 0, 0, {}, "Erhitzer")
    warmwasser = anlagen.karte_anlegen(anlage, "warmwasser", 0, 100, {}, "Warmwasser")
    zirkulation = anlagen.karte_anlegen(anlage, "zirkulation", 0, 200, {}, "Zirkulation")
    bilanz = anlagen.karte_anlegen(anlage, "bilanz", 300, 100, {}, "Bilanz")

    for nummer, quelle in enumerate((erhitzer, warmwasser, zirkulation), start=1):
        anlagen.verbindung_anlegen(
            anlage,
            anlagen.port_id(quelle, "QH"),
            anlagen.port_id(bilanz, f"waerme_{nummer}"),
        )

    assert anlagen.port_id(bilanz, "waerme_4"), "nach drei Belegungen muss waerme_4 bereitstehen"


def test_gemischtes_verdrahten_bleibt_stimmig(anlage):
    """Erst ein Pfeil, dann von Hand: der naechste Anschluss muss auch dann da
    sein, wenn die beiden Wege sich abwechseln."""
    erhitzer = anlagen.karte_anlegen(anlage, "erhitzer", 0, 0, {}, "Erhitzer")
    warmwasser = anlagen.karte_anlegen(anlage, "warmwasser", 0, 100, {}, "Warmwasser")
    bilanz = anlagen.karte_anlegen(anlage, "bilanz", 300, 100, {}, "Bilanz")

    anlagen.pfeil_anlegen(anlage, erhitzer, bilanz)
    anlagen.verbindung_anlegen(
        anlage,
        anlagen.port_id(warmwasser, "QH"),
        anlagen.port_id(bilanz, "waerme_2"),
    )
    assert anlagen.port_id(bilanz, "waerme_3")
