"""Liest ein DWD-Testreferenzjahr im .dat-Format.

Aufbau (Handbuch "Ortsgenaue Testreferenzjahre von Deutschland", Kap. 2 und
3.1): ein Kopfblock, der mit einer Zeile aus drei Sternchen endet, danach 8760
Datenzeilen mit 17 durch Leerzeichen getrennten Feldern - je eine Stunde des
Jahres.

Zwei Eigenheiten machen einen naiven Leser falsch:

- Der Kopf ist nicht zeilenfest. Das Gegenwarts-TRY hat eine Zeile
  "Datenbasis", das Zukunfts-TRY drei ("Datenbasis 1" bis "Datenbasis 3").
  Gesucht wird darum nach Schluesselwoertern bis zum Sternchen, nicht gezaehlt.
- Die Datenzeilen tragen kein Jahr, nur Monat, Tag und Stunde. Ein mittleres
  TRJ ist aus Abschnitten verschiedener Jahre zusammengesetzt (Handbuch Kap. 5)
  und hat gar kein echtes Jahr. Als nominelles Jahr dient das Schluesseljahr
  aus dem Dateinamen (2015 fuer die Gegenwart, 2045 fuer die Zukunft) - beides
  keine Schaltjahre, was zu 8760 Stunden passt.

Was das TRY nicht enthaelt, ist die Strahlung auf senkrechte Flaechen; es gibt
nur die waagerechten Werte B und D. Die vier Fassadenwerte rechnet
core/wetter/sonnenstand.py aus dem Sonnenstand dazu, damit ein importierter
Datensatz dieselben Felder fuehrt wie ein abgerufener.
"""

import re
from datetime import datetime, timedelta
from pathlib import Path

from core.wetter import sonnenstand

#: Die Zeile, die den Kopf beendet.
ENDE_KOPF = "***"

#: Spaltennummern der Datenzeilen (Handbuch Kap. 3.1, Tab. 2). Wind, Luftdruck,
#: Bedeckungsgrad, relative Feuchte und die langwelligen Groessen A und E
#: stehen zwar in der Datei, werden vom Rechenkern aber nicht gebraucht.
SPALTE_MONAT, SPALTE_TAG, SPALTE_STUNDE = 2, 3, 4
SPALTE_TEMPERATUR = 5      # t  [GradC]
SPALTE_WASSERDAMPF = 10    # x  [g/kg], Mischungsverhaeltnis
SPALTE_DIREKT = 12         # B  [W/m2] auf die Waagerechte
SPALTE_DIFFUS = 13         # D  [W/m2] auf die Waagerechte
SPALTEN_JE_ZEILE = 17

#: Art des TRY aus dem Kuerzel im Dateinamen (Handbuch Kap. 2, AAAA).
ARTEN = {
    "Jahr": "mittleres Jahr",
    "Somm": "extremer Sommer",
    "Wint": "extremer Winter",
}

#: TRJJJJJ_<Kennziffer>_AAAA. Das Handbuch schreibt in der Kennziffer Rechts-
#: und Hochwert vor; die tatsaechlich ausgelieferten Dateien tragen dort aber
#: Breite und Laenge (Ordner "TRY_510881137633" = 51.0881 / 13.7633). Aus dem
#: Namen werden darum nur Jahr und Art gelesen, niemals Koordinaten - die
#: kommen aus dem Kopf.
_NAMENSMUSTER = re.compile(r"^TR[YJ](\d{4})_[^_]*_(Jahr|Somm|Wint)", re.IGNORECASE)

#: Vorgabejahr, wenn der Dateiname keines hergibt. 2015 ist das Schluesseljahr
#: der Gegenwarts-TRY und kein Schaltjahr.
VORGABEJAHR = 2015


def kennung_aus_dateiname(dateiname):
    """Liest Schluesseljahr und Art aus dem Dateinamen.

    Passt der Name nicht auf die Konvention, bleiben beide Felder leer statt
    geraten zu werden - ein falsch geratenes Jahr faellt spaeter niemandem auf.
    """
    treffer = _NAMENSMUSTER.match(Path(dateiname).name)
    if not treffer:
        return {"jahr": None, "art": ""}
    kuerzel = treffer.group(2).capitalize()
    return {"jahr": int(treffer.group(1)), "art": ARTEN.get(kuerzel, "")}


def _zahl(text):
    """Erste Zahl in einem Kopfeintrag, z. B. '154 Meter ueber NN' -> 154."""
    treffer = re.search(r"-?\d+", text or "")
    return int(treffer.group()) if treffer else None


def _kopfzeilen(datei):
    """Liefert die Kopfzeilen bis zum Sternchen und laesst den Dateizeiger
    danach auf der ersten Datenzeile stehen."""
    zeilen = []
    for zeile in datei:
        if zeile.lstrip().startswith(ENDE_KOPF):
            return zeilen
        zeilen.append(zeile)
    raise ValueError(
        "Die Datei sieht nicht wie ein TRY aus: der Kopf endet nirgends mit "
        "einer Zeile aus drei Sternchen."
    )


def _kopf_auswerten(zeilen):
    eintraege = {}
    for zeile in zeilen:
        if ":" not in zeile:
            continue
        schluessel, _, wert = zeile.partition(":")
        eintraege[schluessel.strip().lower()] = wert.strip()

    kopf = {
        "rechtswert": _zahl(eintraege.get("rechtswert")),
        "hochwert": _zahl(eintraege.get("hochwert")),
        "hoehenlage": _zahl(eintraege.get("hoehenlage")),
        "art": eintraege.get("art des try", ""),
        "bezugszeitraum": eintraege.get("bezugszeitraum", ""),
        "breite": None,
        "laenge": None,
    }
    if kopf["rechtswert"] is not None and kopf["hochwert"] is not None:
        kopf["breite"], kopf["laenge"] = sonnenstand.nach_wgs84(
            kopf["rechtswert"], kopf["hochwert"]
        )
    return kopf


def lese_kopf(pfad):
    """Kopfdaten allein - ohne die 8760 Datenzeilen zu lesen."""
    # latin-1 statt utf-8: die Dateien schreiben Umlaute ohnehin um ("Hoehenlage"),
    # aber latin-1 kann kein Byte ablehnen - ein Zeichensatzfehler waere hier die
    # unnoetigste aller Fehlermeldungen.
    with open(pfad, encoding="latin-1") as datei:
        return _kopf_auswerten(_kopfzeilen(datei))


def lese_mit_kopf(pfad, jahr=None):
    """Liest Kopf und Stundenwerte in einem Durchgang.

    Rueckgabe: (stunden, kopf). Die Stunden haben dieselbe kanonische Form wie
    bei core.wetter.tabelle und core.wetter.openmeteo.
    """
    pfad = Path(pfad)
    if jahr is None:
        jahr = kennung_aus_dateiname(pfad.name)["jahr"] or VORGABEJAHR

    with open(pfad, encoding="latin-1") as datei:
        kopf = _kopf_auswerten(_kopfzeilen(datei))
        rohzeilen = [zeile.split() for zeile in datei if zeile.strip()]

    if kopf["breite"] is None:
        raise ValueError(
            "Im Kopf der TRY-Datei fehlen Rechts- und Hochwert - ohne den Ort "
            "lässt sich die Strahlung auf die Fassaden nicht berechnen."
        )

    stunden = []
    for felder in rohzeilen:
        if len(felder) < SPALTEN_JE_ZEILE:
            continue
        try:
            monat = int(felder[SPALTE_MONAT])
            tag = int(felder[SPALTE_TAG])
            # Stunde 1 des TRY meint 00:00 bis 01:00 - der Zeitstempel ist also
            # der Stundenanfang, sonst begaenne das Jahr um 01:00.
            beginn = datetime(jahr, monat, tag) + timedelta(hours=int(felder[SPALTE_STUNDE]) - 1)
            temperatur = float(felder[SPALTE_TEMPERATUR])
            wasserdampf = float(felder[SPALTE_WASSERDAMPF])
            direkt = float(felder[SPALTE_DIREKT])
            diffus = float(felder[SPALTE_DIFFUS])
        except (ValueError, IndexError):
            # Eine einzelne unlesbare Zeile darf das Jahr nicht kippen; ob am
            # Ende genug Stunden zusammenkamen, prueft der Aufrufer.
            continue

        eintrag = {
            "zeitpunkt": beginn,
            "t_au": temperatur,
            "x_au": wasserdampf,
            "str_h": direkt + diffus,
        }
        # Der Sonnenstand wird fuer die Mitte der Stunde gerechnet: B und D sind
        # Mittelwerte ueber die vergangene Stunde (Handbuch Kap. 3.1), nicht
        # Augenblickswerte zum Stundenanfang.
        eintrag.update(
            sonnenstand.strahlung_auf_senkrechte(
                beginn + timedelta(minutes=30),
                kopf["breite"], kopf["laenge"],
                direkt_h=direkt, diffus_h=diffus,
            )
        )
        stunden.append(eintrag)

    return stunden, kopf


def lese_datei(pfad, jahr=None):
    """Nur die Stundenwerte - gleiche Form wie die uebrigen Leser."""
    return lese_mit_kopf(pfad, jahr)[0]


def beschreibung(pfad):
    """Kopfdaten in der Form, in der core.wetter.speicher sie ablegt.

    Die Art des TRY steht bevorzugt im Kopf; nur wenn sie dort fehlt, wird das
    Kuerzel aus dem Dateinamen genommen.
    """
    pfad = Path(pfad)
    kopf = lese_kopf(pfad)
    kennung = kennung_aus_dateiname(pfad.name)

    art = kopf["art"] or kennung["art"]
    teile = []
    if art:
        teile.append(f"Art des TRY: {art}")
    if kopf["bezugszeitraum"]:
        teile.append(f"Bezugszeitraum {kopf['bezugszeitraum']}")
    if kopf["hoehenlage"] is not None:
        teile.append(f"Höhenlage {kopf['hoehenlage']} m ü. NN")
    if kopf["rechtswert"] is not None:
        teile.append(f"Rechtswert {kopf['rechtswert']}, Hochwert {kopf['hochwert']}")

    return {
        "art": art,
        "jahr": kennung["jahr"],
        "breite": kopf["breite"],
        "laenge": kopf["laenge"],
        "notiz": "DWD-Testreferenzjahr. " + ", ".join(teile) if teile else "DWD-Testreferenzjahr.",
    }
