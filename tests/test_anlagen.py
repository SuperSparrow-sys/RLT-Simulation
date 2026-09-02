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

        with pytest.raises(ValueError, match="gehoert nicht zu dieser Anlage"):
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
        with pytest.raises(ValueError, match="fuehrt schon woanders hin"):
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
