"""Mischkammer: Aufteilung eines Luftstroms auf Außen- und Umluft.

Der Kern dieser Karte ist eine Mengenbilanz, und genau daran ist sie lange
vorbeigegangen: Sie gab die SUMME dessen aus, was ihre beiden Eingänge
anboten (V = V_AU + V_UM), statt der Menge, die der Ventilator dahinter
fordert. In core/vorlagen/testanlage.py kamen dabei 7000 m³/h heraus, wo
5000 gefordert waren - Erhitzer, Kühler und Befeuchter davor rechneten mit
40 Prozent zu viel Luft. Die Tests hier prüfen deshalb zuerst die Mengen und
erst dann die Mischung.
"""

import pytest

from core.bausteine.basis import Luft
from core.bausteine.mischkammer import Mischkammer


def _ein(V_soll, au, um, anteil):
    """Eingänge wie der Solver sie zusammenstellt.

    'luft_aus' trägt die stromabwärts geforderte Menge (core/solver.py,
    _eingaenge) - ohne sie wüsste die Karte nicht, wieviel durch sie strömt.
    """
    return {
        "luft_aus": Luft(V=V_soll),
        "aussenluft_ein": au,
        "umluft_ein": um,
        "umluftanteil": anteil,
    }


def test_gibt_genau_die_geforderte_menge_ab():
    p = {"max_umluft": 80.0}
    ein = _ein(
        5000.0,
        Luft(V=9000.0, T=0.0, x=2.0),    # Angebot weit über dem Bedarf
        Luft(V=3000.0, T=20.0, x=10.0),
        60.0,
    )
    aus, _ = Mischkammer().berechne(ein, p, {})
    assert aus["luft_aus"].V == pytest.approx(5000.0)


def test_mischt_nach_den_tatsaechlich_gezogenen_mengen():
    """Bei 30 % Umluft und 10000 m³/h Bedarf zieht die Kammer 3000 m³/h
    Umluft und 7000 m³/h Außenluft - die Mischtemperatur folgt diesen beiden
    Mengen, nicht der Klappenstellung als Formel."""
    p = {"max_umluft": 80.0}
    ein = _ein(
        10000.0,
        Luft(V=10000.0, T=0.0, x=2.0),
        Luft(V=5000.0, T=20.0, x=10.0),
        30.0,
    )
    aus, _ = Mischkammer().berechne(ein, p, {})
    assert aus["luft_aus"].V == pytest.approx(10000.0)
    assert aus["luft_aus"].T == pytest.approx(6.0)
    assert aus["luft_aus"].x == pytest.approx(0.7 * 2.0 + 0.3 * 10.0)


def test_umluftanteil_wird_auf_das_maximum_begrenzt():
    """Die Obergrenze sichert die Frischluftmenge: auch wenn der Regler 90 %
    fordert, bleiben bei max_umluft = 40 % sechzig Prozent Außenluft."""
    p = {"max_umluft": 40.0}
    ein = _ein(
        10000.0,
        Luft(V=10000.0, T=0.0, x=0.0),
        Luft(V=10000.0, T=20.0, x=0.0),
        90.0,
    )
    aus, _ = Mischkammer().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(0.4 * 20.0)
    assert aus["umluftanteil"] == pytest.approx(40.0)


def test_ohne_umluft_bleibt_die_aussenluft_unveraendert():
    p = {"max_umluft": 80.0}
    ein = _ein(
        10000.0,
        Luft(V=10000.0, T=-5.0, x=1.5),
        Luft(V=0.0, T=20.0, x=10.0),
        0.0,
    )
    aus, _ = Mischkammer().berechne(ein, p, {})
    assert aus["luft_aus"].T == pytest.approx(-5.0)
    assert aus["luft_aus"].x == pytest.approx(1.5)
    assert aus["luft_aus"].V == pytest.approx(10000.0)


def test_zu_wenig_umluft_wird_von_der_aussenluft_ausgeglichen():
    """Die Umluftklappe kann nur beimischen, was die Abluftseite anbietet.
    Fehlt etwas, holt die Außenluftklappe den Rest - die geforderte Menge
    kommt trotzdem zustande, und der ausgewiesene Anteil sagt, wieviel
    Umluft es WIRKLICH geworden ist."""
    p = {"max_umluft": 80.0}
    ein = _ein(
        10000.0,
        Luft(V=10000.0, T=0.0, x=0.0),
        Luft(V=1000.0, T=20.0, x=0.0),   # nur 1000 statt der geforderten 6000
        60.0,
    )
    aus, _ = Mischkammer().berechne(ein, p, {})
    assert aus["luft_aus"].V == pytest.approx(10000.0)
    assert aus["umluftanteil"] == pytest.approx(10.0)
    assert aus["luft_aus"].T == pytest.approx(0.1 * 20.0)


def test_ohne_bedarf_stroemt_nichts():
    p = {"max_umluft": 80.0}
    ein = _ein(0.0, Luft(V=5000.0, T=0.0), Luft(V=5000.0, T=20.0), 50.0)
    aus, _ = Mischkammer().berechne(ein, p, {})
    assert aus["luft_aus"].V == pytest.approx(0.0)


def test_der_gestellte_bedarf_teilt_sich_nach_der_klappenstellung():
    """Damit der Verteiler davor weiß, wieviel Abluft als Umluft gebraucht
    wird - sonst schickt er sie nach seinem eigenen Schlüssel und der Rest
    der Anlage rechnet mit einer Menge, die niemand angefordert hat."""
    p = {"max_umluft": 80.0}
    # Maßgeblich ist der ANGEFORDERTE Anteil, nicht der wirksame: Stünde hier
    # der wirksame, forderte die Kammer nur noch das an, was sie ohnehin schon
    # bekommt, und nähme jeden zu kleinen Wert als neue Vorgabe - sie schnürte
    # sich selbst ein. Nachgestellt in core/vorlagen/testanlage.py: Sie blieb
    # bei 40 Prozent stehen, obwohl 60 angefordert waren.
    aufteilung = Mischkammer().bedarf_gestellt(
        {"luft_aus": 5000.0}, p, {"umluftanteil_soll": 60.0, "umluftanteil": 40.0}
    )
    assert aufteilung["aussenluft_ein"] == pytest.approx(2000.0)
    assert aufteilung["umluft_ein"] == pytest.approx(3000.0)


def test_der_nennbedarf_liegt_ganz_auf_der_aussenluftseite():
    """Auslegungsfall: bei geschlossener Umluftklappe muss die Außenluftseite
    den vollen Strom tragen."""
    p = {"max_umluft": 80.0}
    aufteilung = Mischkammer().bedarf({"luft_aus": 5000.0}, p)
    assert aufteilung["aussenluft_ein"] == pytest.approx(5000.0)
    assert aufteilung["umluft_ein"] == pytest.approx(0.0)
