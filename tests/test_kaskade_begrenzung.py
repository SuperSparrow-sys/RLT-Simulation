"""Die Zuluftbegrenzung darf den Raum nur überstimmen, wenn beide sich widersprechen.

Die Kaskade begrenzt die Zulufttemperatur nach oben und unten. Liegt die Zuluft
außerhalb ihres Bandes, zwingt die Begrenzung sie zurück, statt dem Raum zu
folgen - so weit richtig, das ist der „Vorrang der Zuluftbegrenzung" aus
Anlage!Q140.

Falsch wurde es, wenn beide dasselbe wollten. Steht die Zuluft an ihrer oberen
Grenze und ist der Raum ZUGLEICH zu warm, fordern beide mehr Kühlung - die
Begrenzung aber nur mit einem winzigen Schritt, weil ihr Abstand zur Grenze
fast null ist. Der große Schritt des Raums fiel unter den Tisch, und die
Regelung kroch.

Gemessen an der Vorlage „Produktionshalle": Nach einer kühlen Nacht stand die
Regelabweichung bei -34; die Halle heizte sich auf 37 °C auf, während die
Begrenzung mit 0,03 je Durchgang nachführte. Sechs Stunden lang lief die
Kühlung nicht an.
"""

import pytest

from core.bausteine.basis import hole

PARAMETER = {
    "T_Raum_min": 22.0, "T_AU_min": 15.0, "T_Raum_max": 30.0, "T_AU_max": 30.0,
    "T_ZU_min": 16.0, "T_ZU_max": 30.0, "xp": 5.0,
}


def schritt(T_Raum, T_ZU, e_alt=0.0, T_AU=25.0):
    """Ein Rechenschritt der Kaskade; zurück kommt die Änderung von e."""
    karte = hole("kaskade")()
    werte, _ = karte.berechne(
        {"T_AU": T_AU, "T_Raum": T_Raum, "T_ZU": T_ZU}, PARAMETER, {"e": e_alt},
    )
    return werte["e"] - e_alt


def test_zu_warmer_raum_an_der_oberen_zuluftgrenze_wird_gehoert():
    """Beide wollen mehr Kühlung - der größere Schritt gilt."""
    an_der_grenze = schritt(T_Raum=36.0, T_ZU=30.1)
    frei = schritt(T_Raum=36.0, T_ZU=24.0)
    assert an_der_grenze == pytest.approx(frei, rel=0.05), (
        f"An der Grenze nur {an_der_grenze:.2f} statt {frei:.2f} je Durchgang - "
        f"die Begrenzung bremst eine Forderung, der sie zustimmt."
    )


def test_zu_kalter_raum_an_der_unteren_zuluftgrenze_wird_gehoert():
    """Die Gegenrichtung: Raum zu kalt, Zuluft schon am unteren Anschlag."""
    an_der_grenze = schritt(T_Raum=14.0, T_ZU=15.9)
    frei = schritt(T_Raum=14.0, T_ZU=22.0)
    assert an_der_grenze == pytest.approx(frei, rel=0.05)


def test_die_begrenzung_ueberstimmt_bei_widerspruch_weiterhin():
    """Der eigentliche Zweck bleibt: Ist die Zuluft zu heiß, während der Raum
    noch heizen will, gewinnt die Begrenzung."""
    widerspruch = schritt(T_Raum=18.0, T_ZU=34.0)
    assert widerspruch > 0.0, "die Begrenzung muss die Zuluft zurückzwingen"
    nur_raum = schritt(T_Raum=18.0, T_ZU=24.0)
    assert nur_raum < 0.0, "ohne Begrenzung würde der Raum heizen wollen"


def test_an_der_grenze_bleibt_es_stetig():
    """Die Behebung darf den Sprung an der Grenze nicht wieder einführen
    (siehe Commit 055f86a): Raum im Sollbereich, Zuluft genau an der Grenze."""
    innen = schritt(T_Raum=26.0, T_ZU=29.9)
    aussen = schritt(T_Raum=26.0, T_ZU=30.1)
    assert abs(innen - aussen) < 0.4, f"Sprung von {innen:.3f} auf {aussen:.3f}"
