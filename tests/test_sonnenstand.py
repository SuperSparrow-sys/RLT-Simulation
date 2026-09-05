"""Koordinatenumrechnung, Sonnenstand und Strahlung auf senkrechte Flaechen.

Geprueft wird gegen nachpruefbare Angaben, nicht gegen selbst erzeugte Zahlen:
die Ortsangaben aus Handbuch Kap. 5, den Ursprung der Projektion und den
Ordnernamen der Referenzdaten, der die Koordinaten des Standorts traegt.
"""

import math
from datetime import datetime

import pytest

from core.wetter import sonnenstand

# Handbuch Kap. 5, Tab. 6 nennt zu diesen beiden Koordinaten die Ortslage.
GOERLITZ = (51.1563, 14.9887)
TEUBLITZ = (49.2214, 12.0947)
# Der Ordner, aus dem die Testdaten stammen, hiess TRY_510881137633 - die Ziffernfolge
# im Ordnernamen ist 51.0881 / 13.7633.
DRESDEN_INDUSTRIE = (51.0881, 13.7633)


def entfernung_km(a, b):
    """Grobe Entfernung zweier Punkte - fuer Toleranzen im Kilometerbereich
    genau genug, ohne eine Geo-Bibliothek zu holen."""
    breite_mittel = math.radians((a[0] + b[0]) / 2)
    nord = (a[0] - b[0]) * 111.32
    ost = (a[1] - b[1]) * 111.32 * math.cos(breite_mittel)
    return math.hypot(nord, ost)


# --- Umkehrprojektion EPSG:3034 -------------------------------------------

def test_ursprung_der_projektion_trifft_genau():
    """Beim Versatzpunkt muss exakt 52 N / 10 E herauskommen - sonst stimmen
    die Projektionsbeiwerte nicht."""
    breite, laenge = sonnenstand.nach_wgs84(4000000, 2800000)
    assert breite == pytest.approx(52.0, abs=1e-9)
    assert laenge == pytest.approx(10.0, abs=1e-9)


def test_handbuch_beispiel_goerlitz():
    """Handbuch Kap. 5: 4336500 / 2728500 liegt 8 km noerdlich von Goerlitz."""
    punkt = sonnenstand.nach_wgs84(4336500, 2728500)
    assert entfernung_km(punkt, GOERLITZ) == pytest.approx(8.0, abs=1.5)
    assert punkt[0] > GOERLITZ[0], "muss noerdlich von Goerlitz liegen"


def test_handbuch_beispiel_teublitz():
    """Handbuch Kap. 5: 4150500 / 2503500 liegt 3 km oestlich von Teublitz."""
    punkt = sonnenstand.nach_wgs84(4150500, 2503500)
    assert entfernung_km(punkt, TEUBLITZ) == pytest.approx(3.0, abs=1.5)
    assert punkt[1] > TEUBLITZ[1], "muss oestlich von Teublitz liegen"


def test_referenzdatei_trifft_ihren_eigenen_ordnernamen():
    """Der Ordner heisst TRY_510881137633 - das sind Breite und Laenge."""
    breite, laenge = sonnenstand.nach_wgs84(4254500, 2708500)
    assert breite == pytest.approx(DRESDEN_INDUSTRIE[0], abs=0.001)
    assert laenge == pytest.approx(DRESDEN_INDUSTRIE[1], abs=0.001)


# --- Sonnenstand ----------------------------------------------------------

def test_sonne_steht_mittags_im_sueden_und_am_hoechsten():
    breite, laenge = DRESDEN_INDUSTRIE
    staende = [
        (stunde, *sonnenstand.stand(datetime(2015, 6, 21, stunde, 30), breite, laenge))
        for stunde in range(24)
    ]
    hoechste = max(staende, key=lambda e: e[1])
    assert hoechste[0] in (12, 13), "Sonnenhoechststand liegt in MEZ um die Mittagszeit"
    assert abs(hoechste[2]) < 15.0, "und dabei nahezu im Sueden (Azimut um 0)"


def test_sonnenhoehe_im_sommer_groesser_als_im_winter():
    breite, laenge = DRESDEN_INDUSTRIE
    sommer, _ = sonnenstand.stand(datetime(2015, 6, 21, 12, 30), breite, laenge)
    winter, _ = sonnenstand.stand(datetime(2015, 12, 21, 12, 30), breite, laenge)
    # Fuer 51 Grad Nord: rund 62 Grad im Sommer, rund 15 Grad im Winter.
    assert sommer == pytest.approx(62.0, abs=2.0)
    assert winter == pytest.approx(15.4, abs=2.0)


def test_azimut_wandert_von_ost_nach_west():
    breite, laenge = DRESDEN_INDUSTRIE
    _, vormittags = sonnenstand.stand(datetime(2015, 6, 21, 8, 30), breite, laenge)
    _, nachmittags = sonnenstand.stand(datetime(2015, 6, 21, 16, 30), breite, laenge)
    assert vormittags < 0, "vormittags steht die Sonne oestlich (Azimut negativ)"
    assert nachmittags > 0, "nachmittags westlich (Azimut positiv)"


def test_nachts_steht_die_sonne_unter_dem_horizont():
    breite, laenge = DRESDEN_INDUSTRIE
    hoehe, _ = sonnenstand.stand(datetime(2015, 1, 15, 2, 30), breite, laenge)
    assert hoehe < 0


# --- Strahlung auf senkrechte Flaechen ------------------------------------

def test_nachts_ist_jede_flaeche_dunkel():
    werte = sonnenstand.strahlung_auf_senkrechte(
        datetime(2015, 1, 1, 2, 30), *DRESDEN_INDUSTRIE, direkt_h=0.0, diffus_h=0.0
    )
    assert set(werte) == {"str_s", "str_o", "str_w", "str_n"}
    assert all(wert == 0.0 for wert in werte.values())


def test_ost_bekommt_vormittags_mehr_als_west_und_umgekehrt():
    breite, laenge = DRESDEN_INDUSTRIE
    vormittags = sonnenstand.strahlung_auf_senkrechte(
        datetime(2015, 6, 21, 8, 30), breite, laenge, direkt_h=300.0, diffus_h=150.0
    )
    nachmittags = sonnenstand.strahlung_auf_senkrechte(
        datetime(2015, 6, 21, 16, 30), breite, laenge, direkt_h=300.0, diffus_h=150.0
    )
    assert vormittags["str_o"] > vormittags["str_w"]
    assert nachmittags["str_w"] > nachmittags["str_o"]


def test_nord_bekommt_im_winter_keine_direktstrahlung():
    """Im Winter kommt die Sonne bei uns nie hinter die Nordfassade. Uebrig
    bleiben Diffus- und Bodenanteil - beide fest, also nachrechenbar."""
    diffus, direkt = 100.0, 200.0
    werte = sonnenstand.strahlung_auf_senkrechte(
        datetime(2015, 12, 21, 12, 30), *DRESDEN_INDUSTRIE,
        direkt_h=direkt, diffus_h=diffus,
    )
    erwartet = diffus / 2 + (direkt + diffus) * sonnenstand.ALBEDO / 2
    assert werte["str_n"] == pytest.approx(erwartet)
    assert werte["str_s"] > werte["str_n"], "die Suedfassade bekommt mehr"


def test_bodenreflexion_steckt_in_jeder_richtung():
    """Auch eine Flaeche ohne Direktanteil sieht den beleuchteten Boden."""
    ohne_sonne = sonnenstand.strahlung_auf_senkrechte(
        datetime(2015, 12, 21, 12, 30), *DRESDEN_INDUSTRIE,
        direkt_h=0.0, diffus_h=100.0,
    )
    # Diffus 100/2 = 50, Boden 100 * 0.2 / 2 = 10.
    assert ohne_sonne["str_n"] == pytest.approx(60.0)


def test_flache_sonne_laesst_den_direktanteil_nicht_explodieren():
    """B / sin(Hoehe) geht bei Sonnenaufgang gegen unendlich - der Deckel muss
    greifen, sonst stehen im Datensatz Strahlungswerte jenseits der
    Solarkonstante."""
    breite, laenge = DRESDEN_INDUSTRIE
    for stunde in range(0, 24):
        werte = sonnenstand.strahlung_auf_senkrechte(
            datetime(2015, 6, 21, stunde, 30), breite, laenge,
            direkt_h=50.0, diffus_h=50.0,
        )
        for richtung, wert in werte.items():
            assert 0.0 <= wert < sonnenstand.SOLARKONSTANTE, (stunde, richtung, wert)
