"""Grundtypen aller Bausteine: Parameter, Ports, Luftzustand, Registrierung.

Ein Baustein deklariert sich vollstaendig selbst. Palette, Parameterfenster,
Portanlage in der Datenbank und Ergebnisspalten werden aus dieser Deklaration
erzeugt - ein neuer Kartentyp ist deshalb genau eine neue Datei.
"""

import copy
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

# Signalrollen fuer Betrieb und Protokoll. Ohne sie muesste alles ueber MESSWERT
# laufen, und beim Verbinden passte fast jeder Signalausgang auf fast jeden
# Signaleingang - ein Ventilatoraustritt zum Beispiel auf den Eingang fuer die
# Aussentemperatur eines Raums.
ZEITPLAN = "zeitplan"
FERIEN = "ferien"
LASTGANG = "lastgang"
BETRIEB = "betrieb"
PROTOKOLL = "protokoll"

LUFTROLLEN = (ZULUFT, ABLUFT, AUSSENLUFT, FORTLUFT, UMLUFT, LUFTWEG)
ENERGIEROLLEN = (STROM, WAERME, KAELTE, WASSER)

# Rollen, die nur auf sich selbst passen.
PAARWEISE_ROLLEN = (
    STELLGROESSE, ZEITPLAN, FERIEN, LASTGANG, BETRIEB,
    STROM, WAERME, KAELTE, WASSER,
)


# Darstellungsarten: WIE ein Parameterwert angezeigt und eingegeben wird. Das
# Parameterfenster liest allein diese Angabe (plus Einheit, Beschriftung und
# Nachkommastellen) und richtet sich danach - kein Sonderfall je Kartentyp.
#
# ZAHL        - Zahl mit Einheit; die Anzeige rundet auf `dezimalstellen`, der
#               gespeicherte Wert bleibt exakt (siehe tests/bausteine/test_basis.py).
# PROZENT     - Zahl 0-100, mit Prozentzeichen statt einer Einheit.
# UHRZEIT     - Tagesanteil (0..1, wie in der Excel gerechnet wird), angezeigt
#               und eingegeben als HH:MM. Siehe uhrzeit_anzeigen()/uhrzeit_einlesen().
# AUSWAHL     - einer von Param.auswahl.
# TEXTLISTE   - mehrere freie Textfelder (z.B. Spaltennamen eines Datenloggers).
# ZEITREIHE   - 24 Zahlen, ein Wert je Stunde des Tages.
# MONATSWERTE - 12 Werte, ein Wert je Kalendermonat.
# ZEITRAEUME  - Liste von Zeitraeumen, je als Tag.Monat von/bis.
# ANTEILE     - Aufteilung (in Prozent) auf die dynamischen Anschluesse einer Karte.
ZAHL = "zahl"
PROZENT = "prozent"
UHRZEIT = "uhrzeit"
AUSWAHL = "auswahl"
TEXTLISTE = "textliste"
ZEITREIHE = "zeitreihe"
MONATSWERTE = "monatswerte"
ZEITRAEUME = "zeitraeume"
ANTEILE = "anteile"


@dataclass(frozen=True)
class Param:
    """Ein einstellbarer Parameter einer Karte.

    `darstellung` und `dezimalstellen` steuern ausschliesslich die Anzeige im
    Parameterfenster (siehe die Konstanten oben) - der Wert selbst, der in der
    Datenbank steht und in berechne() ankommt, ist davon unberuehrt.
    """

    schluessel: str
    label: str
    einheit: str
    vorgabe: float | str | list | dict
    auswahl: tuple = ()
    darstellung: str = ZAHL
    dezimalstellen: int = 1


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
    # Menschenlesere Beschriftung fuer AUSGABEN-Schluessel, die als Messwert
    # (rolle=MESSWERT) an einem Ausgangsport haengen. Nur dort gebraucht, wo ein
    # anderer Baustein diesen Wert als Istwert/Sollwert anzapfen koennte - siehe
    # core.anlagen.messwerte_von(). Fehlt ein Eintrag, dient der Schluessel
    # selbst als Beschriftung.
    AUSGABE_LABEL: dict = {}

    @classmethod
    def vorgabeparameter(cls) -> dict:
        """Frische Vorgabewerte fuer eine neue Karte.

        Es wird tief kopiert, weil Vorgaben auch Listen und Tabellen sein
        koennen - Zeitplaene, Lastgaenge, Ferienzeitraeume, Anteile eines
        Verteilers. Ohne Kopie teilten sich alle Karten desselben Typs dasselbe
        Objekt, und die erste Aenderung an einer Karte schluege auf alle
        anderen und auf die Klassenvorgabe durch.
        """
        return {p.schluessel: copy.deepcopy(p.vorgabe) for p in cls.PARAMETER}

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


def uhrzeit_anzeigen(tagesanteil: float) -> str:
    """Ein Tagesanteil (0..1, wie ihn die Excel und die Bausteine rechnen) als
    'HH:MM'.

    Rundet auf die Minute - NUR fuer die Anzeige im Parameterfenster. Der
    gespeicherte Tagesanteil bleibt exakt; ein Aufruf hier veraendert nichts an
    dem Wert, aus dem er gebildet wurde (siehe test_basis.py).
    """
    minuten = round((tagesanteil % 1.0) * 24 * 60) % (24 * 60)
    stunden, minute = divmod(int(minuten), 60)
    return f"{stunden:02d}:{minute:02d}"


def uhrzeit_einlesen(text: str) -> float:
    """Kehrfunktion zu uhrzeit_anzeigen(): 'HH:MM' als Tagesanteil (0..1)."""
    stunden, minute = text.strip().split(":")
    return (int(stunden) * 60 + int(minute)) / (24 * 60)


def druckverlust(V: float, V_nenn: float, dp_nenn: float) -> float:
    """Quadratischer Druckverlust eines durchstroemten Bauteils.

    dp = dp_nenn * (V / V_nenn)^2 - in der Excel dreimal wortgleich als
    Anlage!S135 (Erhitzer), AB135 (Kuehler) und AE135 (Luftwaescher). Bei
    V_nenn = 0 ist der Druckverlust null; die Excel faengt das ebenso ab.
    """
    if not V_nenn:
        return 0.0
    return dp_nenn * (V / V_nenn) ** 2


def nach_gruppen() -> dict:
    """Alle Bausteine nach Palettengruppe sortiert."""
    gruppen: dict = {}
    for klasse in _REGISTER.values():
        gruppen.setdefault(klasse.GRUPPE, []).append(klasse)
    return gruppen
