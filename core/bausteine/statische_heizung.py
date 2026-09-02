"""Statische Heizung als eigene Karte.

Nimmt die vom Raum gemeldete Unterdeckung auf und begrenzt sie auf die
Nennleistung, entsprechend Anlage!AH128/AH129.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, MESSWERT, SIGNAL, WAERME, ZAHL,
    Baustein, Param, Port, registriere,
)


@registriere
class StatischeHeizung(Baustein):
    KENNUNG = "statische_heizung"
    NAME = "Statische Heizung"
    GRUPPE = "Räume"
    SYMBOL = "statische_heizung.svg"

    PARAMETER = [
        Param("QH_nenn", "Nennheizleistung (QH_nenn)", "kW", 0.0,
              darstellung=ZAHL, dezimalstellen=1, minimum=0.0,
              hinweis="Obergrenze: Fordert der Raum mehr, gibt die Heizung trotzdem "
                      "nur diese Leistung ab. 0 heißt, sie heizt gar nicht.")
    ]

    PORTS = [
        # Der Anschluss heisst wie die Groesse, die er aufnimmt. Ein namenloser
        # 'bedarf' wuerde vom Raum den erstbesten Messwert bekommen - T_Raum statt
        # QH_stat -, weil der Raum drei davon anbietet.
        Port("QH_stat", SIGNAL, EINGANG, MESSWERT),
        Port("QH", SIGNAL, AUSGANG, WAERME),
    ]

    AUSGABEN = ["QH"]
    AUSGABE_LABEL = {"QH": "abgegebene Heizleistung (kW)"}
    PORT_LABEL = {"QH_stat": "vom Raum geforderte Heizleistung (kW)"}

    def berechne(self, ein, p, zustand):
        gefordert = float(ein.get("QH_stat", 0.0))
        QH = max(min(gefordert, p["QH_nenn"]), 0.0)
        return {"QH": QH}, zustand
