# TRY-Ordner-Import und Standort-Gruppierung

Stand: 2026-09-04

## Ausgangslage

`core/wetter/try_import.py` heisst nach dem Testreferenzjahr, liest aber kein
einziges davon. Es liest `.xls`, `.xlsx` und `.csv` im Layout des Excel-Blattes
"Wetterdaten" (Excel-Datumszahl, danach `t_au`, `x_au` und fuenf
Strahlungswerte). Eine echte DWD-TRY-Datei mit der Endung `.dat` scheitert an
`ValueError: Format '.dat' wird nicht unterstuetzt`. Die Oberflaeche sagt das
offen: das Dateifeld in `templates/index.html` traegt
`accept=".xls,.xlsx,.csv"`, waehrend der Hinweistext daneben eine
"TRY-Wetterdatei" verspricht.

Ein Ordner-Upload existiert nicht. Das Formular nimmt genau eine Datei, und der
Endpunkt `POST /api/wetter/upload` liest genau ein Feld `datei`.

## Ziel

Ein Anwender waehlt den Ordner, den er vom DWD bezogen hat - etwa
`Dresden_Industriegelaende` mit dem Handbuch-PDF und einem Unterordner voller
`.dat`-Dateien. Er kreuzt an, welche Testreferenzjahre er braucht, und bekommt
sie als vollwertige Wetterdatensaetze, die sich in Simulationslaeufen genauso
verwenden lassen wie ein Open-Meteo-Abruf. Das Handbuch-PDF wird dabei nicht
hochgeladen. Derselbe Ordnerweg gilt fuer `.xls`, `.xlsx` und `.csv`.

Weil ein Standort schnell sechs oder mehr Datensaetze mitbringt, wird die
Auswahl im Simulationsdialog zweistufig: erst Standort, dann Datensatz.

## Entscheidungen

Vier Weichen wurden im Vorgespraech gestellt:

1. **Auswahl beim Hochladen.** Nicht alle gefundenen Dateien werden importiert,
   sondern die angekreuzten.
2. **Fassadenstrahlung wird gerechnet**, nicht auf Null gelassen und nicht von
   Open-Meteo nachgeladen.
3. **Gefiltert wird im Browser.** Nur die angekreuzten Dateien gehen zum Server;
   das PDF verlaesst den Rechner nie. Ein Serveraufruf, kein Zwischenspeicher.
4. **Zwei Auswahlfelder** im Simulationsdialog, gruppiert ueber die vorhandene
   Spalte `wetterdatensatz.ort`. Keine Schema-Aenderung.

## Aufbau der TRY-Datei

Geprueft an den sechs Dateien in `referenz/Dresden_Industriegelaende/`.

Der Kopf laeuft bis zu einer Zeile, die mit `***` beginnt; danach folgen 8760
Datenzeilen mit 17 durch Leerzeichen getrennten Feldern. Der Kopf ist **nicht**
zeilenfest: das Gegenwarts-TRY hat eine Zeile `Datenbasis`, das Zukunfts-TRY
drei (`Datenbasis 1` bis `Datenbasis 3`, Handbuch Kap. 2). Der Leser sucht
darum nach Schluesselwoertern bis zum `***`, statt Zeilen zu zaehlen.

Gelesen werden aus dem Kopf: `Rechtswert`, `Hochwert`, `Hoehenlage`,
`Art des TRY` und `Bezugszeitraum`.

Spalten der Datenzeilen (Handbuch Kap. 3.1, Tab. 2):

| Nr. | Kuerzel | Bedeutung | Verwendung |
|-----|---------|-----------|------------|
| 1,2 | RW, HW  | Koordinaten | ignoriert, stehen schon im Kopf |
| 3,4,5 | MM, DD, HH | Monat, Tag, Stunde MEZ | Zeitstempel |
| 6   | t       | Lufttemperatur [GradC] | `t_au` |
| 7   | p       | Luftdruck [hPa] | ignoriert |
| 8,9 | WR, WG  | Wind | ignoriert |
| 10  | N       | Bedeckungsgrad | ignoriert |
| 11  | x       | Wasserdampfgehalt [g/kg] | `x_au` |
| 12  | RF      | relative Feuchte [%] | ignoriert |
| 13  | B       | direkte Bestrahlungsstaerke, waagerecht [W/m2] | Strahlung |
| 14  | D       | diffuse Bestrahlungsstaerke, waagerecht [W/m2] | Strahlung |
| 15,16 | A, E  | langwellige Waermestrahlung | ignoriert |
| 17  | IL      | Qualitaetsbit | ignoriert |

`t` und `x` passen ohne Umrechnung auf `t_au` und `x_au` - der Rechenkern
fuehrt dieselben Groessen in denselben Einheiten.

**Zeitstempel.** `HH` laeuft von 1 bis 24 und bezeichnet die *vergangene*
Stunde; `HH=1` ist also 00:00 bis 01:00. Als Uhrzeit wird `HH-1` gesetzt, damit
8760 Stunden bei 00:00 am 1. Januar beginnen. Die Datenzeilen tragen kein Jahr,
weil ein mittleres TRJ aus Abschnitten verschiedener Jahre zusammengesetzt ist
(Handbuch Kap. 5). Als nominelles Jahr dient das Schluesseljahr aus dem
Dateinamen, 2015 oder 2045 - beides keine Schaltjahre, was zu 8760 Stunden
passt. Fehlt es, wird 2015 angenommen.

**Namenskonvention.** Das Handbuch (Kap. 2) beschreibt
`TRJJJJJ_RRRRRRRHHHHHHH_AAAA` mit Rechts- und Hochwert im Mittelteil. Die
tatsaechlich ausgelieferten Dateien halten sich nicht daran: der Ordner
`TRY_510881137633` und die Dateien darin tragen `510881137633`, also
51.0881 N / 13.7633 E - Breite und Laenge. Aus dem Dateinamen werden darum nur
Schluesseljahr (`TRY2015`, `TRY2045`) und Art (`Jahr`, `Somm`, `Wint`) gelesen,
niemals Koordinaten. Die kommen aus dem Kopf.

## Fassadenstrahlung

Das TRY liefert nur `B` und `D` auf die Waagerechte. Der Baustein Wetterkarte
(`core/bausteine/wetterkarte.py`) gibt aber `QH_S`, `QH_O`, `QH_W` und `QH_N`
aus, also Strahlung auf senkrechte Flaechen. Diese vier Werte werden gerechnet.

`str_h = B + D`.

Fuer die vier Himmelsrichtungen, je Stunde:

1. **Ort.** Rechts- und Hochwert aus dem Kopf stehen in Lambert konform
   konisch, EPSG:3034 (ETRS89-LCC Europa, GRS80, Normalparallelen 35 und 65
   Grad Nord, Ursprung 52 Grad Nord / 10 Grad Ost, Versatz 4 000 000 /
   2 800 000 Meter). Die geschlossene Umkehrformel liefert Breite und Laenge.
2. **Sonnenstand.** Deklination und Zeitgleichung nach den ueblichen Reihen;
   wahre Ortszeit aus MEZ, fest UTC+1 ohne Sommerzeit (das TRY ist durchgehend
   in MEZ angegeben, Handbuch Kap. 2), korrigiert um die geografische Laenge.
   Gerechnet wird auf die Mitte der jeweiligen Stunde.
3. **Direktanteil.** `B` ist auf die Waagerechte bezogen. Zurueck auf die
   Normale mit `B / sin(Sonnenhoehe)`, dann auf die Senkrechte projizieren mit
   `cos(Sonnenhoehe) * cos(Sonnenazimut - Flaechenazimut)`. Negative Werte
   bedeuten, dass die Sonne hinter der Flaeche steht, und werden zu Null.
   Unterhalb einer Mindest-Sonnenhoehe wird der Direktanteil ganz auf Null
   gesetzt, sonst laesst der Nenner den Wert ins Unsinnige laufen.
4. **Diffusanteil.** Isotroper Himmel: eine Senkrechte sieht den halben
   Himmel, also `D / 2`.
5. **Bodenreflexion.** `(B + D) * ALBEDO / 2` mit `ALBEDO = 0.2` fuer
   mitteleuropaeisches Umland (Wiese, Erde, gemischte Bebauung).

Die Bodenreflexion ist eine bewusste Wahl, keine Beigabe: Open-Meteos
`global_tilted_irradiance` enthaelt sie. Ohne sie waeren TRY-Datensaetze
systematisch dunkler als abgerufene, und beim Vergleich zweier Wetterjahre
derselben Anlage waere der Unterschied ein Artefakt des Imports statt einer
Aussage ueber das Wetter.

Die Albedo bleibt eine feste, benannte Konstante. Bei Schneelage waeren 0.7
richtig, aber das TRY fuehrt keine Schneegroesse (Handbuch Kap. 3.1, Tab. 2) -
eine automatische Umschaltung waere geraten, keine Rechnung. Wer Schneelagen
ernsthaft rechnen will, braucht eine Schneezeitreihe von anderswo; das ist eine
eigene Aufgabe, kein Eingabefeld.

## Module

`core/wetter/try_import.py` wird aufgeteilt. Der Name bleibt nicht bestehen:
echte TRY-Leserei in eine Datei zu legen, die "try_import" heisst und Excel
liest, waere genau die Verwechslung, die diese Arbeit sonst weitertraegt.

| Modul | Aufgabe |
|-------|---------|
| `core/wetter/tabelle.py` | der heutige Excel-/CSV-Leser, unveraendert umgezogen |
| `core/wetter/try_dat.py` | neu: DWD-TRY `.dat` - Kopf und Datenzeilen |
| `core/wetter/sonnenstand.py` | neu: EPSG:3034 nach WGS84, Sonnenstand, Strahlung auf Senkrechte |
| `core/wetter/einlesen.py` | neu: duenner Verteiler `lese_datei()`, waehlt nach Endung |
| `static/js/wetterauswahl.js` | neu: Buendelung nach Standort und die zwei Auswahlfelder |

`static/js/wetterauswahl.js` ist eine eigene Datei, weil beide Seiten sie
brauchen: die Startseite fuer ihre Tabelle, der Editor fuer seine beiden
Simulationsdialoge. Die einzige bisher gemeinsame Datei ist `zahlen.js`, und
dort gehoert Wetterauswahl nicht hinein - die rechnet mit Zahlen. Beide Seiten
laden sie vor ihren Nutzern; es sind klassische Skripte ohne Modulaufloesung,
die Reihenfolge ist also verbindlich und durch einen Test abgesichert.

`routes/wetter.py`, `core/wetter/openmeteo.py` (Verweis im Kopfkommentar) und
`tests/test_wetter.py` folgen der Umbenennung.

Jedes Modul ist fuer sich pruefbar. `sonnenstand` kennt kein Dateiformat,
`try_dat` keine Sonnenrechnung ausser dem Aufruf, `einlesen` kein Format ausser
der Endung.

## Schnittstelle

`POST /api/wetter/upload` nimmt kuenftig mehrere Dateien im Feld `datei` und
zusaetzlich ein Feld `ort`. Ein Einzelupload ist der Sonderfall mit einer
Datei; bestehende Aufrufe brechen nicht.

Antwort bei Erfolg (HTTP 201):

```json
{"datensaetze": [{"datei": "TRY2015_..._Jahr.dat", "id": 7, "name": "...", "stunden": 8760}],
 "dateifehler": [{"datei": "kaputt.dat", "fehler": "..."}]}
```

Eine unlesbare Datei darf die uebrigen nicht mitreissen: jede Datei wird
einzeln verarbeitet, Fehler werden gesammelt und mitgeliefert. Nur wenn keine
einzige Datei durchkommt, antwortet der Endpunkt mit HTTP 400.

Die Liste heisst 'dateifehler' und nicht 'fehler': 'fehler' bedeutet in dieser
Schnittstelle ueberall eine Meldung als Text. Denselben Schluessel je nach
Statuscode einmal als Zeichenkette und einmal als Liste zu belegen waere eine
Falle fuer jeden spaeteren Aufrufer.

Die Datei wird vor dem Lesen unter ihrem urspruenglichen Namen zwischengelegt,
nicht unter einem zufaelligen: das Schluesseljahr steht nur im Dateinamen, und
mit einem Namen wie "tmp8f3k.dat" bekaeme jedes Zukunfts-TRY stillschweigend
das Vorgabejahr 2015. Der Name kommt vom Browser und laeuft darum durch
secure_filename.

Gefuellt werden beim TRY-Import: `ort` aus dem Ordnernamen, `breite` und
`laenge` aus dem umgerechneten Kopf, `jahr` aus dem Schluesseljahr, `notiz` aus
Art des TRY, Bezugszeitraum und Hoehenlage.

`GET /api/wetter` bleibt unveraendert - `ort` liefert es bereits.

## Oberflaeche

**Upload.** Aus dem Einzeldatei-Feld wird ein Ordnerfeld (`webkitdirectory`).
JavaScript geht rekursiv durch die Auswahl, behaelt `.dat`, `.xls`, `.xlsx` und
`.csv` und zeigt eine Ankreuzliste, beschriftet aus dem Dateinamen
("2015 - mittleres Jahr"). Der Standort wird aus dem obersten Ordnernamen
vorbelegt und bleibt aenderbar. Voreingestellt angekreuzt sind die
Gegenwarts-TRY; die Zukunfts-TRY bleiben frei, weil sie seltener gebraucht
werden. Das Einzeldatei-Feld bleibt daneben bestehen - wer eine Datei hat, soll
keinen Ordner bauen muessen.

**Auswahl im Simulationsdialog.** Zwei Felder statt einem, in
`static/js/simulation.js` an beiden Stellen (Einzellauf, Vergleichsreihe): erst
Standort, dann Datensatz. Das zweite Feld zeigt nur, was zum gewaehlten
Standort gehoert. Datensaetze mit leerem `ort` - alle bisherigen Uploads -
sammeln sich unter "Ohne Standort". Bei nur einem Standort wird das erste Feld
nicht versteckt, sondern zeigt ihn an; ein Feld, das je nach Datenlage
erscheint und verschwindet, verwirrt mehr, als es spart.

**Liste auf der Startseite.** Die Tabelle bleibt, bekommt aber Zwischenzeilen
je Standort, damit sechs TRY-Jahre nicht als sechs zusammenhanglose Zeilen
dastehen.

## Tests

Zuerst die Tests, dann der Code. Geprueft wird gegen echte DWD-Dateien, nicht
gegen erfundene - gerade der Kopf ist die Stelle, an der ein selbstgebautes
Muster die Wirklichkeit verfehlen wuerde (siehe die drei Datenbasis-Zeilen des
Zukunfts-TRY).

**`try_dat`**
- liest 8760 Stunden aus der Gegenwarts-Datei
- erste Zeile ist der 1. Januar, 00:00, mit -3.7 GradC und 2.7 g/kg
- letzte Zeile ist der 31. Dezember, 23:00
- der Zukunfts-Kopf mit drei `Datenbasis`-Zeilen wird genauso gelesen wie der
  mit einer
- Art des TRY, Bezugszeitraum und Hoehenlage landen in der Notiz
- Schluesseljahr und Art werden aus dem Dateinamen gelesen
- eine Datei ohne `***` meldet einen verstaendlichen Fehler

**`sonnenstand`**
- die Umkehrprojektion trifft den Ursprung (52 N / 10 E) exakt
- sie trifft die beiden Ortsangaben aus Handbuch Kap. 5 auf besser als 1 km:
  4336500/2728500 liegt 8 km noerdlich von Goerlitz, 4150500/2503500 liegt
  3 km oestlich von Teublitz
- sie trifft fuer die Referenzdatei 51.0881 N / 13.7633 E, also genau die
  Zahlen im Ordnernamen
- die Sonne steht mittags im Sueden und dann am hoechsten
- nachts sind alle fuenf Strahlungswerte Null
- im Sommer bekommt Ost vormittags mehr als West, nachmittags umgekehrt
- Nord bekommt im Winter nur Diffus- und Bodenanteil, nie Direktstrahlung
- bei sehr flacher Sonne bleibt der Direktanteil endlich

**Upload**
- ein Upload mit zwei `.dat`-Dateien legt zwei Datensaetze mit demselben `ort` an
- eine kaputte Datei unter guten wird gemeldet, die guten entstehen trotzdem
- kommt keine Datei durch, antwortet der Endpunkt mit 400
- der Einzeldatei-Upload einer Excel-Mappe funktioniert weiter

**Oberflaeche**
- die Startseite bringt das Ordnerfeld mit `webkitdirectory` aus
- der Simulationsdialog enthaelt beide Auswahlfelder

## Nicht Teil dieser Arbeit

- Schneeabhaengige Albedo
- Die langwelligen Groessen `A` und `E` aus dem TRY - der Rechenkern kennt sie
  nicht
- Wind und Luftdruck aus dem TRY - dasselbe
- Eine eigene Standort-Tabelle in der Datenbank


## Nachtrag: was sich waehrend der Umsetzung geaendert hat

- Die Liste der Fehler je Datei heisst `dateifehler`, nicht `fehler` (siehe
  oben, Abschnitt Schnittstelle).
- Die Buendelung nach Standort wurde in eine eigene, von beiden Seiten geladene
  Datei `static/js/wetterauswahl.js` gezogen, statt sie in `start.js` und
  `simulation.js` zu verdoppeln.
- Das Standortfeld bietet zusaetzlich "Alle Standorte", sobald es mehr als
  einen gibt - sonst waere der Vergleich zweier Wetterjahre verschiedener Orte
  nicht mehr moeglich gewesen, der vorher ging.
- In der Wetterliste der Startseite ist die Spalte "Ort" entfallen; sie stuende
  unter der Standort-Zwischenzeile nur doppelt.
- Die Testdaten liegen unter `tests/daten/try/`, nicht mehr im urspruenglich
  dorthin gelegten `referenz/Dresden_Industriegelaende/`. Nur das mittlere
  Jahr ist vollstaendig (daran haengen die Pruefungen auf 8760 lueckenlose
  Stunden); von den beiden anderen genuegen Kopf und zwei Tage, denn an ihnen
  wird allein die Kopfauswertung geprueft. Aus 5,9 MB werden so 681 kB.
