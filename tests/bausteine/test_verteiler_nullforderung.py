"""Ein Gang, der NULL fordert, ist etwas anderes als einer, der nichts sagt.

Der Verteiler teilt seinen Strom nach dem auf, was die Gänge anfordern. Was
übrig bleibt, geht an die Gänge, die nichts angefordert haben - typisch die
Fortluft, die als Senke nie etwas fordert. Beides wurde bisher an derselben
Zahl festgemacht: Ein Bedarf von 0,0 galt als „hat nichts gefordert", und der
Gang bekam den festen Anteil des Verteilers zugeteilt.

Aufgefallen ist das am Rechenzentrum. Dessen freie Kühlung fährt die
Umluftklappe zu, wenn die Außenluft kühl genug ist. Die Forderung der
Mischkammer läuft dann sauber gegen null - 49,6, 40,4, 31,4, 22,6, 14,0, 5,5
m³/h - und in dem Durchgang, in dem sie null erreicht, schob der Verteiler ihr
80 Prozent der Abluft zu: 26 400 m³/h in einen Strang, den niemand haben
wollte. Im nächsten Durchgang forderte die Mischkammer wieder null, und das
Spiel begann von vorn. Die Rechnung blieb in dieser Stunde an ihrer
Iterationsgrenze stehen.

Die Unterscheidung steckt schon in den Daten: Die Fortluftkarte meldet aus
`bedarf()` ein leeres Verzeichnis - sie sagt gar nichts -, die Mischkammer
meldet ausdrücklich `"umluft_ein": 0.0`. Der Rückwärtslauf hat beides zu
derselben Null verrechnet.
"""

import pytest

from core.bausteine.basis import Luft
from core.bausteine.verteiler import Verteiler


def verteile(bedarf_je_abgang, V=33000.0, anteile=None):
    v = Verteiler()
    v.abgaenge = ["luft_aus_1", "luft_aus_2"]
    v.bedarf_je_abgang = bedarf_je_abgang
    p = Verteiler.vorgabeparameter()
    p["anteile"] = anteile or {"luft_aus_1": 80.0, "luft_aus_2": 20.0}
    aus, _ = v.berechne({"luft_ein": Luft(V=V, T=25.0, x=9.0)}, p, {})
    return {a: aus[a].V for a in v.abgaenge}


def test_ein_gang_der_null_fordert_bekommt_null():
    """Genau der Fall aus dem Rechenzentrum: Die Umluftklappe ist zu."""
    verteilt = verteile({"luft_aus_1": 0.0, "luft_aus_2": None})
    assert verteilt["luft_aus_1"] == pytest.approx(0.0), (
        f"{verteilt['luft_aus_1']:.0f} m³/h in einen Strang, der null fordert"
    )
    assert verteilt["luft_aus_2"] == pytest.approx(33000.0), (
        "was niemand fordert, gehört ins Freie - und zwar alles"
    )


def test_ein_gang_der_nichts_sagt_bekommt_den_rest():
    """Die Fortluft fordert nie etwas an und nimmt trotzdem alles auf, was
    übrig bleibt - sonst löste sich Luft auf."""
    verteilt = verteile({"luft_aus_1": 12000.0, "luft_aus_2": None})
    assert verteilt["luft_aus_1"] == pytest.approx(12000.0)
    assert verteilt["luft_aus_2"] == pytest.approx(21000.0)


def test_eine_geforderte_menge_wird_nicht_ueberschrieben():
    """Der Regelfall bleibt, wie er war."""
    verteilt = verteile({"luft_aus_1": 20000.0, "luft_aus_2": None})
    assert verteilt["luft_aus_1"] == pytest.approx(20000.0)
    assert verteilt["luft_aus_2"] == pytest.approx(13000.0)


def test_fordern_alle_gaenge_zu_viel_wird_anteilig_gekuerzt():
    verteilt = verteile({"luft_aus_1": 30000.0, "luft_aus_2": 30000.0})
    assert verteilt["luft_aus_1"] == pytest.approx(16500.0)
    assert verteilt["luft_aus_2"] == pytest.approx(16500.0)


def test_fordert_niemand_etwas_gilt_der_feste_schluessel():
    """Der erste Rückwärtsdurchlauf kennt noch keine Forderungen. Dann teilt
    der Verteiler nach seinem Parameter auf - das ist die Notaufteilung, mit
    der die Rechnung überhaupt anfangen kann."""
    verteilt = verteile({"luft_aus_1": None, "luft_aus_2": None})
    assert verteilt["luft_aus_1"] == pytest.approx(26400.0)
    assert verteilt["luft_aus_2"] == pytest.approx(6600.0)


def test_fordern_alle_gaenge_null_loest_das_keine_division_durch_null_aus():
    """Ein Grenzfall ohne Senke: Jeder Gang sagt ausdrücklich null, und es ist
    trotzdem Luft da. Sie muss irgendwohin - nach dem festen Schlüssel."""
    verteilt = verteile({"luft_aus_1": 0.0, "luft_aus_2": 0.0})
    assert sum(verteilt.values()) == pytest.approx(33000.0)
