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

Danach werden die Speichergroessen auf die naechste Stunde uebertragen - die
Entsprechung des VBA-Unterprogramms Speicher().
"""

from dataclasses import dataclass, field

from core import config
from core.bausteine import basis
from core.bausteine.basis import Luft

BILANZGROESSEN = ("strom_ht", "strom_nt", "waerme", "kaelte", "wasser")


@dataclass
class Lauf:
    stunden: list = field(default_factory=list)
    bilanz: dict = field(default_factory=dict)
    warnungen: list = field(default_factory=list)


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

            # Verteiler braucht die Aufteilung im Vorwaertslauf. Sie gehoert zur
            # Topologie und wird nur im Nenn-Durchgang gesetzt.
            if topologie_merken and hasattr(karte.baustein, "bedarf_je_abgang"):
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
            quellen = [
                v for v in self.graph.verbindungen if v.nach_port.id == port.id
            ]
            if not quellen:
                if port.art == basis.LUFT:
                    ein[port.schluessel] = Luft()
                continue
            v = quellen[0]
            wert = ausgaben.get(v.von_port.karte_id, {}).get(v.von_port.schluessel)
            if wert is None:
                wert = Luft() if port.art == basis.LUFT else 0.0
            ein[port.schluessel] = wert
        return ein

    def _abweichung(self, alt, neu):
        groesste = 0.0
        for karte_id, werte in neu.items():
            vorher = alt.get(karte_id, {})
            for name, wert in werte.items():
                if isinstance(wert, Luft):
                    vor = vorher.get(name)
                    if not isinstance(vor, Luft):
                        return float("inf")
                    groesste = max(
                        groesste,
                        abs(wert.T - vor.T), abs(wert.x - vor.x),
                        abs(wert.V - vor.V) / 1000.0,
                    )
                elif isinstance(wert, (int, float)):
                    vor = vorher.get(name)
                    if not isinstance(vor, (int, float)):
                        return float("inf")
                    groesste = max(groesste, abs(wert - vor))
        return groesste

    def _rechne_stunde(self, stunde, zustaende, gefordert):
        ausgaben = {}
        letzte_abweichung = float("inf")

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
                # Hier gilt bewusst die NENNabnahme, nicht die gestellte: die
                # Mappe legt die Bauteile vor dem Ventilator auf den Nennstrom
                # aus (S13 = S9 = V9 = Y9). Der Sprung der Luftmenge am
                # Ventilator ist der Mappe getreu.
                if karte.typ == "aussenluft":
                    ausgang = next(
                        p for p in karte.ports
                        if p.art == basis.LUFT and p.richtung == basis.AUSGANG
                    )
                    zustand["bedarf"] = self.abnahme.get(ausgang.id, 0.0)

                werte, zustand_neu = karte.baustein.berechne(
                    ein, karte.parameter, zustand
                )
                zustand_neu.pop("stunde", None)
                zustand_neu.pop("bedarf", None)
                ausgaben[karte_id] = werte
                neue_zustaende[karte_id] = zustand_neu
                iterationszustaende[karte_id] = zustand_neu

                # Eingangsgroessen mitschreiben, damit sie protokolliert werden koennen
                for schluessel, wert in ein.items():
                    if isinstance(wert, Luft):
                        werte.setdefault(f"V_{schluessel}", wert.V)
                        werte.setdefault(f"T_{schluessel}", wert.T)
                    elif isinstance(wert, (int, float)):
                        werte.setdefault(f"in_{schluessel}", wert)
                if "luft_ein" in ein and isinstance(ein["luft_ein"], Luft):
                    werte.setdefault("V_ein", ein["luft_ein"].V)

            letzte_abweichung = self._abweichung(vorher, ausgaben)
            if letzte_abweichung < config.MAX_AENDERUNG:
                return ausgaben, neue_zustaende, durchgang + 1, None

        return (
            ausgaben,
            neue_zustaende,
            config.MAX_ITERATIONEN,
            letzte_abweichung,
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

            ausgaben, zustaende, durchgaenge, abweichung = self._rechne_stunde(
                stunde, zustaende, gefordert
            )
            if abweichung is not None:
                lauf.warnungen.append(
                    {
                        "stunde": nummer,
                        "zeitpunkt": str(stunde.get("zeitpunkt", "")),
                        "abweichung": abweichung,
                        "text": (
                            f"Stunde {nummer} nicht konvergiert, "
                            f"größte Änderung {abweichung:.4f}"
                        ),
                    }
                )

            lauf.stunden.append(ausgaben)
            for werte in ausgaben.values():
                for name in BILANZGROESSEN:
                    if name in werte:
                        lauf.bilanz[name] += float(werte[name])

            if fortschritt is not None:
                fortschritt(nummer, gesamt)

        return lauf
