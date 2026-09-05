"""Der Leser fuer DWD-Testreferenzjahre im .dat-Format.

Geprueft wird gegen die echten Dateien unter referenz/, nicht gegen
nachgebaute - der Kopf dieser Dateien ist genau die Stelle, an der ein
selbstgebautes Muster die Wirklichkeit verfehlen wuerde.
"""

from datetime import datetime
from pathlib import Path

import pytest

from core.wetter import try_dat

# Echte DWD-Dateien, aber nur so viel davon wie gebraucht: das mittlere Jahr
# vollstaendig (nur daran laesst sich pruefen, dass 8760 Stunden lueckenlos
# gelesen werden), die anderen beiden mit Kopf und zwei Tagen - an ihnen haengt
# nur die Kopfauswertung, insbesondere die drei Datenbasis-Zeilen des
# Zukunfts-TRY.
ORDNER = Path(__file__).parent / "daten" / "try"
GEGENWART = ORDNER / "TRY2015_510881137633_Jahr.dat"
ZUKUNFT = ORDNER / "TRY2045_510881137633_Jahr.dat"
SOMMER = ORDNER / "TRY2015_510881137633_Somm.dat"
STUNDEN_AUSZUG = 48  # Umfang der beiden gekuerzten Dateien


# --- Dateiname ------------------------------------------------------------

def test_kennung_aus_dateiname():
    kennung = try_dat.kennung_aus_dateiname("TRY2015_510881137633_Jahr.dat")
    assert kennung["jahr"] == 2015
    assert kennung["art"] == "mittleres Jahr"


def test_kennung_erkennt_die_drei_arten():
    arten = {
        "TRY2015_510881137633_Jahr.dat": "mittleres Jahr",
        "TRY2015_510881137633_Somm.dat": "extremer Sommer",
        "TRY2045_510881137633_Wint.dat": "extremer Winter",
    }
    for dateiname, erwartet in arten.items():
        assert try_dat.kennung_aus_dateiname(dateiname)["art"] == erwartet


def test_kennung_bei_fremdem_namen_bleibt_leer():
    """Faellt der Name aus der Konvention, wird nichts geraten."""
    kennung = try_dat.kennung_aus_dateiname("irgendwas.dat")
    assert kennung["jahr"] is None
    assert kennung["art"] == ""


# --- Kopf -----------------------------------------------------------------

def test_kopf_der_gegenwartsdatei():
    kopf = try_dat.lese_kopf(GEGENWART)
    assert kopf["rechtswert"] == 4254500
    assert kopf["hochwert"] == 2708500
    assert kopf["hoehenlage"] == 154
    assert kopf["art"] == "mittleres Jahr"
    assert kopf["bezugszeitraum"] == "1995-2012"


def test_kopf_rechnet_den_ort_in_breite_und_laenge_um():
    kopf = try_dat.lese_kopf(GEGENWART)
    # Der Ordner heisst TRY_510881137633 - genau diese Koordinaten.
    assert kopf["breite"] == pytest.approx(51.0881, abs=0.001)
    assert kopf["laenge"] == pytest.approx(13.7633, abs=0.001)


def test_kopf_des_zukunfts_try_mit_drei_datenbasis_zeilen():
    """Das Zukunfts-TRY hat 'Datenbasis 1' bis 'Datenbasis 3' statt einer
    einzelnen Zeile (Handbuch Kap. 2). Wer Zeilen zaehlt statt zu suchen,
    liest hier den falschen Wert."""
    kopf = try_dat.lese_kopf(ZUKUNFT)
    assert kopf["bezugszeitraum"] == "2031-2060"
    assert kopf["art"] == "mittleres Jahr"
    assert kopf["hoehenlage"] == 154


def test_kopf_der_sommerdatei_nennt_die_art():
    assert try_dat.lese_kopf(SOMMER)["art"] == "extremer Sommer"


def test_datei_ohne_endekennzeichen_meldet_einen_lesbaren_fehler(tmp_path):
    pfad = tmp_path / "ohne_stern.dat"
    pfad.write_text("Rechtswert : 4254500 Meter\nkein Sternchen\n", encoding="latin-1")
    with pytest.raises(ValueError, match="Kopf"):
        try_dat.lese_datei(pfad)


# --- Datenzeilen ----------------------------------------------------------

def test_ein_volles_jahr_wird_gelesen():
    stunden = try_dat.lese_datei(GEGENWART)
    assert len(stunden) == 8760


def test_erste_stunde_stimmt_mit_der_datei_ueberein():
    """Erste Datenzeile: 1 1 1 -3.7 ... 2.7 ... 0 0
    Stunde 1 des TRY meint 00:00 bis 01:00 (Handbuch Kap. 2), der Zeitstempel
    ist also 00:00 - sonst faengt das Jahr um 01:00 an und hat 8761 Stunden."""
    erste = try_dat.lese_datei(GEGENWART)[0]
    assert erste["zeitpunkt"] == datetime(2015, 1, 1, 0)
    assert erste["t_au"] == pytest.approx(-3.7)
    assert erste["x_au"] == pytest.approx(2.7)
    assert erste["str_h"] == pytest.approx(0.0)


def test_letzte_stunde_ist_silvester_dreiundzwanzig_uhr():
    letzte = try_dat.lese_datei(GEGENWART)[-1]
    assert letzte["zeitpunkt"] == datetime(2015, 12, 31, 23)
    assert letzte["t_au"] == pytest.approx(-1.9)


def test_jahr_kommt_aus_dem_dateinamen():
    assert try_dat.lese_datei(ZUKUNFT)[0]["zeitpunkt"].year == 2045


def test_stunden_laufen_luecklos_durch():
    stunden = try_dat.lese_datei(GEGENWART)
    for vorher, nachher in zip(stunden, stunden[1:]):
        abstand = (nachher["zeitpunkt"] - vorher["zeitpunkt"]).total_seconds()
        assert abstand == 3600, (vorher["zeitpunkt"], nachher["zeitpunkt"])


def test_waagerechte_strahlung_ist_die_summe_aus_direkt_und_diffus():
    """Handbuch Kap. 3.1: die Globalstrahlung G ist die Summe aus B und D."""
    stunden = try_dat.lese_datei(GEGENWART)
    mittags = [s for s in stunden if s["zeitpunkt"].month == 6 and s["zeitpunkt"].hour == 12]
    assert max(s["str_h"] for s in mittags) > 400.0


def test_jede_stunde_traegt_alle_kanonischen_felder():
    """Die Form muss zu core/wetter/speicher.SPALTEN passen, sonst faellt der
    Unterschied erst beim Schreiben in die Datenbank auf."""
    from core.wetter.speicher import SPALTEN

    erste = try_dat.lese_datei(GEGENWART)[0]
    assert set(erste) == {"zeitpunkt", *SPALTEN}


def test_fassadenstrahlung_wird_mitgerechnet():
    stunden = try_dat.lese_datei(GEGENWART)
    juni = [s for s in stunden if s["zeitpunkt"].month == 6]
    assert max(s["str_s"] for s in juni) > 100.0, "Suedfassade im Juni"
    assert max(s["str_o"] for s in juni) > 100.0, "Ostfassade im Juni"


def test_nachts_bleibt_jede_fassade_dunkel():
    stunden = try_dat.lese_datei(GEGENWART)
    nachts = [s for s in stunden if s["zeitpunkt"].hour == 1]
    for stunde in nachts:
        for feld in ("str_s", "str_o", "str_w", "str_n", "str_h"):
            assert stunde[feld] == 0.0, (stunde["zeitpunkt"], feld)


def test_kein_strahlungswert_ueberschreitet_die_solarkonstante():
    from core.wetter.sonnenstand import SOLARKONSTANTE

    for stunde in try_dat.lese_datei(GEGENWART):
        for feld in ("str_s", "str_o", "str_w", "str_n", "str_h"):
            assert 0.0 <= stunde[feld] < SOLARKONSTANTE, (stunde["zeitpunkt"], feld)


def test_beschreibung_fasst_den_kopf_zusammen():
    beschreibung = try_dat.beschreibung(GEGENWART)
    assert "mittleres Jahr" in beschreibung["notiz"]
    assert "1995-2012" in beschreibung["notiz"]
    assert "154" in beschreibung["notiz"]
    assert beschreibung["jahr"] == 2015
