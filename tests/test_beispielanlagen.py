"""Jede Beispielanlage rechnet und bleibt physikalisch möglich.

Die Beispielanlagen (core/lehrinhalte/) sind das, was jemand beim Lernen als
erstes öffnet - eine davon, die unbemerkt Unsinn rechnet, wäre dort am
schädlichsten. Die eigentliche Prüfung steht in
werkzeuge/beispielpruefung.py, damit sie sich auch von Hand aufrufen lässt
und dann eine lesbare Übersicht ausgibt; dieser Test ruft dasselbe auf und
lässt die Reihe scheitern, wenn etwas herauskommt.

Als 'slow' markiert: alle Anlagen über je zwei Wochen brauchen einige
Sekunden - zu viel für den schnellen Durchlauf, richtig für den vollen. Beide
Prüfungen teilen sich EINEN Durchgang; sie sehen dieselben Ergebnisse aus
verschiedenen Blickwinkeln an, und zweimal zu rechnen kostete die doppelte
Zeit für dieselben Zahlen.
"""

import pathlib

import pytest

from app import create_app
from core import config, database
from werkzeuge import beispielpruefung
from werkzeuge.abgleich import lade_wetterstunden


@pytest.fixture(scope="module")
def berichte(tmp_path_factory, protokoll_pfad):
    """Rechnet jede Beispielanlage einmal ueber eine Januar- und eine
    Juliwoche - Heiz- und Kuehlfall in einem Durchgang.

    Der Protokollpfad kommt aus conftest.py (sitzungsweit) und wird hier
    ausdruecklich gesetzt: Eine modulweite Vorrichtung laeuft VOR den
    funktionsweiten, ruft create_app() also noch bevor _protokoll_umbiegen
    greift. app.create_app() entdoppelt seine Protokoll-Handler nach PFAD - ein
    eigener Pfad hinterliesse deshalb einen zusaetzlichen Handler am
    gemeinsamen Logger, und tests/test_app.py, das genau diese Handler zaehlt,
    fiele fehl. Auffaellig wird das nur im vollen Lauf, denn der schnelle
    Durchgang laesst diese Vorrichtungen aus."""
    pfad = tmp_path_factory.mktemp("beispiele") / "rlt.db"
    alt = config.DB_PATH
    config.DB_PATH = pfad
    config.LOG_FILE = protokoll_pfad
    try:
        anwendung = create_app()
        with anwendung.app_context():
            database.init_db()
        alle = lade_wetterstunden()
        yield beispielpruefung.rechne_alle(anwendung, alle[0:168] + alle[4344:4512])
    finally:
        config.DB_PATH = alt


@pytest.mark.slow
def test_jede_beispielanlage_rechnet_und_bleibt_physikalisch_moeglich(berichte):
    """Eine Januar- und eine Juliwoche - Heiz- und Kühlfall in einem Durchgang.

    Geprüft wird je Stunde und Karte: Zahlen sind endlich, jede Luft bleibt
    unterhalb der Sättigung, Temperaturen und Feuchten bleiben im möglichen
    Band. Was dabei herauskommt, steht als lesbarer Satz in der Meldung.
    """
    from core.bausteine import basis, lade_alle

    lade_alle()
    # Eine Beispielanlage je Kartentyp - die Zahl steht nicht als Ziffer da,
    # sondern folgt der Bibliothek. Sonst ist sie beim naechsten neuen
    # Baustein falsch, und der Test faellt aus einem Grund, der nichts mit
    # ihm zu tun hat.
    assert len(berichte) == len(basis.alle())
    mit_befund = [b for b in berichte if b["befunde"]]
    assert not mit_befund, beispielpruefung.als_text(mit_befund)


@pytest.mark.slow
def test_keine_beispielanlage_hat_einen_taktenden_regler(berichte):
    """Ein Zweipunktregler, dessen Stellglied die geregelte Größe sofort um
    mehr verändert als seine Schaltdifferenz breit ist, taktet schneller als
    eine Stundenrechnung ihn auflösen kann (core/solver.py). Der Solver weist
    dann das Stundenmittel aus, was richtig ist - aber in einer Anlage, die
    jemandem einen Regler ERKLÄREN soll, will man es nicht: Dort soll man
    sehen, wie ein Regler seinen Sollwert findet.
    """
    taktend = {b["kennung"]: b["takte"] for b in berichte if b["takte"]}
    assert not taktend, taktend
