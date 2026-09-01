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
        Param("preis_strom_ht", "Strom HT", "EUR/MWh", 150.0, darstellung=ZAHL, dezimalstellen=2),
        Param("preis_strom_nt", "Strom NT", "EUR/MWh", 150.0, darstellung=ZAHL, dezimalstellen=2),
        Param("preis_strom_leistung", "Strom Leist.", "EUR/kW/a", 0.0, darstellung=ZAHL, dezimalstellen=2),
        Param("preis_waerme", "Wärme", "EUR/MWh", 50.0, darstellung=ZAHL, dezimalstellen=2),
        Param("preis_kaelte", "Kälte", "EUR/MWh", 50.0, darstellung=ZAHL, dezimalstellen=2),
        Param("preis_wasser", "Wasser", "EUR/m³", 4.0, darstellung=ZAHL, dezimalstellen=2),
        Param("ht_von", "HT von", "", 7.0 / 24.0, darstellung=UHRZEIT),
        Param("ht_bis", "HT bis", "", 20.0 / 24.0, darstellung=UHRZEIT),
    ]

    PORTS = [
        Port("strom", SIGNAL, EINGANG, STROM, dynamisch=True),
        Port("waerme", SIGNAL, EINGANG, WAERME, dynamisch=True),
        Port("kaelte", SIGNAL, EINGANG, KAELTE, dynamisch=True),
        Port("wasser", SIGNAL, EINGANG, WASSER, dynamisch=True),
        Port("hochtarif", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["strom_ht", "strom_nt", "waerme", "kaelte", "wasser", "hochtarif"]
    AUSGABE_LABEL = {"hochtarif": "Hochtarif aktiv"}

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
