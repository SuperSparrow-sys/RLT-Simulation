"""Kuehlflaeche im Raum: Kuehldecke, Kuehlsegel, Umluftkuehler.

Das Gegenstueck zur Statischen Heizung. Sie nimmt die vom Raum gemeldete
Ueberdeckung auf und begrenzt sie auf die Nennleistung.

Warum es diese Karte gibt: Eine Lueftungsanlage bemisst ihre Luftmenge nach
Hygiene - im Buero rund 50 m3/h je Person. Damit laesst sich Waerme nur in dem
Mass abfuehren, wie die Zuluft kaelter sein darf als der Raum, und das sind
etwa 8 Kelvin. Ein Buero mit 8000 m3/h traegt so rund 22 kW; seine innere Last
liegt bei 25 W/m2 auf 2000 m2 aber bei 50 kW. Die Differenz nimmt in fast jedem
gebauten Haus eine Flaeche im Raum auf, nicht die Luft. Ohne diese Karte
rechnete sich der Raum stattdessen auf 30 GradC hoch - eine Zahl, die kein
Anlagenbauer wiedererkennt, und die nur entstand, weil das Modell die
Kuehlflaeche nicht kannte.

Die Kaelte geht ueber den Ausgang QK in die Bilanz, wie bei jedem anderen
Kaelteverbraucher auch.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, KAELTE, MESSWERT, SIGNAL, ZAHL,
    Baustein, Param, Port, registriere,
)


@registriere
class StatischeKuehlung(Baustein):
    KENNUNG = "statische_kuehlung"
    NAME = "Statische Kühlung"
    GRUPPE = "Räume"
    SYMBOL = "statische_kuehlung.svg"

    PARAMETER = [
        Param("QK_nenn", "Nennkühlleistung (QK_nenn)", "kW", 0.0,
              darstellung=ZAHL, dezimalstellen=1, minimum=0.0,
              hinweis="Obergrenze: Fordert der Raum mehr, gibt die Kühlfläche "
                      "trotzdem nur diese Leistung ab. 0 heißt, sie kühlt gar "
                      "nicht."),
    ]

    PORTS = [
        # Wie bei der Statischen Heizung heisst der Anschluss nach der Groesse,
        # die er aufnimmt: Ein namenloser Anschluss bekaeme vom Raum den
        # erstbesten Messwert, und davon bietet er mehrere an.
        Port("QK_stat", SIGNAL, EINGANG, MESSWERT),
        Port("QK", SIGNAL, AUSGANG, KAELTE),
    ]

    AUSGABEN = ["QK"]
    AUSGABE_LABEL = {"QK": "abgegebene Kühlleistung (kW)"}
    PORT_LABEL = {"QK_stat": "vom Raum geforderte Kühlleistung (kW)"}

    def berechne(self, ein, p, zustand):
        gefordert = float(ein.get("QK_stat", 0.0))
        QK = max(min(gefordert, p["QK_nenn"]), 0.0)
        return {"QK": QK}, zustand
