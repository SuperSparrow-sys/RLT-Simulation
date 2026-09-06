"""Der Rechenkern.

Je Stunde laufen zwei Durchgaenge:

1. Rueckwaertslauf - vom Ende des Luftwegs zu den Quellen. Jeder Baustein meldet
   ueber 'bedarf', welchen Volumenstrom er an seinen Eingaengen braucht; an
   Verzweigungen summieren sich die Forderungen. Das bildet nach, dass in der
   Excel der Volumenstrom vom Ventilator zur Quelle durchgereicht wird
   (S9 = V9) und sich an Sammelstellen addiert (M9 = S9 + S31).

2. Vorwaertslauf - die Zustaende laufen durch die Kette. Weil der Graph Zyklen
   enthaelt (Waermerueckgewinnung, Raumrueckfuehrung, jeder Regler), wird der
   Durchgang wiederholt, bis sich keine Groesse mehr um mehr als MAX_AENDERUNG
   aendert. Das entspricht Application.Iteration in der Excel.

   Zu Beginn jedes Durchgangs wird der Rueckwaertslauf ein zweites Mal
   gerechnet, diesmal mit den bereits bekannten Stellgroessen. Nur so sieht ein
   Raum seine Abluft im selben Massstab wie seine Zuluft; die ausfuehrliche
   Begruendung steht bei Solver._aktualisiere_gestellte_abnahme().

   Pendelt der Vorwaertslauf zwischen zwei Zustaenden, statt sich einem zu
   naehern, gilt ihr Mittel. Das ist kein Rechenkniff, sondern die einzige
   Aussage, die eine Stundenrechnung ueber einen schneller taktenden
   Zweipunktregler machen kann - und sie haengt an der Anlage statt daran, ob
   MAX_ITERATIONEN gerade oder ungerade ist.

Danach werden die Speichergroessen auf die naechste Stunde uebertragen - die
Entsprechung des VBA-Unterprogramms Speicher().
"""

from dataclasses import dataclass, field
from functools import lru_cache

from core import config
from core.bausteine import basis
from core.bausteine.basis import Luft

BILANZGROESSEN = ("strom_ht", "strom_nt", "waerme", "kaelte", "wasser")

# Wie oft der Rueckwaertslauf ueber die Karten geht (siehe _rueckwaerts).
RUECKWAERTS_DURCHLAEUFE = 3

# Bezugsgroesse fuer Volumenstromaenderungen im Abweichungsmass, in m3/h.
#
# Temperaturen und Feuchten werden absolut gemessen - ein halbes Kelvin ist ein
# halbes Kelvin, gleich wie gross die Anlage ist. Bei Volumenstroemen gilt das
# nicht: Frueher stand hier fest "durch 1000", womit die Schranke
# MAX_AENDERUNG fuer eine Anlage mit 5000 m3/h eine relative Genauigkeit von
# 2e-7 verlangte, fuer eine mit 25 000 m3/h aber 4e-8. Dieselbe Anlage, groesser
# gebaut, haette fuenfmal genauer einschwingen muessen.
#
# Gemessen wird deshalb relativ zum Strom selbst, unterhalb dieser Grenze aber
# weiterhin absolut - sonst geriete ein Nebenstrang mit 50 m3/h an eine
# unerreichbar feine Schranke. Fuer Anlagen mit konstantem Volumenstrom (AX_SIM
# 2.1) aendert sich dadurch nichts: null bleibt null.
VOLUMEN_BEZUG_MIN = 1000.0

# Ab welchem Ausschlag ein erkanntes Pendeln als Takt gilt.
#
# Der Zweitakt wird erkannt, wenn ein Durchgang nicht den vorigen, wohl aber
# den vorvorigen Stand wiederholt. Das trifft auch zu, wenn beide Staende sich
# um drei Tausendstel Kelvin unterscheiden - dann ist die Rechnung praktisch
# eingeschwungen, ihr Mittel von jedem einzelnen nicht zu unterscheiden, und
# die Meldung "eine Zweipunktregelung taktet" fuehrt in die Irre. Ein echter
# Zweipunktregler schlaegt sein Stellglied voll um und bewegt die Temperatur um
# Kelvin, nicht um Tausendstel.
#
# Gemittelt wird trotzdem in beiden Faellen - das ist bei kleinem Ausschlag
# ohnehin folgenlos; nur die Meldung unterbleibt.
TAKT_MINDESTAUSSCHLAG = 0.1


def _volumenabweichung(neu, alt):
    return abs(neu - alt) / max(VOLUMEN_BEZUG_MIN, abs(alt))


@lru_cache(maxsize=None)
def _ist_volumenstrom(name):
    """Traegt diese Ausgabe einen Volumenstrom in m3/h?

    Die Luftbehandlungskarten schreiben ihre Eintrittsmengen als
    'V_<anschluss>' mit; Aussenluft und Fortluft nennen ihre Menge schlicht
    'V'. Beide muessen relativ gemessen werden, sonst zaehlt ein Kubikmeter je
    Stunde so viel wie ein Kelvin - und eine grosse Anlage gilt schon bei
    anderthalb Zehntausendstel Restabweichung als nicht eingeschwungen.

    Gemerkt, weil die Frage im Abweichungsmass millionenfach gestellt wird
    und die Antwort allein am Namen haengt: Ein Jahreslauf ruft sie ueber
    hundert Millionen Mal mit ein paar Dutzend verschiedenen Namen auf.
    """
    return name == "V" or name.startswith("V_")


@dataclass
class Lauf:
    stunden: list = field(default_factory=list)
    bilanz: dict = field(default_factory=dict)
    warnungen: list = field(default_factory=list)
    # Wie viele Durchgaenge jede Stunde gebraucht hat. Ohne diese Zahl ist von
    # aussen nicht zu sehen, wie nah eine Anlage an MAX_ITERATIONEN rechnet -
    # und der Unterschied zwischen "in drei Durchgaengen fertig" und "hundert
    # gebraucht und dann gemittelt" ist der zwischen einem Ergebnis und einer
    # Schaetzung.
    durchgaenge: list = field(default_factory=list)
    # Je Stunde: Ist der ausgewiesene Wert das Mittel zweier Durchgaenge?
    gemittelt: list = field(default_factory=list)
    # Stunden, in denen eine Zweipunktregelung schneller taktet, als eine
    # Stundenrechnung sie aufloesen kann - getrennt von den Warnungen, weil
    # es kein Rechenfehler ist (siehe Solver._rechne_stunde).
    takte: list = field(default_factory=list)

    @property
    def gemittelte_stunden(self):
        """Stunden, deren Ergebnis das Mittel zweier Durchgaenge ist.

        Zwei Wege fuehren dorthin (siehe _rechne_stunde): ein erkannter
        Zweitakt, und eine Rechnung, die die Iterationsgrenze erreicht, ohne
        sich einzuschwingen. In beiden Faellen ist das Mittel die beste
        Aussage, die eine Stundenrechnung machen kann - aber es ist eine andere
        Aussage als bei einer eingeschwungenen Stunde, und wer die Zahlen
        liest, soll wissen, wie viele davon betroffen sind.
        """
        return sum(1 for g in self.gemittelt if g)


@dataclass
class Stundenergebnis:
    """Was eine gerechnete Stunde ueber sich selbst weiss.

    Frueher gab _rechne_stunde() fuenf unbenannte Werte zurueck, und ob das
    Ergebnis ein eingeschwungener Stand oder ein Mittel war, musste die
    aufrufende Stelle aus der Durchgangszahl erraten. Das ging in einem
    Randfall auch schief (MAX_ITERATIONEN = 1: Grenze erreicht, aber kein
    zweiter Stand zum Mitteln da). Jetzt sagt die Stunde es selbst.
    """

    #: Ausgaben aller Karten am Ende der Stunde.
    ausgaben: dict
    #: Speicherzustaende fuer die naechste Stunde.
    zustaende: dict
    #: Wie viele Vorwaertsdurchgaenge gebraucht wurden.
    durchgaenge: int
    #: Groesste verbliebene Aenderung - None, wenn die Stunde eingeschwungen
    #: ist oder ein Zweitakt erkannt wurde (beides sind keine Warnungen).
    abweichung: float | None
    #: Ein erkannter Zweitakt mit nennenswertem Ausschlag.
    taktet: bool
    #: Ausgewiesen ist das Mittel zweier Durchgaenge statt eines Stands.
    gemittelt: bool


class Solver:
    def __init__(self, anlagengraph):
        self.graph = anlagengraph
        self.reihenfolge = anlagengraph.reihenfolge()
        # Nennabnahme je Luftausgang - einmal je Lauf aus dem Rueckwaertslauf.
        self.abnahme = {}
        # Gestellte Abnahme je Luftausgang - je Iteration neu, siehe
        # _aktualisiere_gestellte_abnahme(). Vor dem ersten Vorwaertsdurchgang
        # leer, dann greift die Nennabnahme als Startwert.
        self.gestellte_abnahme = {}
        self._letzte_stellwerte = None
        self._baue_luftindex()

    # -- Rueckwaertslauf --------------------------------------------------

    def _baue_luftindex(self):
        """Bereitet die Topologie des Luftwegs einmal auf.

        Der Rueckwaertslauf laeuft nicht mehr nur einmal je Lauf, sondern auch
        innerhalb des Vorwaertslaufs (siehe _aktualisiere_gestellte_abnahme). In seiner
        urspruenglichen Form kostete jeder Durchgang Karten x Ports x
        Verbindungen; mit diesem Index ist er linear in der Zahl der Luftports.
        """
        ziele = {}
        for v in self.graph.verbindungen:
            ziele.setdefault(v.von_port.id, []).append(v.nach_port.id)

        # Dieselbe Auskunft in der Gegenrichtung, fuer _eingaenge(): Woher
        # bekommt dieser Eingang seinen Wert? Dort wurde bisher fuer JEDEN
        # Anschluss JEDER Karte in JEDEM Durchgang die ganze Verbindungsliste
        # durchsucht - bei hundert Durchgaengen mal 8760 Stunden sind das
        # Milliarden Vergleiche fuer eine Antwort, die sich waehrend des ganzen
        # Laufs nicht aendert. Genommen wird weiterhin die ERSTE passende
        # Verbindung, wie vorher auch.
        self._quelle_von = {}
        for v in self.graph.verbindungen:
            self._quelle_von.setdefault(v.nach_port.id, v)

        belegt = {v.nach_port.id for v in self.graph.verbindungen}

        self._luftausgaenge = {}   # karte_id -> [(schluessel, port_id, ziel-port-ids)]
        self._portnummern = {}     # karte_id -> {schluessel: port_id}
        self._lufteingangsgruppen = {}  # karte_id -> {grundname: (port_ids,)}
        for karte_id, karte in self.graph.karten.items():
            self._portnummern[karte_id] = {p.schluessel: p.id for p in karte.ports}
            self._luftausgaenge[karte_id] = [
                (p.schluessel, p.id, tuple(ziele.get(p.id, ())))
                for p in karte.ports
                if p.art == basis.LUFT and p.richtung == basis.AUSGANG
            ]

            # Nummerierte Lufteingaenge nach ihrem Grundnamen buendeln - und nur
            # die, an denen wirklich ein Pfeil haengt. Ein freier Anschluss darf
            # keinen Anteil abbekommen: was ihm zugeteilt wuerde, fordert
            # niemand stromaufwaerts an und ginge stillschweigend verloren.
            gruppen = {}
            for port in karte.ports:
                if port.art != basis.LUFT or port.richtung != basis.EINGANG:
                    continue
                if port.schluessel == port.basis or port.id not in belegt:
                    continue
                gruppen.setdefault(port.basis, []).append(port.id)
            self._lufteingangsgruppen[karte_id] = {
                name: tuple(ids) for name, ids in gruppen.items()
            }

        # Karten, die im Vorwaertslauf einen anderen Bedarf melden als im
        # Nenn-Rueckwaertslauf (heute nur der Ventilator).
        self._karten_mit_stellwert = [
            karte_id for karte_id, karte in self.graph.karten.items()
            if hasattr(karte.baustein, "bedarf_gestellt")
        ]

    def _rueckwaerts(self, ausgaben=None, topologie_merken=False):
        """Ein Rueckwaertsdurchgang vom Ende des Luftwegs zu den Quellen.

        Ohne 'ausgaben' meldet jede Karte ihren Nennbedarf ('bedarf'); mit
        'ausgaben' darf sie stattdessen den gestellten Bedarf melden
        ('bedarf_gestellt'), der die Stellgroesse des laufenden Vorwaertslaufs
        kennt. Liefert (gefordert je Lufteingang, Abnahme je Luftausgang).
        """
        gefordert = {}  # port_id -> m³/h
        abnahme = {}    # port_id eines Luftausgangs -> m³/h

        # Mehrere Durchlaeufe, weil der Luftweg Zyklen enthaelt und die
        # topologische Reihenfolge sie irgendwo aufbrechen MUSS. In
        # core/vorlagen/testanlage.py fuehrt eine Umluftschleife vom Verteiler
        # zurueck zur Mischkammer; rueckwaerts wird der Verteiler dadurch vor
        # der Mischkammer bearbeitet und kennt deren Umluftforderung noch
        # nicht. Er teilte seinen Strom deshalb nach seinem festen Schluessel
        # auf (40 statt der geforderten 60 Prozent Umluft), und die ganze
        # Anlage rechnete gegen eine Auslegung, die sie nie erreichte.
        #
        # Drei Durchlaeufe reichen fuer jede Schleife, die ueber hoechstens
        # zwei Aufbruchstellen laeuft; 'gefordert' bleibt dabei stehen, sodass
        # jeder Durchlauf auf dem vorigen aufbaut. Mehr kostet nur Zeit: Der
        # Rueckwaertslauf ist eine reine Summenrechnung ohne Physik, und bei
        # einer Anlage ohne Schleife liefert schon der erste Durchlauf das
        # Endergebnis.
        for _ in range(RUECKWAERTS_DURCHLAEUFE):
            gefordert, abnahme = self._ein_rueckwaertsdurchlauf(
                gefordert, ausgaben, topologie_merken
            )
        return gefordert, abnahme

    def _ein_rueckwaertsdurchlauf(self, gefordert, ausgaben, topologie_merken):
        """Ein einzelner Durchlauf des Rueckwaertslaufs - siehe _rueckwaerts()."""
        gefordert = dict(gefordert)
        abnahme = {}

        for karte_id in reversed(self.reihenfolge):
            karte = self.graph.karten[karte_id]
            aus_bedarf = {}
            for schluessel, port_id, zielports in self._luftausgaenge[karte_id]:
                menge = float(sum(gefordert.get(z, 0.0) for z in zielports))
                aus_bedarf[schluessel] = menge
                abnahme[port_id] = menge

            hook = None
            if ausgaben is not None:
                hook = getattr(karte.baustein, "bedarf_gestellt", None)
            if hook is None:
                eigener = karte.baustein.bedarf(aus_bedarf, karte.parameter)
            else:
                eigener = hook(
                    aus_bedarf, karte.parameter, ausgaben.get(karte_id, {})
                )

            # Die Gegenrichtung zu dem, was der Vorwaertslauf laengst tut: dort
            # sammelt eine Karte mit nummerierten Anschluessen ueber das Praefix
            # ihres Eingangs (siehe Sammler.berechne und _eingaenge unten). Der
            # Rueckwaertslauf ordnete dagegen nur exakt nach Schluessel zu -
            # 'bedarf' meldet aber den Grundnamen ('luft_ein'), waehrend die
            # angelegten Ports 'luft_ein_1', 'luft_ein_2' heissen. Die Forderung
            # landete deshalb nirgends: der Raum vor einem Sammler bekam gar
            # keine Abluftmenge zugewiesen, seine Abluft blieb bei 0 m³/h und
            # 0 °C stehen und die Waermerueckgewinnung dahinter gewann nichts
            # zurueck. Trifft der Schluessel keinen Port, gilt er deshalb der
            # ganzen Gruppe gleichnamiger Anschluesse und wird gleichmaessig auf
            # sie verteilt - so wie die Mappe die Abluft des Raums in zwei
            # gleiche Haelften teilt (Anlage!AH33 = AH35 = M42/2).
            nummern = self._portnummern[karte_id]
            gruppen = self._lufteingangsgruppen[karte_id]
            for schluessel, menge in eigener.items():
                if schluessel in nummern:
                    gefordert[nummern[schluessel]] = menge
                    continue
                anschluesse = gruppen.get(schluessel)
                if anschluesse:
                    anteil = menge / len(anschluesse)
                    for port_id in anschluesse:
                        gefordert[port_id] = anteil

            # Der Verteiler braucht die Aufteilung im Vorwaertslauf: Er teilt
            # seinen Strom nach dem, was die einzelnen Gaenge anfordern, und
            # greift nur auf seinen festen Schluessel zurueck, wenn niemand
            # etwas anfordert.
            #
            # Sie wird in BEIDEN Durchgaengen gesetzt, nicht nur im
            # Nenn-Durchgang. Der Grund ist eine Klappe stromabwaerts: Eine
            # Mischkammer fordert ihren Umluftanteil erst, wenn ihre
            # Klappenstellung bekannt ist (bedarf_gestellt), und die entsteht
            # erst im Vorwaertslauf. Wurde die Aufteilung nur einmal am Anfang
            # gemerkt, bekam sie dauerhaft das, was der feste Schluessel des
            # Verteilers hergab - in core/vorlagen/testanlage.py 40 statt der
            # geforderten 60 Prozent Umluft, und die ganze Anlage rechnete
            # gegen eine Auslegung, die sie nie erreichte.
            if hasattr(karte.baustein, "bedarf_je_abgang"):
                karte.baustein.abgaenge = [
                    schluessel for schluessel, _, _ in self._luftausgaenge[karte_id]
                ]
                karte.baustein.bedarf_je_abgang = dict(aus_bedarf)

        return gefordert, abnahme

    def _volumenstroeme(self):
        """Ermittelt je Lufteingang den geforderten Nenn-Volumenstrom.

        Nebenbei wird in self.abnahme festgehalten, wieviel an jedem Luftausgang
        stromabwaerts abgenommen wird. Der Raum braucht das: seine Abluftmengen
        stehen in der Excel nicht bei ihm, sondern kommen vom Abluftventilator
        (Anlage!AH33 und AH35 lesen beide aus M42, dem Volumenstrom des
        Abluftventilators).
        """
        gefordert, self.abnahme = self._rueckwaerts(topologie_merken=True)
        return gefordert

    def _aktualisiere_gestellte_abnahme(self, ausgaben):
        """Aktualisiert self.gestellte_abnahme aus dem laufenden Vorwaertslauf.

        WARUM ES DIESEN ZWEITEN RUECKWAERTSLAUF GIBT
        --------------------------------------------
        Die Mappe reicht an einer Stelle einen Volumenstrom entgegen der
        Luftrichtung durch: der Raum liest seine Abluftmengen beim
        Abluftventilator ab (AH33 = AH35 = M42/2), und M42 ist der GESTELLTE
        Strom M38/100*M31 - genau wie seine Zuluft AH32 = Y20 und AH34 = Y42
        gestellte Stroeme sind. Beide Seiten der Raumbilanz stehen dort also im
        selben Massstab.

        Der Nenn-Rueckwaertslauf kann das nicht liefern: er laeuft einmal je Lauf
        und damit vor jedem Vorwaertslauf, kennt die Stellgroesse also noch gar
        nicht. Er meldete dem Raum deshalb V_max statt u/100*V_max - der Raum sah
        gestellte Zuluft gegen Nennabluft, erfand aus der Differenz eine
        Infiltration und rechnete zu viel Heizlast.

        Der Nennbedarf bleibt trotzdem stehen, denn er ist an seiner Stelle
        richtig: die Bauteile VOR dem Ventilator legt die Mappe auf den Nennstrom
        aus (S13 = S9 = V9 = Y9, AB13 = AB9 = Y9), und die Aussenluftkarte liefert
        ebenfalls den Nennstrom. Dass die Luftmenge ueber den Ventilator springt,
        ist der Mappe getreu. Es gibt also zwei Groessen, nicht eine: die
        Nennabnahme (self.abnahme, fuer die Aussenluft und die Aufteilung im
        Verteiler) und die gestellte Abnahme (hier, fuer alles, was eine Karte
        ueber ihren eigenen Luftausgang erfaehrt).

        Der zweite Durchgang liegt in der Iterationsschleife des Vorwaertslaufs,
        weil die Stellgroesse erst dort entsteht. Das ist kein Kunstgriff,
        sondern dieselbe Rueckkopplung, die die Mappe ueber
        Application.Iteration aufloest: AH33 haengt an M42, M42 an M38, M38 am
        Regler, der Regler an der Raumtemperatur. Im ersten Durchgang liegt noch
        nichts vor; dann gilt der Nennstrom als Startwert, wie bisher.
        """
        stellwerte = [ausgaben.get(k) for k in self._karten_mit_stellwert]
        if stellwerte == self._letzte_stellwerte:
            return  # nichts Neues - der Durchgang wuerde dasselbe ergeben
        self._letzte_stellwerte = stellwerte
        _, self.gestellte_abnahme = self._rueckwaerts(ausgaben=ausgaben)

    # -- Vorwaertslauf ----------------------------------------------------

    def _eingaenge(self, karte, ausgaben, gefordert):
        ein = {}

        # Luftausgaenge zuerst: die Karte erfaehrt, wieviel stromabwaerts von ihr
        # abgenommen wird. Karten, die das nicht brauchen, ignorieren es einfach;
        # der Raum dagegen liest daraus, wie viele Abluftstraenge er hat und wie
        # gross sie sind. Karten mit dynamischen Lufteingaengen muessen deshalb
        # ueber das Praefix ihres EINGANGS sammeln, nicht ueber alle Luftwerte.
        #
        # Massgeblich ist die GESTELLTE Abnahme (AH33 = M42/2), damit der Raum
        # Zu- und Abluft im selben Massstab sieht; solange sie noch nicht
        # vorliegt - im ersten Durchgang einer Stunde - gilt die Nennabnahme als
        # Startwert. Begruendung siehe _aktualisiere_gestellte_abnahme().
        for port in karte.ports:
            if port.art == basis.LUFT and port.richtung == basis.AUSGANG:
                menge = self.gestellte_abnahme.get(port.id)
                if menge is None:
                    menge = self.abnahme.get(port.id, 0.0)
                ein[port.schluessel] = Luft(V=menge)

        for port in karte.ports:
            if port.richtung != basis.EINGANG:
                continue
            v = self._quelle_von.get(port.id)
            if v is None:
                if port.art == basis.LUFT:
                    ein[port.schluessel] = Luft()
                continue
            wert = ausgaben.get(v.von_port.karte_id, {}).get(v.von_port.schluessel)
            if wert is None:
                wert = Luft() if port.art == basis.LUFT else 0.0
            ein[port.schluessel] = wert
        return ein

    def _abweichung(self, alt, neu):
        """Die groesste Aenderung zwischen zwei Durchgaengen.

        Diese Schleife ist die teuerste Stelle des ganzen Programms: Sie laeuft
        je Durchgang einmal ueber jede Ausgabe jeder Karte, und ein Jahreslauf
        macht bis zu 876 000 Durchgaenge. Sie ist deshalb bewusst flach
        geschrieben - _volumenabweichung() steht hier ausgeschrieben, und
        statt max() mit drei Argumenten stehen einzelne Vergleiche. Beides
        liefert dasselbe Ergebnis; nachgemessen bleiben die Jahresbilanzen aller
        Vorlagen bis auf die letzte Stelle gleich.
        """
        groesste = 0.0
        bezug_min = VOLUMEN_BEZUG_MIN
        for karte_id, werte in neu.items():
            vorher = alt.get(karte_id)
            if vorher is None:
                # Eine Karte, die es im Vorstand gar nicht gab - der erste
                # Durchgang einer Stunde. Eine Karte ganz OHNE Ausgaben sagt
                # dazu nichts und wird uebergangen, wie bisher auch.
                if werte:
                    return float("inf")
                continue
            for name, wert in werte.items():
                vor = vorher.get(name)
                if type(wert) is Luft:
                    if type(vor) is not Luft:
                        return float("inf")
                    d = wert.T - vor.T
                    if d < 0.0:
                        d = -d
                    if d > groesste:
                        groesste = d
                    d = wert.x - vor.x
                    if d < 0.0:
                        d = -d
                    if d > groesste:
                        groesste = d
                    alt_V = vor.V
                    if alt_V < 0.0:
                        alt_V = -alt_V
                    d = wert.V - vor.V
                    if d < 0.0:
                        d = -d
                    d /= bezug_min if alt_V < bezug_min else alt_V
                    if d > groesste:
                        groesste = d
                elif isinstance(wert, (int, float)):
                    if not isinstance(vor, (int, float)):
                        return float("inf")
                    d = wert - vor
                    if d < 0.0:
                        d = -d
                    # Die mitgeschriebenen Volumenstroeme (V_<name>, siehe
                    # "Eingangsgroessen mitschreiben" weiter unten) sind reine
                    # Zahlen, tragen aber m3/h. Ohne diesen Zweig zaehlte eine
                    # Aenderung um 1 m3/h so viel wie eine um 1 Kelvin, und
                    # eine grosse Anlage galt schon bei vier Zehntausendstel
                    # Restabweichung als nicht eingeschwungen.
                    if _ist_volumenstrom(name):
                        alt_V = vor if vor >= 0.0 else -vor
                        d /= bezug_min if alt_V < bezug_min else alt_V
                    if d > groesste:
                        groesste = d
        return groesste

    @staticmethod
    def _mittel(a, b):
        """Der Mittelwert zweier Staende - fuer Grenzzyklen.

        Dient sowohl den Ausgaben als auch den Speichergroessen; beide haben
        dieselbe Form {karte_id: {name: wert}}. Wuerde nur die Ausgabe
        gemittelt, startete die naechste Stunde aus einem der beiden Takte -
        also wieder abhaengig davon, welcher Durchgang zuletzt lief.

        Gemittelt wird, was sich mitteln laesst: Zahlen und Luftzustaende.
        Alles andere (Texte, etwa Warnungen einer Karte) wird aus dem
        JUENGEREN Stand uebernommen; einen halben Text gibt es nicht.
        """
        gemittelt = {}
        for karte_id, werte_b in b.items():
            werte_a = a.get(karte_id, {})
            neu = {}
            for name, wert_b in werte_b.items():
                wert_a = werte_a.get(name)
                if isinstance(wert_b, Luft) and isinstance(wert_a, Luft):
                    neu[name] = Luft(
                        V=(wert_a.V + wert_b.V) / 2.0,
                        T=(wert_a.T + wert_b.T) / 2.0,
                        x=(wert_a.x + wert_b.x) / 2.0,
                        dp=(wert_a.dp + wert_b.dp) / 2.0,
                    )
                elif isinstance(wert_b, (int, float)) and isinstance(wert_a, (int, float)):
                    neu[name] = (wert_a + wert_b) / 2.0
                else:
                    neu[name] = wert_b
            gemittelt[karte_id] = neu
        return gemittelt

    def _rechne_stunde(self, stunde, zustaende, gefordert):
        ausgaben = {}
        letzte_abweichung = float("inf")
        # Fuer die Zweitakt-Erkennung weiter unten: der Stand von VOR dem
        # letzten Durchgang und die Zustaende dazu.
        vorvorher = None
        vorherige_zustaende = {}

        # Zwei Arten von Gedaechtnis, siehe Baustein.ZUSTAND_UEBER_ITERATION:
        # Speichergroessen sehen in jeder Iteration den Stundenanfang, Regler
        # sehen ihren eigenen Wert aus der vorigen Iteration.
        iterationszustaende = {
            karte_id: dict(werte) for karte_id, werte in zustaende.items()
        }

        for durchgang in range(config.MAX_ITERATIONEN):
            vorher = {k: dict(v) for k, v in ausgaben.items()}
            neue_zustaende = {}

            # Gestellte Volumenstroeme aus dem vorigen Durchgang nachziehen.
            self._aktualisiere_gestellte_abnahme(ausgaben)

            for karte_id in self.reihenfolge:
                karte = self.graph.karten[karte_id]
                ein = self._eingaenge(karte, ausgaben, gefordert)

                if karte.baustein.ZUSTAND_UEBER_ITERATION:
                    zustand = dict(iterationszustaende.get(karte_id, {}))
                else:
                    zustand = dict(zustaende.get(karte_id, {}))
                zustand["stunde"] = stunde

                # Die Aussenluftkarte hat keinen Lufteingang - sie erfaehrt erst
                # hier, wieviel die Anlage von ihr fordert. Der Wert steht schon
                # aus dem Rueckwaertslauf bereit; ihn ein zweites Mal aus den
                # Verbindungen aufzusummieren waere dieselbe Regel zweimal
                # geschrieben, und die beiden koennten auseinanderlaufen.
                #
                # Es gilt die GESTELLTE Abnahme: durch die Aussenluftklappe
                # stroemt, was der Ventilator ansaugt, nicht was er im
                # Auslegungsfall ansaugen wuerde. Solange die gestellte Abnahme
                # noch nicht vorliegt - vor dem ersten Vorwaertsdurchgang -,
                # dient der Nennstrom als Startwert.
                #
                # Frueher stand hier dauerhaft die Nennabnahme, mit der
                # Begruendung, die Mappe lege die Bauteile vor dem Ventilator
                # auf den Nennstrom aus (S13 = S9 = V9 = Y9). Das verwechselt
                # AUSLEGUNG mit BETRIEB: dass ein Erhitzer fuer 8000 m3/h
                # ausgelegt ist, heisst nicht, dass jede Stunde 8000 m3/h durch
                # ihn stroemen. In AX_SIM 2.1 faellt der Unterschied nicht auf,
                # weil dort alle Luftmengen konstant auf Nennstrom stehen
                # (nachgemessen); in einer Anlage mit Nachtabsenkung erwaermte
                # der Erhitzer dagegen 8000 m3/h, wovon 1600 in den Raum gingen
                # - vier Fuenftel der Waerme wurden erzeugt, abgerechnet und
                # weggeworfen. Siehe tests/test_teillast_luftmenge.py.
                if karte.typ == "aussenluft":
                    ausgang = next(
                        p for p in karte.ports
                        if p.art == basis.LUFT and p.richtung == basis.AUSGANG
                    )
                    zustand["bedarf"] = self.gestellte_abnahme.get(
                        ausgang.id, self.abnahme.get(ausgang.id, 0.0)
                    )

                werte, zustand_neu = karte.baustein.berechne(
                    ein, karte.parameter, zustand
                )
                zustand_neu.pop("stunde", None)
                zustand_neu.pop("bedarf", None)
                ausgaben[karte_id] = werte
                neue_zustaende[karte_id] = zustand_neu
                iterationszustaende[karte_id] = zustand_neu

                # Eingangsgroessen mitschreiben, damit sie protokolliert werden
                # koennen.
                #
                # 'ein' enthaelt zweierlei: die wirklich anliegenden Zustaende an
                # den Lufteingaengen, und an jedem LuftAUSGANG eine Luft, die
                # allein die stromabwaerts abgenommene Menge traegt (siehe
                # _eingaenge). Von der zweiten Art ist nur der Volumenstrom eine
                # Aussage; ihre Temperatur ist nie gesetzt. Frueher stand sie
                # trotzdem als 'T_luft_aus' im Protokoll und war in jeder Stunde
                # jeder Anlage 0 GradC - eine Spalte, die aussah wie ein Messwert
                # und keiner war.
                abnahmemarken = {
                    port.schluessel for port in karte.ports
                    if port.art == basis.LUFT and port.richtung == basis.AUSGANG
                }
                for schluessel, wert in ein.items():
                    if isinstance(wert, Luft):
                        werte.setdefault(f"V_{schluessel}", wert.V)
                        if schluessel not in abnahmemarken:
                            werte.setdefault(f"T_{schluessel}", wert.T)
                    elif isinstance(wert, (int, float)):
                        werte.setdefault(f"in_{schluessel}", wert)
                if "luft_ein" in ein and isinstance(ein["luft_ein"], Luft):
                    werte.setdefault("V_ein", ein["luft_ein"].V)

            letzte_abweichung = self._abweichung(vorher, ausgaben)
            if letzte_abweichung < config.MAX_AENDERUNG:
                return Stundenergebnis(
                    ausgaben, neue_zustaende, durchgang + 1,
                    abweichung=None, taktet=False, gemittelt=False,
                )

            # Grenzzyklus: Der Durchgang wiederholt nicht den vorigen Stand,
            # aber den VORVORIGEN - die Rechnung pendelt zwischen zwei
            # Zustaenden. Das ist kein Rechenfehler, sondern das, was ein
            # Zweipunktregler tut, dessen Stellglied die geregelte Groesse um
            # mehr veraendert als seine Schaltdifferenz breit ist: Er schaltet
            # ein, ueberschreitet den Sollwert und schaltet sofort wieder aus.
            # In der Wirklichkeit taktet er dabei mehrmals je Stunde; eine
            # Stundenrechnung kann das nicht aufloesen.
            #
            # Frueher lief die Schleife in so einem Fall bis zum Anschlag und
            # gab den ZULETZT gerechneten Stand aus. Der haengt dann allein
            # daran, ob MAX_ITERATIONEN gerade oder ungerade ist - bei einem
            # Waescher also "die ganze Stunde an" oder "die ganze Stunde aus",
            # ausgewuerfelt von einer Einstellung, die mit der Anlage nichts zu
            # tun hat. Stattdessen gilt jetzt das Mittel der beiden Zustaende:
            # der Waescher lief eben die halbe Stunde. Das ist der einzige
            # Wert, den eine Stundenrechnung ueber einen Takt sinnvoll angeben
            # kann, und er haengt an der Anlage statt an der Iterationszahl.
            if vorvorher is not None:
                zyklus = self._abweichung(vorvorher, ausgaben)
                if zyklus < config.MAX_AENDERUNG:
                    return Stundenergebnis(
                        self._mittel(vorher, ausgaben),
                        self._mittel(vorherige_zustaende, neue_zustaende),
                        durchgang + 1,
                        abweichung=None,
                        taktet=letzte_abweichung >= TAKT_MINDESTAUSSCHLAG,
                        gemittelt=True,
                    )
            vorvorher = vorher
            vorherige_zustaende = neue_zustaende

        # Die Grenze ist erreicht, ohne dass sich etwas eingependelt hat.
        # Auch hier gilt das Mittel der beiden letzten Durchgaenge, aus
        # demselben Grund wie beim erkannten Zweitakt oben: Der zuletzt
        # gerechnete Stand ist nicht besser als der davor, aber er haengt
        # daran, ob MAX_ITERATIONEN gerade oder ungerade ist. Beim reinen
        # Zweitakt trifft das Mittel den Stundenwert; bei einer Rechnung, die
        # sich ihrem Wert nur langsam naehert, liegen beide Durchgaenge ohnehin
        # dicht beieinander, und das Mittel ist so gut wie jeder von ihnen.
        #
        # Gemessen ueber das Referenzjahr der Excel-Vorlage: Die Abweichung
        # der Jahreswaerme faellt damit von 32,8 auf 15,6 Prozent, weil der
        # taktende Befeuchtungskreis nicht mehr jede Stunde ganz an oder ganz
        # aus gerechnet wird.
        if vorvorher is not None:
            return Stundenergebnis(
                self._mittel(vorher, ausgaben),
                self._mittel(vorherige_zustaende, neue_zustaende),
                config.MAX_ITERATIONEN,
                abweichung=letzte_abweichung,
                taktet=False,
                gemittelt=True,
            )
        # Nur bei MAX_ITERATIONEN = 1 - dann gibt es keinen zweiten Stand, mit
        # dem sich mitteln liesse.
        return Stundenergebnis(
            ausgaben,
            neue_zustaende,
            config.MAX_ITERATIONEN,
            abweichung=letzte_abweichung,
            taktet=False,
            gemittelt=False,
        )

    # -- Lauf -------------------------------------------------------------

    def starte(self, wetterstunden, fortschritt=None, abbruch=None):
        lauf = Lauf()
        lauf.bilanz = {name: 0.0 for name in BILANZGROESSEN}

        zustaende = {
            karte_id: karte.baustein.anfangszustand(karte.parameter)
            for karte_id, karte in self.graph.karten.items()
        }
        gefordert = self._volumenstroeme()

        gesamt = len(wetterstunden)
        for nummer, stunde in enumerate(wetterstunden, start=1):
            if abbruch is not None and abbruch():
                break

            ergebnis = self._rechne_stunde(stunde, zustaende, gefordert)
            ausgaben, zustaende = ergebnis.ausgaben, ergebnis.zustaende
            abweichung = ergebnis.abweichung
            if abweichung is not None:
                lauf.warnungen.append(
                    {
                        "stunde": nummer,
                        "zeitpunkt": str(stunde.get("zeitpunkt", "")),
                        "abweichung": abweichung,
                        # Deutsche Schreibweise wie ueberall, wo eine Zahl
                        # als Text erscheint (siehe core/bericht.py,
                        # format_zahl): dieser Satz steht im Bericht.
                        "text": (
                            f"Stunde {nummer} nicht konvergiert, "
                            f"größte Änderung {abweichung:.4f}".replace(".", ",")
                        ),
                    }
                )
            elif ergebnis.taktet:
                # Kein Fehler, sondern eine Aussage ueber die Anlage: hier
                # taktet eine Zweipunktregelung schneller, als eine
                # Stundenrechnung sie aufloesen kann. Ausgewiesen wird das
                # Mittel beider Zustaende (siehe _rechne_stunde). Als eigene
                # Art von Meldung, damit sie im Bericht nicht neben echten
                # Konvergenzfehlern steht.
                lauf.takte.append(
                    {
                        "stunde": nummer,
                        "zeitpunkt": str(stunde.get("zeitpunkt", "")),
                        "text": (
                            f"Stunde {nummer}: Zweipunktregelung taktet, "
                            f"ausgewiesen ist das Mittel beider Zustände"
                        ),
                    }
                )

            lauf.durchgaenge.append(ergebnis.durchgaenge)
            lauf.gemittelt.append(ergebnis.gemittelt)
            lauf.stunden.append(ausgaben)
            for werte in ausgaben.values():
                for name in BILANZGROESSEN:
                    if name in werte:
                        lauf.bilanz[name] += float(werte[name])

            if fortschritt is not None:
                fortschritt(nummer, gesamt)

        return lauf
