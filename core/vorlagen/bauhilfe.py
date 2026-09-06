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


# -- Die immer gleiche Verdrahtung eines Zentralgeraets ---------------------
#
# Acht der zehn Anlagenvorlagen bauen ihre Karten selbst - sie unterscheiden
# sich in Namen, Leistungen und dem einen oder anderen zusaetzlichen Bauteil -,
# aber sie verdrahten sie danach alle gleich: Aussenluft ueber die
# Rueckgewinnung durch die Register zum Ventilator in den Raum und ueber die
# Abluft zurueck, die Kaskade an ihre drei Messwerte und ihre Stufen, der
# Betrieb an die Ventilatoren, die Lasten an den Raum, die Verbraucher an die
# Bilanz.
#
# Diese Wiederholung war kein Schoenheitsfehler, sondern hat Arbeit gekostet:
# Beim Anschliessen der Kuehlflaeche, beim Anschliessen der Gebaeudeheizung und
# beim Umsortieren der Datenlogger-Steckplaetze musste jedes Mal dieselbe
# Aenderung in acht Dateien nachgezogen werden - und beim Datenlogger fiel erst
# durch einen Abbruch auf, dass eine davon vergessen worden waere.
#
# Statt eines Alleskoenners mit zwanzig Argumenten stehen hier fuenf kleine
# Helfer, jeder fuer einen Abschnitt. Wer eine Vorlage liest, sieht an ihrem
# Aufruf, welche Abschnitte sie benutzt und welche sie selbst macht.


def luftweg_verdrahten(b, aussenluft, wrg, kette, zuluft, raum, abluft, fortluft):
    """Der Luftweg: Aussenluft -> WRG -> Kette -> Ventilator -> Raum -> zurueck.

    'kette' sind die Luftbehandlungskarten zwischen Rueckgewinnung und
    Zuluftventilator, in Stroemungsrichtung - meist Erhitzer und Kuehler, mit
    einem Befeuchter dahinter, wo es einen gibt.
    """
    b.verbinde(aussenluft, "luft_aus", wrg, "zuluft_ein")
    vorher = wrg
    for karte in kette:
        b.pfeil(vorher, karte)
        vorher = karte
    b.pfeil(vorher, zuluft)
    b.pfeil(zuluft, raum)
    b.pfeil(raum, abluft)
    b.verbinde(abluft, "luft_aus", wrg, "abluft_ein")
    b.verbinde(wrg, "abluft_aus", fortluft, "luft_ein")


def kaskade_verdrahten(b, wetter, raum, zuluft, kaskade, stufen):
    """Die Kaskade an ihre drei Messwerte und ihre Stufen an die Stellglieder.

    'stufen' ordnet jedem benutzten Ausgang der Kaskade die Karte zu, die er
    stellt, zum Beispiel {"waermer_1": wrg, "kaelter_1": kuehler}. Was nicht
    darin steht, bleibt frei - und der Sequenzregler laedt seine Regelabweichung
    nur so weit auf, wie Stufen verdrahtet sind (siehe
    core/bausteine/sequenzregler.py).

    Die REIHENFOLGE der Waermestufen ist eine fachliche Entscheidung, keine
    Formalie: 'waermer_1' zieht zuerst an, 'waermer_2' erst, wenn der erste am
    Anschlag steht. Deshalb gehoert die zurueckgewonnene Waerme auf die erste
    und das Register auf die zweite Stufe. Umgekehrt liefe das Register gegen
    eine Waermerueckgewinnung an, die noch Reserve hat - und die Anlage zahlte
    fuer Waerme, die sie geschenkt bekommt.
    """
    b.verbinde(wetter, "T_AU", kaskade, "T_AU")
    b.verbinde(raum, "T_Raum", kaskade, "T_Raum")
    b.verbinde(zuluft, "T_aus", kaskade, "T_ZU")
    for ausgang, karte in stufen.items():
        b.verbinde(kaskade, ausgang, karte, "stellgroesse")


def betrieb_verdrahten(b, quellen, betrieb, tagesprofil, grundlast,
                       ventilatorstellung, ventilatoren):
    """Zeitplan, Ferien und Profile auf die Betriebskarte, von dort auf die
    Ventilatoren.

    Zwei gleichrangige Forderungen an dieselbe Stellgroesse: der Anlagenbetrieb
    und die nie verschwindende Nachtluft-Grundlast. Das Maximalglied laesst die
    groessere gelten.
    """
    for quelle in quellen:
        b.pfeil(quelle, betrieb)
    b.verbinde(tagesprofil, "lastgang_1", grundlast, "ein")
    b.verbinde(betrieb, "stellgrad", ventilatorstellung, "ein_1")
    b.verbinde(grundlast, "ausgang", ventilatorstellung, "ein_2")
    for ventilator in ventilatoren:
        b.verbinde(ventilatorstellung, "ausgang", ventilator, "stellgroesse")


def lasten_verdrahten(b, tagesprofil, beleuchtung, lasten, raum,
                      gebaeudeheizung=None, kuehlflaeche=None):
    """Innere Lasten und die statischen Geraete an den Raum.

    Der Raum hat je EINEN Eingang fuer Waerme- und Feuchtelast; die Lastenkarte
    zaehlt zusammen, was hineingeht - Personen, Geraete und die Waerme der
    Beleuchtung. Und was er selbst fordert (QH_stat, QK_stat), muss jemand
    entgegennehmen, sonst haelt er seinen Sollwert umsonst; core/pruefung.py
    meldet das.
    """
    b.verbinde(tagesprofil, "lastgang_1", lasten, "belegung")
    if beleuchtung is not None:
        b.verbinde(beleuchtung, "Q_Bel", lasten, "weitere_waerme")
    b.verbinde(lasten, "waermelast", raum, "waermelast")
    b.verbinde(lasten, "feuchtelast", raum, "feuchtelast")
    if gebaeudeheizung is not None:
        b.verbinde(raum, "QH_stat", gebaeudeheizung, "QH_stat")
    if kuehlflaeche is not None:
        b.verbinde(raum, "QK_stat", kuehlflaeche, "QK_stat")


def auswertung_verdrahten(b, verbraucher, bilanz, logger, protokoll=(),
                          pfeile=()):
    """Verbraucher in die Bilanz, benannte Groessen und Karten ins Protokoll.

    Erst die benannten Groessen auf ihre Steckplaetze, dann die Pfeile: Ein
    Pfeil auf den Datenlogger belegt die freien Plaetze der Reihe nach, und zwar
    so viele, wie die Gegenkarte Messwerte anbietet. Stand er zuerst, verschob
    ein neuer Ausgang an einer Karte alle folgenden Nummern - das Anlegen der
    Kuehlflaeche liess so jede Vorlage mit "Der Anschluss 'wert_5' ist schon
    belegt" scheitern.
    """
    for karte in verbraucher:
        b.pfeil(karte, bilanz)
    for karte, groesse, platz in protokoll:
        b.verbinde(karte, groesse, logger, platz)
    for karte in pfeile:
        b.pfeil(karte, logger)
