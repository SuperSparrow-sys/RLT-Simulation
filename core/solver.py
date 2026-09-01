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
        self.abnahme = {}

    # -- Rueckwaertslauf --------------------------------------------------

    def _volumenstroeme(self):
        """Ermittelt je Lufteingang den geforderten Volumenstrom.

        Nebenbei wird in self.abnahme festgehalten, wieviel an jedem Luftausgang
        stromabwaerts abgenommen wird. Der Raum braucht das: seine Abluftmengen
        stehen in der Excel nicht bei ihm, sondern kommen vom Abluftventilator
        (Anlage!AH33 und AH35 lesen beide aus M42, dem Volumenstrom des
        Abluftventilators).
        """
        gefordert = {}  # port_id -> m³/h
        self.abnahme = {}  # port_id eines Luftausgangs -> m³/h

        for karte_id in reversed(self.reihenfolge):
            karte = self.graph.karten[karte_id]
            aus_bedarf = {}
            for port in karte.ports:
                if port.art != basis.LUFT or port.richtung != basis.AUSGANG:
                    continue
                menge = 0.0
                for v in self.graph.verbindungen:
                    if v.von_port.id == port.id:
                        menge += gefordert.get(v.nach_port.id, 0.0)
                aus_bedarf[port.schluessel] = menge
                self.abnahme[port.id] = menge

            eigener = karte.baustein.bedarf(aus_bedarf, karte.parameter)
            for schluessel, menge in eigener.items():
                for port in karte.ports:
                    if port.schluessel == schluessel:
                        gefordert[port.id] = menge

            # Verteiler braucht die Aufteilung im Vorwaertslauf
            if hasattr(karte.baustein, "bedarf_je_abgang"):
                karte.baustein.abgaenge = [
                    p.schluessel for p in karte.ports
                    if p.art == basis.LUFT and p.richtung == basis.AUSGANG
                ]
                karte.baustein.bedarf_je_abgang = dict(aus_bedarf)

        return gefordert

    # -- Vorwaertslauf ----------------------------------------------------

    def _eingaenge(self, karte, ausgaben, gefordert):
        ein = {}

        # Luftausgaenge zuerst: die Karte erfaehrt, wieviel stromabwaerts von ihr
        # abgenommen wird. Karten, die das nicht brauchen, ignorieren es einfach;
        # der Raum dagegen liest daraus, wie viele Abluftstraenge er hat und wie
        # gross sie sind. Karten mit dynamischen Lufteingaengen muessen deshalb
        # ueber das Praefix ihres EINGANGS sammeln, nicht ueber alle Luftwerte.
        for port in karte.ports:
            if port.art == basis.LUFT and port.richtung == basis.AUSGANG:
                ein[port.schluessel] = Luft(V=self.abnahme.get(port.id, 0.0))

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
                            f"groesste Aenderung {abweichung:.4f}"
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
