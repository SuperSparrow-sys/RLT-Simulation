"""Die Auslegung im Kopf einer Vorlage muss zu ihren Karten passen.

Jede Anlagenvorlage trägt ihre Eckdaten als Modulkonstanten - FLAECHE_M2,
LUFTMENGE_M3H, HOEHE_M - und leitet in ihrem Kopfkommentar daraus die Größe
jedes Bauteils ab. Die Karten selbst bekommen diese Zahlen dann noch einmal
mitgegeben.

Das ist die Stelle, an der eine Auslegung und ihre Anlage auseinanderlaufen:
Wer die Luftmenge ändert, muss sie an Ventilator, Erhitzer, Kühler und
Wärmerückgewinnung zugleich ändern. Bleibt eine zurück, rechnet die Anlage mit
zwei verschiedenen Luftmengen - der Ventilator fördert 33 000 m³/h, das
Register ist für 25 000 ausgelegt, und der Teillastfaktor
(core/bausteine/basis.py, uebertragbare_leistung) rechnet mit einem
Volumenstromverhältnis, das es nicht gibt. Auffallen würde das an keiner
einzigen Zahl.

Geprüft wird deshalb: Was eine Karte als Nenn- oder Höchstvolumenstrom trägt,
ist die Luftmenge der Anlage, und was sie als Grundfläche trägt, ist deren
Fläche - oder deren Hälfte, wo eine Anlage zwei gleiche Zonen versorgt.
"""

import pytest

from app import create_app
from core import anlagen, database
from core.vorlagen import anlagen as vorlagen_anlagen

MODULE = vorlagen_anlagen.alle()


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


@pytest.mark.parametrize("kennung", sorted(MODULE))
def test_die_karten_tragen_die_luftmenge_und_die_flaeche_der_anlage(app, kennung):
    modul = MODULE[kennung]
    with app.app_context():
        graph = anlagen.lade_graph(modul.baue(anlagen.projekt_anlegen("Auslegung")))

    luftmenge = getattr(modul, "LUFTMENGE_M3H", None)
    flaeche = getattr(modul, "FLAECHE_M2", None)
    assert luftmenge and flaeche, f"{kennung} nennt seine Eckdaten nicht"

    for karte in graph.karten.values():
        for name, wert in karte.parameter.items():
            if name in ("V_nenn", "V_max"):
                assert wert == luftmenge, (
                    f"„{karte.name}“ ist auf {wert:.0f} m³/h ausgelegt, die "
                    f"Anlage fördert {luftmenge:.0f} m³/h"
                )
            if name == "grundflaeche":
                assert wert in (flaeche, flaeche / 2.0), (
                    f"„{karte.name}“ rechnet mit {wert:.0f} m², die Anlage hat "
                    f"{flaeche:.0f} m² (halb so viel ist erlaubt: zwei Zonen)"
                )
