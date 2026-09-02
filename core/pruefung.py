"""Prüft eine zusammengesteckte Anlage auf stille Fehler.

Es gibt Fehler, die keine Fehlermeldung erzeugen: Die Rechnung läuft durch,
die Zahlen sehen aus wie Zahlen, und trotzdem steht am Ende etwas anderes da,
als der Erbauer gemeint hat. Der häufigste Fall ist ein vergessener Pfeil -
ein Erhitzer, dessen Wärmeleistung nirgends ankommt, taucht in der
Jahresbilanz schlicht nicht auf. Wer die Anlage nicht selbst gebaut hat,
merkt das nie.

Diese Prüfung sucht genau solche Fälle und beschreibt sie in einem Satz,
der sagt, was zu tun ist. Sie urteilt NICHT über die Auslegung (ob ein
Erhitzer zu klein ist, entscheidet der Lauf) und sie verbietet nichts: Jede
Meldung ist ein Hinweis, kein Riegel. Eine Anlage darf unvollständig sein,
solange man weiß, dass sie es ist.

Jede Regel steht als eigene kleine Funktion da und liefert eine Liste von
Meldungen; wer eine neue Regel braucht, schreibt eine Funktion dazu und
trägt sie in REGELN ein.
"""

from core import graph as graph_modul
from core.bausteine import basis

# Rollen, die eine Energie- oder Wassermenge tragen. Genau diese Ausgänge
# gehören in eine Bilanz - alles andere sind Mess- und Stellsignale.
VERBRAUCHSROLLEN = basis.ENERGIEROLLEN


def _reserveports(graph):
    """Die absichtlich freien Anschlüsse dynamischer Karten.

    Ein Sammler, ein Verteiler und ein Raum halten immer einen unbelegten
    Anschluss ihrer Art bereit, damit ein weiterer Pfeil andocken kann
    (core/graph.py, fehlende_ports). Dieser eine ist kein vergessener Pfeil,
    sondern das Angebot der Karte - er darf hier nicht gemeldet werden, sonst
    steht an jeder vollständig verdrahteten Anlage eine Meldung.

    Gemeldet wird dagegen weiterhin eine Gruppe, in der GAR NICHTS hängt: dann
    ist der Anschluss nicht Reserve, sondern schlicht unbenutzt.
    """
    belegt = {v.von_port.id for v in graph.verbindungen}
    belegt |= {v.nach_port.id for v in graph.verbindungen}
    reserve = set()
    for karte in graph.karten.values():
        gruppen = {}
        for port in karte.ports:
            if graph_modul._ist_dynamisch(karte, port):
                gruppen.setdefault((port.basis, port.richtung), []).append(port)
        for ports in gruppen.values():
            if not any(p.id in belegt for p in ports):
                continue  # gar nichts angeschlossen - das ist keine Reserve
            reserve |= {p.id for p in ports if p.id not in belegt}
    return reserve


def _ohne_bilanz(graph):
    """Energieausgänge, die nirgends ankommen.

    Die Bilanzkarte summiert, was AN IHR hängt (core/bausteine/bilanz.py) -
    ein nicht verbundener Verbraucher fehlt deshalb lautlos in der
    Jahressumme.
    """
    belegt = {v.von_port.id for v in graph.verbindungen}
    reserve = _reserveports(graph)
    meldungen = []
    for karte in graph.karten.values():
        for port in karte.ports:
            if port.richtung != basis.AUSGANG or port.rolle not in VERBRAUCHSROLLEN:
                continue
            if port.id in belegt or port.id in reserve:
                continue
            label = basis.port_label(karte.baustein.__class__, port.schluessel, port.rolle)
            meldungen.append(
                {
                    "karte_id": karte.id,
                    "art": "ohne_bilanz",
                    "text": (
                        f"„{karte.name}“ gibt {label} ab, aber der Anschluss ist "
                        f"nicht verbunden - diese Menge fehlt in der Jahresbilanz. "
                        f"Ein Pfeil von der Karte zur Bilanz genügt."
                    ),
                }
            )
    return meldungen


def _luftweg_offen(graph):
    """Lufteingänge ohne Quelle und Luftausgänge ohne Ziel.

    Ein offener Lufteingang bekommt einen Zustand von 0 m³/h und 0 °C - die
    Rechnung läuft weiter und liefert Unsinn. Ausgenommen sind die Karten,
    die den Luftweg naturgemäß beginnen oder beenden (Außenluft, Fortluft):
    sie haben genau eine Seite.
    """
    belegt_ein = {v.nach_port.id for v in graph.verbindungen}
    belegt_aus = {v.von_port.id for v in graph.verbindungen}
    reserve = _reserveports(graph)
    meldungen = []
    for karte in graph.karten.values():
        for port in karte.ports:
            if port.art != basis.LUFT or port.id in reserve:
                continue
            label = basis.port_label(karte.baustein.__class__, port.schluessel, port.rolle)
            if port.richtung == basis.EINGANG and port.id not in belegt_ein:
                meldungen.append(
                    {
                        "karte_id": karte.id,
                        "art": "luft_offen",
                        "text": (
                            f"„{karte.name}“ hat den Lufteingang {label} frei - "
                            f"dort strömt nichts, die Karte rechnet mit 0 m³/h."
                        ),
                    }
                )
            elif port.richtung == basis.AUSGANG and port.id not in belegt_aus:
                meldungen.append(
                    {
                        "karte_id": karte.id,
                        "art": "luft_offen",
                        "text": (
                            f"„{karte.name}“ hat den Luftausgang {label} frei - "
                            f"die Luft endet hier, statt weiterzuströmen."
                        ),
                    }
                )
    return meldungen


def _regler_ohne_wirkung(graph):
    """Regler, deren Stellgröße nirgends ankommt.

    Ein Regler ohne Stellgrößenverbindung rechnet vor sich hin, ohne etwas
    zu bewirken - im Bild sieht die Anlage vollständig aus.
    """
    belegt = {v.von_port.id for v in graph.verbindungen}
    meldungen = []
    for karte in graph.karten.values():
        stellausgaenge = [
            p for p in karte.ports
            if p.richtung == basis.AUSGANG and p.rolle == basis.STELLGROESSE
        ]
        if not stellausgaenge:
            continue
        if any(p.id in belegt for p in stellausgaenge):
            continue
        meldungen.append(
            {
                "karte_id": karte.id,
                "art": "regler_ohne_wirkung",
                "text": (
                    f"„{karte.name}“ regelt, aber keine Stellgröße ist verbunden - "
                    f"die Karte wirkt auf nichts."
                ),
            }
        )
    return meldungen


def _keine_wetterquelle(graph):
    """Eine Anlage ohne Wetterkarte rechnet jede Stunde mit demselben Wetter."""
    if not graph.karten:
        return []
    if any(k.typ == "wetter" for k in graph.karten.values()):
        return []
    return [
        {
            "karte_id": None,
            "art": "kein_wetter",
            "text": (
                "Keine Karte „Wetterdaten“ in der Anlage - ohne sie erfährt "
                "niemand die Außentemperatur, und jede Stunde wird gleich "
                "gerechnet."
            ),
        }
    ]


REGELN = (_luftweg_offen, _ohne_bilanz, _regler_ohne_wirkung, _keine_wetterquelle)


def pruefe(graph):
    """Alle Regeln über eine Anlage - eine flache Liste von Meldungen."""
    meldungen = []
    for regel in REGELN:
        meldungen.extend(regel(graph))
    return meldungen
