"""Gebäudeheizung und Kaskade müssen denselben Raumsollwert haben.

Der einfache Raum hält seine Temperatur bei `T_Raum = max(T_frei,
sollwert_stat)`: Wo die Gebäudeheizung greift, meldet der Raum genau ihren
Sollwert, gleich was die Lüftungsanlage tut. Liegt der Sollwert der Kaskade
darüber, entsteht ein Band, in dem die Kaskade gegen eine Abweichung
integriert, die sie nicht wegregeln kann - der Raum antwortet ihr nicht.

Gemessen an der Produktionshalle, als ihre Gebäudeheizung auf 17 °C stand und
die Kaskade auf 22 °C: drei Stunden je Woche ohne Konvergenz, die
Regelabweichung marschierte mit 1,67 je Durchgang ins Leere und lief in ihre
Begrenzung. Die Anlage rechnete trotzdem durch und lieferte Zahlen.

Die Regel ist deshalb: Wer eine Gebäudeheizung anschließt, gibt ihr denselben
Sollwert, den die Kaskade als unteren Raumsollwert führt. Dann übernimmt die
Heizung genau dort, wo die Lüftung nicht mehr reicht, und beide fordern
dasselbe.
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
def test_gebaeudeheizung_und_kaskade_wollen_dasselbe(app, kennung):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Sollwerte")
        graph = anlagen.lade_graph(MODULE[kennung].baue(projekt))

    kaskaden = [k for k in graph.karten.values() if k.typ == "kaskade"]
    raeume = [k for k in graph.karten.values() if k.typ == "einfacher_raum"]
    if not kaskaden or not raeume:
        pytest.skip("Anlage ohne Kaskade oder ohne einfachen Raum")

    # Nur Räume, deren Wärmeforderung auch abgenommen wird: Ein Raum ohne
    # angeschlossene Gebäudeheizung hält seinen Sollwert zwar ebenfalls, aber
    # dafür meldet core/pruefung.py bereits eine eigene Beanstandung.
    belegt = {v.von_port.id for v in graph.verbindungen}
    mit_heizung = [
        raum for raum in raeume
        if any(p.basis == "QH_stat" and p.richtung == "aus" and p.id in belegt
               for p in raum.ports)
    ]
    if not mit_heizung:
        pytest.skip("Anlage ohne angeschlossene Gebäudeheizung")

    unten = min(k.parameter["T_Raum_min"] for k in kaskaden)
    for raum in mit_heizung:
        assert raum.parameter["sollwert_stat"] == unten, (
            f"„{raum.name}“ hält {raum.parameter['sollwert_stat']:.1f} °C, die "
            f"Kaskade fordert ab {unten:.1f} °C - dazwischen antwortet der Raum "
            "der Regelung nicht."
        )
