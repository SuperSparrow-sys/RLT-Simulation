"""Eine kleine, rechenbare Beispielanlage je Kartentyp.

34 einzelne Anlagen von Hand hinzuschreiben (wie core/vorlagen/ax_sim_2_1.py es
für die eine mitgelieferte Referenzanlage tut) wäre auf Dauer unwartbar: jede
Änderung an einem Baustein müsste an 34 Stellen nachgezogen werden. Der Ausweg
hier ist kein eigenes Beschreibungsformat, sondern eine Handvoll wiederkehrender
Bauteilgruppen (_wetter, _aussenluft, _antrieb, _zuluftventilator, _raum,
_fortluft, _bilanz) plus - je Kartentyp - eine kurze Funktion bau_<typ>(), die
diese Gruppen zu genau der Anlage zusammensteckt, die diesen einen Baustein in
seinem natürlichen Zusammenhang zeigt. Das ist knapper als 34 unabhängige
Vorlagen, bleibt aber lesbar: jede bau_<typ>()-Funktion liest sich wie eine
Kurzbeschreibung der Anlage selbst, nicht wie eine Deklaration in einer
eigenen kleinen Sprache.

Verbunden wird wie überall im Programm: ein Pfeil zwischen zwei Karten
verdrahtet die passenden Anschlüsse automatisch (core/graph.py); nur wo das
mehrdeutig wäre - ein Raum bietet mehrere Messwerte an, ein Regler soll
absichtlich in vertauschter Wirkrichtung hängen - wird über
anlagen.verbindung_anlegen() gezielt verbunden, genau wie in ax_sim_2_1.py.
"""

from core import anlagen

NAME_PROJEKT = "Bausteine"
NOTIZ_PROJEKT = (
    "Beispielanlagen aus der Erklärung. Jede Anlage zeigt genau einen "
    "Kartentyp in seinem natürlichen Zusammenhang."
)


def projekt_bausteine():
    """Liefert die Kennung des Sammelprojekts für Beispielanlagen, legt es
    beim ersten Aufruf an."""
    for projekt in anlagen.projekte():
        if projekt["name"] == NAME_PROJEKT:
            return projekt["id"]
    return anlagen.projekt_anlegen(NAME_PROJEKT, NOTIZ_PROJEKT)


class _Bau:
    """Dünner Wrapper um core.anlagen für die Anlage, die gerade entsteht."""

    def __init__(self, anlage_id):
        self.anlage_id = anlage_id

    def karte(self, typ, x, y, name, **parameter):
        return anlagen.karte_anlegen(self.anlage_id, typ, x, y, parameter, name)

    def pfeil(self, von, nach):
        anlagen.pfeil_anlegen(self.anlage_id, von, nach)

    def verbinde(self, von, von_schluessel, nach, nach_schluessel):
        anlagen.verbindung_anlegen(
            self.anlage_id,
            anlagen.port_id(von, von_schluessel),
            anlagen.port_id(nach, nach_schluessel),
        )


def _anlage(projekt_id, name, notiz):
    anlage_id = anlagen.anlage_anlegen(projekt_id, name, notiz=notiz)
    return _Bau(anlage_id)


# -- Wiederkehrende Bauteilgruppen -------------------------------------------

def _wetter(b, x=40, y=40):
    return b.karte("wetter", x, y, "Wetterdaten")


def _aussenluft(b, wetter, x=40, y=200, name="Außenluft"):
    au = b.karte("aussenluft", x, y, name)
    b.pfeil(wetter, au)
    return au


def _antrieb(b, x=40, y=560):
    """Wochenzeitplan -> Anlagenbetrieb: ein einfaches, realistisches
    Betriebssignal (05-22 Uhr werktags, Vorgabewerte), das anderswo als
    Stellgröße dient. Fast keine Karte in der mitgelieferten Referenzanlage
    (core/vorlagen/ax_sim_2_1.py) hängt an einer festen Stellgröße - fast
    alle hängen letztlich am Anlagenbetrieb."""
    zeitplan = b.karte("wochenzeitplan", x, y, "Wochenzeitplan")
    betrieb = b.karte("anlagenbetrieb", x + 180, y, "Anlagenbetrieb")
    b.pfeil(zeitplan, betrieb)
    return betrieb


def _zuluftventilator(b, x, y, name="Zuluftventilator", V_max=4000.0):
    return b.karte(
        "ventilator", x, y, name, rolle="zuluft", V_max=V_max, dp_max=800.0,
        dp_konst=800.0, PE_max=2.2, regelart="F", stellgroesse=100.0,
    )


def _abluftventilator(b, x, y, name="Abluftventilator", V_max=4000.0):
    return b.karte(
        "ventilator", x, y, name, rolle="abluft", V_max=V_max, dp_max=600.0,
        dp_konst=600.0, PE_max=1.8, regelart="F", stellgroesse=100.0,
    )


def _raum(b, x, y, wetter, name="Raum"):
    raum = b.karte(
        "einfacher_raum", x, y, name, spez_transmission=0.3, sollwert_stat=15.0
    )
    b.pfeil(wetter, raum)
    return raum


def _fortluft(b, x, y):
    return b.karte("fortluft", x, y, "Fortluft")


def _bilanz(b, x, y):
    return b.karte(
        "bilanz", x, y, "Energiepreise und Bilanz",
        preis_strom_ht=150.0, preis_strom_nt=150.0, preis_waerme=50.0,
        preis_kaelte=50.0, preis_wasser=4.0,
    )


def _minimalluft(b, wetter, x=440):
    """Der denkbar kleinste Luftweg: Außenluft -> Ventilator. Für Karten,
    deren Beispiel gar keinen eigenen Luftweg braucht, sondern nur einen
    echten Ventilator zum Steuern (Zeit- und Betriebskarten, reine
    Signalbausteine). Ohne einen Raum dazwischen darf ein Zuluftventilator
    nicht direkt an die Fortluft - Zuluft und Fortluft sind unterschiedliche
    Wege (core/graph.py, VERBOTEN) -, deshalb endet der Weg hier bewusst am
    Ventilator."""
    au = _aussenluft(b, wetter)
    vent = _zuluftventilator(b, x, 200, V_max=2000.0)
    b.pfeil(au, vent)
    return vent


def _luftbehandlung_grund(projekt_id, name, notiz):
    """Wetter, Außenluft und ein Anlagenbetrieb - der gemeinsame Anfang aller
    Beispiele aus der Gruppe 'Luftbehandlung'."""
    b = _anlage(projekt_id, name, notiz)
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    betrieb = _antrieb(b)
    return b, wetter, au, betrieb


# -- Quellen und Senken -------------------------------------------------

def bau_aussenluft(projekt_id):
    b = _anlage(projekt_id, "Außenluft", "Beispiel zum Baustein Außenluft.")
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    vent = _zuluftventilator(b, 440, 200)
    b.pfeil(au, vent)
    raum = _raum(b, 640, 200, wetter)
    b.pfeil(vent, raum)
    fort = _fortluft(b, 840, 200)
    b.pfeil(raum, fort)
    return b.anlage_id


def bau_fortluft(projekt_id):
    b = _anlage(projekt_id, "Fortluft", "Beispiel zum Baustein Fortluft.")
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    zu = _zuluftventilator(b, 440, 120, "Zuluftventilator")
    b.pfeil(au, zu)
    raum = _raum(b, 640, 200, wetter)
    b.pfeil(zu, raum)
    ab = _abluftventilator(b, 840, 280, "Abluftventilator")
    b.pfeil(raum, ab)
    fort = _fortluft(b, 1040, 280)
    b.pfeil(ab, fort)
    return b.anlage_id


def bau_wetter(projekt_id):
    b = _anlage(projekt_id, "Wetterdaten", "Beispiel zum Baustein Wetterdaten.")
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    zu = _zuluftventilator(b, 440, 120, "Zuluftventilator")
    b.pfeil(au, zu)
    raum = b.karte("raum", 640, 200, "Raum")
    b.pfeil(zu, raum)
    b.pfeil(wetter, raum)  # T_AU, F_AU und die fünf Strahlungssignale auf einmal
    fort = _fortluft(b, 840, 200)
    b.pfeil(raum, fort)
    logger = b.karte(
        "datenlogger", 640, 40, "Datenlogger",
        namen=["T Außenluft", "F Außenluft", "Strahlung Süd"] + [""] * 7,
        einheiten=["°C", "g/kg", "kW"] + [""] * 7,
    )
    b.verbinde(wetter, "T_AU", logger, "wert_1")
    b.verbinde(wetter, "F_AU", logger, "wert_2")
    b.verbinde(wetter, "QH_S", logger, "wert_3")
    return b.anlage_id


# -- Luftbehandlung -----------------------------------------------------

def bau_erhitzer(projekt_id):
    b, wetter, au, betrieb = _luftbehandlung_grund(
        projekt_id, "Erhitzer", "Beispiel zum Baustein Erhitzer."
    )
    erhitzer = b.karte(
        "erhitzer", 440, 200, "Erhitzer", V_nenn=4000.0, dp_nenn=150.0, QH_max=40.0
    )
    b.pfeil(au, erhitzer)
    b.pfeil(betrieb, erhitzer)
    vent = _zuluftventilator(b, 640, 200, V_max=4000.0)
    b.pfeil(erhitzer, vent)
    raum = _raum(b, 840, 200, wetter)
    b.pfeil(vent, raum)
    fort = _fortluft(b, 1040, 120)
    b.pfeil(raum, fort)
    bil = _bilanz(b, 1040, 280)
    b.pfeil(erhitzer, bil)
    b.pfeil(vent, bil)
    return b.anlage_id


def bau_kuehler(projekt_id):
    b, wetter, au, betrieb = _luftbehandlung_grund(
        projekt_id, "Kühler", "Beispiel zum Baustein Kühler."
    )
    kuehler = b.karte(
        "kuehler", 440, 200, "Kühler", V_nenn=4000.0, dp_nenn=150.0, QK_nenn=30.0,
        T_KW_mittel=8.0,
    )
    b.pfeil(au, kuehler)
    b.pfeil(betrieb, kuehler)
    vent = _zuluftventilator(b, 640, 200, V_max=4000.0)
    b.pfeil(kuehler, vent)
    raum = _raum(b, 840, 200, wetter)
    b.pfeil(vent, raum)
    fort = _fortluft(b, 1040, 120)
    b.pfeil(raum, fort)
    bil = _bilanz(b, 1040, 280)
    b.pfeil(kuehler, bil)
    b.pfeil(vent, bil)
    return b.anlage_id


def bau_dampfbefeuchter(projekt_id):
    b, wetter, au, betrieb = _luftbehandlung_grund(
        projekt_id, "Dampfbefeuchter", "Beispiel zum Baustein Dampfbefeuchter."
    )
    befeuchter = b.karte(
        "dampfbefeuchter", 440, 200, "Dampfbefeuchter",
        max_leistung=20.0, dampfart="E", absalzverlust=10.0,
    )
    b.pfeil(au, befeuchter)
    b.pfeil(betrieb, befeuchter)
    vent = _zuluftventilator(b, 640, 200, V_max=4000.0)
    b.pfeil(befeuchter, vent)
    raum = _raum(b, 840, 200, wetter)
    b.pfeil(vent, raum)
    fort = _fortluft(b, 1040, 120)
    b.pfeil(raum, fort)
    bil = _bilanz(b, 1040, 280)
    b.pfeil(befeuchter, bil)
    b.pfeil(vent, bil)
    return b.anlage_id


def bau_luftwaescher(projekt_id):
    b, wetter, au, betrieb = _luftbehandlung_grund(
        projekt_id, "Luftwäscher", "Beispiel zum Baustein Luftwäscher."
    )
    waescher = b.karte(
        "luftwaescher", 440, 200, "Luftwäscher", V_nenn=4000.0, dp_nenn=50.0,
        pumpenart="H",
    )
    b.pfeil(au, waescher)
    b.pfeil(betrieb, waescher)
    vent = _zuluftventilator(b, 640, 200, V_max=4000.0)
    b.pfeil(waescher, vent)
    raum = _raum(b, 840, 200, wetter)
    b.pfeil(vent, raum)
    fort = _fortluft(b, 1040, 120)
    b.pfeil(raum, fort)
    bil = _bilanz(b, 1040, 280)
    b.pfeil(waescher, bil)
    b.pfeil(vent, bil)
    return b.anlage_id


def bau_wrg(projekt_id):
    b, wetter, au, betrieb = _luftbehandlung_grund(
        projekt_id, "Wärmerückgewinnung", "Beispiel zum Baustein Wärmerückgewinnung."
    )
    wrg = b.karte(
        "wrg", 440, 200, "Wärmerückgewinnung", V_nenn=4000.0, dp_WRG_nenn=150.0,
        dp_Bypass_nenn=40.0, rueckwaermzahl=75.0, rueckfeuchtzahl=0.0,
    )
    b.pfeil(au, wrg)          # trifft eindeutig zuluft_ein (Rolle Außenluft)
    b.pfeil(betrieb, wrg)     # trifft 'stellgroesse', nicht den Bypass daneben
    vent = _zuluftventilator(b, 640, 120, V_max=4000.0)
    b.pfeil(wrg, vent)
    raum = _raum(b, 840, 200, wetter)
    b.pfeil(vent, raum)
    b.pfeil(raum, wrg)        # Abluft des Raums zurück in die WRG
    fort = _fortluft(b, 1040, 200)
    b.pfeil(wrg, fort)
    bil = _bilanz(b, 1040, 360)
    b.pfeil(vent, bil)
    return b.anlage_id


def bau_mischkammer(projekt_id):
    b, wetter, au, betrieb = _luftbehandlung_grund(
        projekt_id, "Mischkammer", "Beispiel zum Baustein Mischkammer."
    )
    mk = b.karte("mischkammer", 440, 200, "Mischkammer", max_umluft=80.0)
    b.pfeil(au, mk)           # trifft aussenluft_ein
    b.pfeil(betrieb, mk)      # trifft umluftanteil
    vent = _zuluftventilator(b, 640, 120, V_max=4000.0)
    b.pfeil(mk, vent)
    raum = _raum(b, 840, 200, wetter)
    b.pfeil(vent, raum)
    b.pfeil(raum, mk)         # Abluft des Raums als Umluft zurück, umluft_ein ist jetzt frei
    bil = _bilanz(b, 1040, 200)
    b.pfeil(vent, bil)
    return b.anlage_id


def bau_ventilator(projekt_id):
    b, wetter, au, betrieb = _luftbehandlung_grund(
        projekt_id, "Ventilator", "Beispiel zum Baustein Ventilator."
    )
    vent = _zuluftventilator(b, 440, 200, "Zuluftventilator", V_max=4000.0)
    b.pfeil(au, vent)
    b.pfeil(betrieb, vent)
    raum = _raum(b, 640, 200, wetter)
    b.pfeil(vent, raum)
    fort = _fortluft(b, 840, 200)
    b.pfeil(raum, fort)
    bil = _bilanz(b, 840, 360)
    b.pfeil(vent, bil)
    return b.anlage_id


# -- Verteilung --------------------------------------------------------

def bau_verteiler(projekt_id):
    b = _anlage(projekt_id, "Verteiler", "Beispiel zum Baustein Verteiler.")
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    vt = b.karte("verteiler", 440, 200, "Verteiler")
    b.pfeil(au, vt)
    v1 = _zuluftventilator(b, 640, 120, "Ventilator Gang 1", V_max=2000.0)
    b.pfeil(vt, v1)
    v2 = _zuluftventilator(b, 640, 280, "Ventilator Gang 2", V_max=3000.0)
    b.pfeil(vt, v2)
    # Ein Zuluftventilator darf nicht direkt an die Fortluft (core/graph.py,
    # VERBOTEN) - ohne eigenen Raum je Gang endet der Weg hier bewusst an den
    # beiden Ventilatoren; sie zeigen den aufgeteilten Volumenstrom bereits.
    return b.anlage_id


def bau_sammler(projekt_id):
    b = _anlage(projekt_id, "Sammler", "Beispiel zum Baustein Sammler.")
    wetter = _wetter(b)
    au1 = _aussenluft(b, wetter, 40, 120, "Außenluft Gang 1")
    au2 = _aussenluft(b, wetter, 40, 280, "Außenluft Gang 2")
    v1 = _zuluftventilator(b, 240, 120, "Ventilator Gang 1", V_max=2000.0)
    b.pfeil(au1, v1)
    v2 = _zuluftventilator(b, 240, 280, "Ventilator Gang 2", V_max=3000.0)
    b.pfeil(au2, v2)
    sm = b.karte("sammler", 440, 200, "Sammler")
    b.pfeil(v1, sm)
    b.pfeil(v2, sm)
    fort = _fortluft(b, 640, 200)
    b.pfeil(sm, fort)
    return b.anlage_id


# -- Räume ------------------------------------------------------------

def bau_einfacher_raum(projekt_id):
    b = _anlage(projekt_id, "Einfacher Raum", "Beispiel zum Baustein Einfacher Raum.")
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    vent = _zuluftventilator(b, 440, 200, V_max=3000.0)
    b.pfeil(au, vent)
    raum = _raum(b, 640, 200, wetter, "Raum")
    b.pfeil(vent, raum)
    fort = _fortluft(b, 840, 200)
    b.pfeil(raum, fort)
    return b.anlage_id


def bau_statische_heizung(projekt_id):
    b = _anlage(
        projekt_id, "Statische Heizung", "Beispiel zum Baustein Statische Heizung."
    )
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    vent = _zuluftventilator(b, 440, 200, V_max=1000.0)
    b.pfeil(au, vent)
    raum = b.karte(
        "einfacher_raum", 640, 200, "Raum", spez_transmission=0.6, sollwert_stat=20.0
    )
    b.pfeil(vent, raum)
    b.pfeil(wetter, raum)
    fort = _fortluft(b, 840, 120)
    b.pfeil(raum, fort)
    heizung = b.karte(
        "statische_heizung", 640, 360, "Statische Heizung", QH_nenn=15.0
    )
    b.verbinde(raum, "QH_stat", heizung, "QH_stat")
    bil = _bilanz(b, 840, 360)
    b.pfeil(heizung, bil)
    return b.anlage_id


def bau_raum(projekt_id):
    b = _anlage(projekt_id, "Raum", "Beispiel zum Baustein Raum.")
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    vent = _zuluftventilator(b, 440, 200, V_max=3000.0)
    b.pfeil(au, vent)
    raum = b.karte("raum", 640, 200, "Raum")
    b.pfeil(vent, raum)
    b.pfeil(wetter, raum)
    fort = _fortluft(b, 840, 200)
    b.pfeil(raum, fort)
    return b.anlage_id


# -- Regelung -----------------------------------------------------------

def bau_p_regler(projekt_id):
    b = _anlage(projekt_id, "P-Regler", "Beispiel zum Baustein P-Regler.")
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    erhitzer = b.karte(
        "erhitzer", 440, 200, "Erhitzer", V_nenn=3000.0, dp_nenn=120.0, QH_max=30.0
    )
    b.pfeil(au, erhitzer)
    regler = b.karte(
        "p_regler", 440, 40, "Regler Erhitzer", xp_1=5.0, xp_2=3.0, sollwert_2=18.0
    )
    # Ein einziger Pfeil genügt: er verdrahtet ausgang_2 -> stellgroesse und
    # holt sich T_aus automatisch als istwert_2 zurück (siehe core/graph.py).
    b.pfeil(regler, erhitzer)
    vent = _zuluftventilator(b, 640, 200, V_max=3000.0)
    b.pfeil(erhitzer, vent)
    raum = _raum(b, 840, 200, wetter)
    b.pfeil(vent, raum)
    fort = _fortluft(b, 1040, 200)
    b.pfeil(raum, fort)
    return b.anlage_id


def bau_hysterese_regler(projekt_id):
    b = _anlage(
        projekt_id, "Hysterese-Regler", "Beispiel zum Baustein Hysterese-Regler."
    )
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    vent = _zuluftventilator(b, 440, 200, "Zuluftventilator", V_max=3000.0)
    b.pfeil(au, vent)
    waescher = b.karte(
        "luftwaescher", 640, 200, "Luftwäscher", V_nenn=3000.0, dp_nenn=50.0,
        pumpenart="H",
    )
    b.pfeil(vent, waescher)
    raum = _raum(b, 840, 200, wetter)
    b.pfeil(waescher, raum)
    fort = _fortluft(b, 1040, 200)
    b.pfeil(raum, fort)
    # Wirkrichtung umgekehrt, wie in core/vorlagen/ax_sim_2_1.py: Istwert ist
    # eine feste Zahl (Parameter), Sollwert die gemessene Raumfeuchte. Beide
    # Verbindungen ausdrücklich statt über pfeil() - ein gewöhnlicher Pfeil
    # vom Regler zum Luftwäscher würde die automatische Rückverdrahtung
    # auslösen und den Istwert mit der Luftwäscher-Austrittstemperatur
    # überschreiben.
    regler = b.karte(
        "hysterese_regler", 640, 40, "Regler Luftwäscher", hysterese=0.1, istwert=6.0
    )
    b.verbinde(raum, "F_Raum", regler, "sollwert")
    b.verbinde(regler, "ausgang", waescher, "stellgroesse")
    return b.anlage_id


def bau_sequenzregler(projekt_id):
    # Der Sequenzregler baut seine Regelabweichung ueber die Iterationen einer
    # Stunde hinweg auf (ZUSTAND_UEBER_ITERATION, core/bausteine/basis.py) -
    # ohne einen echten Regelkreis, der auf seine Ausgaenge zurueckwirkt,
    # waechst sie unbegrenzt an, statt sich einzupendeln, und die Stunde
    # konvergiert nie. Wie beim P-Regler-Beispiel treibt er deshalb hier
    # tatsaechlich einen Erhitzer.
    b = _anlage(projekt_id, "Sequenzregler", "Beispiel zum Baustein Sequenzregler.")
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    erhitzer = b.karte(
        "erhitzer", 440, 200, "Erhitzer", V_nenn=3000.0, dp_nenn=120.0, QH_max=100.0
    )
    b.pfeil(au, erhitzer)
    vent = _zuluftventilator(b, 640, 200, V_max=3000.0)
    b.pfeil(erhitzer, vent)
    raum = _raum(b, 840, 200, wetter)
    b.pfeil(vent, raum)
    fort = _fortluft(b, 1040, 200)
    b.pfeil(raum, fort)
    regler = b.karte(
        "sequenzregler", 440, 40, "Sequenzregler", oberer_sw=22.0, unterer_sw=20.0,
        xp=5.0,
    )
    # Istwert ist die eigene Erhitzer-Austrittstemperatur, nicht die
    # Raumtemperatur: der Kreis über den Raum reagiert bei einem trägheitslosen
    # 'einfacher_raum' zu unmittelbar und schwingt.
    b.verbinde(erhitzer, "T_aus", regler, "istwert")
    b.verbinde(regler, "waermer_1", erhitzer, "stellgroesse")
    logger = b.karte(
        "datenlogger", 840, 40, "Datenlogger",
        namen=["Wärmer 3", "Wärmer 2", "Wärmer 1", "Kälter 1", "Kälter 2"] + [""] * 5,
        einheiten=["%", "%", "%", "%", "%"] + [""] * 5,
    )
    b.verbinde(regler, "waermer_3", logger, "wert_1")
    b.verbinde(regler, "waermer_2", logger, "wert_2")
    b.verbinde(regler, "waermer_1", logger, "wert_3")
    b.verbinde(regler, "kaelter_1", logger, "wert_4")
    b.verbinde(regler, "kaelter_2", logger, "wert_5")
    return b.anlage_id


def bau_kaskade(projekt_id):
    b = _anlage(
        projekt_id, "Raum-/Zuluft-Kaskade", "Beispiel zum Baustein Raum-/Zuluft-Kaskade."
    )
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    erhitzer = b.karte(
        "erhitzer", 440, 200, "Erhitzer", V_nenn=3000.0, dp_nenn=120.0, QH_max=30.0
    )
    b.pfeil(au, erhitzer)
    vent = _zuluftventilator(b, 640, 200, V_max=3000.0)
    b.pfeil(erhitzer, vent)
    raum = _raum(b, 840, 200, wetter)
    b.pfeil(vent, raum)
    fort = _fortluft(b, 1040, 200)
    b.pfeil(raum, fort)
    kaskade = b.karte(
        "kaskade", 440, 40, "Kaskade",
        T_Raum_min=20.0, T_AU_min=15.0, T_Raum_max=22.0, T_AU_max=25.0,
        T_ZU_min=16.0, T_ZU_max=30.0, xp=5.0,
    )
    b.verbinde(wetter, "T_AU", kaskade, "T_AU")
    b.verbinde(raum, "T_Raum", kaskade, "T_Raum")
    b.verbinde(erhitzer, "T_aus", kaskade, "T_ZU")
    b.verbinde(kaskade, "waermer_1", erhitzer, "stellgroesse")
    return b.anlage_id


def bau_maximalwert(projekt_id):
    b = _anlage(projekt_id, "Maximalwert", "Beispiel zum Baustein Maximalwert.")
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    betrieb = _antrieb(b)
    grundlast = b.karte("faktor", 440, 40, "Grundlast", faktor=0.4)
    b.pfeil(betrieb, grundlast)
    maxw = b.karte("maximalwert", 640, 120, "Größere Anforderung gewinnt")
    b.pfeil(betrieb, maxw)
    b.pfeil(grundlast, maxw)
    vent = _zuluftventilator(b, 840, 200, V_max=3000.0)
    b.pfeil(au, vent)
    b.pfeil(maxw, vent)
    # Ein Zuluftventilator darf nicht direkt an die Fortluft (core/graph.py,
    # VERBOTEN) - hier geht es um das Signal, das er bekommt, nicht um den
    # weiteren Luftweg, deshalb endet die Anlage bewusst am Ventilator.
    return b.anlage_id


def bau_faktor(projekt_id):
    b = _anlage(projekt_id, "Faktor", "Beispiel zum Baustein Faktor.")
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    betrieb = _antrieb(b)
    faktor = b.karte("faktor", 440, 120, "Faktor 0,5", faktor=0.5)
    b.pfeil(betrieb, faktor)
    vent = _zuluftventilator(b, 640, 200, V_max=3000.0)
    b.pfeil(au, vent)
    b.pfeil(faktor, vent)
    return b.anlage_id


def bau_umkehrglied(projekt_id):
    b = _anlage(projekt_id, "Umkehrglied", "Beispiel zum Baustein Umkehrglied.")
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    betrieb = _antrieb(b)
    faktor = b.karte("faktor", 440, 40, "Faktor 0,6", faktor=0.6)
    b.pfeil(betrieb, faktor)
    umkehr = b.karte("umkehrglied", 640, 120, "Umkehrglied", bezug=100.0)
    b.pfeil(faktor, umkehr)
    vent = _zuluftventilator(b, 840, 200, V_max=3000.0)
    b.pfeil(au, vent)
    b.pfeil(umkehr, vent)
    return b.anlage_id


# -- Zeit und Betrieb -----------------------------------------------------

def bau_wochenzeitplan(projekt_id):
    b = _anlage(projekt_id, "Wochenzeitplan", "Beispiel zum Baustein Wochenzeitplan.")
    wetter = _wetter(b)
    vent = _minimalluft(b, wetter)
    zeitplan = b.karte("wochenzeitplan", 240, 40, "Wochenzeitplan")
    betrieb = b.karte("anlagenbetrieb", 440, 40, "Anlagenbetrieb")
    b.pfeil(zeitplan, betrieb)
    b.pfeil(betrieb, vent)
    return b.anlage_id


def bau_ferien(projekt_id):
    b = _anlage(projekt_id, "Ferien", "Beispiel zum Baustein Ferien.")
    wetter = _wetter(b)
    vent = _minimalluft(b, wetter)
    zeitplan = b.karte("wochenzeitplan", 240, 40, "Wochenzeitplan")
    ferien = b.karte(
        "ferien", 240, 160, "Ferien",
        zeitraeume=[{"name": "Betriebsferien", "von": "24.12.", "bis": "02.01."}],
    )
    betrieb = b.karte("anlagenbetrieb", 440, 80, "Anlagenbetrieb")
    b.pfeil(zeitplan, betrieb)
    b.pfeil(ferien, betrieb)
    b.pfeil(betrieb, vent)
    return b.anlage_id


def bau_monatsprofil(projekt_id):
    b = _anlage(projekt_id, "Monatsprofil", "Beispiel zum Baustein Monatsprofil.")
    wetter = _wetter(b)
    vent = _minimalluft(b, wetter)
    zeitplan = b.karte("wochenzeitplan", 240, 40, "Wochenzeitplan")
    heizperiode = [m in (9, 10, 11, 0, 1, 2) for m in range(12)]  # Okt.-März
    monatsprofil = b.karte(
        "monatsprofil", 240, 160, "Monatsprofil (Heizperiode)", monate=heizperiode
    )
    betrieb = b.karte("anlagenbetrieb", 440, 80, "Anlagenbetrieb")
    b.pfeil(zeitplan, betrieb)
    b.pfeil(monatsprofil, betrieb)
    b.pfeil(betrieb, vent)
    return b.anlage_id


def bau_tageslastprofil(projekt_id):
    b = _anlage(projekt_id, "Tageslastprofil", "Beispiel zum Baustein Tageslastprofil.")
    wetter = _wetter(b)
    vent = _minimalluft(b, wetter)
    zeitplan = b.karte("wochenzeitplan", 240, 40, "Wochenzeitplan")
    profil = b.karte(
        "tageslastprofil", 240, 160, "Tageslastprofil",
        lastgang_1=[0.3] * 6 + [1.0] * 12 + [0.3] * 6,
        lastgang_2=[0.0] * 24, lastgang_3=[0.0] * 24,
    )
    betrieb = b.karte("anlagenbetrieb", 440, 80, "Anlagenbetrieb")
    b.pfeil(zeitplan, betrieb)
    b.pfeil(profil, betrieb)  # trifft lastgang_1, das einzige belegte Profil
    b.pfeil(betrieb, vent)
    return b.anlage_id


def bau_anlagenbetrieb(projekt_id):
    b = _anlage(projekt_id, "Anlagenbetrieb", "Beispiel zum Baustein Anlagenbetrieb.")
    wetter = _wetter(b)
    vent = _minimalluft(b, wetter)
    zeitplan = b.karte("wochenzeitplan", 240, 40, "Wochenzeitplan")
    ferien = b.karte(
        "ferien", 240, 160, "Ferien",
        zeitraeume=[{"name": "Sommer", "von": "15.07.", "bis": "15.08."}],
    )
    profil = b.karte(
        "tageslastprofil", 240, 280, "Tageslastprofil",
        lastgang_1=[0.3] * 6 + [1.0] * 12 + [0.3] * 6,
        lastgang_2=[0.0] * 24, lastgang_3=[0.0] * 24,
    )
    betrieb = b.karte("anlagenbetrieb", 440, 160, "Anlagenbetrieb")
    b.pfeil(zeitplan, betrieb)
    b.pfeil(ferien, betrieb)
    b.pfeil(profil, betrieb)
    b.pfeil(betrieb, vent)
    return b.anlage_id


# -- Verbraucher ----------------------------------------------------------

def bau_heizungspumpen(projekt_id):
    b = _anlage(projekt_id, "Heizungspumpen", "Beispiel zum Baustein Heizungspumpen.")
    zeitplan = b.karte("wochenzeitplan", 40, 40, "Wochenzeitplan")
    betrieb = b.karte("anlagenbetrieb", 240, 40, "Anlagenbetrieb")
    b.pfeil(zeitplan, betrieb)
    pumpen = b.karte(
        "heizungspumpen", 440, 40, "Heizungspumpen",
        P_allgemein=1.5, P_wwb=0.3, P_kessel=0.5,
    )
    b.pfeil(betrieb, pumpen)  # trifft 'betrieb' - Namensgleichheit geht vor
    bil = _bilanz(b, 640, 40)
    b.pfeil(pumpen, bil)
    return b.anlage_id


def bau_warmwasser(projekt_id):
    b = _anlage(
        projekt_id, "Warmwasserbereitung", "Beispiel zum Baustein Warmwasserbereitung."
    )
    ww = b.karte(
        "warmwasser", 240, 120, "Warmwasserbereitung",
        speichervolumen=500.0, verbrauch=200.0, sollwert=55.0,
    )
    bil = _bilanz(b, 440, 120)
    b.pfeil(ww, bil)
    return b.anlage_id


def bau_zirkulation(projekt_id):
    b = _anlage(projekt_id, "Zirkulation", "Beispiel zum Baustein Zirkulation.")
    zeitplan = b.karte("wochenzeitplan", 40, 40, "Wochenzeitplan")
    betrieb = b.karte("anlagenbetrieb", 240, 40, "Anlagenbetrieb")
    b.pfeil(zeitplan, betrieb)
    zirk = b.karte(
        "zirkulation", 440, 40, "Zirkulation",
        volumenstrom=1.0, spreizung=5.0, P_pumpe=0.03,
    )
    b.pfeil(betrieb, zirk)
    bil = _bilanz(b, 640, 40)
    b.pfeil(zirk, bil)
    return b.anlage_id


def bau_beleuchtung(projekt_id):
    b = _anlage(projekt_id, "Beleuchtung", "Beispiel zum Baustein Beleuchtung.")
    zeitplan = b.karte("wochenzeitplan", 40, 40, "Wochenzeitplan")
    betrieb = b.karte("anlagenbetrieb", 240, 40, "Anlagenbetrieb")
    b.pfeil(zeitplan, betrieb)
    bel = b.karte(
        "beleuchtung", 440, 40, "Beleuchtung",
        spez_leistung=2.0, grundflaeche=200.0, nennbeleuchtung=300.0,
    )
    b.pfeil(betrieb, bel)
    bil = _bilanz(b, 640, 40)
    b.pfeil(bel, bil)
    return b.anlage_id


def bau_enthalpierechner(projekt_id):
    b = _anlage(
        projekt_id, "Enthalpie / rel. Feuchte", "Beispiel zum Baustein Enthalpie / rel. Feuchte."
    )
    wetter = _wetter(b)
    rechner = b.karte("enthalpierechner", 240, 120, "Enthalpie / rel. Feuchte")
    b.verbinde(wetter, "T_AU", rechner, "t")
    b.verbinde(wetter, "F_AU", rechner, "x")
    logger = b.karte(
        "datenlogger", 440, 120, "Datenlogger",
        namen=["Enthalpie", "rel. Feuchte"] + [""] * 8,
        einheiten=["kJ/kg", "%"] + [""] * 8,
    )
    b.verbinde(rechner, "h", logger, "wert_1")
    b.verbinde(rechner, "rF", logger, "wert_2")
    return b.anlage_id


def bau_bilanz(projekt_id):
    b, wetter, au, betrieb = _luftbehandlung_grund(
        projekt_id, "Energiepreise und Bilanz", "Beispiel zum Baustein Energiepreise und Bilanz."
    )
    erhitzer = b.karte(
        "erhitzer", 440, 120, "Erhitzer", V_nenn=3000.0, dp_nenn=120.0, QH_max=30.0
    )
    b.pfeil(au, erhitzer)
    b.pfeil(betrieb, erhitzer)
    kuehler = b.karte(
        "kuehler", 640, 120, "Kühler", V_nenn=3000.0, dp_nenn=120.0, QK_nenn=20.0,
        T_KW_mittel=8.0,
    )
    b.pfeil(erhitzer, kuehler)
    b.pfeil(betrieb, kuehler)
    waescher = b.karte(
        "luftwaescher", 840, 120, "Luftwäscher", V_nenn=3000.0, dp_nenn=50.0,
        pumpenart="H",
    )
    b.pfeil(kuehler, waescher)
    b.pfeil(betrieb, waescher)
    vent = _zuluftventilator(b, 1040, 120, V_max=3000.0)
    b.pfeil(waescher, vent)
    raum = _raum(b, 1240, 120, wetter)
    b.pfeil(vent, raum)
    fort = _fortluft(b, 1440, 120)
    b.pfeil(raum, fort)
    bil = _bilanz(b, 640, 320)
    b.pfeil(erhitzer, bil)
    b.pfeil(kuehler, bil)
    b.pfeil(waescher, bil)
    b.pfeil(vent, bil)
    return b.anlage_id


def bau_datenlogger(projekt_id):
    b = _anlage(projekt_id, "Datenlogger", "Beispiel zum Baustein Datenlogger.")
    wetter = _wetter(b)
    au = _aussenluft(b, wetter)
    vent = _zuluftventilator(b, 440, 200, V_max=3000.0)
    b.pfeil(au, vent)
    raum = _raum(b, 640, 200, wetter)
    b.pfeil(vent, raum)
    fort = _fortluft(b, 840, 200)
    b.pfeil(raum, fort)
    logger = b.karte(
        "datenlogger", 440, 40, "Datenlogger",
        namen=["Außentemperatur", "Außenfeuchte", "Ventilatorleistung"] + [""] * 7,
        einheiten=["°C", "g/kg", "kW"] + [""] * 7,
    )
    b.verbinde(wetter, "T_AU", logger, "wert_1")
    b.verbinde(wetter, "F_AU", logger, "wert_2")
    b.verbinde(vent, "PE", logger, "wert_3")
    return b.anlage_id


BAUPLAENE = {
    "wetter": bau_wetter,
    "aussenluft": bau_aussenluft,
    "fortluft": bau_fortluft,
    "erhitzer": bau_erhitzer,
    "kuehler": bau_kuehler,
    "wrg": bau_wrg,
    "mischkammer": bau_mischkammer,
    "dampfbefeuchter": bau_dampfbefeuchter,
    "luftwaescher": bau_luftwaescher,
    "ventilator": bau_ventilator,
    "verteiler": bau_verteiler,
    "sammler": bau_sammler,
    "einfacher_raum": bau_einfacher_raum,
    "statische_heizung": bau_statische_heizung,
    "raum": bau_raum,
    "p_regler": bau_p_regler,
    "sequenzregler": bau_sequenzregler,
    "hysterese_regler": bau_hysterese_regler,
    "kaskade": bau_kaskade,
    "maximalwert": bau_maximalwert,
    "faktor": bau_faktor,
    "umkehrglied": bau_umkehrglied,
    "wochenzeitplan": bau_wochenzeitplan,
    "ferien": bau_ferien,
    "monatsprofil": bau_monatsprofil,
    "tageslastprofil": bau_tageslastprofil,
    "anlagenbetrieb": bau_anlagenbetrieb,
    "heizungspumpen": bau_heizungspumpen,
    "warmwasser": bau_warmwasser,
    "zirkulation": bau_zirkulation,
    "beleuchtung": bau_beleuchtung,
    "enthalpierechner": bau_enthalpierechner,
    "bilanz": bau_bilanz,
    "datenlogger": bau_datenlogger,
}


def baue_beispiel(kennung, projekt_id):
    if kennung not in BAUPLAENE:
        raise KeyError(f"Für den Kartentyp '{kennung}' gibt es keine Beispielanlage")
    return BAUPLAENE[kennung](projekt_id)
