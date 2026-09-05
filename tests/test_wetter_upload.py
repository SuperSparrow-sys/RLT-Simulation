"""Ordner-Upload: mehrere Wetterdateien in einem Aufruf.

Der Browser filtert vorab auf die lesbaren Endungen (static/js/start.js), aber
der Endpunkt darf sich darauf nicht verlassen - geprueft wird hier deshalb auch
das, was ein Browser gar nicht erst schicken sollte.
"""

import io
from pathlib import Path

import pytest

from app import create_app
from core import database
from core.wetter import speicher

# Siehe tests/test_try_dat.py: das mittlere Jahr vollstaendig, die uebrigen
# gekuerzt auf Kopf und zwei Tage.
ORDNER = Path(__file__).parent / "daten" / "try"
JAHR_2015 = ORDNER / "TRY2015_510881137633_Jahr.dat"
SOMMER_2015 = ORDNER / "TRY2015_510881137633_Somm.dat"
JAHR_2045 = ORDNER / "TRY2045_510881137633_Jahr.dat"
MAPPE = Path(__file__).parent.parent / "referenz" / "RLTSimulation_Vorlage_AX_SIM_2.1.xls"
STUNDEN_AUSZUG = 48


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def hochladen(app, dateien, **felder):
    daten = {"datei": [(open(p, "rb"), Path(p).name) for p in dateien], **felder}
    return app.test_client().post(
        "/api/wetter/upload", data=daten, content_type="multipart/form-data"
    )


# --- Mehrere Dateien ------------------------------------------------------

def test_zwei_try_dateien_werden_zwei_datensaetze(app):
    antwort = hochladen(app, [JAHR_2015, SOMMER_2015], ort="Dresden_Industriegelände")
    assert antwort.status_code == 201

    ergebnis = antwort.get_json()
    assert len(ergebnis["datensaetze"]) == 2
    assert ergebnis["dateifehler"] == []
    nach_datei = {e["datei"]: e["stunden"] for e in ergebnis["datensaetze"]}
    assert nach_datei[JAHR_2015.name] == 8760
    assert nach_datei[SOMMER_2015.name] == STUNDEN_AUSZUG

    with app.app_context():
        gespeichert = speicher.datensaetze()
    assert len(gespeichert) == 2
    assert {d["ort"] for d in gespeichert} == {"Dresden_Industriegelände"}


def test_name_kommt_aus_jahr_und_art_des_try(app):
    hochladen(app, [JAHR_2015, SOMMER_2015, JAHR_2045], ort="Dresden")
    with app.app_context():
        namen = {d["name"] for d in speicher.datensaetze()}
    assert namen == {
        "2015 – mittleres Jahr",
        "2015 – extremer Sommer",
        "2045 – mittleres Jahr",
    }


def test_ort_koordinaten_und_jahr_landen_am_datensatz(app):
    hochladen(app, [JAHR_2015], ort="Dresden_Industriegelände")
    with app.app_context():
        eintrag = speicher.datensatz(speicher.datensaetze()[0]["id"])
    assert eintrag["ort"] == "Dresden_Industriegelände"
    assert eintrag["jahr"] == 2015
    assert eintrag["breite"] == pytest.approx(51.0881, abs=0.001)
    assert eintrag["laenge"] == pytest.approx(13.7633, abs=0.001)
    assert "mittleres Jahr" in eintrag["notiz"]
    assert "154" in eintrag["notiz"], "Höhenlage aus dem Kopf"


# --- Fehler einzelner Dateien ---------------------------------------------

def test_eine_kaputte_datei_reisst_die_guten_nicht_mit(app):
    daten = {
        "datei": [
            (open(JAHR_2015, "rb"), "TRY2015_510881137633_Jahr.dat"),
            (io.BytesIO(b"kein Testreferenzjahr"), "kaputt.dat"),
            (open(SOMMER_2015, "rb"), "TRY2015_510881137633_Somm.dat"),
        ],
        "ort": "Dresden",
    }
    antwort = app.test_client().post(
        "/api/wetter/upload", data=daten, content_type="multipart/form-data"
    )
    assert antwort.status_code == 201

    ergebnis = antwort.get_json()
    assert len(ergebnis["datensaetze"]) == 2
    assert len(ergebnis["dateifehler"]) == 1
    assert ergebnis["dateifehler"][0]["datei"] == "kaputt.dat"

    with app.app_context():
        assert len(speicher.datensaetze()) == 2


def test_kommt_keine_datei_durch_ist_es_ein_fehler(app):
    daten = {"datei": [(io.BytesIO(b"nichts"), "kaputt.dat")]}
    antwort = app.test_client().post(
        "/api/wetter/upload", data=daten, content_type="multipart/form-data"
    )
    assert antwort.status_code == 400
    assert antwort.get_json()["fehler"]


def test_eine_datei_mit_falscher_endung_wird_abgewiesen(app):
    """Der Browser filtert das dem TRY beiliegende Handbuch schon heraus; der
    Endpunkt darf sich darauf trotzdem nicht verlassen."""
    antwort = app.test_client().post(
        "/api/wetter/upload",
        data={"datei": (io.BytesIO(b"%PDF-1.4 kein Wetter"), "TRY-Handbuch.pdf")},
        content_type="multipart/form-data",
    )
    assert antwort.status_code == 400
    with app.app_context():
        assert speicher.datensaetze() == []


def test_ohne_datei_bleibt_es_bei_einer_meldung(app):
    antwort = app.test_client().post(
        "/api/wetter/upload", data={}, content_type="multipart/form-data"
    )
    assert antwort.status_code == 400
    assert "Datei" in antwort.get_json()["fehler"]


# --- Rueckwaertsvertraeglichkeit ------------------------------------------

def test_einzelne_excel_mappe_geht_weiter_wie_bisher(app):
    """Der alte Einzelupload ist der Sonderfall mit einer Datei - die Antwort
    traegt weiterhin 'id' und 'stunden' unmittelbar."""
    antwort = hochladen(app, [MAPPE], name="TRY04")
    assert antwort.status_code == 201
    ergebnis = antwort.get_json()
    assert ergebnis["stunden"] == 8760
    assert ergebnis["id"]
    with app.app_context():
        assert speicher.datensaetze()[0]["name"] == "TRY04"


def test_gegebener_name_gilt_nur_bei_einer_einzelnen_datei(app):
    """Bei mehreren Dateien waeren sonst alle gleich benannt."""
    hochladen(app, [JAHR_2015, SOMMER_2015], name="Sammelname", ort="Dresden")
    with app.app_context():
        namen = {d["name"] for d in speicher.datensaetze()}
    assert namen == {"2015 – mittleres Jahr", "2015 – extremer Sommer"}


def test_ein_archiv_wird_mit_einem_brauchbaren_hinweis_abgewiesen(app):
    """Ein hochgeladenes Zip soll nicht ausgepackt werden - aber der Nutzer
    soll erfahren, was er stattdessen tun kann."""
    import io

    antwort = app.test_client().post(
        "/api/wetter/upload",
        data={"datei": (io.BytesIO(b"PK\x03\x04"), "TRY_510881137633.zip")},
        content_type="multipart/form-data",
    )
    assert antwort.status_code == 400
    meldung = antwort.get_json()["fehler"]
    assert "entpack" in meldung.lower(), meldung
    with app.app_context():
        assert speicher.datensaetze() == []
