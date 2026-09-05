"""Wetterdaten ueber die Open-Meteo Archive-API (ERA5-Reanalyse) abrufen.

Bildet die Antwort auf dieselbe kanonische Form ab wie core.wetter.einlesen.lese_datei:
eine Liste von Stunden-Dictionaries mit den Schluesseln 'zeitpunkt', 't_au', 'x_au',
'str_s', 'str_o', 'str_w', 'str_n', 'str_h'.

Ueber die Quelle (geprueft am 2026-09-01 mit echten Abrufen gegen
https://archive-api.open-meteo.com/v1/archive, siehe wetter-api-report.md):

- Kein Schluessel noetig. Der erlaubte Zeitraum reicht von 1940-01-01 bis zum
  aktuellen Tag; eine Anfrage ausserhalb davon liefert HTTP 400 mit
  {"error": true, "reason": "Parameter 'start_date' is out of allowed range ..."}.
  Da das laufende Jahr nie vollstaendig ist, wird hier nur bis einschliesslich des
  letzten abgeschlossenen Kalenderjahres abgerufen (siehe _jahr_pruefen).
- Bei gesetzter Zeitzone liefert die API fuer jeden Kalendertag genau 24 Stunden
  (00:00 bis 23:00), auch am Tag der Sommerzeitumstellung - es wird also keine
  Stunde uebersprungen oder doppelt geliefert. Die Zeitstempel kommen als
  "2023-01-01T00:00" zurueck und werden direkt uebernommen.
- 'global_tilted_irradiance' kennt pro Abfrage genau einen tilt/azimuth-Satz -
  "azimuth=0,90" wird mit einem Fehler abgelehnt. Fuer die vier Himmelsrichtungen
  sind darum vier getrennte Abfragen noetig (tilt=90, azimuth wie unten), dazu eine
  fuenfte fuer die horizontale Globalstrahlung ('shortwave_radiation', kein
  tilt/azimuth noetig), zusammen mit Temperatur und relativer Feuchte. Das macht
  fuenf Abfragen je Jahr - sie werden parallel geschickt, damit die Wartezeit nicht
  auf das Fuenffache anwaechst.
- Azimut-Konvention der API (durch einen Abruf fuer den 21. Juni bestaetigt: Ost hat
  sein Maximum vormittags, West nachmittags): 0 = Sued, -90 = Ost, 90 = West,
  180 = Nord.
- Absolute Feuchte liefert die API nicht direkt. Aus Temperatur und relativer
  Feuchte wird sie mit den Stoffdatenfunktionen des Projekts berechnet (Umkehrung
  von core.bausteine.stoffdaten.rel_feuchte), damit die Zahlen zum Rechenkern
  passen statt zu einer zweiten, abweichenden Formel.
"""

import concurrent.futures
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

from core.bausteine import stoffdaten

BASIS_URL = "https://archive-api.open-meteo.com/v1/archive"
ZEITZONE = "Europe/Berlin"
ZEITUEBERSCHREITUNG_S = 20
FRUEHESTES_JAHR = 1940

# Feldname im kanonischen Ergebnis -> Azimut fuer 'global_tilted_irradiance' (tilt=90)
_AZIMUTE = {"str_s": 0, "str_o": -90, "str_w": 90, "str_n": 180}


class WetterAbrufFehler(Exception):
    """Der Abruf ist gescheitert - Text ist eine verstaendliche deutsche Meldung."""


class WetterEingabeFehler(WetterAbrufFehler):
    """Ort oder Jahr sind ungueltig - durch andere Eingaben behebbar."""


def _jahr_pruefen(jahr):
    try:
        jahr = int(jahr)
    except (TypeError, ValueError):
        raise WetterEingabeFehler("Das Jahr muss eine Zahl sein") from None

    letztes_abgeschlossenes_jahr = date.today().year - 1
    if jahr < FRUEHESTES_JAHR or jahr > letztes_abgeschlossenes_jahr:
        raise WetterEingabeFehler(
            f"Für das Jahr {jahr} liegen keine vollständigen Wetterdaten vor. "
            f"Open-Meteo liefert abgeschlossene Jahre von {FRUEHESTES_JAHR} bis "
            f"{letztes_abgeschlossenes_jahr}."
        )
    return jahr


def _ort_pruefen(breite, laenge):
    try:
        breite = float(breite)
        laenge = float(laenge)
    except (TypeError, ValueError):
        raise WetterEingabeFehler("Breite und Länge müssen Zahlen sein") from None
    return breite, laenge


def _anfrage(parameter):
    """Ein einzelner Abruf. Wandelt jeden Fehlschlag in eine WetterAbrufFehler um."""
    url = f"{BASIS_URL}?{urllib.parse.urlencode(parameter)}"
    try:
        with urllib.request.urlopen(url, timeout=ZEITUEBERSCHREITUNG_S) as antwort:
            rohdaten = antwort.read()
    except urllib.error.HTTPError as fehler:
        try:
            grund = json.loads(fehler.read()).get("reason", "")
        except (ValueError, AttributeError):
            grund = ""
        meldung = f"Open-Meteo hat die Anfrage abgelehnt: {grund}" if grund else (
            f"Open-Meteo hat die Anfrage abgelehnt (HTTP {fehler.code})."
        )
        # Ein 400er liegt an unseren Parametern (Ort/Jahr) - alles andere ist ein
        # Problem auf Seiten der Quelle, nicht der Eingabe.
        if fehler.code == 400:
            raise WetterEingabeFehler(meldung) from fehler
        raise WetterAbrufFehler(meldung) from fehler
    except urllib.error.URLError as fehler:
        # Deckt u.a. eine Zeitueberschreitung ab - urlopen() wickelt einen
        # socket.timeout beim Verbindungsaufbau in eine URLError ein, wirft ihn
        # nicht roh weiter - sowie eine fehlende Netzverbindung.
        raise WetterAbrufFehler(
            "Die Wetterdaten konnten nicht abgerufen werden: keine Verbindung zu "
            "Open-Meteo oder die Anfrage hat zu lange gedauert. Bitte später erneut "
            "versuchen."
        ) from fehler

    try:
        return json.loads(rohdaten)
    except json.JSONDecodeError as fehler:
        raise WetterAbrufFehler("Open-Meteo hat eine unlesbare Antwort geliefert.") from fehler


def _parameter(breite, laenge, jahr, zusatz):
    parameter = {
        "latitude": breite,
        "longitude": laenge,
        "start_date": f"{jahr}-01-01",
        "end_date": f"{jahr}-12-31",
        "timezone": ZEITZONE,
        "timeformat": "iso8601",
    }
    parameter.update(zusatz)
    return parameter


def _erwartete_stunden(jahr):
    ist_schaltjahr = date(jahr, 12, 31).timetuple().tm_yday == 366
    return 8784 if ist_schaltjahr else 8760


def _stundenwerte(antwort, feld):
    """Liest eine Messreihe aus der Antwort und meldet fehlende Werte als
    unvollstaendige Daten, statt sie z.B. stillschweigend zu Null zu machen -
    ein fehlender Temperaturwert waere sonst eine falsche, nicht eine fehlende
    Stunde."""
    reihe = antwort.get("hourly", {}).get(feld)
    if reihe is None:
        raise WetterAbrufFehler(f"Die Antwort von Open-Meteo enthält kein Feld '{feld}'.")
    if any(wert is None for wert in reihe):
        raise WetterAbrufFehler(
            "Open-Meteo liefert für Teile des angefragten Jahres keine Werte "
            "(Datenlücke). Bitte einen anderen Ort oder ein anderes Jahr versuchen."
        )
    return reihe


def _absolute_feuchte(temperatur, rel_feuchte_prozent):
    """Kehrt core.bausteine.stoffdaten.rel_feuchte(T, x) um: aus Temperatur und
    relativer Feuchte wird die absolute Feuchte in g/kg berechnet, mit derselben
    Saettigungsdampfdruck-Formel wie im Rechenkern."""
    rel_feuchte_prozent = max(0.0, min(100.0, rel_feuchte_prozent))
    p_dampf = rel_feuchte_prozent / 100.0 * stoffdaten.p_saett(temperatur)
    return 622.2 * p_dampf / (100000.0 - p_dampf)


def abrufen(breite, laenge, jahr, ort=""):
    """Ruft ein volles Kalenderjahr Wetterdaten fuer (breite, laenge) ab und gibt
    sie in der kanonischen Form zurueck, die auch einlesen.lese_datei liefert.
    """
    jahr = _jahr_pruefen(jahr)
    breite, laenge = _ort_pruefen(breite, laenge)

    horizont_parameter = _parameter(breite, laenge, jahr, {
        "hourly": "temperature_2m,relative_humidity_2m,shortwave_radiation",
    })
    richtungs_parameter = {
        feld: _parameter(breite, laenge, jahr, {
            "hourly": "global_tilted_irradiance", "tilt": 90, "azimuth": azimut,
        })
        for feld, azimut in _AZIMUTE.items()
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        horizont_future = pool.submit(_anfrage, horizont_parameter)
        richtungs_futures = {
            feld: pool.submit(_anfrage, parameter)
            for feld, parameter in richtungs_parameter.items()
        }
        # Zuerst der Reihe nach abholen (nicht as_completed): so meldet ein
        # gescheiterter Abruf immer denselben, vorhersagbaren Fehler statt eines
        # zufaelligen je nachdem, welche Anfrage zuerst zurueckkam.
        horizont = horizont_future.result()
        richtungen = {feld: future.result() for feld, future in richtungs_futures.items()}

    zeiten = _stundenwerte(horizont, "time")
    erwartet = _erwartete_stunden(jahr)
    if len(zeiten) != erwartet:
        raise WetterAbrufFehler(
            f"Open-Meteo hat {len(zeiten)} Stunden statt der erwarteten {erwartet} "
            f"für {jahr} geliefert."
        )
    for feld, antwort in richtungen.items():
        if _stundenwerte(antwort, "time") != zeiten:
            raise WetterAbrufFehler(
                "Die Zeitreihen der einzelnen Abrufe stimmen nicht überein - "
                "bitte den Abruf erneut versuchen."
            )

    temperaturen = _stundenwerte(horizont, "temperature_2m")
    luftfeuchten = _stundenwerte(horizont, "relative_humidity_2m")
    horizontal = _stundenwerte(horizont, "shortwave_radiation")
    richtungswerte = {
        feld: _stundenwerte(antwort, "global_tilted_irradiance")
        for feld, antwort in richtungen.items()
    }

    stunden = []
    for i, zeit in enumerate(zeiten):
        t_au = float(temperaturen[i])
        eintrag = {
            "zeitpunkt": datetime.fromisoformat(zeit),
            "t_au": t_au,
            "x_au": _absolute_feuchte(t_au, float(luftfeuchten[i])),
            "str_h": float(horizontal[i]),
        }
        for feld in _AZIMUTE:
            eintrag[feld] = float(richtungswerte[feld][i])
        stunden.append(eintrag)
    return stunden
