"""Anschlusspunkt Aussenluft. Wandelt die Wettersignale in einen Luftzustand.

Dabei wird die Feuchte auf die Saettigung begrenzt. Testreferenzjahre und
Messreihen enthalten Nebelstunden, deren absolute Feuchte knapp ueber der
Saettigung liegt - im TRY-Datensatz etwa 13,7 GradC mit 10,0 g/kg, moeglich
sind 9,90. Das ist kein Fehler der Datei: Bei 100 % relativer Feuchte traegt
die Luft den Ueberschuss als Nebel, also als Troepfchen, und nicht als Dampf.
Eine Anlage saugt Troepfchen an, die im ersten warmen Bauteil verdunsten oder
im Filter haengenbleiben; als Dampf weitergereicht ergaeben sie dagegen
Zustaende, die es nicht geben kann, und die Bauteile dahinter machen daraus
groessere: Der Kuehler mischt geradlinig und verlaesst die gekruemmte
Saettigungskurve dabei noch weiter.

Wieviel dabei wegfaellt, verschweigt die Karte nicht - sie weist es als
'nebel' aus.
"""

from core.bausteine import stoffdaten as st
from core.bausteine.basis import (
    AUSGANG, AUSSENLUFT, EINGANG, LUFT, MESSWERT, SIGNAL,
    Baustein, Luft, Port, registriere,
)


@registriere
class Aussenluft(Baustein):
    KENNUNG = "aussenluft"
    NAME = "Außenluft"
    GRUPPE = "Quellen und Senken"
    SYMBOL = "aussenluft.svg"

    PARAMETER = []

    PORTS = [
        Port("T_AU", SIGNAL, EINGANG, MESSWERT),
        Port("F_AU", SIGNAL, EINGANG, MESSWERT),
        Port("luft_aus", LUFT, AUSGANG, AUSSENLUFT),
    ]

    AUSGABEN = ["T_AU", "F_AU", "V", "nebel"]
    # Beschriftet zugleich die beiden Eingaenge T_AU/F_AU (core.bausteine.basis
    # .port_label) - ohne sie stuenden im Parameterfenster zwei Zeilen
    # "Messwert", und niemand saehe, welche die Temperatur ist.
    AUSGABE_LABEL = {
        "T_AU": "Außentemperatur (°C)",
        "F_AU": "Außenfeuchte, absolut (g/kg)",
        "V": "angesaugter Volumenstrom (m³/h)",
        "nebel": "als Nebel abgeschiedene Feuchte (g/kg)",
    }

    def berechne(self, ein, p, zustand):
        T = float(ein.get("T_AU", 0.0))
        gemessen = float(ein.get("F_AU", 0.0))
        V = float(zustand.get("bedarf", 0.0))
        x = min(gemessen, st.x_saett(T))
        return (
            {
                "luft_aus": Luft(V=V, T=T, x=x, dp=0.0),
                "T_AU": T, "F_AU": x, "V": V, "nebel": gemessen - x,
            },
            zustand,
        )

    def bedarf(self, aus_bedarf, p):
        return {}
