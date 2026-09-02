"""Energiebilanz und Preise. Formeln aus Anlage!C32 bis D31 und AO30:AR42.

Die Karte summiert alles, was an ihre dynamischen Eingaenge angeschlossen ist,
und teilt den Strom nach Hoch- und Niedertarif auf.

Die sechs Preisparameter werden hier bewusst NICHT verrechnet: je Stunde
interessieren die Mengen, die Kosten entstehen erst in der Jahresbilanz. Sie
stehen trotzdem an dieser Karte, weil sie fachlich hierher gehoeren und im
Parameterfenster zusammen mit den Mengen zu sehen sein sollen;
core/ergebnisse.py liest sie beim Speichern eines Laufs aus.
"""

from core.bausteine.basis import (
    AUSGANG, EINGANG, KAELTE, MESSWERT, SIGNAL, STROM, UHRZEIT, WAERME, WASSER,
    ZAHL, Baustein, Param, Port, registriere,
)


@registriere
class Bilanz(Baustein):
    KENNUNG = "bilanz"
    NAME = "Energiepreise und Bilanz"
    GRUPPE = "Verbraucher"
    SYMBOL = "bilanz.svg"

    PARAMETER = [
        Param("preis_strom_ht", "Strompreis Hochtarif", "EUR/MWh", 150.0,
              darstellung=ZAHL, dezimalstellen=2,
              hinweis="Arbeitspreis je Megawattstunde. 150 EUR/MWh sind 15 Cent je "
                      "Kilowattstunde."),
        Param("preis_strom_nt", "Strompreis Niedertarif", "EUR/MWh", 150.0,
              darstellung=ZAHL, dezimalstellen=2),
        # core/ergebnisse.py, BILANZ: die Kostenbilanz kennt nur die fuenf
        # Arbeitspreise. Der Leistungspreis stand schon in der Mappe und bleibt
        # als Notiz erhalten, wird aber nirgends verrechnet.
        Param("preis_strom_leistung", "Strom-Leistungspreis",
              "EUR/(kW·a)", 0.0, darstellung=ZAHL, dezimalstellen=2,
              hinweis="Wird nicht gerechnet: In die Kostenbilanz gehen nur die "
                      "Arbeitspreise für Strom, Wärme, Kälte und Wasser ein - keine "
                      "Leistungs- oder Grundpreise.", ohne_wirkung=True),
        Param("preis_waerme", "Wärmepreis", "EUR/MWh", 50.0,
              darstellung=ZAHL, dezimalstellen=2),
        Param("preis_kaelte", "Kältepreis", "EUR/MWh", 50.0,
              darstellung=ZAHL, dezimalstellen=2),
        Param("preis_wasser", "Wasserpreis", "EUR/m³", 4.0,
              darstellung=ZAHL, dezimalstellen=2),
        Param("ht_von", "Hochtarif von", "", 7.0 / 24.0, darstellung=UHRZEIT,
              hinweis="Der Hochtarif gilt nur montags bis freitags zwischen diesen "
                      "beiden Uhrzeiten; alles andere zählt als Niedertarif."),
        Param("ht_bis", "Hochtarif bis", "", 20.0 / 24.0, darstellung=UHRZEIT),
    ]

    PORTS = [
        Port("strom", SIGNAL, EINGANG, STROM, dynamisch=True),
        Port("waerme", SIGNAL, EINGANG, WAERME, dynamisch=True),
        Port("kaelte", SIGNAL, EINGANG, KAELTE, dynamisch=True),
        Port("wasser", SIGNAL, EINGANG, WASSER, dynamisch=True),
        Port("hochtarif", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["strom_ht", "strom_nt", "waerme", "kaelte", "wasser", "hochtarif"]
    # Die Eingaenge nehmen LEISTUNGEN auf (kW bzw. l/h), die AUSGABEN darunter
    # sind die daraus gebildeten Stundenmengen (kWh bzw. l) - ohne eigene
    # Portbeschriftung stuende an einem Eingang "Wärme (kWh)".
    PORT_LABEL = {
        "strom": "elektrische Leistung (kW)",
        "waerme": "Wärmeleistung (kW)",
        "kaelte": "Kälteleistung (kW)",
        "wasser": "Wasserverbrauch (l/h)",
    }
    AUSGABE_LABEL = {
        "hochtarif": "Hochtarif aktiv (1 = ja, 0 = nein)",
        "strom_ht": "Strom im Hochtarif (kWh)",
        "strom_nt": "Strom im Niedertarif (kWh)",
        "waerme": "Wärme (kWh)",
        "kaelte": "Kälte (kWh)",
        "wasser": "Wasser (l)",
    }

    def _summe(self, ein, praefix):
        return sum(
            float(w) for s, w in ein.items()
            if s.startswith(praefix) and isinstance(w, (int, float))
        )

    def berechne(self, ein, p, zustand):
        s = zustand.get("stunde") or {}
        zeitpunkt = s.get("zeitpunkt")

        hochtarif = 0.0
        if zeitpunkt is not None and zeitpunkt.weekday() < 5:
            anteil = (zeitpunkt.hour + zeitpunkt.minute / 60.0) / 24.0
            # Anlage!AP42 vergleicht beidseitig streng: AR4 > AP39 und AR4 < AQ39.
            # Der Wochenzeitplan (Anlage!AN7) macht es anders - dort heisst es
            # AN4 >= AL7 und AN4 < AM7, also links geschlossen. Die Mappe ist an
            # dieser Stelle in sich uneinheitlich; jede Karte gibt ihre eigene Zelle
            # wieder. Beim Tarif faellt die volle Stunde des Beginns damit noch in den
            # Niedertarif. Der Test unten haelt das fest.
            if p["ht_von"] < anteil < p["ht_bis"]:
                hochtarif = 1.0

        strom = self._summe(ein, "strom")
        return (
            {
                "strom_ht": strom if hochtarif else 0.0,
                "strom_nt": 0.0 if hochtarif else strom,
                "waerme": self._summe(ein, "waerme"),
                "kaelte": self._summe(ein, "kaelte"),
                "wasser": self._summe(ein, "wasser"),
                "hochtarif": hochtarif,
            },
            zustand,
        )
