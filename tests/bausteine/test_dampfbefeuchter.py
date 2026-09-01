import pytest

from core.bausteine import stoffdaten as st
from core.bausteine.basis import Luft
from core.bausteine.dampfbefeuchter import Dampfbefeuchter


def parameter(**abweichend):
    p = Dampfbefeuchter.vorgabeparameter()
    p.update(abweichend)
    return p


def test_elektrodampf_verwendet_feste_enthalpie():
    p = parameter(dampfart="E")
    assert Dampfbefeuchter().dampfenthalpie(p) == 2676.0


def test_fremddampf_folgt_dem_polynom_der_excel():
    p = parameter(dampfart="F", dampftemperatur=180.0)
    erwartet = (
        2501.482
        + 1.789736 * 180.0
        + 8.957546e-4 * 180.0**2
        - 1.300254e-5 * 180.0**3
    )
    assert Dampfbefeuchter().dampfenthalpie(p) == pytest.approx(erwartet)


def test_befeuchtung_erhoeht_feuchte_und_temperatur():
    """Achtung: dieser Test ist selbstbezueglich.

    Die Mappe enthaelt keinen brauchbaren Rechenstand fuer den Dampfbefeuchter -
    beide Befeuchter stehen dort auf null. Der Test rechnet die erwarteten Werte
    mit derselben Formel nach, die der Baustein verwendet, und weist damit nur
    Selbstkonsistenz nach, nicht Uebereinstimmung mit der Vorlage. Die Formeln
    wurden stattdessen gegen den Formeltext der Zellen Anlage!P131 bis P134
    geprueft; der rechnerische Nachweis erfolgt ueber die Jahresbilanz.
    """
    p = parameter(
        dampfart="E", max_leistung=32.0, absalzverlust=10.0, dampftemperatur=180.0
    )
    ein = {"luft_ein": Luft(V=8200.0, T=20.0, x=5.0), "stellgroesse": 50.0}
    aus, _ = Dampfbefeuchter().berechne(ein, p, {})

    assert aus["luft_aus"].x == pytest.approx(5.0 + 1000.0 * 0.5 * 32.0 / (8200.0 * 1.2))
    assert aus["luft_aus"].T == pytest.approx(
        20.0 + 0.5 * 32.0 * (2676.0 - 2256.9) / (8200.0 * 1.2 * 1.007)
    )
    assert aus["wasser"] == pytest.approx(1.1 * 0.5 * 32.0)
    assert aus["QH"] == pytest.approx(1.1 * 16.0 * (2676.0 - 42.0) / 3600.0)


def test_feuchte_wird_bei_saettigung_begrenzt_und_gemeldet():
    p = parameter(dampfart="E", max_leistung=500.0, absalzverlust=0.0)
    ein = {"luft_ein": Luft(V=1000.0, T=20.0, x=5.0), "stellgroesse": 100.0}
    aus, _ = Dampfbefeuchter().berechne(ein, p, {})
    assert aus["luft_aus"].x == pytest.approx(st.x_saett(20.0))
    assert aus["warnung"] == "Uebersaettigung"


def test_ohne_volumenstrom_passiert_nichts():
    p = parameter(dampfart="E", max_leistung=32.0)
    ein = {"luft_ein": Luft(V=0.0, T=20.0, x=5.0), "stellgroesse": 100.0}
    aus, _ = Dampfbefeuchter().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(20.0)
    assert aus["luft_aus"].x == pytest.approx(5.0)
    assert aus["wasser"] == 0.0
