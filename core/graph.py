"""Karten, Ports, automatische Verdrahtung und Reihenfolge.

Verbunden werden Karten, nicht Ports: ein Pfeil von A nach B erzeugt alle
passenden Portverbindungen auf einmal. Grundlage ist die Rolle jedes Ports.
"""

from dataclasses import dataclass, field

from core.bausteine import basis


@dataclass
class PortInstanz:
    id: int
    karte_id: int
    schluessel: str
    basis: str
    art: str
    richtung: str
    rolle: str
    nummer: int = 1


@dataclass
class KarteInstanz:
    id: int
    typ: str
    name: str
    parameter: dict
    baustein: object
    ports: list = field(default_factory=list)

    def port(self, schluessel):
        for p in self.ports:
            if p.schluessel == schluessel:
                return p
        raise KeyError(f"Port '{schluessel}' gibt es nicht an Karte {self.id}")


@dataclass
class VerbindungInstanz:
    von_port: PortInstanz
    nach_port: PortInstanz


def _deklarierte_ports(klasse, parameter):
    """Beruecksichtigt Karten, deren Ports von Parametern abhaengen."""
    if hasattr(klasse, "ports_fuer"):
        return klasse.ports_fuer(parameter)
    return klasse.PORTS


def erzeuge_ports(klasse, parameter, karte_id, ab_id):
    """Legt die Ports einer frisch angelegten Karte an."""
    ports = []
    laufend = ab_id
    for deklariert in _deklarierte_ports(klasse, parameter):
        schluessel = (
            f"{deklariert.schluessel}_1" if deklariert.dynamisch
            else deklariert.schluessel
        )
        ports.append(
            PortInstanz(
                id=laufend,
                karte_id=karte_id,
                schluessel=schluessel,
                basis=deklariert.schluessel,
                art=deklariert.art,
                richtung=deklariert.richtung,
                rolle=deklariert.rolle,
                nummer=1,
            )
        )
        laufend += 1
    return ports


def _ist_dynamisch(karte, port):
    for deklariert in _deklarierte_ports(basis.hole(karte.typ), karte.parameter):
        if deklariert.schluessel == port.basis:
            return deklariert.dynamisch
    return False


def fehlende_ports(karte, belegt):
    """Laesst dynamische Ports nachwachsen, deren letzter frei gewordener belegt ist."""
    neue = []
    naechste_id = max((p.id for p in karte.ports), default=0) + 1

    gruppen = {}
    for p in karte.ports:
        if _ist_dynamisch(karte, p):
            gruppen.setdefault((p.basis, p.richtung), []).append(p)

    for (basis_name, richtung), ports in gruppen.items():
        if any(p.id not in belegt for p in ports):
            continue
        vorbild = ports[-1]
        nummer = max(p.nummer for p in ports) + 1
        neue.append(
            PortInstanz(
                id=naechste_id,
                karte_id=karte.id,
                schluessel=f"{basis_name}_{nummer}",
                basis=basis_name,
                art=vorbild.art,
                richtung=richtung,
                rolle=vorbild.rolle,
                nummer=nummer,
            )
        )
        naechste_id += 1
    return neue


# Luftwege, die niemals zusammengehoeren. Ohne diese Sperre wuerde ein Pfeil von
# der Waermerueckgewinnung zur Fortluft den Zuluftstrang erwischen.
VERBOTEN = {
    (basis.ZULUFT, basis.ABLUFT),
    (basis.ZULUFT, basis.FORTLUFT),
    (basis.ABLUFT, basis.ZULUFT),
    (basis.ABLUFT, basis.AUSSENLUFT),
    (basis.AUSSENLUFT, basis.ABLUFT),
    (basis.AUSSENLUFT, basis.FORTLUFT),
}

# Luftwege, die sinnvoll aufeinander folgen, ohne dieselbe Rolle zu tragen.
# Umluft ist zurueckgefuehrte ABLUFT - der einzige Umluftanschluss im Programm ist
# der Umlufteingang der Mischkammer. Zuluft gehoert dort nicht hin; sie darf nur
# ueber den Aussenlufteingang in die Mischkammer laufen, und das faengt die
# Vorgabewertung von 1 ab.
FOLGT_AUF = {
    (basis.AUSSENLUFT, basis.ZULUFT),
    (basis.ABLUFT, basis.FORTLUFT),
    (basis.ABLUFT, basis.UMLUFT),
}


def _luftpunkte(von, nach):
    if basis.LUFTWEG in (von.rolle, nach.rolle):
        return 2          # Verteiler und Sammler passen in jeden Strang
    if (von.rolle, nach.rolle) in VERBOTEN:
        return 0
    if von.rolle == nach.rolle or (von.rolle, nach.rolle) in FOLGT_AUF:
        return 2
    return 1


def _signalpunkte(von, nach):
    """Wie gut passen zwei Signalanschluesse zueinander?

    Entscheidend ist, dass MESSWERT NICHT auf MESSWERT passt. Ein Messwert ist eine
    benannte physikalische Groesse - Aussentemperatur, Strahlung, Austrittstemperatur.
    Zwei davon gehoeren nur zusammen, wenn sie denselben Namen tragen. Ohne diese
    Einschraenkung landete die Suedstrahlung auf dem Feuchteeingang eines Raums,
    sobald der gleichnamige Anschluss schon belegt war.
    """
    if von.basis == nach.basis:
        return 3
    if von.rolle == nach.rolle and von.rolle in basis.PAARWEISE_ROLLEN:
        return 2
    if von.rolle == basis.MESSWERT and nach.rolle == basis.ISTWERT:
        return 2
    if von.rolle == basis.MESSWERT and nach.rolle == basis.PROTOKOLL:
        return 1     # niedrig, damit ein Namenstreffer immer vorgeht
    return 0


def _punkte(von, nach):
    """Wie gut passen zwei Ports zueinander? Hoeher ist besser, 0 heisst gar nicht."""
    if von.art != nach.art:
        return 0
    if von.richtung != basis.AUSGANG or nach.richtung != basis.EINGANG:
        return 0
    if von.art == basis.LUFT:
        punkte = _luftpunkte(von, nach)
        return 3 if (punkte and von.basis == nach.basis) else punkte
    return _signalpunkte(von, nach)


def _paare(von_karte, nach_karte, belegt):
    kandidaten = []
    for v in von_karte.ports:
        if v.id in belegt or v.richtung != basis.AUSGANG:
            continue
        for n in nach_karte.ports:
            if n.id in belegt or n.richtung != basis.EINGANG:
                continue
            punkte = _punkte(v, n)
            if punkte:
                kandidaten.append((punkte, v, n))

    # Nach Punkten, dann nach der Reihenfolge, in der die Ports angelegt wurden.
    # Ein Textvergleich waere falsch: 'wert_10' stuende vor 'wert_2'.
    kandidaten.sort(key=lambda k: (-k[0], k[1].id, k[2].id))

    gewaehlt = []
    vergeben = set()
    for _, v, n in kandidaten:
        if v.id in vergeben or n.id in vergeben:
            continue
        gewaehlt.append((v, n))
        vergeben.add(v.id)
        vergeben.add(n.id)
    return gewaehlt, vergeben


def verdrahte(von_karte, nach_karte, belegt):
    """Erzeugt alle Portverbindungen eines Pfeils von einer Karte zur anderen.

    Zusaetzlich wird die Rueckrichtung ergaenzt: schickt A eine Stellgroesse an B,
    so bekommt A den passenden Messwert von B als Istwert zurueck. Damit ist ein
    Regler mit einem einzigen Pfeil vollstaendig angeschlossen.
    """
    vorwaerts, vergeben = _paare(von_karte, nach_karte, belegt)

    schickt_stellgroesse = any(
        v.rolle == basis.STELLGROESSE for v, _ in vorwaerts
    )
    rueckwaerts = []
    if schickt_stellgroesse:
        rueckwaerts, _ = _paare(nach_karte, von_karte, belegt | vergeben)
        rueckwaerts = [
            (v, n) for v, n in rueckwaerts if n.rolle == basis.ISTWERT
        ]

    return vorwaerts + rueckwaerts


def alternativen(von_karte, nach_karte, belegt):
    """Gleich gut bewertete Zuordnungen, die 'verdrahte' NICHT gewaehlt hat.

    Wenn eine Karte mehrere Luftrollen anbietet und die Gegenkarte einen neutralen
    Anschluss hat, ist die Zuordnung echt mehrdeutig: Eine Waermerueckgewinnung an
    einem Sammler koennte den Zuluft- oder den Abluftstrang meinen. 'verdrahte'
    entscheidet dann nach der Reihenfolge, in der die Ports angelegt wurden - das
    ist verlaesslich wiederholbar, aber nicht unbedingt das, was gemeint war.

    Diese Funktion nennt die verworfenen Moeglichkeiten, damit der Editor den Pfeil
    als mehrdeutig kennzeichnen und zur Korrektur anbieten kann. Sie raet nicht
    besser - sie macht sichtbar, dass geraten wurde.
    """
    gewaehlt = {(v.id, n.id) for v, n in verdrahte(von_karte, nach_karte, belegt)}
    genommene_ziele = {n for _, n in gewaehlt}
    genommene_quellen = {v for v, _ in gewaehlt}

    verworfen = []
    for v in von_karte.ports:
        if v.id in belegt or v.richtung != basis.AUSGANG:
            continue
        for n in nach_karte.ports:
            if n.id in belegt or n.richtung != basis.EINGANG:
                continue
            if not _punkte(v, n) or (v.id, n.id) in gewaehlt:
                continue
            # Nur echte Konkurrenz zaehlt: eine Zuordnung, die um denselben
            # Anschluss gestritten und verloren hat.
            if v.id in genommene_quellen or n.id in genommene_ziele:
                verworfen.append((v, n))
    return verworfen


class Anlagengraph:
    """Die Karten einer Anlage samt ihrer Verbindungen."""

    def __init__(self, karten, verbindungen):
        self.karten = karten
        self.verbindungen = verbindungen
        self._rueckkanten = set()
        self._reihenfolge = None

    def kanten(self):
        return [
            (v.von_port.karte_id, v.nach_port.karte_id)
            for v in self.verbindungen
            if v.von_port.karte_id != v.nach_port.karte_id
        ]

    def eingaenge_von(self, karte_id):
        """Alle Verbindungen, die auf diese Karte zeigen."""
        return [v for v in self.verbindungen if v.nach_port.karte_id == karte_id]

    def reihenfolge(self):
        """Topologische Reihenfolge; Zyklen werden an Rueckkanten aufgebrochen.

        Es wird eine Tiefensuche verwendet, damit die Rueckkanten eindeutig
        bestimmt sind. Der Solver iteriert ueber diese Reihenfolge, bis sich
        nichts mehr aendert - die aufgebrochenen Kanten schliessen sich dadurch.
        """
        if self._reihenfolge is not None:
            return self._reihenfolge

        nachfolger = {kid: [] for kid in self.karten}
        for von, nach in self.kanten():
            if nach not in nachfolger[von]:
                nachfolger[von].append(nach)

        WEISS, GRAU, SCHWARZ = 0, 1, 2
        farbe = {kid: WEISS for kid in self.karten}
        ergebnis = []
        rueckkanten = set()

        def besuche(kid):
            farbe[kid] = GRAU
            for folge in sorted(nachfolger[kid]):
                if farbe[folge] == GRAU:
                    rueckkanten.add((kid, folge))
                elif farbe[folge] == WEISS:
                    besuche(folge)
            farbe[kid] = SCHWARZ
            ergebnis.append(kid)

        for kid in sorted(self.karten):
            if farbe[kid] == WEISS:
                besuche(kid)

        self._rueckkanten = rueckkanten
        self._reihenfolge = list(reversed(ergebnis))
        return self._reihenfolge

    def rueckkanten(self):
        self.reihenfolge()
        return self._rueckkanten
