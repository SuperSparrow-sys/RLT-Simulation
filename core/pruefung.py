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

from datetime import datetime

from core import graph as graph_modul
from core import solver
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


def _stellgroesse_ohne_quelle(graph):
    """Geregelte Karten, deren Stellgröße nirgends herkommt.

    Die Gegenrichtung zu _regler_ohne_wirkung: Dort regelt jemand ins Leere,
    hier wartet jemand auf eine Anweisung, die nie kommt. Eine Karte ohne
    Quelle an ihrer Stellgröße rechnet mit null Prozent - der Erhitzer heizt
    nie, der Kühler kühlt nie, und eine Wärmerückgewinnung liegt vollständig
    im Bypass und überträgt nichts.

    Der Fehler ist besonders still, weil die Luft ordentlich durch die Karte
    fließt: Im Bild ist die Anlage vollständig, die Rechnung läuft durch, und
    nur die Zahlen sind falsch. Genau so blieb in einer Anlage mit
    Wärmerückgewinnung Q_WRG dauerhaft null, während die Heizleistung fast
    doppelt so hoch lag wie ausgelegt.

    Nicht gemeldet wird, wo die Karte denselben Namen auch als Parameter führt
    - der Ventilator etwa läuft ohne Verbindung auf seinem eingestellten Wert,
    das ist Absicht und kein Versäumnis.
    """
    belegt = {v.nach_port.id for v in graph.verbindungen}
    reserve = _reserveports(graph)
    meldungen = []
    for karte in graph.karten.values():
        eigene_parameter = {p.schluessel for p in karte.baustein.PARAMETER}
        # Nur der ERSTE Stelleingang einer Karte ist ihr Hauptschalter. Die
        # Waermerueckgewinnung hat daneben 'stellgroesse_bypass'; dort bedeutet
        # null "Bypass zu" und ist der richtige Vorgabewert, kein Versaeumnis.
        # Am Baustein deklarierte Ports tragen 'schluessel'; die angelegten
        # Anschlussinstanzen tragen zusaetzlich 'basis' - bei dynamischen Ports
        # ist der Schluessel 'ein_2', die Basis 'ein'.
        haupt = next(
            (p.schluessel for p in karte.baustein.PORTS
             if p.richtung == basis.EINGANG and p.rolle == basis.STELLGROESSE),
            None,
        )
        for port in karte.ports:
            if port.richtung != basis.EINGANG or port.rolle != basis.STELLGROESSE:
                continue
            if port.basis != haupt:
                continue
            # Ein freier Reserveanschluss einer dynamischen Karte ist ihr
            # Angebot fuer den naechsten Pfeil, kein vergessener.
            if port.id in reserve:
                continue
            if port.id in belegt or port.basis in eigene_parameter:
                continue
            meldungen.append(
                {
                    "karte_id": karte.id,
                    "art": "stellgroesse_ohne_quelle",
                    "text": (
                        f"„{karte.name}“ bekommt keine Stellgröße an "
                        f"„{port.schluessel}“ - die Karte arbeitet deshalb mit "
                        f"0 % und bleibt ohne Wirkung."
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


def _luftweg_ohne_volumenstrom(graph):
    """Verdrahtete Luftwege, durch die nichts strömt.

    Der schlimmste stille Fehler dieser Art: Jeder Anschluss hängt, die
    Rechnung läuft durch, die Temperaturen sehen richtig aus - und durch den
    ganzen Strang strömen null Kubikmeter, weil kein Ventilator ihn antreibt.
    Ein Luftwäscher meldet dann brav seine Austrittstemperatur und verbraucht
    kein Wasser; eine Wärmerückgewinnung überträgt nichts. Niemand sieht es an
    den Zahlen, weil keine davon falsch aussieht. Aufgefallen ist es beim Bau
    einer Anlage mit Abluftwäscher, der der Abluftventilator fehlte.

    _luftweg_offen() findet das nicht: Dort ist ja alles verbunden.

    Ermittelt wird es, indem die Prüfung EINE Stunde rechnen lässt und
    nachsieht, wo Luft ankommt. Das ist nicht der Umweg, als der es aussieht:
    Der Volumenstrom entsteht im Rückwärtslauf nur STROMAUFWÄRTS eines
    Ventilators - was hinter ihm liegt, bekommt seine Menge erst im
    Vorwärtslauf zugetragen. Beide Hälften nachzubilden hieße, den halben
    Rechenkern ein zweites Mal zu schreiben und ihn auseinanderlaufen zu
    lassen. So steht die Meldung dagegen auf genau der Rechnung, über die sie
    urteilt. Eine Stunde kostet Millisekunden.

    Die Probestunde ist bewusst reizlos - 0 °C, kein Sonnenschein: Gefragt ist
    die Luftmenge, und die hängt an Ventilator und Verdrahtung, nicht am
    Wetter.
    """
    # Der Zeitpunkt ist ein datetime, kein Text: Karten mit Tages- oder
    # Wochenprofil lesen daraus Stunde und Wochentag ab.
    probe = {
        "zeitpunkt": datetime(2024, 1, 1, 12), "t_au": 0.0, "x_au": 4.0,
        "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
    }
    stunde = solver.Solver(graph).starte([probe]).stunden[0]
    belegt_ein = {v.nach_port.id for v in graph.verbindungen}

    ohne_strom = []
    for karte in graph.karten.values():
        werte = stunde.get(karte.id, {})
        for port in karte.ports:
            if port.art != basis.LUFT or port.richtung != basis.EINGANG:
                continue
            if port.id not in belegt_ein:
                continue          # meldet schon _luftweg_offen()
            if werte.get(f"V_{port.schluessel}", 0.0) > 0.0:
                continue
            ohne_strom.append((karte, port))

    if not ohne_strom:
        return []

    # Volumenstrom entsteht ausschliesslich an Karten, die ihn selbst
    # bestimmen: Ihr Bedarf steht auch dann ueber null, wenn stromabwaerts
    # nichts abgenommen wird (core/bausteine/ventilator.py). Das ist die
    # Eigenschaft, auf die es ankommt - nicht der Kartentyp.
    def bestimmt_selbst(karte):
        leer = {
            p.schluessel: 0.0 for p in karte.ports
            if p.art == basis.LUFT and p.richtung == basis.AUSGANG
        }
        gefordert = karte.baustein.bedarf(leer, karte.parameter)
        return any(menge > 0.0 for menge in gefordert.values())

    if not any(bestimmt_selbst(k) for k in graph.karten.values()):
        # Eine Anlage im Bau soll nicht unter Hinweisen verschwinden.
        return [
            {
                "karte_id": ohne_strom[0][0].id,
                "art": "kein_volumenstrom",
                "text": (
                    "In dieser Anlage gibt es keinen Ventilator - durch keinen "
                    "Luftweg strömt etwas. Die Rechnung läuft trotzdem durch "
                    "und liefert überall 0 m³/h."
                ),
            }
        ]

    return [
        {
            "karte_id": karte.id,
            "art": "kein_volumenstrom",
            "text": (
                "Durch den Lufteingang "
                f"{basis.port_label(karte.baustein.__class__, port.schluessel, port.rolle)}"
                f" von „{karte.name}“ strömt nichts: Kein Ventilator zieht oder "
                "drückt Luft durch diesen Strang. Die Karte rechnet mit "
                "0 m³/h, ohne es zu melden."
            ),
        }
        for karte, port in ohne_strom
    ]


def _raumforderung_ohne_abnehmer(graph):
    """Ein Raum fordert Wärme oder Kälte, und niemand nimmt sie entgegen.

    Der einfache Raum meldet über QH_stat, wieviel eine statische Heizung
    beisteuern müsste, damit er seinen Sollwert hält - und über QK_stat
    dasselbe für eine Kühlfläche. Hängt dort kein Pfeil, hält er den Sollwert
    trotzdem: Die Rechnung setzt ihn schlicht auf den Sollwert. Die Energie
    dafür taucht dann in keiner Bilanz auf. Das Gebäude heizt sich umsonst.

    Der Fehler ist besonders tückisch, weil er die Zahlen nicht falsch
    aussehen lässt, sondern zu GUT: Neun der zehn Anlagenvorlagen liefen so,
    und ihr Heizwärmebedarf lag dadurch bei einem Bruchteil dessen, was ein
    Gebäude dieser Hülle braucht. Aufgefallen ist es erst, als eine Vorlage
    unter ihr Erwartungsband fiel.

    Gemeldet wird nur, wo der zugehörige Sollwert überhaupt gesetzt ist: Eine
    Kühlfläche mit sollwert_kuehl = 0 gibt es nicht, und ihr Anschluss soll
    dann auch nicht angemahnt werden.
    """
    sollwerte = {"QH_stat": "sollwert_stat", "QK_stat": "sollwert_kuehl"}
    belegt_aus = {v.von_port.id for v in graph.verbindungen}

    meldungen = []
    for karte in graph.karten.values():
        for port in karte.ports:
            if port.richtung != basis.AUSGANG or port.basis not in sollwerte:
                continue
            if port.id in belegt_aus:
                continue
            sollwert = karte.parameter.get(sollwerte[port.basis], 0.0)
            if not sollwert:
                continue
            was = "Heizung" if port.basis == "QH_stat" else "Kühlfläche"
            # Deutsche Schreibweise wie ueberall, wo eine Zahl als Text
            # erscheint - tests/test_bericht.py haelt das fest.
            als_text = f"{sollwert:.1f}".replace(".", ",")
            meldungen.append({
                "karte_id": karte.id,
                "art": "forderung_ohne_abnehmer",
                "text": (
                    f"„{karte.name}“ meldet über {port.schluessel}, wieviel eine "
                    f"statische {was} beisteuern müsste - dort hängt aber kein "
                    f"Pfeil. Der Raum hält seinen Sollwert von {als_text} °C "
                    "trotzdem, und die Energie dafür steht in keiner Bilanz."
                ),
            })
    return meldungen


REGELN = (
    _luftweg_offen, _ohne_bilanz, _regler_ohne_wirkung,
    _stellgroesse_ohne_quelle, _keine_wetterquelle,
    _luftweg_ohne_volumenstrom, _raumforderung_ohne_abnehmer,
)


def pruefe(graph):
    """Alle Regeln über eine Anlage - eine flache Liste von Meldungen."""
    meldungen = []
    for regel in REGELN:
        meldungen.extend(regel(graph))
    return meldungen
