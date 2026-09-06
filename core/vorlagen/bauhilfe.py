"""Handgriffe, die jede Anlagenvorlage braucht.

Eine Vorlage besteht aus drei immer gleichen Handgriffen: eine Karte anlegen,
zwei Karten mit einem Pfeil verbinden (die Anschluesse sucht core/graph.py dann
selbst), und eine Verbindung ausdruecklich setzen, wo das Raten nicht genuegt.
Sie standen bisher als Schliessungen in jeder Vorlage. Bei zwoelf Vorlagen
waeren das zwoelf Kopien derselben sechs Zeilen - und zwoelf Stellen, an denen
eine Aenderung an core.anlagen nachgezogen werden muesste.

Benutzung:

    with Bauplatz(projekt_id, "Buerogebaeude", notiz="...") as b:
        wetter = b.karte("wetter", 40, 20, "Wetterdaten")
        luft = b.karte("aussenluft", 40, 170, "Aussenluft")
        b.pfeil(wetter, luft)
        b.verbinde(wetter, "T_AU", regler, "T_AU")
    anlage_id = b.anlage

Der Kontextblock schaltet den Verlauf stumm: Der Aufbau ist ueber hundert
einzelne Schreibvorgaenge, aber EINE Handlung der Anwenderin - niemand will ihn
Schritt fuer Schritt zuruecknehmen (siehe core/verlauf.py, stumm()).
"""

from core import anlagen, verlauf


class Bauplatz:
    """Sammelt die Handgriffe zum Bauen einer Anlage."""

    def __init__(self, projekt_id, name, notiz=""):
        self._projekt_id = projekt_id
        self._name = name
        self._notiz = notiz
        self._stumm = None
        self.anlage = None

    def __enter__(self):
        self._stumm = verlauf.stumm()
        self._stumm.__enter__()
        self.anlage = anlagen.anlage_anlegen(self._projekt_id, self._name, notiz=self._notiz)
        return self

    def __exit__(self, *fehler):
        return self._stumm.__exit__(*fehler)

    def karte(self, typ, x, y, bezeichnung, **parameter):
        return anlagen.karte_anlegen(self.anlage, typ, x, y, parameter, bezeichnung)

    def pfeil(self, von_karte_id, nach_karte_id):
        """Verbindet zwei Karten und laesst core/graph.py die Anschluesse suchen."""
        return anlagen.pfeil_anlegen(self.anlage, von_karte_id, nach_karte_id)

    def verbinde(self, von_karte_id, von_schluessel, nach_karte_id, nach_schluessel):
        """Setzt eine Verbindung ausdruecklich.

        Noetig, wo mehrere gleichrangige Anschluesse in Frage kommen: dort
        entscheidet die automatische Verdrahtung nach der Reihenfolge, in der
        die Ports angelegt wurden, nicht danach, welcher Anschluss fachlich
        gemeint ist (siehe core/graph.py, _paare()).
        """
        anlagen.verbindung_anlegen(
            self.anlage,
            anlagen.port_id(von_karte_id, von_schluessel),
            anlagen.port_id(nach_karte_id, nach_schluessel),
        )
