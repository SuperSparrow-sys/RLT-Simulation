from datetime import datetime

import pytest

from core.bausteine.anlagenbetrieb import Anlagenbetrieb
from core.bausteine.ferien import Ferien
from core.bausteine.monatsprofil import Monatsprofil
from core.bausteine.tageslastprofil import Tageslastprofil
from core.bausteine.wochenzeitplan import Wochenzeitplan


def stunde(jahr, monat, tag, uhr):
    return {"stunde": {"zeitpunkt": datetime(jahr, monat, tag, uhr)}}


def wochenparameter():
    """Anlage!AK4:AN14 - werktags 05:00 bis 22:00, Sonntag aus."""
    p = Wochenzeitplan.vorgabeparameter()
    for tag in ("montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag"):
        p[f"von_{tag}"] = 5.0 / 24.0
        p[f"bis_{tag}"] = 22.0 / 24.0
    p["von_sonntag"] = 0.0
    p["bis_sonntag"] = 0.0
    return p


def test_wochenzeitplan_laeuft_werktags_in_der_betriebszeit():
    # 2. Januar 2024 ist ein Dienstag
    aus, _ = Wochenzeitplan().berechne({}, wochenparameter(), stunde(2024, 1, 2, 10))
    assert aus["betrieb"] == 1.0


def test_wochenzeitplan_steht_nachts():
    aus, _ = Wochenzeitplan().berechne({}, wochenparameter(), stunde(2024, 1, 2, 3))
    assert aus["betrieb"] == 0.0


def test_wochenzeitplan_steht_sonntags():
    # 7. Januar 2024 ist ein Sonntag
    aus, _ = Wochenzeitplan().berechne({}, wochenparameter(), stunde(2024, 1, 7, 10))
    assert aus["betrieb"] == 0.0


def test_ferien_erkennen_den_zeitraum():
    p = {"zeitraeume": [{"name": "Weihnachten", "von": "22.12.", "bis": "06.01."}]}
    aus, _ = Ferien().berechne({}, p, stunde(2024, 12, 27, 10))
    assert aus["ferien"] == 1.0


def test_ferien_ueber_den_jahreswechsel():
    p = {"zeitraeume": [{"name": "Weihnachten", "von": "22.12.", "bis": "06.01."}]}
    aus, _ = Ferien().berechne({}, p, stunde(2024, 1, 3, 10))
    assert aus["ferien"] == 1.0


def test_ausserhalb_der_ferien_ist_null():
    p = {"zeitraeume": [{"name": "Weihnachten", "von": "22.12.", "bis": "06.01."}]}
    aus, _ = Ferien().berechne({}, p, stunde(2024, 6, 15, 10))
    assert aus["ferien"] == 0.0


def test_monatsprofil_schaltet_den_sommer_ab():
    """Anlage!AO16:AR27 - Mai bis September aus."""
    monate = [True, True, True, True, False, False, False, False, False, True, True, True]
    aus, _ = Monatsprofil().berechne({}, {"monate": monate}, stunde(2024, 7, 15, 10))
    assert aus["betrieb"] == 0.0

    aus, _ = Monatsprofil().berechne({}, {"monate": monate}, stunde(2024, 2, 15, 10))
    assert aus["betrieb"] == 1.0


def test_tageslastprofil_liefert_den_wert_der_stunde():
    """Anlage!AS6:AV32 - nachts 0,4, tagsueber 1,0."""
    lastgang = [0.4] * 7 + [1.0] * 13 + [0.4] * 4
    p = {"lastgang_1": lastgang, "lastgang_2": [0.0] * 24, "lastgang_3": [0.0] * 24}
    aus, _ = Tageslastprofil().berechne({}, p, stunde(2024, 3, 5, 12))
    assert aus["lastgang_1"] == pytest.approx(1.0)

    aus, _ = Tageslastprofil().berechne({}, p, stunde(2024, 3, 5, 3))
    assert aus["lastgang_1"] == pytest.approx(0.4)


def test_anlagenbetrieb_verknuepft_zeitplan_ferien_und_profil():
    """Anlage!AL37/AL38."""
    ein = {"zeitplan": 1.0, "ferien": 0.0, "tagesprofil": 0.4}
    aus, _ = Anlagenbetrieb().berechne(ein, {}, {})
    assert aus["betrieb"] == 1.0
    assert aus["stellgrad"] == pytest.approx(40.0)


def test_ferien_sperren_den_betrieb():
    ein = {"zeitplan": 1.0, "ferien": 1.0, "tagesprofil": 1.0}
    aus, _ = Anlagenbetrieb().berechne(ein, {}, {})
    assert aus["betrieb"] == 0.0
    assert aus["stellgrad"] == 0.0
