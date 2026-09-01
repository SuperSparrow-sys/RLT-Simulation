from datetime import datetime

import pytest

from core.bausteine.bilanz import Bilanz
from core.bausteine.datenlogger import Datenlogger


def parameter(**abweichend):
    p = Bilanz.vorgabeparameter()
    p.update(
        {
            "preis_strom_ht": 150.0,
            "preis_strom_nt": 150.0,
            "preis_waerme": 50.0,
            "preis_kaelte": 50.0,
            "preis_wasser": 4.0,
            "ht_von": 7.0 / 24.0,
            "ht_bis": 20.0 / 24.0,
        }
    )
    p.update(abweichend)
    return p


def stunde(jahr, monat, tag, uhr):
    return {"stunde": {"zeitpunkt": datetime(jahr, monat, tag, uhr)}}


def test_werktags_tagsueber_gilt_der_hochtarif():
    # 2. Januar 2024 ist ein Dienstag
    aus, _ = Bilanz().berechne({"strom_1": 10.0}, parameter(), stunde(2024, 1, 2, 12))
    assert aus["hochtarif"] == 1.0
    assert aus["strom_ht"] == pytest.approx(10.0)
    assert aus["strom_nt"] == 0.0


def test_nachts_gilt_der_niedertarif():
    aus, _ = Bilanz().berechne({"strom_1": 10.0}, parameter(), stunde(2024, 1, 2, 3))
    assert aus["hochtarif"] == 0.0
    assert aus["strom_nt"] == pytest.approx(10.0)


def test_am_wochenende_gilt_der_niedertarif():
    # 6. Januar 2024 ist ein Samstag
    aus, _ = Bilanz().berechne({"strom_1": 10.0}, parameter(), stunde(2024, 1, 6, 12))
    assert aus["hochtarif"] == 0.0


def test_tarifgrenzen_sind_beidseitig_streng():
    """Anlage!AP42 - anders als der Wochenzeitplan, absichtlich.

    Das Hochtariffenster prueft AR4 > AP39 und AR4 < AQ39, also beidseitig streng.
    Der Wochenzeitplan (Anlage!AN7) prueft dagegen AN4 >= AL7 und AN4 < AM7. Die
    Mappe ist hier in sich uneinheitlich; beide Karten geben ihre eigene Zelle
    wieder. Praktisch heisst das: die volle Stunde des Tarifbeginns zaehlt noch
    zum Niedertarif.
    """
    p = parameter()
    genau_am_anfang = Bilanz().berechne({"strom_1": 10.0}, p, stunde(2024, 1, 2, 7))[0]
    eine_stunde_spaeter = Bilanz().berechne({"strom_1": 10.0}, p, stunde(2024, 1, 2, 8))[0]
    genau_am_ende = Bilanz().berechne({"strom_1": 10.0}, p, stunde(2024, 1, 2, 20))[0]

    assert genau_am_anfang["hochtarif"] == 0.0
    assert eine_stunde_spaeter["hochtarif"] == 1.0
    assert genau_am_ende["hochtarif"] == 0.0


def test_bilanz_summiert_alle_angeschlossenen_leistungen():
    ein = {
        "strom_1": 4.9, "strom_2": 1.7, "strom_3": 0.18,
        "waerme_1": 26.1, "waerme_2": 50.5,
        "kaelte_1": 12.0,
        "wasser_1": 46.2,
    }
    aus, _ = Bilanz().berechne(ein, parameter(), stunde(2024, 1, 2, 3))
    assert aus["strom_nt"] == pytest.approx(4.9 + 1.7 + 0.18)
    assert aus["waerme"] == pytest.approx(76.6)
    assert aus["kaelte"] == pytest.approx(12.0)
    assert aus["wasser"] == pytest.approx(46.2)


def test_datenlogger_gibt_die_benannten_werte_zurueck():
    p = {
        "namen": ["WRG", "T Raum", "F Raum"] + [""] * 7,
        "einheiten": ["kW", "°C", "g/kg"] + [""] * 7,
    }
    ein = {"wert_1": 51.66, "wert_2": 16.61, "wert_3": 5.33}
    aus, _ = Datenlogger().berechne(ein, p, {})
    assert aus["wert_1"] == pytest.approx(51.66)
    assert aus["wert_3"] == pytest.approx(5.33)


def test_datenlogger_meldet_seine_spalten():
    p = {
        "namen": ["WRG", "T Raum"] + [""] * 8,
        "einheiten": ["kW", "°C"] + [""] * 8,
    }
    assert Datenlogger().spalten(p) == [
        ("wert_1", "WRG", "kW"),
        ("wert_2", "T Raum", "°C"),
    ]
