"""Wetterabruf ueber die Open-Meteo Archive-API.

Alle Tests ausser den mit @pytest.mark.slow markierten laufen ohne Internet -
core.wetter.openmeteo._anfrage wird durch feste Beispieldaten ersetzt.
"""

import urllib.error
from datetime import date, datetime

import pytest

from app import create_app
from core import database
from core.bausteine import stoffdaten
from core.wetter import openmeteo, speicher

BREITE, LAENGE = 52.52, 13.41
NICHT_SCHALTJAHR = 2023  # 365 Tage
SCHALTJAHR = 2024  # 366 Tage


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "test.db")
    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()
        yield anwendung


def _stunden_reihe(jahr):
    tage = 366 if jahr == SCHALTJAHR else 365
    zeiten = []
    tag = date(jahr, 1, 1)
    stunde = 0
    while stunde < tage * 24:
        zeiten.append(f"{tag.isoformat()}T{stunde % 24:02d}:00")
        if stunde % 24 == 23:
            tag = date.fromordinal(tag.toordinal() + 1)
        stunde += 1
    return zeiten


def _antworten(jahr, *, luecke_in=None, kuerzen=False, azimut_abweichung=None):
    """Baut die fuenf Antworten nach, wie sie _anfrage() liefern wuerde -
    fuer jede der fuenf Teilabfragen eine, in der Reihenfolge, in der
    abrufen() sie erwartet (str_s, str_o, str_w, str_n je einzeln, dazu die
    gemeinsame Horizont-Antwort)."""
    zeiten = _stunden_reihe(jahr)
    if kuerzen:
        zeiten = zeiten[:-1]
    n = len(zeiten)

    horizont = {
        "hourly": {
            "time": list(zeiten),
            "temperature_2m": [10.0 + (i % 20) for i in range(n)],
            "relative_humidity_2m": [60.0 for _ in range(n)],
            "shortwave_radiation": [0.0 if i % 24 < 6 else 100.0 for i in range(n)],
        }
    }
    if luecke_in == "temperature_2m":
        horizont["hourly"]["temperature_2m"][5] = None
    if luecke_in == "relative_humidity_2m":
        horizont["hourly"]["relative_humidity_2m"][5] = None

    richtungen = {}
    for feld, basis in (("str_s", 50.0), ("str_o", 30.0), ("str_w", 20.0), ("str_n", 5.0)):
        eigene_zeiten = list(zeiten)
        if azimut_abweichung == feld:
            eigene_zeiten[0] = "abweichend"
        richtungen[feld] = {
            "hourly": {
                "time": eigene_zeiten,
                "global_tilted_irradiance": [
                    0.0 if i % 24 < 6 else basis for i in range(n)
                ],
            }
        }
    return horizont, richtungen


def _anfrage_faelschen(monkeypatch, horizont, richtungen):
    """Ersetzt openmeteo._anfrage so, dass sie je nach angefragtem Feld/Azimut
    die passende vorbereitete Antwort liefert, ohne das Netz zu benutzen."""
    azimut_zu_feld = {azimut: feld for feld, azimut in openmeteo._AZIMUTE.items()}

    def gefaelscht(parameter):
        if parameter["hourly"] == "global_tilted_irradiance":
            feld = azimut_zu_feld[parameter["azimuth"]]
            return richtungen[feld]
        return horizont

    monkeypatch.setattr(openmeteo, "_anfrage", gefaelscht)


# -- Umrechnung relative -> absolute Feuchte ---------------------------------

def test_absolute_feuchte_stimmt_mit_stoffdaten_ueberein():
    for t, rh in [(20.0, 50.0), (-5.0, 80.0), (30.0, 90.0), (0.0, 100.0), (15.0, 0.0)]:
        x = openmeteo._absolute_feuchte(t, rh)
        assert stoffdaten.rel_feuchte(t, x) == pytest.approx(rh, abs=1e-6)


def test_absolute_feuchte_kappt_werte_ausserhalb_0_bis_100():
    # Open-Meteo kann durch Rundung minimal ueber 100% liegen - das darf nicht
    # zu einem negativen Nenner (100000 - p_dampf) oder einem Fehler fuehren.
    assert openmeteo._absolute_feuchte(10.0, 103.0) == pytest.approx(
        openmeteo._absolute_feuchte(10.0, 100.0)
    )
    assert openmeteo._absolute_feuchte(10.0, -5.0) == pytest.approx(0.0)


# -- Jahr- und Ortspruefung ---------------------------------------------------

def test_jahr_vor_1940_wird_abgelehnt():
    with pytest.raises(openmeteo.WetterEingabeFehler):
        openmeteo._jahr_pruefen(1900)


def test_laufendes_jahr_wird_abgelehnt(monkeypatch):
    heute = date(2026, 9, 1)

    class GefaelschtesDatum(date):
        @classmethod
        def today(cls):
            return heute

    monkeypatch.setattr(openmeteo, "date", GefaelschtesDatum)
    with pytest.raises(openmeteo.WetterEingabeFehler):
        openmeteo._jahr_pruefen(2026)
    # das letzte abgeschlossene Jahr ist dagegen erlaubt
    assert openmeteo._jahr_pruefen(2025) == 2025


def test_jahr_muss_eine_zahl_sein():
    with pytest.raises(openmeteo.WetterEingabeFehler):
        openmeteo._jahr_pruefen("nicht-numerisch")


def test_ort_muss_zahlen_sein():
    with pytest.raises(openmeteo.WetterEingabeFehler):
        openmeteo._ort_pruefen("nicht-numerisch", 13.41)


# -- Abruf: Abbildung auf die kanonische Form ---------------------------------

def test_abrufen_liefert_die_kanonische_form(monkeypatch):
    horizont, richtungen = _antworten(NICHT_SCHALTJAHR)
    _anfrage_faelschen(monkeypatch, horizont, richtungen)

    stunden = openmeteo.abrufen(BREITE, LAENGE, NICHT_SCHALTJAHR)

    assert len(stunden) == 8760
    erste = stunden[0]
    assert set(erste) == {"zeitpunkt", "t_au", "x_au", "str_s", "str_o", "str_w",
                           "str_n", "str_h"}
    assert erste["zeitpunkt"] == datetime(NICHT_SCHALTJAHR, 1, 1, 0)
    assert erste["t_au"] == pytest.approx(10.0)
    assert erste["x_au"] == pytest.approx(openmeteo._absolute_feuchte(10.0, 60.0))
    # Mittagsstunde (12 Uhr) hat in den gefaelschten Daten Strahlung > 0
    mittag = stunden[12]
    assert mittag["str_s"] == pytest.approx(50.0)
    assert mittag["str_o"] == pytest.approx(30.0)
    assert mittag["str_w"] == pytest.approx(20.0)
    assert mittag["str_n"] == pytest.approx(5.0)
    assert mittag["str_h"] == pytest.approx(100.0)


def test_abrufen_erkennt_ein_schaltjahr(monkeypatch):
    horizont, richtungen = _antworten(SCHALTJAHR)
    _anfrage_faelschen(monkeypatch, horizont, richtungen)

    stunden = openmeteo.abrufen(BREITE, LAENGE, SCHALTJAHR)

    assert len(stunden) == 8784


def test_abrufen_meldet_eine_datenluecke(monkeypatch):
    horizont, richtungen = _antworten(NICHT_SCHALTJAHR, luecke_in="temperature_2m")
    _anfrage_faelschen(monkeypatch, horizont, richtungen)

    with pytest.raises(openmeteo.WetterAbrufFehler):
        openmeteo.abrufen(BREITE, LAENGE, NICHT_SCHALTJAHR)


def test_abrufen_meldet_zu_wenige_stunden(monkeypatch):
    horizont, richtungen = _antworten(NICHT_SCHALTJAHR, kuerzen=True)
    _anfrage_faelschen(monkeypatch, horizont, richtungen)

    with pytest.raises(openmeteo.WetterAbrufFehler):
        openmeteo.abrufen(BREITE, LAENGE, NICHT_SCHALTJAHR)


def test_abrufen_meldet_abweichende_zeitreihen(monkeypatch):
    horizont, richtungen = _antworten(NICHT_SCHALTJAHR, azimut_abweichung="str_o")
    _anfrage_faelschen(monkeypatch, horizont, richtungen)

    with pytest.raises(openmeteo.WetterAbrufFehler):
        openmeteo.abrufen(BREITE, LAENGE, NICHT_SCHALTJAHR)


def test_abrufen_lehnt_ein_zu_altes_jahr_ab_ohne_netzzugriff(monkeypatch):
    aufgerufen = []
    monkeypatch.setattr(openmeteo, "_anfrage", lambda parameter: aufgerufen.append(parameter))

    with pytest.raises(openmeteo.WetterEingabeFehler):
        openmeteo.abrufen(BREITE, LAENGE, 1800)
    assert aufgerufen == []


# -- Fehlerwege des einzelnen HTTP-Abrufs -------------------------------------

def test_anfrage_wandelt_400er_in_eingabefehler_um(monkeypatch):
    def urlopen_faelschen(url, timeout=None):
        raise urllib.error.HTTPError(
            url, 400, "Bad Request", None,
            _FakeBody(b'{"error": true, "reason": "Latitude must be in range of -90 to 90"}'),
        )

    monkeypatch.setattr(openmeteo.urllib.request, "urlopen", urlopen_faelschen)
    with pytest.raises(openmeteo.WetterEingabeFehler, match="Latitude"):
        openmeteo._anfrage({"latitude": 999})


def test_anfrage_wandelt_serverfehler_in_wetterabruffehler_um(monkeypatch):
    def urlopen_faelschen(url, timeout=None):
        raise urllib.error.HTTPError(url, 500, "Server Error", None, _FakeBody(b"oops"))

    monkeypatch.setattr(openmeteo.urllib.request, "urlopen", urlopen_faelschen)
    with pytest.raises(openmeteo.WetterAbrufFehler) as ausnahme:
        openmeteo._anfrage({})
    assert not isinstance(ausnahme.value, openmeteo.WetterEingabeFehler)


def test_anfrage_wandelt_zeitueberschreitung_in_verstaendliche_meldung_um(monkeypatch):
    import socket

    def urlopen_faelschen(url, timeout=None):
        # So kommt eine Zeitueberschreitung bei urlopen() tatsaechlich an: als
        # URLError, die den socket.timeout einwickelt - nicht als roher
        # socket.timeout (siehe _anfrage()).
        raise urllib.error.URLError(socket.timeout("timed out"))

    monkeypatch.setattr(openmeteo.urllib.request, "urlopen", urlopen_faelschen)
    with pytest.raises(openmeteo.WetterAbrufFehler, match="später erneut"):
        openmeteo._anfrage({})


def test_anfrage_wandelt_fehlendes_netz_in_verstaendliche_meldung_um(monkeypatch):
    def urlopen_faelschen(url, timeout=None):
        raise urllib.error.URLError("[Errno -2] Name or service not known")

    monkeypatch.setattr(openmeteo.urllib.request, "urlopen", urlopen_faelschen)
    with pytest.raises(openmeteo.WetterAbrufFehler):
        openmeteo._anfrage({})


class _FakeBody:
    """Minimaler Ersatz fuer den lesbaren Rumpf eines HTTPError."""

    def __init__(self, inhalt):
        self._inhalt = inhalt

    def read(self):
        return self._inhalt

    def close(self):
        pass


# -- Endpunkt ------------------------------------------------------------------

def test_endpunkt_ruft_ab_und_legt_den_datensatz_an(app, monkeypatch):
    stunden = [
        {
            "zeitpunkt": datetime(2023, 1, 1, i), "t_au": 5.0, "x_au": 4.0,
            "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
        }
        for i in range(24)
    ]
    monkeypatch.setattr(openmeteo, "abrufen", lambda breite, laenge, jahr, ort="": stunden)

    antwort = app.test_client().post(
        "/api/wetter/abrufen",
        json={"breite": 52.52, "laenge": 13.41, "jahr": 2023, "ort": "Berlin"},
    )

    assert antwort.status_code == 201
    daten = antwort.get_json()
    assert daten["stunden"] == 24

    with app.app_context():
        [datensatz] = speicher.datensaetze()
    assert datensatz["quelle"] == "open-meteo"
    assert datensatz["ort"] == "Berlin"
    assert datensatz["jahr"] == 2023


def test_endpunkt_verlangt_breite_laenge_und_jahr(app):
    antwort = app.test_client().post("/api/wetter/abrufen", json={"breite": 52.52})
    assert antwort.status_code == 400
    assert "fehler" in antwort.get_json()


def test_endpunkt_meldet_einen_eingabefehler_als_400(app, monkeypatch):
    def abrufen_faelschen(breite, laenge, jahr, ort=""):
        raise openmeteo.WetterEingabeFehler("Für dieses Jahr liegen keine Daten vor")

    monkeypatch.setattr(openmeteo, "abrufen", abrufen_faelschen)
    antwort = app.test_client().post(
        "/api/wetter/abrufen", json={"breite": 52.52, "laenge": 13.41, "jahr": 1800},
    )
    assert antwort.status_code == 400
    assert "Daten vor" in antwort.get_json()["fehler"]


def test_endpunkt_meldet_einen_netzfehler_als_502(app, monkeypatch):
    def abrufen_faelschen(breite, laenge, jahr, ort=""):
        raise openmeteo.WetterAbrufFehler("Keine Verbindung zu Open-Meteo")

    monkeypatch.setattr(openmeteo, "abrufen", abrufen_faelschen)
    antwort = app.test_client().post(
        "/api/wetter/abrufen", json={"breite": 52.52, "laenge": 13.41, "jahr": 2023},
    )
    assert antwort.status_code == 502


# -- Echter Abruf (Netzzugriff) -------------------------------------------------

@pytest.mark.slow
def test_echter_abruf_gegen_open_meteo():
    """Prueft nur die grobe Plausibilitaet - die genauen Werte haengen vom
    Wetter des jeweiligen Jahres ab und sind hier bewusst nicht festgeschrieben."""
    stunden = openmeteo.abrufen(BREITE, LAENGE, 2023, ort="Berlin (Test)")
    assert len(stunden) == 8760
    assert -40.0 < stunden[0]["t_au"] < 45.0
    assert all(s["x_au"] >= 0.0 for s in stunden)
    assert max(s["str_h"] for s in stunden) > 100.0
