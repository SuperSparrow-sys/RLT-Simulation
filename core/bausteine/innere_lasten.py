"""Innere Lasten eines Raums: Menschen und Geraete.

In der Mappe steckt nur die Beleuchtung als eigene Groesse im Raumblock
(Anlage!AK134); Personen- und Geraetelasten sind dort Bestandteil der von Hand
eingetragenen Kuehllast. Beim Bau der Anlagenvorlagen fiel auf, dass die
Simulation deshalb keinen Weg hatte, sie anzugeben: Der Raum hat zwar die
Eingaenge 'waermelast' und 'feuchtelast', aber keine Karte, die sie ausrechnet.
Gebaut wurde beides bisher aus einem Tageslastprofil mal einem Faktor - eine
Zahlenkette, die niemand als "40 Personen im Buero" wiedererkennt, und die die
Feuchte regelmaessig ganz vergass. Der Buerobau etwa speiste 'waermelast' nur
aus der Beleuchtung und 'feuchtelast' ueberhaupt nicht.

Diese Karte rechnet stattdessen mit den Groessen, die in einer Auslegung
stehen: Personenzahl, Waerme- und Feuchteabgabe je Person, Geraeteleistung je
Quadratmeter. Die Werte der Vorgaben stammen aus DIN EN 16798-1 und VDI 2078
fuer sitzende, leichte Taetigkeit (Buero, Schule): rund 75 W trockene Waerme
und rund 50 g/h Wasserdampf je Person bei 22 GradC. Wer schwerere Arbeit
rechnet - Turnhalle, Produktion -, setzt beide Werte hoch; die Karte urteilt
nicht darueber.

Zwei Lastanteile, weil sie sich verschieden verhalten:

* Was an der Belegung haengt - Menschen und ihre Geraete. Der Eingang
  'belegung' nimmt einen Anteil zwischen 0 und 1 entgegen, ueblicherweise aus
  einem Tageslastprofil. Ohne Anschluss gilt der eingestellte Wert.
* Was durchlaeuft - Kuehlgeraete, Server, Anlagentechnik. Sie stehen als
  Grundlast je Quadratmeter daneben und laufen rund um die Uhr.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, MESSWERT, SIGNAL, ZAHL,
    Baustein, Param, Port, registriere,
)


@registriere
class InnereLasten(Baustein):
    KENNUNG = "innere_lasten"
    NAME = "Innere Lasten"
    GRUPPE = "Verbraucher"
    SYMBOL = "innere_lasten.svg"

    PARAMETER = [
        Param("personen", "Personen im Raum", "Anzahl", 40.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0),
        Param("waerme_je_person", "Wärmeabgabe je Person", "W", 75.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0,
              hinweis="Trockene Wärme bei sitzender, leichter Tätigkeit "
                      "(DIN EN 16798-1). Bei schwerer Arbeit - Turnhalle, "
                      "Produktion - liegt sie bei 150 W und mehr."),
        Param("feuchte_je_person", "Feuchteabgabe je Person", "g/h", 50.0,
              darstellung=ZAHL, dezimalstellen=0, minimum=0.0,
              hinweis="Wasserdampf aus Atmung und Verdunstung, bei sitzender "
                      "Tätigkeit rund 50 g/h. Sie steigt mit der Aktivität "
                      "steiler als die trockene Wärme: bei Sport das Fünffache."),
        Param("grundflaeche", "Grundfläche", "m²", 2000.0,
              darstellung=ZAHL, dezimalstellen=1, minimum=0.0),
        Param("geraete", "Geräteleistung bei voller Belegung", "W/m²", 10.0,
              darstellung=ZAHL, dezimalstellen=1, minimum=0.0,
              hinweis="Was mit den Menschen kommt und geht: Rechner, Bildschirme, "
                      "Küchengeräte. Folgt der Belegung."),
        Param("grundlast", "Dauerlast", "W/m²", 0.0,
              darstellung=ZAHL, dezimalstellen=1, minimum=0.0,
              hinweis="Was rund um die Uhr läuft, unabhängig von der Belegung - "
                      "Server, Kühlmöbel, Anlagentechnik."),
        Param("belegung", "Belegung (fest)", "Anteil 0–1", 1.0,
              darstellung=ZAHL, dezimalstellen=2, minimum=0.0, maximum=1.0,
              hinweis="Gilt, solange am Eingang 'Belegung' kein Pfeil hängt. "
                      "Sonst entscheidet der angeschlossene Wert, meist ein "
                      "Tageslastprofil."),
    ]

    PORTS = [
        Port("belegung", SIGNAL, EINGANG, MESSWERT),
        # Der Raum hat nur EINEN Waermelasteingang. Was sonst noch Waerme in
        # den Raum gibt - allen voran die Beleuchtungskarte - haengt deshalb
        # hier und wird mitgezaehlt; sonst braeuchte es eine Summenkarte, deren
        # einziger Zweck es waere, zwei innere Lasten zu addieren.
        Port("weitere_waerme", SIGNAL, EINGANG, MESSWERT),
        # Dasselbe fuer die Feuchte: Der Raum hat auch davon nur einen
        # Eingang, und in einer Schwimmhalle kommt die Verdunstung des Beckens
        # zur Feuchteabgabe der Badegaeste hinzu.
        Port("weitere_feuchte", SIGNAL, EINGANG, MESSWERT),
        Port("waermelast", SIGNAL, AUSGANG, MESSWERT),
        Port("feuchtelast", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["waermelast", "feuchtelast", "personenwaerme", "geraetewaerme"]
    # Beschriftet zugleich die Eingaenge (core.bausteine.basis.port_label):
    # Ohne sie stuenden im Parameterfenster drei Zeilen "Messwert", und
    # niemand saehe, welche die Belegung ist und welche die Zusatzwaerme.
    PORT_LABEL = {
        "belegung": "Belegung, Anteil 0–1",
        "weitere_waerme": "weitere innere Wärme (kW)",
        "weitere_feuchte": "weitere innere Feuchte (kg/h)",
    }
    AUSGABE_LABEL = {
        "waermelast": "innere Wärmelast (kW)",
        "feuchtelast": "innere Feuchtelast (kg/h)",
        "personenwaerme": "davon von Personen (kW)",
        "geraetewaerme": "davon von Geräten (kW)",
    }

    def berechne(self, ein, p, zustand):
        # Ein Tageslastprofil liefert 0 bis 1; ein versehentlich angeschlossener
        # Prozentwert wuerde die Last sonst verhundertfachen, ohne dass es
        # irgendwo auffiele.
        belegung = min(max(float(ein.get("belegung", p["belegung"])), 0.0), 1.0)

        personen = belegung * p["personen"] * p["waerme_je_person"] / 1000.0
        geraete = (
            belegung * p["grundflaeche"] * p["geraete"]
            + p["grundflaeche"] * p["grundlast"]
        ) / 1000.0
        feuchte = belegung * p["personen"] * p["feuchte_je_person"] / 1000.0
        weitere = float(ein.get("weitere_waerme", 0.0))
        weitere_feuchte = float(ein.get("weitere_feuchte", 0.0))

        return {
            "waermelast": personen + geraete + weitere,
            "feuchtelast": feuchte + weitere_feuchte,
            "personenwaerme": personen,
            "geraetewaerme": geraete,
        }, zustand
