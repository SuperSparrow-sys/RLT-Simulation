"""Die Mischkammer muss ihren Umluftanteil auch herausgeben können.

Die Karte rechnet den tatsächlich gefahrenen Umluftanteil aus (er steht in
ihren AUSGABEN) - anschließen ließ er sich aber nirgends, weil sie keinen
Ausgang dafür hatte. Wer im Datenlogger sehen wollte, wie weit die
Umluftklappe steht, oder wer einen zweiten Regelkreis darauf setzen wollte,
kam nicht heran. Alle übrigen Karten geben ihre Messwerte heraus; die
Mischkammer war die Ausnahme.

Aufgefallen beim Bau der Vorlage „Rechenzentrum", deren freie Kühlung genau
über diesen Anteil arbeitet.
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
        projekt = anlagen.projekt_anlegen("Mischkammer")
        yield anlagen.anlage_anlegen(projekt, "Probe")


def test_umluftanteil_laesst_sich_anschliessen(anlage):
    mischkammer = anlagen.karte_anlegen(anlage, "mischkammer", 0, 0, {}, "Mischkammer")
    logger = anlagen.karte_anlegen(anlage, "datenlogger", 200, 0, {}, "Datenlogger")
    anlagen.verbindung_anlegen(
        anlage,
        anlagen.port_id(mischkammer, "umluftanteil_ist"),
        anlagen.port_id(logger, "wert_1"),
    )


def test_automatische_verdrahtung_findet_ihn_auch(anlage):
    """Ein Pfeil von der Mischkammer zum Datenlogger muss ankommen."""
    mischkammer = anlagen.karte_anlegen(anlage, "mischkammer", 0, 0, {}, "Mischkammer")
    logger = anlagen.karte_anlegen(anlage, "datenlogger", 200, 0, {}, "Datenlogger")
    ergebnis = anlagen.pfeil_anlegen(anlage, mischkammer, logger)
    assert ergebnis["verbindungen"], "kein Anschluss gefunden"


def test_der_ausgang_traegt_den_gefahrenen_anteil():
    """Nicht den geforderten, sondern den wirklich gefahrenen.

    Der Unterschied zaehlt: Begrenzt der Parameter max_umluft die Klappe auf
    60 %, waehrend 90 % angefordert sind, muss am Messwert-Ausgang 60 stehen.
    Er wird aus den Luftmengen gebildet, nicht aus der Anforderung - ohne Luft
    ist er null, auch wenn die Klappe voll offen steht."""
    from core.bausteine.basis import Luft, hole

    karte = hole("mischkammer")()
    werte, _ = karte.berechne(
        {
            "aussenluft_ein": Luft(V=4000.0, T=0.0, x=2.0),
            "umluft_ein": Luft(V=6000.0, T=22.0, x=8.0),
            "umluftanteil": 90.0,
        },
        {"max_umluft": 60.0},
        {},
    )
    # Der Ausgang traegt genau den Wert, den die Karte auch in ihren AUSGABEN
    # zeigt - kein zweiter, moeglicherweise abweichender Rechenweg.
    assert werte["umluftanteil_ist"] == pytest.approx(werte["umluftanteil"])
    # Und er bleibt bei der Begrenzung: 90 % gefordert, 60 % erlaubt.
    assert werte["umluftanteil_ist"] <= 60.0 + 1e-6
