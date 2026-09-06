"""Grundtypen aller Bausteine: Parameter, Ports, Luftzustand, Registrierung.

Ein Baustein deklariert sich vollstaendig selbst. Palette, Parameterfenster,
Portanlage in der Datenbank und Ergebnisspalten werden aus dieser Deklaration
erzeugt - ein neuer Kartentyp ist deshalb genau eine neue Datei.
"""

import copy
import math
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

# Menschenlesbare Beschriftung einer Rolle, fuer den Anschluesse-Abschnitt des
# Parameterfensters (siehe core.anlagen._port_label und static/js/panel.js,
# bauePortliste). Ein Anschluss ohne eigene Beschriftung (kein Treffer in
# AUSGABE_LABEL, kein gleichnamiger Parameter) faellt hierauf zurueck statt auf
# seinen rohen, technischen Schluessel.
# Die Signalrollen nennen ihren Wertebereich gleich mit: ein Anfaenger sieht
# sonst "Stellgröße" und weiss nicht, ob dort 0..1, 0..100 oder eine Temperatur
# fliesst. Alle Stellgroessen der Mappe sind auf 0..100 % geklemmt (siehe
# p_regler.klemme, faktor, umkehrglied, maximalwert, anlagenbetrieb), Zeitplan,
# Ferien und Betrieb sind Schalter (0/1), ein Lastgang ist ein Anteil.
ROLLEN_LABEL = {
    ZULUFT: "Zuluft", ABLUFT: "Abluft", AUSSENLUFT: "Außenluft",
    FORTLUFT: "Fortluft", UMLUFT: "Umluft", LUFTWEG: "Luftweg",
    STELLGROESSE: "Stellgröße (0–100 %)", ISTWERT: "Istwert",
    SOLLWERT: "Sollwert", MESSWERT: "Messwert", STROM: "Strom",
    WAERME: "Wärme", KAELTE: "Kälte", WASSER: "Wasser",
    ZEITPLAN: "Zeitplan (1 = Freigabe, 0 = gesperrt)",
    FERIEN: "Ferien (1 = Ferientag, 0 = normaler Tag)",
    LASTGANG: "Lastgang (Anteil 0–1)",
    BETRIEB: "Betrieb (1 = ein, 0 = aus)",
    PROTOKOLL: "Protokollwert",
}


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


def wahl(wert, label):
    """Ein moeglicher Wert eines Auswahlparameters, mit lesbarer Beschriftung
    fuer das Parameterfenster (z.B. wahl("E", "Elektrisch (E)")).

    Reines dict statt eines eigenen Typs: core.anlagen.als_json() und
    routes/lehre.py reichen Param.auswahl unveraendert als JSON weiter
    (list(f.auswahl)) - ein eigener Python-Typ liesse sich dort nicht
    serialisieren, ein dict schon.
    """
    return {"wert": wert, "label": label}


@dataclass(frozen=True)
class Param:
    """Ein einstellbarer Parameter einer Karte.

    `darstellung` und `dezimalstellen` steuern ausschliesslich die Anzeige im
    Parameterfenster (siehe die Konstanten oben) - der Wert selbst, der in der
    Datenbank steht und in berechne() ankommt, ist davon unberuehrt.

    `auswahl` traegt bei AUSWAHL-Parametern die moeglichen Werte SAMT ihrer
    lesbaren Beschriftung (siehe wahl() oben) - die Karte kennt ihre eigenen
    Kuerzel, das Parameterfenster nicht. Damit muss niemand static/js/panel.js
    anfassen, nur weil ein neuer Kartentyp ein Auswahlfeld bekommt.

    `hinweis` ist ein kurzer Erklaersatz, den das Parameterfenster unter dem
    Eingabefeld anzeigt (static/js/panel.js, feldZeile) und den der
    Erklaerbereich /bausteine mit auflistet. Er ist da, wo eine Beschriftung
    allein nicht reicht: was ein Proportionalbereich bewirkt, dass ein
    Lastgang ein ANTEIL der Nennlast ist, oder dass ein Wert die Rechnung gar
    nicht erreicht (beleuchtung.nennbeleuchtung, sequenzregler.xp). Er steht
    aus demselben Grund an der Karte wie `darstellung` und `auswahl`: nur die
    Karte weiss, was fuer ihren eigenen Parameter gilt. Leer lassen, wo die
    Beschriftung samt Einheit schon alles sagt - ein Hinweis an jedem Feld
    liest sich niemand mehr durch.

    `ohne_wirkung` markiert einen Parameter, der in KEINE Formel dieser Karte
    eingeht. Solche Werte gibt es, weil die Excel-Mappe sie neben der Rechnung
    fuehrt (etwa die Nennbeleuchtungsstaerke oder ein Leistungspreis) - sie
    gehen nicht verloren, aber das Parameterfenster zeigt sie als festen Wert
    statt als Eingabefeld an. Ein beschreibbares Feld ohne Wirkung ist die
    unfreundlichste Variante: man traegt etwas ein und wartet auf eine
    Aenderung, die nie kommt. Wer so einen Parameter setzt, sagt im `hinweis`
    dazu, was stattdessen gerechnet wird.

    `minimum`/`maximum` tragen die physikalisch zulaessige Spanne, wenn es eine
    gibt (siehe pruefe_wert() unten) - None heisst "keine Grenze". Sie gehoeren
    an den Parameter und nicht an eine zentrale Prueffunktion, aus demselben
    Grund wie `darstellung` und `auswahl`: nur die Karte weiss, was fuer ihren
    eigenen Parameter gilt. Eine erfundene Grenze ist schlimmer als keine -
    gesetzt wird nur, was die Physik der Groesse tatsaechlich hergibt (ein
    Volumenstrom, eine Leistung, ein Druckverlust und aehnliche Betraege koennen
    nicht negativ sein; ein Anteil oder Prozentwert nicht ueber sein Maximum).
    """

    schluessel: str
    label: str
    einheit: str
    vorgabe: float | str | list | dict
    auswahl: tuple = ()
    darstellung: str = ZAHL
    dezimalstellen: int = 1
    minimum: float | None = None
    maximum: float | None = None
    hinweis: str = ""
    ohne_wirkung: bool = False


def pruefe_wert(param: "Param", wert) -> str | None:
    """Prueft einen einzelnen Wert gegen die Erlaubnis von `param`.

    Rueckgabe: eine lesbare, deutsche Fehlermeldung, wenn der Wert unzulaessig
    ist - sonst None. Bei AUSWAHL-Parametern muss der Wert einer der
    deklarierten Kuerzel sein (param.auswahl); sonst greifen, falls gesetzt,
    param.minimum/maximum. Strukturierte Darstellungsarten (Zeitreihe,
    Monatswerte, Zeitraeume, Anteile, Textliste) tragen weder auswahl noch
    minimum/maximum und werden hier deshalb nie beanstandet - fuer ihre
    einzelnen Eintraege gibt es keine Karte, die eine sinnvolle Grenze kennt.
    """
    if param.darstellung == AUSWAHL:
        zulaessig = {w["wert"] for w in param.auswahl}
        if wert not in zulaessig:
            werte_text = ", ".join(str(w["wert"]) for w in param.auswahl)
            return (
                f"„{wert}“ ist bei {param.label} nicht zulässig "
                f"(erlaubt: {werte_text})"
            )
        return None

    if param.minimum is None and param.maximum is None:
        return None

    try:
        zahl = float(wert)
    except (TypeError, ValueError):
        return f"{param.label} muss eine Zahl sein"
    if param.minimum is not None and zahl < param.minimum:
        return f"{param.label} darf nicht kleiner als {param.minimum:g} sein"
    if param.maximum is not None and zahl > param.maximum:
        return f"{param.label} darf nicht größer als {param.maximum:g} sein"
    return None


def pruefe_parameter(klasse, werte: dict) -> dict:
    """Prueft nur die in `werte` enthaltenen Parameter von `klasse`.

    Rueckgabe: {schluessel: Fehlermeldung} je unzulaessigem Eintrag, leer wenn
    alles zulaessig ist. Ein Schluessel, den `klasse` nicht kennt, wird
    uebergangen - dafuer ist diese Pruefung nicht da (siehe karte_aendern in
    core/anlagen.py, das ohnehin nur bekannte Parameter uebernimmt).
    """
    parameter_nach_schluessel = {p.schluessel: p for p in klasse.PARAMETER}
    fehler = {}
    for schluessel, wert in werte.items():
        param = parameter_nach_schluessel.get(schluessel)
        if param is None:
            continue
        meldung = pruefe_wert(param, wert)
        if meldung is not None:
            fehler[schluessel] = meldung
    return fehler


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
    # Menschenlesbare Beschriftung fuer EINGANGs-Anschluesse, die weder in
    # AUSGABE_LABEL stehen noch einen gleichnamigen Parameter haben. Ohne sie
    # faellt der Anschluesse-Abschnitt des Parameterfensters auf die blosse
    # Rolle zurueck, und ein Raum zeigt zehnmal "Messwert" - unbrauchbar fuer
    # jemanden, der das Fach nicht kennt. AUSGABE_LABEL kann das nicht leisten:
    # dort stehen ausschliesslich AUSGABEN-Schluessel, und core.ergebnisse
    # sowie core.anlagen.messwerte_von() lesen es genau so.
    PORT_LABEL: dict = {}

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

    #: Welche eigenen Ausgaben in bedarf_gestellt() eingehen.
    #:
    #: Der Solver ruft den zweiten Rueckwaertslauf nur dann erneut, wenn sich
    #: etwas geaendert hat, was in ihn eingeht (core/solver.py,
    #: _aktualisiere_gestellte_abnahme). Ohne diese Angabe muss er ALLE
    #: Ausgaben der Karte vergleichen - und dann laeuft er in jedem Durchgang
    #: neu, weil sich irgendeine davon immer noch um ein Tausendstel bewegt.
    #: Gemessen an AX_SIM 2.1 waren das zwei Fuenftel der Rechenzeit fuer ein
    #: Ergebnis, das sich nicht aendert.
    #:
    #: Leer heisst "unbekannt, also alles vergleichen" - die sichere Vorgabe.
    #: Eine Karte mit bedarf_gestellt() sollte sie setzen; sie weiss als
    #: einzige, was sie liest.
    BEDARF_HAENGT_AN: tuple = ()

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


def port_label(klasse, basis_schluessel: str, rolle: str) -> str:
    """Menschenlesbare Beschriftung eines Anschlusses von `klasse`.

    Vier Quellen, in dieser Reihenfolge - jede naeher an der Karte als die
    naechste: die eigene Portbeschriftung (PORT_LABEL), die Beschriftung der
    gleichnamigen Ausgabegroesse (AUSGABE_LABEL), das Label des gleichnamigen
    Parameters, zuletzt die uebersetzte Rolle (ROLLEN_LABEL). Nie der rohe,
    technische Schluessel.

    `basis_schluessel` ist der Grundname ohne die laufende Nummer, die die
    Anlage dynamischen Anschluessen anhaengt (core.graph: PortInstanz.basis) -
    fuer eine Kartenklasse ohne Anlage ist das der Portschluessel selbst.
    Gebraucht von core.anlagen._port_label (Parameterfenster) und
    routes/lehre.py (Erklaerbereich); beide sollen dieselbe Beschriftung
    zeigen.
    """
    for quelle in (klasse.PORT_LABEL, klasse.AUSGABE_LABEL):
        label = quelle.get(basis_schluessel)
        if label:
            return label
    feld = next((p for p in klasse.PARAMETER if p.schluessel == basis_schluessel), None)
    if feld is not None:
        return feld.label
    return ROLLEN_LABEL.get(rolle, rolle)


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


#: Waermetechnische Guete eines Registers im Auslegungspunkt.
#:
#: eps = 1 - exp(-NTU) ist der Anteil der moeglichen Temperaturdifferenz, den
#: ein Register tatsaechlich ueberbrueckt. 0,6 ist fuer ein Rippenrohrregister
#: im Lueftungsbau die uebliche Groessenordnung. Der Wert geht nur schwach in
#: das Ergebnis ein: zwischen eps_nenn 0,5 und 0,7 aendert sich der Exponent
#: der Teillastkennlinie von 0,87 auf 0,91 (nachgerechnet, siehe
#: tests/test_register_teillast.py). Er ist deshalb hier fest und kein
#: Parameter, den jemand einstellen muesste.
REGISTER_GUETE_NENN = 0.6

#: Wie der Waermeuebergang der Luftseite mit der Geschwindigkeit waechst.
#: alpha ~ v^0,8 ist die uebliche Naeherung fuer turbulente Rohrstroemung
#: (Dittus-Boelter); bei einem Rippenrohrregister bestimmt die Luftseite den
#: Uebergang, weil die Rippen dort sitzen.
LUFTSEITE_EXPONENT = 0.8


def uebertragbare_leistung(anteil_ventil: float, V: float, V_nenn: float) -> float:
    """Anteil der Nennleistung, den ein Register bei DIESER Luftmenge schafft.

    Ein Register uebertraegt

        Q = eps * m_L * cp * (T_Wasser - T_Luft),   eps = 1 - exp(-NTU)

    mit NTU = UA / (m_L * cp). Faellt der Volumenstrom, faellt UA mit V^0,8
    (Luftseite), der Massenstrom aber mit V - der Wirkungsgrad eps steigt
    also, die uebertragene Leistung faellt trotzdem, und zwar mit rund V^0,9.

    Frueher rechneten Erhitzer und Kuehler ihre Leistung allein aus der
    Ventilstellung: ein 70-kW-Register gab auch bei einem Fuenftel der
    Luftmenge 70 kW ab, was einer Temperaturerhoehung von ueber 300 K
    entsprach. Die Mappe rechnet ebenso - sie faehrt aber durchgehend auf
    Nennvolumenstrom und kennt den Fall gar nicht. Bei V = V_nenn liefert
    diese Funktion genau 1,0; der Abgleich gegen die Mappe bleibt damit
    unberuehrt.

    Ueber dem Nennvolumenstrom wird nicht extrapoliert: Ein Register waechst
    nicht, wenn man mehr Luft hindurchschickt.
    """
    if V <= 0.0 or V_nenn <= 0.0:
        return 0.0
    verhaeltnis = min(V / V_nenn, 1.0)

    ntu_nenn = -math.log(1.0 - REGISTER_GUETE_NENN)
    ntu = ntu_nenn * verhaeltnis ** (LUFTSEITE_EXPONENT - 1.0)
    guete = 1.0 - math.exp(-ntu)
    return guete * verhaeltnis / REGISTER_GUETE_NENN


def bypassfaktor(bf_nenn: float, V: float, V_nenn: float) -> float:
    """Bypassfaktor eines Kuehlregisters bei DIESER Luftmenge.

    Der Bypassfaktor sagt, welcher Anteil der Luft die Kuehlflaeche nicht
    beruehrt - je kleiner, desto naeher kommt die Austrittsluft der
    Oberflaechentemperatur. Er ist keine Konstante des Bauteils, sondern haengt
    an der Verweilzeit: BF = exp(-NTU), und NTU waechst, wenn die Luft
    langsamer stroemt.

    Mit NTU(r) = NTU_nenn * r^-0,2 (siehe uebertragbare_leistung) folgt

        BF(r) = BF_nenn ^ (r^-0,2)

    Bei Nennvolumenstrom kommt genau der eingestellte Wert heraus. Bei einem
    Fuenftel der Luftmenge sinkt ein Bypassfaktor von 0,55 auf 0,44 - die Luft
    wird kaelter, die insgesamt uebertragene Kaelteleistung faellt trotzdem,
    weil viel weniger Luft durchgeht.

    Nicht beruecksichtigt ist die Abhaengigkeit von der Kaltwassertemperatur
    (ueber die Stoffwerte des Wassers und den wasserseitigen Uebergang). Sie
    ist zweiter Ordnung, solange die Wassermenge konstant bleibt; der
    eingestellte Wert gilt weiterhin als Auslegungswert des Registers.
    """
    if V <= 0.0 or V_nenn <= 0.0:
        return bf_nenn
    if not 0.0 < bf_nenn < 1.0:
        return bf_nenn
    verhaeltnis = min(V / V_nenn, 1.0)
    return bf_nenn ** (verhaeltnis ** (LUFTSEITE_EXPONENT - 1.0))


def strangparameter():
    """Der Parameter, mit dem eine Luftbehandlungskarte ihren Einbauort nennt.

    Ein Erhitzer, ein Kuehler, ein Waescher oder ein Befeuchter ist im
    Abluftkanal genau dasselbe Geraet wie im Zuluftkanal - die Rolle seiner
    Luftanschluesse ist es nicht. Sie entscheidet, welche Pfeile das Programm
    annimmt: (Abluft -> Zuluft) steht in core/graph.py unter VERBOTEN, damit
    ein Pfeil von der Waermerueckgewinnung zur Fortluft nicht versehentlich den
    Zuluftstrang erwischt. Ohne diesen Parameter liesse sich deshalb keine
    dieser Karten in den Abluftstrang setzen - eine adiabate Abluftkuehlung,
    das ueblichste Verfahren der indirekten Verdunstungskuehlung, war schlicht
    nicht baubar.

    Die Rolle bleibt also streng, statt die Anschluesse neutral zu machen: Ein
    Erhitzer sitzt fast immer in der Zuluft, und ein neutraler Anschluss haenge
    ebenso bereitwillig im falschen Strang.

    Karten, die diesen Parameter fuehren, brauchen dazu ein ports_fuer() mit
    strangrolle() - siehe core/bausteine/ventilator.py. core.anlagen zieht die
    Anschluesse nach, wenn der Parameter sich aendert.
    """
    return [
        Param(
            "rolle", "Einbau im Zuluft- oder Abluftstrang", "-", ZULUFT,
            auswahl=(wahl(ZULUFT, "Zuluft"), wahl(ABLUFT, "Abluft")),
            darstellung=AUSWAHL,
        ),
    ]


def strangrolle(p):
    """Die Luftrolle, die zum eingestellten Einbauort gehoert."""
    return ABLUFT if p.get("rolle") == ABLUFT else ZULUFT


def nach_gruppen() -> dict:
    """Alle Bausteine nach Palettengruppe sortiert."""
    gruppen: dict = {}
    for klasse in _REGISTER.values():
        gruppen.setdefault(klasse.GRUPPE, []).append(klasse)
    return gruppen
