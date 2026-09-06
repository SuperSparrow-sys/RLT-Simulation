"""Die Außenluftkarte reicht keine unmögliche Feuchte in die Anlage.

Testreferenzjahre enthalten Nebelstunden, deren absolute Feuchte knapp über
der Sättigung liegt - im TRY-Datensatz 13,7 °C mit 10,0 g/kg, möglich sind
9,90. Das ist kein Fehler der Datei: Bei 100 % relativer Feuchte trägt die
Luft den Überschuss als Tröpfchen, nicht als Dampf.

Weitergereicht wurde daraus ein Zustand, den es nicht geben kann - und die
Bauteile dahinter machten daraus größere: Der Kühler mischt Eintritt und
Registeroberfläche geradlinig und entfernt sich dabei von der gekrümmten
Sättigungskurve noch weiter. Über das Jahr ergab das 53 unmögliche Zustände
in der Testanlage.
"""

import pytest

from core.bausteine import stoffdaten as st
from core.bausteine.aussenluft import Aussenluft


def luft(T, x, V=5000.0):
    aus, _ = Aussenluft().berechne(
        {"T_AU": T, "F_AU": x}, {}, {"bedarf": V},
    )
    return aus


def test_nebel_wird_abgeschieden():
    """Genau die Stunde aus dem Testreferenzjahr."""
    aus = luft(13.7, 10.0)
    grenze = st.x_saett(13.7)
    assert aus["luft_aus"].x == pytest.approx(grenze)
    assert aus["nebel"] == pytest.approx(10.0 - grenze)
    assert aus["F_AU"] == pytest.approx(grenze), (
        "der ausgewiesene Messwert muss derselbe sein wie der weitergereichte"
    )


def test_moegliche_luft_bleibt_unangetastet():
    """Die Grenze darf nur greifen, wo sie muss - sonst trocknete sie die
    Außenluft und rechnete der Anlage Befeuchtungsarbeit weg."""
    aus = luft(20.0, 8.0)
    assert aus["luft_aus"].x == 8.0
    assert aus["nebel"] == 0.0


@pytest.mark.parametrize("T", [-15.0, -5.0, 0.0, 10.0, 25.0, 35.0])
def test_ueber_den_ganzen_temperaturbereich_bleibt_der_austritt_moeglich(T):
    """Auch bei Frost: 100 % relative Feuchte im Winter ist der Normalfall,
    und die Sättigungsfeuchte ist dort sehr klein."""
    aus = luft(T, 40.0)
    assert aus["luft_aus"].x <= st.x_saett(T) + 1e-9
