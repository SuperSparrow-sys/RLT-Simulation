import pytest

from app import create_app
from core import anlagen, database
from core.vorlagen import ax_sim_2_1


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def test_vorlage_legt_alle_karten_an(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        daten = anlagen.als_json(anlage)
    typen = [k["typ"] for k in daten["karten"]]
    assert typen.count("ventilator") == 3          # zwei Zuluft, eine Abluft
    assert typen.count("kuehler") == 2
    assert typen.count("luftwaescher") == 2
    assert "wrg" in typen
    assert "einfacher_raum" in typen
    assert "bilanz" in typen


def test_vorlage_ist_vollstaendig_verdrahtet(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        g = anlagen.lade_graph(anlage)

    ohne_eingang = [
        k for k in g.karten.values()
        if any(p.art == "luft" and p.richtung == "ein" for p in k.ports)
        and not g.eingaenge_von(k.id)
    ]
    assert ohne_eingang == [], [k.name for k in ohne_eingang]


def test_nennwerte_entsprechen_der_excel(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        daten = anlagen.als_json(anlage)

    nach_name = {k["name"]: k["parameter"] for k in daten["karten"]}
    assert nach_name["Wärmerückgewinnung"]["V_nenn"] == 12200.0
    assert nach_name["Wärmerückgewinnung"]["rueckwaermzahl"] == 81.0
    assert nach_name["Zuluftventilator Halle"]["V_max"] == 8200.0
    assert nach_name["Zuluftventilator Halle"]["PE_max"] == 4.9
    assert nach_name["Erhitzer Halle"]["QH_max"] == 101.0
    assert nach_name["Kühler Halle"]["QK_nenn"] == 63.0


def test_energiepreise_entsprechen_der_excel(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        daten = anlagen.als_json(anlage)
    bilanz = next(k for k in daten["karten"] if k["typ"] == "bilanz")["parameter"]
    assert bilanz["preis_strom_nt"] == 150.0
    assert bilanz["preis_waerme"] == 50.0
    assert bilanz["preis_kaelte"] == 50.0
    assert bilanz["preis_wasser"] == 4.0


def test_vorlage_ist_rechenbar(app):
    """Sie muss sich sortieren lassen und darf keine losen Enden haben."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        g = anlagen.lade_graph(anlage)
    assert len(g.reihenfolge()) == len(g.karten)


def test_api_legt_die_vorlage_an(app):
    klient = app.test_client()
    projekt = klient.post("/api/projekte", json={"name": "P"}).get_json()["id"]
    antwort = klient.post(
        "/api/anlagen/aus_vorlage",
        json={"projekt_id": projekt, "vorlage": "ax_sim_2_1", "name": "Referenz"},
    )
    assert antwort.status_code == 201
    assert antwort.get_json()["id"] > 0


def test_api_vorlagen_liefert_einen_lesbaren_anzeigenamen(app):
    """'name' ist ein Anzeigename fuer die Anwenderin, keine zweite Kopie der
    technischen Kennung - die Startseite zeigt dieses Feld direkt an, eine
    Kennung wie 'ax_sim_2_1' waere dort fehl am Platz. Die Kennung selbst
    bleibt unveraendert der Schluessel des Objekts."""
    klient = app.test_client()
    daten = klient.get("/api/vorlagen").get_json()
    assert "ax_sim_2_1" in daten
    vorlage = daten["ax_sim_2_1"]
    assert vorlage["name"] == "AX_SIM 2.1"
    assert vorlage["name"] != "ax_sim_2_1"


def test_waescherregler_misst_die_raumfeuchte(app):
    """Sonst laeuft der Waescher das ganze Jahr auf Vollast."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        daten = anlagen.als_json(anlage)

    nach_id = {k["id"]: k for k in daten["karten"]}
    ports = {p["id"]: (nach_id[k["id"]]["name"], p["schluessel"])
             for k in daten["karten"] for p in k["ports"]}
    verbindungen = [
        (ports[v["von_port_id"]], ports[v["nach_port_id"]])
        for pfeil in daten["pfeile"] for v in pfeil["verbindungen"]
    ]
    an_die_waescherregler = [
        (von, nach) for von, nach in verbindungen
        if "Regler Luftwäscher" in nach[0]
    ]
    assert an_die_waescherregler, "Die Waescherregler bekommen gar keinen Messwert"
    for von, nach in an_die_waescherregler:
        assert von[1] == "F_Raum", f"{von} -> {nach}"
        assert nach[1] == "sollwert", f"{von} -> {nach}"


def test_kuehler_wird_von_zwei_reglern_gestellt(app):
    """Anlage!S16 = MAX(100-S61; S72) - Entfeuchtung und Kuehlung."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        daten = anlagen.als_json(anlage)

    typen = [k["typ"] for k in daten["karten"]]
    assert typen.count("maximalwert") >= 2, "je Kuehler ein Maximalglied"
    assert typen.count("faktor") >= 2, "je Erhitzer ein Faktorglied fuer die Verriegelung"


def test_waermerueckgewinnung_wird_geregelt(app):
    """Anlage!J20 = J61, J21 = 100 - J20, J60 = J38.

    Befund vor dieser Pruefung: An den beiden Stellgroessen-Anschluessen der WRG
    hing kein Pfeil. Der Baustein liest 'stellgroesse' mit 0 als Vorgabe, und
    anders als der Ventilator hat er keinen Ersatzparameter - die
    Rueckgewinnung war damit das ganze Jahr ueber abgeschaltet, Q_WRG blieb
    null, und die Fortluft ging ungenutzt ins Freie.
    """
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        daten = anlagen.als_json(anlage)

    nach_id = {k["id"]: k for k in daten["karten"]}
    ports = {p["id"]: (nach_id[k["id"]]["name"], p["schluessel"])
             for k in daten["karten"] for p in k["ports"]}
    verbindungen = [
        (ports[v["von_port_id"]], ports[v["nach_port_id"]])
        for pfeil in daten["pfeile"] for v in pfeil["verbindungen"]
    ]

    an_die_wrg = {
        (von, nach[1]) for von, nach in verbindungen
        if nach[0] == "Wärmerückgewinnung" and nach[1].startswith("stellgroesse")
    }
    gestellt = {schluessel for _, schluessel in an_die_wrg}
    assert gestellt == {"stellgroesse", "stellgroesse_bypass"}, an_die_wrg

    # Anlage!J20 = J61: der TRAEGE Ausgang des Reglers, nicht der schnelle.
    quellen = dict(an_die_wrg)
    assert quellen[("Regler Wärmerückgewinnung", "ausgang_2")] == "stellgroesse"
    # Anlage!J21 = 100 - J20: der Bypass ueber ein Umkehrglied.
    assert quellen[("Umkehrung WRG-Bypass", "ausgang")] == "stellgroesse_bypass"

    # Anlage!J60 = J38: der Regler misst die Zulufttemperatur der WRG selbst.
    istwert = [
        (von, nach) for von, nach in verbindungen
        if nach == ("Regler Wärmerückgewinnung", "istwert_2")
    ]
    assert istwert == [(("Wärmerückgewinnung", "T_ZU"),
                        ("Regler Wärmerückgewinnung", "istwert_2"))], istwert

    regler = next(k for k in daten["karten"] if k["name"] == "Regler Wärmerückgewinnung")
    assert regler["parameter"]["sollwert_2"] == 18.0   # Anlage!J59


def test_reglerverstaerkungen_entsprechen_der_excel(app):
    """Anlage!K52 speist Ausgang 1, K54 speist Ausgang 2 - der traege hat die 10."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Referenz")
        anlage = ax_sim_2_1.baue(projekt, "AX_SIM 2.1")
        daten = anlagen.als_json(anlage)

    regler = [k for k in daten["karten"] if k["typ"] == "p_regler"]
    assert regler, "die Vorlage hat keine P-Regler"
    for k in regler:
        assert k["parameter"]["xp_1"] == 5.0, k["name"]
        assert k["parameter"]["xp_2"] == 10.0, k["name"]
