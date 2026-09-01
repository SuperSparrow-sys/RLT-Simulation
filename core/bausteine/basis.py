"""Grundtypen aller Bausteine: Parameter, Ports, Luftzustand, Registrierung.

Ein Baustein deklariert sich vollstaendig selbst. Palette, Parameterfenster,
Portanlage in der Datenbank und Ergebnisspalten werden aus dieser Deklaration
erzeugt - ein neuer Kartentyp ist deshalb genau eine neue Datei.
"""

from dataclasses import dataclass

# Portarten
LUFT = "luft"
SIGNAL = "signal"

# Portrichtungen
EINGANG = "ein"
AUSGANG = "aus"

# Portrollen. Sie steuern die automatische Verdrahtung.
ZULUFT = "zuluft"
ABLUFT = "abluft"
AUSSENLUFT = "aussenluft"
FORTLUFT = "fortluft"
UMLUFT = "umluft"
# Neutraler Luftweg: Verteiler und Sammler stehen in jedem Strang, sie duerfen
# sowohl an Zuluft als auch an Abluft haengen.
LUFTWEG = "luftweg"
STELLGROESSE = "stellgroesse"
ISTWERT = "istwert"
SOLLWERT = "sollwert"
MESSWERT = "messwert"

# Energierollen. Sie sorgen dafuer, dass beim Verbinden mit der Bilanzkarte die
# elektrische Leistung auf Strom trifft und nicht auf Waerme.
STROM = "strom"
WAERME = "waerme"
KAELTE = "kaelte"
WASSER = "wasser"

LUFTROLLEN = (ZULUFT, ABLUFT, AUSSENLUFT, FORTLUFT, UMLUFT, LUFTWEG)
ENERGIEROLLEN = (STROM, WAERME, KAELTE, WASSER)


@dataclass(frozen=True)
class Param:
    """Ein einstellbarer Parameter einer Karte."""

    schluessel: str
    label: str
    einheit: str
    vorgabe: float | str
    auswahl: tuple = ()


@dataclass(frozen=True)
class Port:
    """Ein Anschluss einer Karte."""

    schluessel: str
    art: str
    richtung: str
    rolle: str
    dynamisch: bool = False


@dataclass
class Luft:
    """Ein Luftzustand, wie er ueber einen Luft-Port fliesst."""

    V: float = 0.0    # Volumenstrom in m³/h
    T: float = 0.0    # Temperatur in °C
    x: float = 0.0    # absolute Feuchte in g/kg
    dp: float = 0.0   # Druckverlust in Pa

    def kopie(self) -> "Luft":
        return Luft(self.V, self.T, self.x, self.dp)


class Baustein:
    """Oberklasse aller Kartentypen.

    ZUSTAND_UEBER_ITERATION unterscheidet die beiden Arten von Gedaechtnis:

    * False (Vorgabe) - Speichergroessen von Stunde zu Stunde, etwa Raum- und
      Wandtemperatur. Innerhalb einer Stunde sehen alle Iterationen denselben
      Startwert; erst am Ende der Stunde wird fortgeschrieben. Das entspricht
      dem VBA-Unterprogramm Speicher().
    * True - Groessen, die sich ueber die Iterationen selbst aufbauen. Das sind
      die Regler: in der Excel bezieht sich ihr Ausgang auf den eigenen Vorwert
      (K51 = J57 - Regelabweichung/Xp), wodurch sie waehrend der iterativen
      Neuberechnung integrieren. Ohne dieses Kennzeichen wuerde ein Regler je
      Stunde nur einen einzigen Proportionalschritt machen und den Sollwert nie
      erreichen.
    """

    ZUSTAND_UEBER_ITERATION: bool = False
    KENNUNG: str = ""
    NAME: str = ""
    GRUPPE: str = ""
    SYMBOL: str = ""
    PARAMETER: list = []
    PORTS: list = []
    AUSGABEN: list = []

    @classmethod
    def vorgabeparameter(cls) -> dict:
        return {p.schluessel: p.vorgabe for p in cls.PARAMETER}

    @classmethod
    def port(cls, schluessel: str) -> Port:
        for p in cls.PORTS:
            if p.schluessel == schluessel:
                return p
        raise KeyError(f"Port '{schluessel}' gibt es nicht in {cls.KENNUNG}")

    def berechne(self, ein: dict, p: dict, zustand: dict) -> tuple:
        """Rechnet den Baustein fuer eine Stunde.

        ein     -- {portschluessel: Luft oder Zahl}
        p       -- Parameterwerte
        zustand -- Speichergroessen der vorigen Stunde

        Rueckgabe: ({portschluessel und Ausgabegroessen: Wert}, neuer Zustand)
        """
        raise NotImplementedError

    def bedarf(self, aus_bedarf: dict, p: dict) -> dict:
        """Volumenstrombedarf im Rueckwaertslauf.

        Vorgabe: die Summe dessen, was an den Luftausgaengen abgenommen wird,
        wird auf den einzigen Lufteingang gefordert. Bausteine, die den
        Volumenstrom selbst bestimmen - vor allem Ventilatoren - ueberschreiben
        diese Methode.
        """
        summe = sum(aus_bedarf.values())
        eingaenge = [
            p_.schluessel
            for p_ in self.PORTS
            if p_.art == LUFT and p_.richtung == EINGANG
        ]
        if not eingaenge:
            return {}
        return {eingaenge[0]: summe}

    def anfangszustand(self, p: dict) -> dict:
        """Speichergroessen zu Beginn der Simulation."""
        return {}


_REGISTER: dict = {}


def registriere(klasse):
    """Klassendekorator: macht einen Baustein in Palette und Solver bekannt."""
    if not klasse.KENNUNG:
        raise ValueError(f"{klasse.__name__} hat keine KENNUNG")
    vorhanden = _REGISTER.get(klasse.KENNUNG)
    if vorhanden is not None and vorhanden is not klasse:
        raise ValueError(
            f"Die Kennung '{klasse.KENNUNG}' ist schon von {vorhanden.__name__} belegt"
        )
    _REGISTER[klasse.KENNUNG] = klasse
    return klasse


def hole(kennung: str):
    if kennung not in _REGISTER:
        raise KeyError(f"Den Baustein '{kennung}' gibt es nicht")
    return _REGISTER[kennung]


def alle() -> list:
    return list(_REGISTER.values())


def nach_gruppen() -> dict:
    """Alle Bausteine nach Palettengruppe sortiert."""
    gruppen: dict = {}
    for klasse in _REGISTER.values():
        gruppen.setdefault(klasse.GRUPPE, []).append(klasse)
    return gruppen
