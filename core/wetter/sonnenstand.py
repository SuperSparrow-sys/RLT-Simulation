"""Sonnenstand und Strahlung auf senkrechte Flaechen.

Ein DWD-Testreferenzjahr liefert die Sonnenstrahlung nur bezogen auf die
Waagerechte: direkt (B) und diffus (D). Der Baustein Wetterkarte
(core/bausteine/wetterkarte.py) gibt dagegen QH_S, QH_O, QH_W und QH_N aus,
also die Strahlung auf senkrechte Flaechen - Fassaden. Diese vier Werte stehen
im TRY nicht drin und werden hier aus dem Sonnenstand gerechnet.

Der Weg dorthin geht ueber drei Schritte, die dieses Modul in dieser
Reihenfolge anbietet:

1. nach_wgs84()  - der TRY-Kopf nennt den Ort in Lambert konform konisch
                   (EPSG:3034); fuer jede Sonnenrechnung braucht es aber
                   geografische Breite und Laenge.
2. stand()       - Hoehe und Azimut der Sonne zu einem Zeitpunkt.
3. strahlung_auf_senkrechte() - daraus und aus B und D die vier Fassadenwerte.

Die Azimut-Zaehlung ist dieselbe wie in core/wetter/openmeteo.py (_AZIMUTE):
0 Grad ist Sued, -90 Ost, +90 West, 180 Nord. So bedeuten str_s/str_o/str_w/
str_n bei abgerufenen und bei importierten Datensaetzen dasselbe.

Zeitrechnung: das TRY ist durchgehend in MEZ angegeben (Handbuch Kap. 2), also
fest UTC+1 ohne Sommerzeit. Die wahre Ortszeit ergibt sich daraus ueber die
geografische Laenge und die Zeitgleichung.
"""

import math

# --- Beiwerte -------------------------------------------------------------

#: Rueckstrahlwert des Bodens vor der Fassade. 0,2 steht fuer mitteleuropaeisches
#: Umland (Wiese, Erde, gemischte Bebauung). Bewusst fest: bei Schneelage waeren
#: rund 0,7 richtig, aber das TRY fuehrt keine Schneegroesse (Handbuch Kap. 3.1,
#: Tab. 2) - eine automatische Umschaltung waere geraten, nicht gerechnet.
ALBEDO = 0.2

#: Obergrenze fuer die aus B zurueckgerechnete Direktnormalstrahlung. Mehr als
#: die Solarkonstante kann am Boden nicht ankommen; ohne den Deckel liesse die
#: Division durch sin(Sonnenhoehe) den Wert bei flacher Sonne ins Unsinnige
#: laufen.
SOLARKONSTANTE = 1367.0

#: Unterhalb dieser Sonnenhoehe wird gar kein Direktanteil mehr angesetzt. Bei
#: streifendem Einfall ist die Rueckrechnung B / sin(h) zahlenmaessig wertlos,
#: und die tatsaechliche Direktstrahlung ist dort ohnehin verschwindend.
MIN_SONNENHOEHE_GRAD = 3.0

#: Zeitzone des TRY: MEZ, also der Bezugslaengengrad 15 Grad Ost.
BEZUGSLAENGE_GRAD = 15.0

#: Flaechenazimut je Feldname im kanonischen Stundensatz.
AUSRICHTUNGEN = {"str_s": 0.0, "str_o": -90.0, "str_w": 90.0, "str_n": 180.0}


# --- EPSG:3034: Lambert konform konisch nach WGS84 -------------------------

# ETRS89 / LCC Europa auf dem Ellipsoid GRS80. Die Beiwerte stehen so in der
# Definition des Kennzeichens 3034; der TRY-Kopf nennt genau dieses System
# ("Koordinatensystem : Lambert konform konisch", Handbuch Kap. 2).
_A = 6378137.0                    # grosse Halbachse GRS80 [m]
_F = 1 / 298.257222101            # Abplattung GRS80
_E = math.sqrt(2 * _F - _F * _F)  # erste numerische Exzentrizitaet
_NORMALPARALLELE_1 = math.radians(35.0)
_NORMALPARALLELE_2 = math.radians(65.0)
_URSPRUNG_BREITE = math.radians(52.0)
_URSPRUNG_LAENGE = math.radians(10.0)
_VERSATZ_OST = 4000000.0
_VERSATZ_NORD = 2800000.0


def _m(breite):
    return math.cos(breite) / math.sqrt(1 - _E * _E * math.sin(breite) ** 2)


def _t(breite):
    verhaeltnis = (1 - _E * math.sin(breite)) / (1 + _E * math.sin(breite))
    return math.tan(math.pi / 4 - breite / 2) / verhaeltnis ** (_E / 2)


_N = (math.log(_m(_NORMALPARALLELE_1)) - math.log(_m(_NORMALPARALLELE_2))) / (
    math.log(_t(_NORMALPARALLELE_1)) - math.log(_t(_NORMALPARALLELE_2))
)
_F_BEIWERT = _m(_NORMALPARALLELE_1) / (_N * _t(_NORMALPARALLELE_1) ** _N)
_R_URSPRUNG = _A * _F_BEIWERT * _t(_URSPRUNG_BREITE) ** _N


def nach_wgs84(rechtswert, hochwert):
    """Rechnet Rechts- und Hochwert aus dem TRY-Kopf in Breite und Laenge um.

    Rueckgabe in Grad, (breite, laenge). Nachgeprueft an den beiden Ortsangaben
    aus Handbuch Kap. 5: 4336500/2728500 liegt 8 km noerdlich von Goerlitz,
    4150500/2503500 liegt 3 km oestlich von Teublitz.
    """
    ost = float(rechtswert) - _VERSATZ_OST
    nord = _R_URSPRUNG - (float(hochwert) - _VERSATZ_NORD)

    radius = math.copysign(math.hypot(ost, nord), _N)
    t_wert = (radius / (_A * _F_BEIWERT)) ** (1 / _N)
    winkel = math.atan2(ost, nord)

    laenge = winkel / _N + _URSPRUNG_LAENGE
    # Die konforme Breite laesst sich nicht geschlossen umkehren; die Reihe
    # konvergiert aber in wenigen Schritten weit unter Millimetergenauigkeit.
    breite = math.pi / 2 - 2 * math.atan(t_wert)
    for _ in range(12):
        verhaeltnis = (1 - _E * math.sin(breite)) / (1 + _E * math.sin(breite))
        breite = math.pi / 2 - 2 * math.atan(t_wert * verhaeltnis ** (_E / 2))

    return math.degrees(breite), math.degrees(laenge)


# --- Sonnenstand ----------------------------------------------------------

def _tageswinkel(zeitpunkt):
    return 2 * math.pi * (zeitpunkt.timetuple().tm_yday - 1) / 365.0


def _deklination(tageswinkel):
    """Sonnendeklination in Radiant nach der Reihe von Spencer (1971)."""
    b = tageswinkel
    return (
        0.006918
        - 0.399912 * math.cos(b) + 0.070257 * math.sin(b)
        - 0.006758 * math.cos(2 * b) + 0.000907 * math.sin(2 * b)
        - 0.002697 * math.cos(3 * b) + 0.001480 * math.sin(3 * b)
    )


def _zeitgleichung(tageswinkel):
    """Zeitgleichung in Minuten - der Gang zwischen mittlerer und wahrer
    Sonnenzeit, ueber das Jahr rund plus/minus 16 Minuten."""
    b = tageswinkel
    return 229.18 * (
        0.000075
        + 0.001868 * math.cos(b) - 0.032077 * math.sin(b)
        - 0.014615 * math.cos(2 * b) - 0.040849 * math.sin(2 * b)
    )


def stand(zeitpunkt, breite, laenge):
    """Hoehe und Azimut der Sonne zum angegebenen Zeitpunkt (MEZ).

    Rueckgabe in Grad, (hoehe, azimut). Die Hoehe wird ueber dem Horizont
    gezaehlt und ist nachts negativ. Der Azimut zaehlt von Sued: 0 ist Sued,
    negative Werte stehen fuer den oestlichen Vormittag, positive fuer den
    westlichen Nachmittag.
    """
    tageswinkel = _tageswinkel(zeitpunkt)
    deklination = _deklination(tageswinkel)
    breite_rad = math.radians(breite)

    # Wahre Ortszeit: Uhrzeit, verschoben um den Abstand zum Bezugslaengengrad
    # (vier Minuten je Grad) und um die Zeitgleichung.
    uhrzeit_min = zeitpunkt.hour * 60 + zeitpunkt.minute + zeitpunkt.second / 60
    wahre_ortszeit = (
        uhrzeit_min + 4.0 * (laenge - BEZUGSLAENGE_GRAD) + _zeitgleichung(tageswinkel)
    )
    stundenwinkel = math.radians(wahre_ortszeit / 4.0 - 180.0)

    sinus_hoehe = (
        math.sin(breite_rad) * math.sin(deklination)
        + math.cos(breite_rad) * math.cos(deklination) * math.cos(stundenwinkel)
    )
    sinus_hoehe = max(-1.0, min(1.0, sinus_hoehe))
    hoehe = math.asin(sinus_hoehe)

    nenner = math.cos(hoehe) * math.cos(breite_rad)
    if abs(nenner) < 1e-9:
        # Sonne genau im Zenit oder Beobachter am Pol - beides kommt in
        # Deutschland nicht vor, aber ohne diesen Zweig teilte es durch Null.
        azimut = 0.0
    else:
        kosinus_azimut = (sinus_hoehe * math.sin(breite_rad) - math.sin(deklination)) / nenner
        kosinus_azimut = max(-1.0, min(1.0, kosinus_azimut))
        azimut = math.copysign(math.acos(kosinus_azimut), stundenwinkel)

    return math.degrees(hoehe), math.degrees(azimut)


# --- Strahlung auf senkrechte Flaechen ------------------------------------

def strahlung_auf_senkrechte(zeitpunkt, breite, laenge, direkt_h, diffus_h):
    """Rechnet die waagerechten TRY-Strahlungswerte auf vier Fassaden um.

    'direkt_h' und 'diffus_h' sind die Spalten B und D des TRY, beide bezogen
    auf die waagerechte Ebene, in W/m2. Rueckgabe ist ein Dictionary mit
    str_s, str_o, str_w und str_n.

    Der Zeitpunkt muss den Augenblick bezeichnen, fuer den gerechnet werden
    soll - bei Stundenmitteln also die Mitte der Stunde, nicht ihren Anfang.
    Das Umrechnen darauf ist Sache des Aufrufers (siehe core/wetter/try_dat.py),
    damit diese Funktion nichts ueber die Zeitrasterung ihrer Quelle annimmt.

    Jede Fassade bekommt drei Beitraege:
      - direkt von der Sonnenscheibe, sofern sie vor der Flaeche steht,
      - diffus vom halben sichtbaren Himmel,
      - vom Boden davor zurueckgeworfen (ALBEDO).
    """
    direkt_h = max(0.0, float(direkt_h))
    diffus_h = max(0.0, float(diffus_h))

    hoehe, azimut = stand(zeitpunkt, breite, laenge)

    # Beide Anteile sieht jede Senkrechte gleich: sie blickt auf den halben
    # Himmel und auf den halben Boden.
    diffus_anteil = diffus_h / 2.0
    boden_anteil = (direkt_h + diffus_h) * ALBEDO / 2.0
    grundanteil = diffus_anteil + boden_anteil

    if hoehe <= MIN_SONNENHOEHE_GRAD or direkt_h <= 0.0:
        return {feld: grundanteil for feld in AUSRICHTUNGEN}

    # B ist auf die Waagerechte bezogen; fuer die Projektion auf eine andere
    # Flaeche braucht es zuerst den Wert senkrecht zur Sonnenrichtung zurueck.
    direkt_normal = min(direkt_h / math.sin(math.radians(hoehe)), SOLARKONSTANTE)

    werte = {}
    for feld, flaechen_azimut in AUSRICHTUNGEN.items():
        # Einfallswinkel auf eine senkrechte Flaeche: nur der Anteil, der noch
        # in Blickrichtung der Flaeche zeigt. Negativ heisst, die Sonne steht
        # hinter der Wand.
        kosinus_einfall = math.cos(math.radians(hoehe)) * math.cos(
            math.radians(azimut - flaechen_azimut)
        )
        direkt_anteil = direkt_normal * kosinus_einfall if kosinus_einfall > 0 else 0.0
        werte[feld] = direkt_anteil + grundanteil
    return werte
