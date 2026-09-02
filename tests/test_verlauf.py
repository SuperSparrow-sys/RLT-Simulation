"""Rueckgaengig und Wiederholen (core/verlauf.py).

Die acht Pruefungen aus Abschnitt 10 des Plans
(docs/superpowers/plans/2026-09-02-rueckgaengig.md) - jede einzeln benannt,
damit im Fehlerfall sofort zu sehen ist, welche Zusage gebrochen ist. Die
schaerfste ist Nummer 4 (zehn Aenderungen, zehnmal zurueck, byteweise
derselbe Zustand): sie faengt alles, was beim Entwurf uebersehen wurde.
"""

from datetime import datetime, timedelta

import pytest

from app import create_app
from core import anlagen, database, ergebnisse, solver, verlauf
from core.wetter import speicher


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def _anlage_mit_zwei_karten():
    """Erhitzer -> Kuehler, verbunden. Kleinste Anlage, an der sich Karten,
    Anschluesse, Pfeil und Verbindung gemeinsam pruefen lassen."""
    projekt = anlagen.projekt_anlegen("P")
    anlage = anlagen.anlage_anlegen(projekt, "A")
    a = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
    b = anlagen.karte_anlegen(anlage, "kuehler", 300.0, 0.0)
    pfeil = anlagen.pfeil_anlegen(anlage, a, b)
    return anlage, a, b, pfeil["id"]


def _fremdschluessel_pruefen():
    """PRAGMA foreign_key_check - Pruefung 8. Nach jedem Einspielen faellig:
    bleibt hier etwas uebrig, ist der Entwurf falsch und nicht der
    Einzelfall."""
    db = database.get_db()
    uebrig = db.execute("PRAGMA foreign_key_check").fetchall()
    assert not uebrig, f"verwaiste Verweise nach dem Einspielen: {uebrig}"


def _zustand(anlage_id):
    return verlauf._packe(verlauf.momentaufnahme(anlage_id))


# -- 1 --------------------------------------------------------------------

def test_1_geloeschte_karte_kommt_mit_derselben_kennung_zurueck(app):
    """Pruefung 1: Karte loeschen, zurueck - dieselbe Kennung, dieselben
    Anschluesse, und die Pfeile, die an ihr hingen, samt Verbindungen."""
    with app.app_context():
        anlage, a, b, pfeil_id = _anlage_mit_zwei_karten()
        db = database.get_db()
        ports_vorher = [
            z["id"] for z in db.execute(
                "SELECT id FROM port WHERE karte_id = ? ORDER BY id", (a,)
            )
        ]
        verbindungen_vorher = [
            dict(z) for z in db.execute(
                "SELECT * FROM verbindung WHERE pfeil_id = ?", (pfeil_id,)
            )
        ]

        anlagen.karte_loeschen(a)
        assert db.execute("SELECT 1 FROM karte WHERE id = ?", (a,)).fetchone() is None

        verlauf.zurueck(anlage)
        _fremdschluessel_pruefen()

        karte = db.execute("SELECT * FROM karte WHERE id = ?", (a,)).fetchone()
        assert karte is not None, "die Karte muss mit DERSELBEN Kennung wiederkommen"
        assert karte["typ"] == "erhitzer"
        ports_nachher = [
            z["id"] for z in db.execute(
                "SELECT id FROM port WHERE karte_id = ? ORDER BY id", (a,)
            )
        ]
        assert ports_nachher == ports_vorher
        pfeil = db.execute("SELECT * FROM pfeil WHERE id = ?", (pfeil_id,)).fetchone()
        assert pfeil is not None
        verbindungen_nachher = [
            dict(z) for z in db.execute(
                "SELECT * FROM verbindung WHERE pfeil_id = ?", (pfeil_id,)
            )
        ]
        assert verbindungen_nachher == verbindungen_vorher


# -- 2 --------------------------------------------------------------------

def test_2_getrennte_verbindung_zeigt_wieder_auf_dieselben_anschluesse(app):
    """Pruefung 2: Verbindung trennen, zurueck - sie zeigt wieder auf
    dieselben Anschluesse."""
    with app.app_context():
        anlage, a, b, pfeil_id = _anlage_mit_zwei_karten()
        db = database.get_db()
        vorher = [
            dict(z) for z in db.execute(
                "SELECT * FROM verbindung WHERE pfeil_id = ? ORDER BY id", (pfeil_id,)
            )
        ]

        anlagen.pfeil_loeschen(pfeil_id)
        assert db.execute(
            "SELECT 1 FROM verbindung WHERE pfeil_id = ?", (pfeil_id,)
        ).fetchone() is None

        verlauf.zurueck(anlage)
        _fremdschluessel_pruefen()

        nachher = [
            dict(z) for z in db.execute(
                "SELECT * FROM verbindung WHERE pfeil_id = ? ORDER BY id", (pfeil_id,)
            )
        ]
    assert nachher == vorher


# -- 3 --------------------------------------------------------------------

def test_3_parameter_wandert_hin_und_zurueck(app):
    """Pruefung 3: Parameter aendern, zurueck, wiederholen - auch bei einer
    Liste (das Wochenprofil des Zeitplans ist eine)."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        vorgabe = anlagen.als_json(anlage)["karten"][0]["parameter"]["QH_max"]

        anlagen.karte_aendern(karte, parameter={"QH_max": 55.0})
        assert anlagen.als_json(anlage)["karten"][0]["parameter"]["QH_max"] == 55.0

        verlauf.zurueck(anlage)
        _fremdschluessel_pruefen()
        assert anlagen.als_json(anlage)["karten"][0]["parameter"]["QH_max"] == vorgabe

        verlauf.vor(anlage)
        _fremdschluessel_pruefen()
        assert anlagen.als_json(anlage)["karten"][0]["parameter"]["QH_max"] == 55.0


def test_3b_listenparameter_wandert_hin_und_zurueck(app):
    """Derselbe Weg fuer einen Parameter, der eine Liste ist - hier die
    zwoelf Monatsschalter des Monatsprofils. Ein Wert, der nur 'ungefaehr'
    zurueckkaeme, faellt bei einer Liste am ehesten auf."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "monatsprofil", 0.0, 0.0)
        daten = anlagen.als_json(anlage)["karten"][0]["parameter"]
        listen = [s for s, w in daten.items() if isinstance(w, list)]
        assert listen, "das Monatsprofil sollte einen Listenparameter haben"
        schluessel = listen[0]
        vorher = list(daten[schluessel])

        neu = list(vorher)
        neu[0] = not neu[0]
        anlagen.karte_aendern(karte, parameter={schluessel: neu})
        assert anlagen.als_json(anlage)["karten"][0]["parameter"][schluessel] == neu

        verlauf.zurueck(anlage)
        _fremdschluessel_pruefen()
        assert anlagen.als_json(anlage)["karten"][0]["parameter"][schluessel] == vorher


# -- 4 --------------------------------------------------------------------

def test_4_zehn_aenderungen_zehnmal_zurueck_ergeben_denselben_zustand(app):
    """Pruefung 4, die schaerfste: zehn Aenderungen unterschiedlicher Art,
    zehnmal zurueck - der Zustand ist BYTEWEISE derselbe wie am Anfang."""
    with app.app_context():
        anlage, a, b, pfeil_id = _anlage_mit_zwei_karten()
        anfang = _zustand(anlage)

        # Zehn Aenderungen, jede von der Art, die im Editor wirklich
        # vorkommt - und jede ein eigener Schritt (verschiedene Karten bzw.
        # verschiedene Felder, sonst wuerden sie gebuendelt).
        c = anlagen.karte_anlegen(anlage, "ventilator", 600.0, 0.0)   # 1
        anlagen.karte_aendern(a, pos_x=10.0, pos_y=20.0)              # 2
        anlagen.karte_aendern(b, name="Kühler neu")                   # 3
        anlagen.karte_aendern(a, parameter={"QH_max": 42.0})          # 4
        pfeil2 = anlagen.pfeil_anlegen(anlage, b, c)                  # 5
        anlagen.anlage_umbenennen(anlage, "Anlage neu")               # 6
        anlagen.karte_aendern(c, pos_x=5.0)                           # 7
        anlagen.pfeil_loeschen(pfeil_id)                              # 8
        d = anlagen.karte_anlegen(anlage, "kuehler", 900.0, 0.0)      # 9
        anlagen.karte_loeschen(b)                                     # 10

        stand = verlauf.stand_lesen(anlage)
        # Ausgangszustand + zwei Karten + ein Pfeil aus dem Aufbau, dann die
        # zehn Aenderungen.
        assert stand["stand"] == 14

        for _ in range(10):
            verlauf.zurueck(anlage)
            _fremdschluessel_pruefen()

        assert _zustand(anlage) == anfang
        # Zurueck geht es weiter - bis in den Aufbau der Anlage hinein.
        assert verlauf.stand_lesen(anlage)["stand"] == 4


def test_4b_wieder_nach_vorn_ergibt_wieder_den_endzustand(app):
    """Die Gegenprobe: zehnmal zurueck und zehnmal vor fuehrt byteweise an
    dieselbe Stelle zurueck, an der man war."""
    with app.app_context():
        anlage, a, b, _pfeil = _anlage_mit_zwei_karten()
        for i in range(10):
            anlagen.karte_aendern(a, pos_x=float(i), pos_y=float(i))
            anlagen.karte_aendern(b, name=f"Kühler {i}")
        ende = _zustand(anlage)
        for _ in range(20):
            verlauf.zurueck(anlage)
        for _ in range(20):
            verlauf.vor(anlage)
        _fremdschluessel_pruefen()
        assert _zustand(anlage) == ende


# -- 5 --------------------------------------------------------------------

def test_5_neue_aenderung_nach_dem_zuruecknehmen_wirft_den_vorwaertsverlauf_weg(app):
    """Pruefung 5: Nach einem Zurueecknehmen eine neue Aenderung - der
    Vorwaertsverlauf ist weg, die neue Aenderung haengt richtig."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        anlagen.karte_aendern(karte, name="Erst")
        anlagen.karte_aendern(karte, name="Zweit")

        verlauf.zurueck(anlage)
        assert verlauf.stand_lesen(anlage)["kann_vor"] is True

        anlagen.karte_aendern(karte, name="Anders")
        stand = verlauf.stand_lesen(anlage)
        assert stand["kann_vor"] is False, "der Vorwaertsverlauf muss weg sein"
        assert stand["zurueck_text"] == "Karte 'Anders' umbenannt"

        verlauf.zurueck(anlage)
        _fremdschluessel_pruefen()
        assert anlagen.als_json(anlage)["karten"][0]["name"] == "Erst"


# -- 6 --------------------------------------------------------------------

def test_6_ergebnisse_eines_laufs_zeigen_nach_dem_zuruecknehmen_richtig(app):
    """Pruefung 6, die den Entwurf traegt oder widerlegt: Simulationslauf,
    dann Karte loeschen, dann zurueecknehmen - die Zeitreihen des Laufs
    zeigen weiterhin auf DIESELBE Karte.

    Bewusst ein Lauf ueber drei Stunden statt ueber ein Jahr: gepruefte
    Frage ist die Zuordnung ueber karte_id, nicht die Rechnung."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        aussen = anlagen.karte_anlegen(anlage, "aussenluft", 0.0, 0.0)
        erhitzer = anlagen.karte_anlegen(anlage, "erhitzer", 300.0, 0.0)
        anlagen.pfeil_anlegen(anlage, aussen, erhitzer)

        wetter = speicher.datensatz_anlegen(
            "Test", "upload",
            [
                {"zeitpunkt": datetime(2024, 1, 1, i), "t_au": -5.0, "x_au": 2.0,
                 "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0,
                 "str_h": 0.0}
                for i in range(3)
            ],
        )
        graph = anlagen.lade_graph(anlage)
        stunden = speicher.lade_stunden(wetter, 0, 3)
        lauf = solver.Solver(graph).starte(stunden)
        sim = ergebnisse.speichere(anlage, wetter, 0, 3, lauf, graph, dauer=0.1)

        db = database.get_db()
        reihen = {
            (z["karte_id"], z["groesse"])
            for z in db.execute(
                "SELECT karte_id, groesse FROM zeitreihe WHERE simulation_id = ?",
                (sim,),
            )
        }
        assert any(k == erhitzer for k, _ in reihen), "der Lauf muss Werte fuer die Karte haben"
        groesse = next(g for k, g in reihen if k == erhitzer)
        werte_vorher = ergebnisse.lade_zeitreihe(sim, erhitzer, groesse)

        anlagen.karte_loeschen(erhitzer)
        verlauf.zurueck(anlage)
        _fremdschluessel_pruefen()

        karte = db.execute(
            "SELECT * FROM karte WHERE id = ?", (erhitzer,)
        ).fetchone()
        assert karte is not None and karte["typ"] == "erhitzer"
        assert ergebnisse.lade_zeitreihe(sim, erhitzer, groesse) == werte_vorher
        # Und der Lauf selbst hat das Zurueecknehmen unversehrt ueberstanden.
        assert db.execute(
            "SELECT COUNT(*) AS n FROM simulation WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"] == 1


# -- 7 --------------------------------------------------------------------

def test_7_der_verlauf_waechst_nicht_ueber_die_grenze(app, monkeypatch):
    """Pruefung 7: Ueber die Grenze hinaus arbeiten - der Verlauf waechst
    nicht unbegrenzt, und der erste Zustand bleibt erreichbar."""
    monkeypatch.setattr(verlauf, "GRENZE", 6)
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        # Der Ausgangszustand ist der Stand VOR der ersten aufgezeichneten
        # Aenderung - hier also die noch leere Anlage.
        anfang = _zustand(anlage)
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)

        for i in range(20):
            anlagen.karte_aendern(karte, name=f"Name {i}")

        db = database.get_db()
        anzahl = db.execute(
            "SELECT COUNT(*) AS n FROM zustand WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"]
        assert anzahl == 6

        # Der Ausgangszustand ist nie weggefallen und bleibt erreichbar.
        assert db.execute(
            "SELECT 1 FROM zustand WHERE anlage_id = ? AND nummer = 1", (anlage,)
        ).fetchone() is not None
        while verlauf.stand_lesen(anlage)["kann_zurueck"]:
            verlauf.zurueck(anlage)
        _fremdschluessel_pruefen()
        assert verlauf.stand_lesen(anlage)["stand"] == 1
        assert _zustand(anlage) == anfang


# -- 8 --------------------------------------------------------------------

def test_8_fremdschluesselpruefung_bleibt_nach_jedem_einspielen_leer(app):
    """Pruefung 8: PRAGMA foreign_key_check bleibt leer - hier ueber eine
    ganze Folge von Aenderungen samt Hin und Her, nicht nur einmal."""
    with app.app_context():
        anlage, a, b, pfeil_id = _anlage_mit_zwei_karten()
        c = anlagen.karte_anlegen(anlage, "ventilator", 600.0, 0.0)
        anlagen.pfeil_anlegen(anlage, b, c)
        anlagen.karte_loeschen(b)      # reisst zwei Pfeile mit
        for _ in range(3):
            verlauf.zurueck(anlage)
            _fremdschluessel_pruefen()
        for _ in range(3):
            verlauf.vor(anlage)
            _fremdschluessel_pruefen()


# -- Buendelung, Grenzen, Endpunkte ---------------------------------------

def test_verschiebungen_kurz_hintereinander_sind_ein_schritt(app):
    """Frage 1 des Auftrags: Eine Karte mehrmals kurz hintereinander
    zurechtzuruecken ist EINE Handlung - ein Schritt, nicht drei."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        vorher = _zustand(anlage)

        for x in (10.0, 20.0, 30.0):
            anlagen.karte_aendern(karte, pos_x=x, pos_y=0.0)

        db = database.get_db()
        assert db.execute(
            "SELECT COUNT(*) AS n FROM zustand WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"] == 3   # Ausgang + Karte angelegt + EIN Verschieben

        verlauf.zurueck(anlage)
        assert _zustand(anlage) == vorher


def test_verschiebungen_mit_abstand_sind_zwei_schritte(app, monkeypatch):
    """... aber dieselbe Karte spaeter noch einmal zu verschieben ist eine
    zweite Handlung. Die Zeit wird vorgestellt statt gewartet."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        anlagen.karte_aendern(karte, pos_x=10.0)

        spaeter = verlauf._jetzt() + timedelta(seconds=60)
        monkeypatch.setattr(verlauf, "_jetzt", lambda: spaeter)
        anlagen.karte_aendern(karte, pos_x=20.0)

        db = database.get_db()
        assert db.execute(
            "SELECT COUNT(*) AS n FROM zustand WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"] == 4


def test_verschiebungen_verschiedener_karten_bleiben_getrennt(app):
    with app.app_context():
        anlage, a, b, _pfeil = _anlage_mit_zwei_karten()
        anlagen.karte_aendern(a, pos_x=10.0)
        anlagen.karte_aendern(b, pos_x=10.0)
        db = database.get_db()
        # Ausgang + 2 Karten + 1 Pfeil + 2 Verschiebungen
        assert db.execute(
            "SELECT COUNT(*) AS n FROM zustand WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"] == 6


def test_zwei_aenderungen_desselben_feldes_sind_ein_schritt(app):
    """Abschnitt 5 des Plans: mehrere schnelle Aenderungen DESSELBEN Feldes
    gehoeren zu einem Schritt - zwei verschiedene Felder nicht."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        vorher = anlagen.als_json(anlage)["karten"][0]["parameter"]["QH_max"]
        anlagen.karte_aendern(karte, parameter={"QH_max": 50.0})
        anlagen.karte_aendern(karte, parameter={"QH_max": 60.0})
        anlagen.karte_aendern(karte, parameter={"QH_max": 70.0})

        db = database.get_db()
        assert db.execute(
            "SELECT COUNT(*) AS n FROM zustand WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"] == 3

        verlauf.zurueck(anlage)
        assert anlagen.als_json(anlage)["karten"][0]["parameter"]["QH_max"] == vorher


def test_folgenlose_aenderung_erzeugt_keinen_schritt(app):
    """Der Editor speichert die Position schon beim blossen Anwaehlen einer
    Karte (das Ziehen endet immer mit einem PATCH) und das
    Parameterfenster beim Verlassen eines Feldes, auch wenn niemand etwas
    getippt hat. Solche Anfragen aendern nichts - und duerfen deshalb auch
    keinen Schritt erzeugen, sonst taeuschte der Rueckgaengig-Knopf eine
    Wirkung vor, die er nicht hat."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 100.0, 200.0)
        db = database.get_db()
        vorher = db.execute(
            "SELECT COUNT(*) AS n FROM zustand WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"]

        anlagen.karte_aendern(karte, pos_x=100.0, pos_y=200.0)        # nichts bewegt
        anlagen.karte_aendern(karte, parameter={"QH_max": 101.0})     # derselbe Wert
        anlagen.karte_aendern(karte, name="Erhitzer")                 # derselbe Name

        assert db.execute(
            "SELECT COUNT(*) AS n FROM zustand WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"] == vorher


def test_folgenlose_aenderung_wirft_den_vorwaertsverlauf_nicht_weg(app):
    """Eine Anfrage, die nichts aendert, darf auch nichts wegwerfen - sonst
    verlaere ein Klick auf eine Karte nach einem Zurueecknehmen die
    Moeglichkeit, wieder nach vorn zu gehen."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 100.0, 200.0)
        anlagen.karte_aendern(karte, name="Neuer Name")
        verlauf.zurueck(anlage)
        assert verlauf.stand_lesen(anlage)["kann_vor"] is True

        anlagen.karte_aendern(karte, pos_x=100.0, pos_y=200.0)   # folgenlos
        assert verlauf.stand_lesen(anlage)["kann_vor"] is True

        verlauf.vor(anlage)
        assert anlagen.als_json(anlage)["karten"][0]["name"] == "Neuer Name"


def test_einspielen_erzeugt_keinen_neuen_zustand(app):
    """Abschnitt 6: Das Einspielen selbst haelt nichts fest - sonst wuechse
    der Verlauf bei jedem Zurueecknehmen."""
    with app.app_context():
        anlage, a, _b, _pfeil = _anlage_mit_zwei_karten()
        db = database.get_db()
        vorher = db.execute(
            "SELECT COUNT(*) AS n FROM zustand WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"]
        verlauf.zurueck(anlage)
        verlauf.vor(anlage)
        nachher = db.execute(
            "SELECT COUNT(*) AS n FROM zustand WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"]
    assert nachher == vorher


def test_der_verlauf_verschwindet_mit_der_anlage(app):
    """ON DELETE CASCADE (core/database.py) - eine geloeschte Anlage
    hinterlaesst keinen Verlauf."""
    with app.app_context():
        anlage, _a, _b, _pfeil = _anlage_mit_zwei_karten()
        anlagen.anlage_loeschen(anlage)
        db = database.get_db()
        assert db.execute(
            "SELECT COUNT(*) AS n FROM zustand WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"] == 0


def test_neu_angelegte_karte_bekommt_keine_schon_vergebene_kennung(app):
    """Abschnitt 3: SQLite merkt sich den Hoechststand des Zaehlers - nach
    einer Wiederherstellung darf keine neue Karte eine Kennung bekommen, die
    ein frueherer Simulationslauf schon einer anderen zuordnet."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        a = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        b = anlagen.karte_anlegen(anlage, "kuehler", 300.0, 0.0)
        anlagen.karte_loeschen(b)
        verlauf.zurueck(anlage)          # b ist wieder da, mit Kennung b
        c = anlagen.karte_anlegen(anlage, "ventilator", 600.0, 0.0)
    assert c not in (a, b)
    assert c > b


def test_ohne_verlauf_meldet_zurueck_sich_deutsch(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        with pytest.raises(verlauf.Leer) as fehler:
            verlauf.zurueck(anlage)
        assert "zurückzunehmen" in str(fehler.value)


def test_stand_einer_unbekannten_anlage_ist_ein_schluesselfehler(app):
    with app.app_context():
        with pytest.raises(KeyError):
            verlauf.stand_lesen(999999)


# -- Die Endpunkte --------------------------------------------------------

def test_endpunkte_nehmen_zurueck_und_wiederholen(app):
    with app.app_context():
        anlage, a, _b, _pfeil = _anlage_mit_zwei_karten()
    klient = app.test_client()

    antwort = klient.get(f"/api/anlagen/{anlage}/verlauf")
    assert antwort.status_code == 200
    assert antwort.get_json()["kann_zurueck"] is True
    assert antwort.get_json()["kann_vor"] is False

    antwort = klient.post(f"/api/anlagen/{anlage}/verlauf/zurueck")
    assert antwort.status_code == 200
    assert antwort.get_json()["kann_vor"] is True

    antwort = klient.post(f"/api/anlagen/{anlage}/verlauf/vor")
    assert antwort.status_code == 200
    assert antwort.get_json()["kann_vor"] is False

    with app.app_context():
        assert len(anlagen.als_json(anlage)["pfeile"]) == 1


def test_endpunkt_meldet_leeren_verlauf_mit_400_und_deutscher_meldung(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
    klient = app.test_client()
    antwort = klient.post(f"/api/anlagen/{anlage}/verlauf/zurueck")
    assert antwort.status_code == 400
    assert "zurückzunehmen" in antwort.get_json()["fehler"]

    antwort = klient.post(f"/api/anlagen/{anlage}/verlauf/vor")
    assert antwort.status_code == 400
    assert "wiederholen" in antwort.get_json()["fehler"]


def test_endpunkt_meldet_unbekannte_anlage_mit_404(app):
    klient = app.test_client()
    assert klient.get("/api/anlagen/999999/verlauf").status_code == 404
    assert klient.post("/api/anlagen/999999/verlauf/zurueck").status_code == 404
    assert klient.post("/api/anlagen/999999/verlauf/vor").status_code == 404


def test_pfeil_mit_mehreren_verbindungen_kommt_vollstaendig_zurueck(app):
    """Ein Pfeil kann mehr als eine Anschlussverbindung tragen (in AX_SIM 2.1
    sieben von 61) - zurueckgenommen muessen ALLE wieder da sein, mit ihren
    eigenen Kennungen, nicht nur der Pfeil selbst.

    Das ist die Pruefung, die das Loeschen eines Pfeils (Auswahl im Editor,
    static/js/editor.js) mit dem Verlauf zusammenbringt."""
    from core.vorlagen import ax_sim_2_1

    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        daten = anlagen.als_json(anlage)
        pfeil = next(p for p in daten["pfeile"] if len(p["verbindungen"]) > 1)
        db = database.get_db()
        vorher = [
            dict(z) for z in db.execute(
                "SELECT * FROM verbindung WHERE pfeil_id = ? ORDER BY id", (pfeil["id"],)
            )
        ]
        assert len(vorher) > 1

        anlagen.pfeil_loeschen(pfeil["id"])
        assert db.execute(
            "SELECT 1 FROM pfeil WHERE id = ?", (pfeil["id"],)
        ).fetchone() is None

        verlauf.zurueck(anlage)
        _fremdschluessel_pruefen()

        nachher = [
            dict(z) for z in db.execute(
                "SELECT * FROM verbindung WHERE pfeil_id = ? ORDER BY id", (pfeil["id"],)
            )
        ]
        assert nachher == vorher
        assert len(anlagen.als_json(anlage)["pfeile"]) == len(daten["pfeile"])


def test_vorlage_schreibt_ihren_aufbau_nicht_in_den_verlauf(app):
    """Eine Anlage aus einer Vorlage anzulegen ist EINE Handlung, kein
    Bauprozess, den jemand Schritt fuer Schritt zuruecknehmen will.

    Ohne verlauf.stumm() standen hier ueber hundert Schritte - 42 Karten und
    61 Pfeile einzeln -, von denen die Grenze fuenfzig uebrig liess: wer eine
    frische Vorlage oeffnete und "Rueckgaengig" drueckte, baute sie Pfeil fuer
    Pfeil auseinander, statt seine eigene Aenderung zurueckzunehmen."""
    from core import vorlagen

    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = vorlagen.baue("ax_sim_2_1", projekt, "Frisch aus der Vorlage")
        db = database.get_db()
        assert db.execute(
            "SELECT COUNT(*) AS n FROM zustand WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"] == 0
        stand = verlauf.stand_lesen(anlage)
        assert stand["kann_zurueck"] is False, "eine frische Vorlage hat nichts zurückzunehmen"
        assert stand["kann_vor"] is False

        # Der fertige Zustand wird zum Ausgangszustand, sobald selbst etwas
        # geaendert wird - und genau dorthin fuehrt das erste Rueckgaengig.
        fertig = _zustand(anlage)
        karte = anlagen.als_json(anlage)["karten"][0]["id"]
        anlagen.karte_loeschen(karte)
        assert db.execute(
            "SELECT COUNT(*) AS n FROM zustand WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"] == 2

        verlauf.zurueck(anlage)
        _fremdschluessel_pruefen()
        assert _zustand(anlage) == fertig
        assert verlauf.stand_lesen(anlage)["kann_zurueck"] is False


def test_beispielanlage_schreibt_ihren_aufbau_nicht_in_den_verlauf(app):
    """Dasselbe fuer die Beispielanlagen des Erklaerbereichs - sie bauen ueber
    denselben Weg (core/lehrinhalte/beispielanlagen.py, _Bau)."""
    from core.lehrinhalte import beispielanlagen

    with app.app_context():
        projekt = anlagen.projekt_anlegen("Bausteine")
        anlage = beispielanlagen.baue_beispiel("erhitzer", projekt)
        db = database.get_db()
        assert db.execute(
            "SELECT COUNT(*) AS n FROM zustand WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"] == 0


def test_editorseite_bringt_die_beiden_knoepfe_mit(app):
    """Die Bedienung haengt an zwei festen Kennungen (siehe
    static/js/editor.js) - fehlt eine davon in der Vorlage, bleibt der
    Verlauf unbedienbar, ohne dass irgendein Test es merkte."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
    seite = app.test_client().get(f"/anlage/{anlage}").get_data(as_text=True)
    assert 'id="btn-zurueck"' in seite
    assert 'id="btn-vor"' in seite
    assert "Rückgängig" in seite


def test_editorseite_bringt_das_pfeilwerkzeug_mit(app):
    """Ein Pfeil laesst sich auswaehlen und dann ueber diesen Knopf loeschen
    (static/js/editor.js, pfeilAuswahlZeichnen) - der einzige Weg, der auf
    dem iPad ohne Entf-Taste funktioniert. Fehlt er in der Vorlage, bleibt
    eine falsche Verbindung dort unloeschbar, ohne dass es auffiele."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
    seite = app.test_client().get(f"/anlage/{anlage}").get_data(as_text=True)
    assert 'id="pfeil-werkzeug"' in seite
    assert 'id="btn-pfeil-loeschen"' in seite
    assert "Verbindung löschen" in seite
