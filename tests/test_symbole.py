"""Die 34 Kartensymbole (static/symbole/) und die Bedienzeichen.

Wie sie AUSSEHEN, entscheidet kein Test - das wurde im Browser angesehen,
jedes einzeln und alle nebeneinander. Hier steht das Nachprüfbare: dass jedes
Symbol dieselbe Zeichenfläche, dieselbe Strichstärke und dieselbe Form der
Pfeilspitze benutzt, und dass nichts über den Rand hinausläuft. Genau das
waren die drei Fehler, die beim Durchsehen auffielen.
"""

import pathlib
import re

import pytest

from core.bausteine import basis, lade_alle
from tests.svg_huelle import huelle

SYMBOLE = pathlib.Path(__file__).resolve().parent.parent / "static" / "symbole"
BEDIENZEICHEN = (
    pathlib.Path(__file__).resolve().parent.parent / "templates" / "bedienzeichen"
)

# Zeichenfläche 48x48 bei Strichstärke 2: die halbe Strichbreite liegt außen,
# eine runde Strichkappe kommt am Linienende noch dazu. Geometrie außerhalb
# von 1..47 wird also am Rand beschnitten. Gefunden hat das maximalwert, das
# seine Stutzen bei x=0 und x=48 hatte, während alle übrigen Kastensymbole
# 2..6 und 42..46 benutzen.
RAND = 1.0
FLAECHE = 48.0


def symboldateien():
    return sorted(SYMBOLE.glob("*.svg"))


def test_jede_karte_hat_ihr_symbol_und_kein_symbol_ist_verwaist():
    lade_alle()
    erwartet = {k.SYMBOL for k in basis.alle()}
    vorhanden = {f.name for f in symboldateien()}
    assert erwartet == vorhanden


@pytest.mark.parametrize("datei", symboldateien(), ids=lambda p: p.stem)
def test_symbol_bleibt_in_seiner_zeichenflaeche(datei):
    x0, y0, x1, y1 = huelle(datei.read_text(encoding="utf-8"))
    assert x0 >= RAND and y0 >= RAND, f"{datei.name}: beginnt bei ({x0}, {y0})"
    assert x1 <= FLAECHE - RAND and y1 <= FLAECHE - RAND, (
        f"{datei.name}: reicht bis ({x1}, {y1})"
    )


@pytest.mark.parametrize("datei", symboldateien(), ids=lambda p: p.stem)
def test_symbol_traegt_dieselben_grundangaben(datei):
    """Ein Satz Angaben für alle: dieselbe Fläche, dieselbe Strichstärke,
    Farbe über currentColor (damit ein Symbol die Farbe seiner Umgebung
    annimmt statt eine eigene mitzubringen), runde Enden."""
    s = datei.read_text(encoding="utf-8")
    assert 'viewBox="0 0 48 48"' in s
    assert 'stroke="currentColor"' in s
    assert 'stroke-width="2"' in s
    assert 'stroke-linecap="round"' in s
    assert 'stroke-linejoin="round"' in s


def test_alle_pfeilspitzen_haben_dieselbe_form():
    """Eine Spitze ist ein Winkel von 90 Grad mit fünf Einheiten langen
    Schenkeln, deren Scheitel genau auf dem Linienende sitzt. Uneinheitliche
    Spitzen waren der erste Befund beim Durchsehen der Symbole."""
    muster = re.compile(
        r"M\s*([\d.]+)\s+([\d.]+)\s*L\s*([\d.]+)\s+([\d.]+)\s*L\s*([\d.]+)\s+([\d.]+)"
    )
    gesehen = 0
    for datei in symboldateien():
        for treffer in muster.finditer(datei.read_text(encoding="utf-8")):
            x1, y1, sx, sy, x2, y2 = (float(v) for v in treffer.groups())
            # Nur echte Spitzen: beide Schenkel gleich lang und symmetrisch
            # zum Scheitel. Ein Zickzack (erhitzer) erfüllt das nicht.
            if not (abs(x1 - sx) == abs(x2 - sx) and abs(y1 - sy) == abs(y2 - sy)):
                continue
            if (y1 - sy) * (y2 - sy) >= 0:  # beide Schenkel auf derselben Seite
                continue
            gesehen += 1
            assert abs(x1 - sx) == 5 and abs(y1 - sy) == 5, (
                f"{datei.name}: Schenkel {abs(x1 - sx)}/{abs(y1 - sy)} statt 5/5"
            )
    assert gesehen >= 5, "keine Pfeilspitzen gefunden - Muster stimmt nicht mehr"


def test_keine_pfeilspitze_klebt_an_einer_kastenkante():
    """Die Spitze der Mischkammer saß mit ihren Schenkeln genau auf der
    rechten Kastenkante und wirkte daran angeklebt. Zwischen Kante und
    Schenkelanfang gehören mindestens drei Einheiten Strich - so viel wie
    bei einfacher_raum, dem anderen Kastensymbol mit Pfeil."""
    ABSTAND = 3.0
    for datei in symboldateien():
        s = datei.read_text(encoding="utf-8")
        kaesten = [
            tuple(float(v) for v in t)
            for t in re.findall(
                r'<rect[^>]*x="([\d.]+)"[^>]*y="([\d.]+)"'
                r'[^>]*width="([\d.]+)"[^>]*height="([\d.]+)"', s
            )
        ]
        for treffer in re.finditer(
            r"M\s*([\d.]+)\s+([\d.]+)\s*L\s*([\d.]+)\s+([\d.]+)\s*L\s*([\d.]+)\s+([\d.]+)", s
        ):
            x1, y1, sx, sy, x2, y2 = (float(v) for v in treffer.groups())
            if not (abs(x1 - sx) == abs(x2 - sx) == 5 and abs(y1 - sy) == abs(y2 - sy) == 5):
                continue
            if (y1 - sy) * (y2 - sy) >= 0:
                continue
            anfang = min(x1, x2, sx)
            for rx, ry, rw, rh in kaesten:
                if not (ry - 1 <= sy <= ry + rh + 1):
                    continue
                if rx + rw <= anfang:  # Spitze rechts vom Kasten
                    assert anfang - (rx + rw) >= ABSTAND, (
                        f"{datei.name}: Spitze beginnt {anfang - (rx + rw)} "
                        f"Einheiten hinter der Kastenkante"
                    )


def test_bedienzeichen_holen_ihr_aussehen_aus_dem_css():
    """Die Zeichen der Kopfleisten (templates/bedienzeichen/) sind dieselbe
    Sache in kleinerem Format, aber anders gebaut: die Datei trägt nur die
    Form, Strichstärke und Farbe kommen aus einer CSS-Klasse. Das ist der
    Grund, warum ein Zeichen die Farbe und die Abblendung seines Knopfes
    annimmt, statt eine eigene mitzubringen.

    Der Haken war anfangs der Ausreißer und schrieb seine Strichangaben
    selbst hin - dieser Test hält die gemeinsame Bauweise fest."""
    css = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (pathlib.Path(__file__).resolve().parent.parent / "static" / "css").glob("*.css")
    )
    dateien = sorted(BEDIENZEICHEN.glob("*.svg"))
    assert dateien, "keine Bedienzeichen gefunden"
    for datei in dateien:
        s = datei.read_text(encoding="utf-8")
        assert 'aria-hidden="true"' in s, datei.name
        assert "stroke=" not in s, f"{datei.name}: Strichangaben gehören ins CSS"
        klasse = re.search(r'<svg[^>]*class="([^"]+)"', s)
        assert klasse, f"{datei.name}: ohne Klasse bekommt es kein Aussehen"
        for name in klasse.group(1).split():
            # Eine Klasse darf mehrere Regeln haben (eine Grundregel in
            # style.css, zusaetzliche in start.css) - eine davon muss die
            # Farbe setzen.
            regeln = [
                css[stelle:css.index("}", stelle)]
                for stelle in _fundstellen(css, f".{name} {{")
            ]
            assert regeln, f"{datei.name}: .{name} ist nirgends beschrieben"
            assert any("stroke: currentColor" in r for r in regeln), (
                f".{name}: ohne currentColor"
            )


def _fundstellen(text, was):
    stelle = text.find(was)
    while stelle >= 0:
        yield stelle
        stelle = text.find(was, stelle + 1)
