"""Alle 34 Beispielanlagen rechnen und bleiben physikalisch möglich.

Die Beispielanlagen (core/lehrinhalte/) sind das, was jemand beim Lernen als
erstes öffnet - eine davon, die unbemerkt Unsinn rechnet, wäre dort am
schädlichsten. Die eigentliche Prüfung steht in
werkzeuge/beispielpruefung.py, damit sie sich auch von Hand aufrufen lässt
und dann eine lesbare Übersicht ausgibt; dieser Test ruft dasselbe auf und
lässt die Reihe scheitern, wenn etwas herauskommt.

Als 'slow' markiert: 34 Anlagen über je zwei Wochen brauchen rund 15
Sekunden - zu viel für den schnellen Durchlauf, richtig für den vollen.
"""

import pathlib

import pytest

from app import create_app
from core import config, database
from werkzeuge import beispielpruefung
from werkzeuge.abgleich import lade_wetterstunden


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "rlt.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


@pytest.mark.slow
def test_jede_beispielanlage_rechnet_und_bleibt_physikalisch_moeglich(app):
    """Eine Januar- und eine Juliwoche - Heiz- und Kühlfall in einem Durchgang.

    Geprüft wird je Stunde und Karte: Zahlen sind endlich, jede Luft bleibt
    unterhalb der Sättigung, Temperaturen und Feuchten bleiben im möglichen
    Band. Was dabei herauskommt, steht als lesbarer Satz in der Meldung.
    """
    alle = lade_wetterstunden()
    stunden = alle[0:168] + alle[4344:4512]
    berichte = beispielpruefung.rechne_alle(app, stunden)

    assert len(berichte) == 34
    mit_befund = [b for b in berichte if b["befunde"]]
    assert not mit_befund, beispielpruefung.als_text(mit_befund)


@pytest.mark.slow
def test_keine_beispielanlage_hat_einen_taktenden_regler(app):
    """Ein Zweipunktregler, dessen Stellglied die geregelte Größe sofort um
    mehr verändert als seine Schaltdifferenz breit ist, taktet schneller als
    eine Stundenrechnung ihn auflösen kann (core/solver.py). Der Solver weist
    dann das Stundenmittel aus, was richtig ist - aber in einer Anlage, die
    jemandem einen Regler ERKLÄREN soll, will man es nicht: Dort soll man
    sehen, wie ein Regler seinen Sollwert findet.
    """
    alle = lade_wetterstunden()
    stunden = alle[0:168] + alle[4344:4512]
    berichte = beispielpruefung.rechne_alle(app, stunden)

    taktend = {b["kennung"]: b["takte"] for b in berichte if b["takte"]}
    assert not taktend, taktend
