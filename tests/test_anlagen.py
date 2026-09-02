from datetime import datetime

import pytest

from app import create_app
from core import anlagen, database, ergebnisse, solver
from core.wetter import speicher


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def test_karte_anlegen_erzeugt_die_ports(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Testprojekt")
        anlage = anlagen.anlage_anlegen(projekt, "Variante A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 100.0, 200.0)

        db = database.get_db()
        ports = db.execute(
            "SELECT schluessel FROM port WHERE karte_id = ?", (karte,)
        ).fetchall()
        schluessel = {r["schluessel"] for r in ports}
    assert "luft_ein" in schluessel
    assert "stellgroesse" in schluessel


def test_karte_bekommt_die_vorgabeparameter(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        daten = anlagen.als_json(anlage)
    erhitzer = next(k for k in daten["karten"] if k["id"] == karte)
    assert erhitzer["parameter"]["QH_max"] == 101.0


def test_pfeil_verdrahtet_automatisch(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        a = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        b = anlagen.karte_anlegen(anlage, "kuehler", 300.0, 0.0)
        pfeil = anlagen.pfeil_anlegen(anlage, a, b)
    assert len(pfeil["verbindungen"]) == 1
    assert pfeil["verbindungen"][0]["von_schluessel"] == "luft_aus"
    assert pfeil["verbindungen"][0]["nach_schluessel"] == "luft_ein"


def test_eindeutiger_pfeil_meldet_keine_mehrdeutigkeit(app):
    """Erhitzer -> Kuehler hat nur einen passenden Luftweg - keine Alternative."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        a = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        b = anlagen.karte_anlegen(anlage, "kuehler", 300.0, 0.0)
        pfeil = anlagen.pfeil_anlegen(anlage, a, b)
        daten = anlagen.als_json(anlage)
    assert pfeil["mehrdeutig"] is False
    gelesen = next(p for p in daten["pfeile"] if p["id"] == pfeil["id"])
    assert gelesen["mehrdeutig"] is False


def test_mehrdeutiger_pfeil_wird_im_ergebnis_gemeldet(app):
    """Die WRG bietet Zu- und Abluft an - an einem neutralen Sammler ist das
    mehrdeutig (siehe core/graph.py: test_mehrdeutige_zuordnung_wird_gemeldet)."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        wrg = anlagen.karte_anlegen(anlage, "wrg", 0.0, 0.0)
        sammler = anlagen.karte_anlegen(anlage, "sammler", 300.0, 0.0)
        pfeil = anlagen.pfeil_anlegen(anlage, wrg, sammler)
        daten = anlagen.als_json(anlage)
    assert pfeil["mehrdeutig"] is True
    gelesen = next(p for p in daten["pfeile"] if p["id"] == pfeil["id"])
    assert gelesen["mehrdeutig"] is True


def test_regler_pfeil_verdrahtet_hin_und_zurueck(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        regler = anlagen.karte_anlegen(anlage, "p_regler", 0.0, 0.0)
        erhitzer = anlagen.karte_anlegen(anlage, "erhitzer", 300.0, 0.0)
        pfeil = anlagen.pfeil_anlegen(anlage, regler, erhitzer)
    richtungen = {(v["von_karte_id"], v["nach_karte_id"]) for v in pfeil["verbindungen"]}
    assert (regler, erhitzer) in richtungen
    assert (erhitzer, regler) in richtungen


def test_dynamischer_port_waechst_beim_zweiten_pfeil_nach(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        verteiler = anlagen.karte_anlegen(anlage, "verteiler", 0.0, 0.0)
        a = anlagen.karte_anlegen(anlage, "erhitzer", 300.0, 0.0)
        b = anlagen.karte_anlegen(anlage, "erhitzer", 300.0, 200.0)

        erster = anlagen.pfeil_anlegen(anlage, verteiler, a)
        zweiter = anlagen.pfeil_anlegen(anlage, verteiler, b)
    assert erster["verbindungen"][0]["von_schluessel"] == "luft_aus_1"
    assert zweiter["verbindungen"][0]["von_schluessel"] == "luft_aus_2"


def test_pfeil_loeschen_entfernt_alle_verbindungen(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        regler = anlagen.karte_anlegen(anlage, "p_regler", 0.0, 0.0)
        erhitzer = anlagen.karte_anlegen(anlage, "erhitzer", 300.0, 0.0)
        pfeil = anlagen.pfeil_anlegen(anlage, regler, erhitzer)
        anlagen.pfeil_loeschen(pfeil["id"])

        db = database.get_db()
        anzahl = db.execute("SELECT COUNT(*) AS n FROM verbindung").fetchone()["n"]
    assert anzahl == 0


def test_parameter_aendern_wird_gespeichert(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        anlagen.karte_aendern(karte, parameter={"QH_max": 55.0})
        daten = anlagen.als_json(anlage)
    assert next(k for k in daten["karten"] if k["id"] == karte)["parameter"]["QH_max"] == 55.0


def test_parameter_aendern_lehnt_negativen_wert_ab(app):
    """Ein Nennvolumenstrom kann nicht negativ sein (siehe
    core/bausteine/erhitzer.py, Param V_nenn) - das muss schon beim Speichern
    auffallen, nicht erst als falsches Rechenergebnis."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)

        with pytest.raises(anlagen.UngueltigeParameter) as ausnahme:
            anlagen.karte_aendern(karte, parameter={"V_nenn": -5.0})
        assert "V_nenn" in ausnahme.value.fehler
        assert "V_nenn" in str(ausnahme.value)

        # Der unzulaessige Wert wurde nicht gespeichert.
        daten = anlagen.als_json(anlage)
    assert next(k for k in daten["karten"] if k["id"] == karte)["parameter"]["V_nenn"] == 8200.0


def test_parameter_aendern_lehnt_unbekannten_auswahlwert_ab(app):
    """Konkretes Beispiel aus dem Bugreport: die Pumpenart eines Luftwaeschers
    kennt nur V/F/H - ein 'Q' darf nicht still auf einen Ersatzzweig fallen."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "luftwaescher", 0.0, 0.0)

        with pytest.raises(anlagen.UngueltigeParameter) as ausnahme:
            anlagen.karte_aendern(karte, parameter={"pumpenart": "Q"})
        assert "pumpenart" in ausnahme.value.fehler

        daten = anlagen.als_json(anlage)
    assert next(k for k in daten["karten"] if k["id"] == karte)["parameter"]["pumpenart"] == "H"


def test_parameter_aendern_erlaubt_grenzwerte(app):
    """Die Grenzen selbst sind gueltig (>=, <=, nicht > / <) - ein Wirkungsgrad
    von genau 100% darf nicht faelschlich abgelehnt werden."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "luftwaescher", 0.0, 0.0)
        anlagen.karte_aendern(karte, parameter={"absalzverlust": 0.0})
        anlagen.karte_aendern(karte, parameter={"absalzverlust": 100.0})
        anlagen.karte_aendern(karte, parameter={"V_nenn": 0.0})
        daten = anlagen.als_json(anlage)
    parameter = next(k for k in daten["karten"] if k["id"] == karte)["parameter"]
    assert parameter["absalzverlust"] == 100.0
    assert parameter["V_nenn"] == 0.0


def test_graph_laesst_sich_zurueckladen(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        a = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        b = anlagen.karte_anlegen(anlage, "kuehler", 300.0, 0.0)
        anlagen.pfeil_anlegen(anlage, a, b)
        g = anlagen.lade_graph(anlage)
    assert g.reihenfolge() == [a, b]


def test_pfeil_zwischen_zwei_anlagen_wird_verweigert(app):
    """Sonst entstuende ein Pfeil, dessen Verbindungen beim Laden verschwinden."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        eine = anlagen.anlage_anlegen(projekt, "A")
        andere = anlagen.anlage_anlegen(projekt, "B")
        hier = anlagen.karte_anlegen(eine, "erhitzer", 0.0, 0.0)
        dort = anlagen.karte_anlegen(andere, "kuehler", 0.0, 0.0)

        with pytest.raises(ValueError, match="gehört nicht zu dieser Anlage"):
            anlagen.pfeil_anlegen(eine, hier, dort)


def test_pfeil_zu_sich_selbst_wird_verweigert(app):
    """Die Oberflaeche macht diese Geste jetzt direkt erreichbar (Umschalt+Ziehen
    auf die eigene Karte zurueck) - ohne eigene Pruefung faellt sie nur zufaellig
    durch 'passt kein freier Anschluss zusammen'."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)

        with pytest.raises(ValueError, match="nicht mit sich selbst"):
            anlagen.pfeil_anlegen(anlage, karte, karte)


def test_karte_loeschen_nimmt_ihre_pfeile_mit(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        a = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        b = anlagen.karte_anlegen(anlage, "kuehler", 300.0, 0.0)
        anlagen.pfeil_anlegen(anlage, a, b)
        anlagen.karte_loeschen(a)

        db = database.get_db()
        pfeile = db.execute("SELECT COUNT(*) AS n FROM pfeil").fetchone()["n"]
        verbindungen = db.execute("SELECT COUNT(*) AS n FROM verbindung").fetchone()["n"]
    assert pfeile == 0
    assert verbindungen == 0


def test_api_listet_projekte_und_anlagen(app):
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Bürohaus")
        anlagen.anlage_anlegen(projekt, "Variante A")
        anlagen.anlage_anlegen(projekt, "Variante B")

    projekte = klient.get("/api/projekte").get_json()
    assert [p["name"] for p in projekte] == ["Bürohaus"]
    assert projekte[0]["anlagen"] == 2

    liste = klient.get(f"/api/anlagen?projekt_id={projekt}").get_json()
    assert [a["name"] for a in liste] == ["Variante A", "Variante B"]
    assert liste[0]["projekt_name"] == "Bürohaus"


def test_projekte_markiert_das_bausteine_sammelprojekt_als_lehrmaterial(app):
    """core.lehrinhalte.beispielanlagen.NAME_PROJEKT ("Bausteine") ist kein
    eigenes Projekt des Benutzers - die Startseite nutzt dieses Feld, um es
    getrennt von den eigenen Projekten anzuzeigen (siehe static/js/start.js,
    eigeneProjekte()/lehrmaterialProjekte())."""
    with app.app_context():
        anlagen.projekt_anlegen("Bausteine")
        anlagen.projekt_anlegen("Eigenes Projekt")

    projekte = {p["name"]: p for p in app.test_client().get("/api/projekte").get_json()}
    assert projekte["Bausteine"]["ist_lehrmaterial"] is True
    assert projekte["Eigenes Projekt"]["ist_lehrmaterial"] is False


def test_api_meldet_unbekannte_karte_als_nicht_gefunden(app):
    antwort = app.test_client().patch("/api/karten/9999", json={"pos_x": 1.0})
    assert antwort.status_code == 404


def test_api_liefert_die_palette(app):
    klient = app.test_client()
    antwort = klient.get("/api/palette")
    assert antwort.status_code == 200
    gruppen = antwort.get_json()
    assert "Luftbehandlung" in gruppen
    kennungen = {k["kennung"] for gruppe in gruppen.values() for k in gruppe}
    assert "erhitzer" in kennungen


def test_api_legt_karte_an(app):
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
    antwort = klient.post(
        "/api/karten",
        json={"anlage_id": anlage, "typ": "kuehler", "pos_x": 10, "pos_y": 20},
    )
    assert antwort.status_code == 201
    assert antwort.get_json()["typ"] == "kuehler"


def test_api_patch_meldet_ungueltigen_parameter_als_400(app):
    """Die Oberflaeche muss den Fehler erkennen koennen: eine deutsche,
    verstaendliche Meldung UND, welches Feld betroffen war (feldfehler) - nicht
    nur ein Statuscode (siehe static/js/panel.js, markiereFeldFehler)."""
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "luftwaescher", 0.0, 0.0)

    antwort = klient.patch(
        f"/api/karten/{karte}", json={"parameter": {"pumpenart": "Q"}}
    )
    assert antwort.status_code == 400
    daten = antwort.get_json()
    assert "pumpenart" in daten["feldfehler"]
    assert daten["fehler"]  # nicht leer, verstaendlicher Text auf Deutsch
    assert "Q" in daten["fehler"]

    with app.app_context():
        gelesen = anlagen.als_json(anlage)
    # Der ungueltige Wert steht nicht in der Datenbank.
    assert next(k for k in gelesen["karten"] if k["id"] == karte)["parameter"]["pumpenart"] == "H"


def test_api_patch_erhaelt_parametertypen(app):
    """PATCH /api/karten/<id> - der Weg, auf dem das Parameterfenster jede
    Aenderung sofort speichert - darf keinen Werttyp verbiegen: ein dict
    (Verteiler.anteile) muss ein dict bleiben, eine Liste (Ferien.zeitraeume)
    eine Liste, und eine Zahl (Erhitzer.QH_max) eine Zahl statt eines Texts.
    Ein Statuscode 200 allein sagt darueber nichts aus - deshalb wird nach
    dem Schreiben ueber GET zurueckgelesen und die Struktur geprueft."""
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        verteiler = anlagen.karte_anlegen(anlage, "verteiler", 0.0, 0.0)
        ferien = anlagen.karte_anlegen(anlage, "ferien", 0.0, 0.0)
        erhitzer = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)

    assert klient.patch(
        f"/api/karten/{verteiler}",
        json={"parameter": {"anteile": {"zuluft": 60, "abluft": 40}}},
    ).status_code == 200
    assert klient.patch(
        f"/api/karten/{ferien}",
        json={"parameter": {"zeitraeume": [{"von": "23.12.", "bis": "05.01."}]}},
    ).status_code == 200
    assert klient.patch(
        f"/api/karten/{erhitzer}", json={"parameter": {"QH_max": 55.5}}
    ).status_code == 200

    daten = klient.get(f"/api/anlagen/{anlage}").get_json()
    karten = {k["id"]: k for k in daten["karten"]}

    anteile = karten[verteiler]["parameter"]["anteile"]
    assert anteile == {"zuluft": 60, "abluft": 40}
    assert isinstance(anteile, dict)

    zeitraeume = karten[ferien]["parameter"]["zeitraeume"]
    assert zeitraeume == [{"von": "23.12.", "bis": "05.01."}]
    assert isinstance(zeitraeume, list)

    qh_max = karten[erhitzer]["parameter"]["QH_max"]
    assert qh_max == 55.5
    assert isinstance(qh_max, float)
    # dp_nenn wurde nicht mitgeschickt und muss bei der Vorgabe bleiben -
    # die PATCH-Route ersetzt nur die genannten Schluessel, nicht die ganze
    # Parametermenge.
    assert karten[erhitzer]["parameter"]["dp_nenn"] == 240.0


def test_einzelne_verbindung_von_hand(app):
    """Wo die Zuordnung offen bleibt, muss sie sich ausdruecklich setzen lassen."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        raum = anlagen.karte_anlegen(anlage, "einfacher_raum", 0.0, 0.0)
        regler = anlagen.karte_anlegen(anlage, "hysterese_regler", 300.0, 0.0)

        with pytest.raises(ValueError, match="kein freier Anschluss"):
            anlagen.pfeil_anlegen(anlage, raum, regler)

        daten = anlagen.als_json(anlage)
        ports = {k["id"]: {p["schluessel"]: p["id"] for p in k["ports"]}
                 for k in daten["karten"]}
        pfeil = anlagen.verbindung_anlegen(
            anlage, ports[raum]["F_Raum"], ports[regler]["istwert"]
        )
        assert pfeil["verbindungen"][0]["von_schluessel"] == "F_Raum"

        with pytest.raises(ValueError, match="schon belegt"):
            anlagen.verbindung_anlegen(
                anlage, ports[raum]["T_Raum"], ports[regler]["istwert"]
            )


def test_port_id_findet_den_anschluss(app):
    """anlagen.port_id ist der einzige Weg, an eine Anschluss-Id zu kommen -

    Vorlagen sollen dafuer keine eigene SQL-Abfrage schreiben."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        raum = anlagen.karte_anlegen(anlage, "einfacher_raum", 0.0, 0.0)

        daten = anlagen.als_json(anlage)
        erwartet = next(
            p["id"] for k in daten["karten"] for p in k["ports"]
            if k["id"] == raum and p["schluessel"] == "F_Raum"
        )

        assert anlagen.port_id(raum, "F_Raum") == erwartet

        with pytest.raises(KeyError, match="gibt es nicht"):
            anlagen.port_id(raum, "unbekannter_anschluss")


def test_handverdrahtung_verzweigt_keinen_luftkanal(app):
    """Auch von Hand fuehrt ein Luftausgang an genau eine Stelle."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        erhitzer = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        erster = anlagen.karte_anlegen(anlage, "kuehler", 300.0, 0.0)
        zweiter = anlagen.karte_anlegen(anlage, "kuehler", 300.0, 200.0)
        anlagen.pfeil_anlegen(anlage, erhitzer, erster)

        ports = {k["id"]: {p["schluessel"]: p["id"] for p in k["ports"]}
                 for k in anlagen.als_json(anlage)["karten"]}
        with pytest.raises(ValueError, match="führt schon woanders hin"):
            anlagen.verbindung_anlegen(
                anlage, ports[erhitzer]["luft_aus"], ports[zweiter]["luft_ein"]
            )


def test_handverdrahtung_speist_mehrere_verbraucher_mit_einem_signal(app):
    """Ein Stellsignal darf von Hand an mehrere Stellen gehen."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        regler = anlagen.karte_anlegen(anlage, "p_regler", 0.0, 0.0)
        eins = anlagen.karte_anlegen(anlage, "erhitzer", 300.0, 0.0)
        zwei = anlagen.karte_anlegen(anlage, "erhitzer", 300.0, 200.0)

        ports = {k["id"]: {p["schluessel"]: p["id"] for p in k["ports"]}
                 for k in anlagen.als_json(anlage)["karten"]}
        for ziel in (eins, zwei):
            anlagen.verbindung_anlegen(
                anlage, ports[regler]["ausgang_2"], ports[ziel]["stellgroesse"]
            )

        g = anlagen.lade_graph(anlage)
    assert len(g.verbindungen) == 2


def test_felder_tragen_darstellung_und_dezimalstellen(app):
    """Jedes Feld sagt, WIE es angezeigt/eingegeben wird - nicht nur Label und
    Einheit. Am Wochenzeitplan haengt genau der Fall aus dem Bugreport:
    05:00 Uhr als Tagesanteil mit siebzehn Nachkommastellen."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        plan = anlagen.karte_anlegen(anlage, "wochenzeitplan", 0.0, 0.0)
        daten = anlagen.als_json(anlage)

    karte = next(k for k in daten["karten"] if k["id"] == plan)
    montag_von = next(f for f in karte["felder"] if f["schluessel"] == "von_montag")
    assert montag_von["darstellung"] == "uhrzeit"
    # Der gespeicherte Wert bleibt der exakte Tagesanteil - nur die Anzeige
    # rundet, siehe test_basis.py fuer die Umrechnung selbst.
    assert karte["parameter"]["von_montag"] == pytest.approx(5.0 / 24.0)


def test_ports_tragen_eine_lesbare_beschriftung(app):
    """Der Anschluesse-Abschnitt des Parameterfensters zeigte bisher nur den
    rohen Schluessel samt Rolle (z.B. 'ausgang_2 · stellgroesse') - jeder Port
    bekommt jetzt ein Label (core.anlagen._port_label)."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        erhitzer = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        bilanz = anlagen.karte_anlegen(anlage, "bilanz", 0.0, 0.0)
        daten = anlagen.als_json(anlage)

    erhitzer_karte = next(k for k in daten["karten"] if k["id"] == erhitzer)
    # Kein AUSGABE_LABEL und kein gleichnamiger Parameter -> uebersetzte Rolle.
    luft_ein = next(p for p in erhitzer_karte["ports"] if p["schluessel"] == "luft_ein")
    assert luft_ein["label"] == "Zuluft"
    # AUSGABE_LABEL greift, wo vorhanden.
    t_aus = next(p for p in erhitzer_karte["ports"] if p["schluessel"] == "T_aus")
    assert t_aus["label"] == "Austrittstemperatur"

    # 'hochtarif' hat kein passendes Wort in der uebersetzten Rolle
    # (rolle=messwert) - AUSGABE_LABEL traegt die eigentliche Bedeutung.
    bilanz_karte = next(k for k in daten["karten"] if k["id"] == bilanz)
    hochtarif = next(p for p in bilanz_karte["ports"] if p["schluessel"] == "hochtarif")
    assert hochtarif["label"] == "Hochtarif aktiv"


def test_felder_ohne_gleichnamigen_eingang_sind_nicht_ueberschreibbar(app):
    """Ein Parameter ohne gleichnamigen Eingangsport - etwa QH_max am Erhitzer -
    kann nicht durch eine Verbindung ausser Kraft gesetzt werden."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        erhitzer = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        daten = anlagen.als_json(anlage)

    karte = next(k for k in daten["karten"] if k["id"] == erhitzer)
    feld = next(f for f in karte["felder"] if f["schluessel"] == "QH_max")
    assert feld["ueberschrieben_von"] is None


def test_fester_wert_zeigt_ueberschreibung_durch_verbindung_an(app):
    """Sobald ein Pfeil auf 'istwert' zeigt, muss das Fenster erkennen, dass
    der feste Parameterwert wirkungslos ist - samt Herkunft der Verbindung."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        raum = anlagen.karte_anlegen(anlage, "raum", 0.0, 0.0)
        regler = anlagen.karte_anlegen(anlage, "hysterese_regler", 200.0, 0.0)

        daten = anlagen.als_json(anlage)
        ports = {k["id"]: {p["schluessel"]: p["id"] for p in k["ports"]}
                 for k in daten["karten"]}

        vor = next(k for k in daten["karten"] if k["id"] == regler)
        feld_vor = next(f for f in vor["felder"] if f["schluessel"] == "istwert")
        assert feld_vor["ueberschrieben_von"] is None

        verbindung = anlagen.verbindung_anlegen(
            anlage, ports[raum]["T_Raum"], ports[regler]["istwert"]
        )

        nachher = anlagen.als_json(anlage)
        regler_karte = next(k for k in nachher["karten"] if k["id"] == regler)
        feld = next(f for f in regler_karte["felder"] if f["schluessel"] == "istwert")

    assert feld["ueberschrieben_von"] == {
        "von_karte_id": raum,
        "von_karte_name": "Raum",
        "von_schluessel": "T_Raum",
        "von_label": "Raumtemperatur",
        "pfeil_id": verbindung["id"],
    }

    # Und sie laesst sich ueber genau diese Pfeil-Id wieder loesen.
    with app.app_context():
        anlagen.pfeil_loeschen(verbindung["id"])
        wieder_frei = anlagen.als_json(anlage)
    regler_karte = next(k for k in wieder_frei["karten"] if k["id"] == regler)
    feld = next(f for f in regler_karte["felder"] if f["schluessel"] == "istwert")
    assert feld["ueberschrieben_von"] is None


def test_messwerte_von_listet_alle_messwertausgaenge(app):
    """Grundlage fuer die Regler-Verdrahtung: welche Groessen bietet die Anlage
    ueberhaupt an, um sie gezielt an einen Istwert/Sollwert zu haengen?"""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        raum = anlagen.karte_anlegen(anlage, "raum", 0.0, 0.0)

        messwerte = anlagen.messwerte_von(anlage)
        ports = {p["schluessel"]: p["id"] for p in
                 next(k for k in anlagen.als_json(anlage)["karten"]
                      if k["id"] == raum)["ports"]}

    schluessel = {m["schluessel"] for m in messwerte}
    assert {"T_Raum", "F_Raum"} <= schluessel
    treffer = next(m for m in messwerte if m["schluessel"] == "T_Raum")
    assert treffer == {
        "port_id": ports["T_Raum"],
        "karte_id": raum,
        "karte_name": "Raum",
        "karte_typ": "raum",
        "schluessel": "T_Raum",
        "label": "Raumtemperatur",
    }


def test_messwerte_von_bleibt_verfuegbar_wenn_schon_verbunden(app):
    """Ein Messwert darf mehrere Abnehmer speisen - er soll deshalb auch dann
    noch in der Auswahl stehen, wenn er schon irgendwo angeschlossen ist."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        raum = anlagen.karte_anlegen(anlage, "raum", 0.0, 0.0)
        regler = anlagen.karte_anlegen(anlage, "hysterese_regler", 200.0, 0.0)
        ports = {k["id"]: {p["schluessel"]: p["id"] for p in k["ports"]}
                 for k in anlagen.als_json(anlage)["karten"]}
        anlagen.verbindung_anlegen(
            anlage, ports[raum]["T_Raum"], ports[regler]["istwert"]
        )
        messwerte = anlagen.messwerte_von(anlage)

    assert any(m["schluessel"] == "T_Raum" for m in messwerte)


# -- Loeschen und Umbenennen -----------------------------------------------

def _wetter_anlegen():
    return speicher.datensatz_anlegen(
        "W", "upload",
        [{"zeitpunkt": datetime(2024, 1, 1), "t_au": 0.0, "x_au": 4.0,
          "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0}],
    )


def _lauf_anlegen(anlage_id, wetter_id):
    """Legt einen abgeschlossenen Simulationslauf mit Zeitreihe und Bilanz an
    - fuer die Kaskaden-Tests unten reicht ein einstuendiger Lauf."""
    graph = anlagen.lade_graph(anlage_id)
    lauf = solver.Lauf(
        stunden=[{}], bilanz={"strom_ht": 0.0, "strom_nt": 0.0, "waerme": 0.0,
                               "kaelte": 0.0, "wasser": 0.0},
        warnungen=[],
    )
    return ergebnisse.speichere(anlage_id, wetter_id, 0, 1, lauf, graph, dauer=0.1)


def test_projekt_umbenennen(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Alt")
        anlagen.projekt_umbenennen(projekt, "Neu")
        name = database.get_db().execute(
            "SELECT name FROM projekt WHERE id = ?", (projekt,)
        ).fetchone()["name"]
    assert name == "Neu"


def test_projekt_umbenennen_unbekanntes_projekt_meldet_fehler(app):
    with app.app_context():
        with pytest.raises(KeyError):
            anlagen.projekt_umbenennen(9999, "Neu")


def test_projekt_loeschen_nimmt_anlagen_karten_und_laeufe_mit(app):
    """Ein Projekt mit einer Anlage, die eine Karte und einen gespeicherten
    Lauf traegt - nach dem Loeschen darf keine Zeile mehr uebrig sein, auch
    nicht in zeitreihe/bilanz (ON DELETE CASCADE ueber drei Ebenen: projekt ->
    anlage -> simulation -> zeitreihe/bilanz)."""
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        wetter = _wetter_anlegen()
        sim = _lauf_anlegen(anlage, wetter)

        anlagen.projekt_loeschen(projekt)

        db = database.get_db()
        assert db.execute(
            "SELECT COUNT(*) AS n FROM anlage WHERE projekt_id = ?", (projekt,)
        ).fetchone()["n"] == 0
        assert db.execute(
            "SELECT COUNT(*) AS n FROM karte WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"] == 0
        assert db.execute(
            "SELECT COUNT(*) AS n FROM simulation WHERE id = ?", (sim,)
        ).fetchone()["n"] == 0
        assert db.execute(
            "SELECT COUNT(*) AS n FROM zeitreihe WHERE simulation_id = ?", (sim,)
        ).fetchone()["n"] == 0
        assert db.execute(
            "SELECT COUNT(*) AS n FROM bilanz WHERE simulation_id = ?", (sim,)
        ).fetchone()["n"] == 0
        # Der Wetterdatensatz gehoert nicht zum Projekt und bleibt stehen.
        assert db.execute(
            "SELECT COUNT(*) AS n FROM wetterdatensatz WHERE id = ?", (wetter,)
        ).fetchone()["n"] == 1
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_anlage_umbenennen(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "Alt")
        anlagen.anlage_umbenennen(anlage, "Neu")
        name = database.get_db().execute(
            "SELECT name FROM anlage WHERE id = ?", (anlage,)
        ).fetchone()["name"]
    assert name == "Neu"


def test_anlage_umbenennen_unbekannte_anlage_meldet_fehler(app):
    with app.app_context():
        with pytest.raises(KeyError):
            anlagen.anlage_umbenennen(9999, "Neu")


def test_anlage_loeschen_nimmt_karten_pfeile_und_laeufe_mit(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        a = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
        b = anlagen.karte_anlegen(anlage, "kuehler", 300.0, 0.0)
        anlagen.pfeil_anlegen(anlage, a, b)
        wetter = _wetter_anlegen()
        sim = _lauf_anlegen(anlage, wetter)

        anlagen.anlage_loeschen(anlage)

        db = database.get_db()
        assert db.execute(
            "SELECT COUNT(*) AS n FROM karte WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"] == 0
        assert db.execute(
            "SELECT COUNT(*) AS n FROM pfeil WHERE anlage_id = ?", (anlage,)
        ).fetchone()["n"] == 0
        assert db.execute(
            "SELECT COUNT(*) AS n FROM zeitreihe WHERE simulation_id = ?", (sim,)
        ).fetchone()["n"] == 0
        # Das Projekt selbst bleibt bestehen - nur diese eine Anlage ist weg.
        assert db.execute(
            "SELECT COUNT(*) AS n FROM projekt WHERE id = ?", (projekt,)
        ).fetchone()["n"] == 1
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_anlagen_von_zaehlt_simulationen_mit(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        wetter = _wetter_anlegen()
        _lauf_anlegen(anlage, wetter)
        _lauf_anlegen(anlage, wetter)
        eintrag = next(a for a in anlagen.anlagen_von(projekt) if a["id"] == anlage)
    assert eintrag["simulationen"] == 2


def test_projekte_zaehlt_simulationen_ueber_alle_anlagen(app):
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        eine = anlagen.anlage_anlegen(projekt, "A")
        andere = anlagen.anlage_anlegen(projekt, "B")
        wetter = _wetter_anlegen()
        _lauf_anlegen(eine, wetter)
        _lauf_anlegen(andere, wetter)
        eintrag = next(p for p in anlagen.projekte() if p["id"] == projekt)
    assert eintrag["simulationen"] == 2
    assert eintrag["anlagen"] == 2


def test_api_projekt_umbenennen_und_loeschen(app):
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Alt")

    antwort = klient.patch(f"/api/projekte/{projekt}", json={"name": "Neu"})
    assert antwort.status_code == 200
    assert klient.get("/api/projekte").get_json()[0]["name"] == "Neu"

    antwort = klient.delete(f"/api/projekte/{projekt}")
    assert antwort.status_code == 200
    assert klient.get("/api/projekte").get_json() == []


def test_api_projekt_umbenennen_unbekannt_meldet_404(app):
    klient = app.test_client()
    antwort = klient.patch("/api/projekte/9999", json={"name": "Neu"})
    assert antwort.status_code == 404


def test_api_anlage_umbenennen_und_loeschen(app):
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "Alt")

    antwort = klient.patch(f"/api/anlagen/{anlage}", json={"name": "Neu"})
    assert antwort.status_code == 200
    assert klient.get(f"/api/anlagen?projekt_id={projekt}").get_json()[0]["name"] == "Neu"

    antwort = klient.delete(f"/api/anlagen/{anlage}")
    assert antwort.status_code == 200
    assert klient.get(f"/api/anlagen?projekt_id={projekt}").get_json() == []


# -- Eingabefehler (400) und unbekannte Kennungen (404) statt 500 -----------
#
# Vorher fuehrten alle Faelle hier zu einem rohen 500: ein fehlendes
# Pflichtfeld oder ein unbekannter Bezug wurde nirgends abgefangen. Jetzt gilt
# durchgehend: ein Eingabefehler (fehlendes/leeres Feld, falscher Typ) ergibt
# 400 mit einer deutschen Meldung, eine unbekannte Kennung (Projekt, Anlage,
# Kartentyp, Karte, Port) 404 - genau wie es beim Umbenennen schon lief.

def test_api_projekt_anlegen_ohne_name_meldet_400(app):
    klient = app.test_client()
    antwort = klient.post("/api/projekte", json={})
    assert antwort.status_code == 400
    assert antwort.get_json()["fehler"]


def test_api_anlage_anlegen_ohne_name_meldet_400(app):
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
    antwort = klient.post("/api/anlagen", json={"projekt_id": projekt})
    assert antwort.status_code == 400


def test_api_anlage_anlegen_mit_fremdem_projekt_meldet_404(app):
    klient = app.test_client()
    antwort = klient.post("/api/anlagen", json={"projekt_id": 9999, "name": "A"})
    assert antwort.status_code == 404


def test_api_anlage_umbenennen_ohne_name_meldet_400(app):
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
    antwort = klient.patch(f"/api/anlagen/{anlage}", json={})
    assert antwort.status_code == 400


def test_api_anlage_lesen_unbekannte_anlage_meldet_404(app):
    klient = app.test_client()
    antwort = klient.get("/api/anlagen/9999")
    assert antwort.status_code == 404


def test_api_karte_anlegen_unbekannter_typ_meldet_404(app):
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
    antwort = klient.post("/api/karten", json={"anlage_id": anlage, "typ": "gibtsnicht"})
    assert antwort.status_code == 404
    assert antwort.get_json()["fehler"]


def test_api_karte_anlegen_fremde_anlage_meldet_404(app):
    klient = app.test_client()
    antwort = klient.post("/api/karten", json={"anlage_id": 9999, "typ": "erhitzer"})
    assert antwort.status_code == 404


def test_api_karte_anlegen_ohne_typ_meldet_400(app):
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
    antwort = klient.post("/api/karten", json={"anlage_id": anlage})
    assert antwort.status_code == 400


def test_api_pfeil_anlegen_ohne_pflichtfeld_meldet_400(app):
    klient = app.test_client()
    antwort = klient.post("/api/pfeile", json={"anlage_id": 1})
    assert antwort.status_code == 400


def test_api_pfeil_anlegen_unbekannte_karte_meldet_404(app):
    klient = app.test_client()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("P")
        anlage = anlagen.anlage_anlegen(projekt, "A")
        karte = anlagen.karte_anlegen(anlage, "erhitzer", 0.0, 0.0)
    antwort = klient.post(
        "/api/pfeile",
        json={"anlage_id": anlage, "von_karte_id": karte, "nach_karte_id": 9999},
    )
    assert antwort.status_code == 404


def test_api_verbindung_anlegen_ohne_pflichtfeld_meldet_400(app):
    klient = app.test_client()
    antwort = klient.post("/api/verbindungen", json={"anlage_id": 1})
    assert antwort.status_code == 400
