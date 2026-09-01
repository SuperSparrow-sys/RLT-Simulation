# RLT-Simulation — Entwurf

Nachbau der Excel-Arbeitsmappe `RLTSimulation_Vorlage_AX_SIM_2.1` als Flask-Webanwendung
mit grafischem Karteneditor.

Stand: 2026-09-01

---

## 1. Ziel und Abgrenzung

Die vorhandene Excel-Mappe simuliert raumlufttechnische Anlagen über ein Jahr in
Stundenschritten und bilanziert Strom, Wärme, Kälte, Wasser und die daraus
entstehenden Kosten. Sie besteht aus drei Blättern:

- `Anlage` — Konfiguration und die vollständige Physik in 465 Formeln
- `Wetterdaten` — 8760 Stundenwerte (Datum, Temperatur, absolute Feuchte, Strahlung S/O/W/N/H)
- `Ergebnis` — Stundenprotokoll und Jahresbilanz

Die Simulation läuft als VBA-Stundenschleife (`Berechnungen.Wetterdaten_verarbeiten`,
`frm_Simulation.Daten_berechnen`): je Stunde werden die Wetterwerte in benannte Zellen
geschrieben, Excel rechnet **iterativ** (`Application.Iteration = True`, `MaxChange = 0.001`)
bis zur Konvergenz, danach kopiert `Speicher()` alle Endwerte auf die zugehörigen
Startwerte und die nächste Stunde beginnt.

Die Mappe ist bereits kartenbasiert aufgebaut: in den Zeilen 116–159 liegt eine
Bausteinbibliothek als benannte Blöcke (`WRG`, `MK`, `DBF`, `LE1`, `LK`, `ZU`,
`Wascher`, `Raum`, `Enthalpie`, `HRegler`, `SRegler2`), darüber in den Zeilen 2–115
die konkret verdrahtete Anlage. Die Verbindungen sind Zellbezüge: `S14 = M17` bedeutet
„Kühler.T_ein = Erhitzer.T_aus".

**Ziel:** dieselbe Fachlichkeit als wartbares Webprogramm, in dem Anlagen aus Karten
zusammengezogen und mit Pfeilen verbunden werden.

**Festgelegte Randbedingungen**

| Punkt | Entscheidung |
|---|---|
| Physik | 1:1 aus der Excel übernommen, gegen deren Ergebnisse validiert |
| Erste Version | Rechenkern und Editor gemeinsam, inkl. TRY-Upload und Jahresbilanz |
| Anlagenerzeugung | mitgelieferte Vorlage „AX_SIM 2.1" plus leere Leinwand mit Palette |
| Betrieb | lokal beziehungsweise im LAN, keine Benutzerverwaltung |
| Solver | Bausteine als Python-Objekte, äußere Fixpunkt-Iteration |

**Nicht Teil dieses Entwurfs:** Import beliebiger vorhandener AX_SIM-Dateien,
Benutzerverwaltung, Mehrbenutzer-Bearbeitung derselben Leinwand.

---

## 2. Kartenkatalog

30 Kartentypen in sieben Palettengruppen. Die Spaltenangabe verweist auf den
Bausteinblock in der Excel.

### 2.1 Luftbehandlung

| Karte | Excel | Wesentliche Parameter |
|---|---|---|
| Wärmerückgewinnung | `I:K` | V_nenn, dp_WRG_nenn, dp_Bypass_nenn, Rückwärmzahl, Rückfeuchtzahl |
| Mischkammer | `L:N` | max. Umluftanteil |
| Erhitzer | `R:T` | V_nenn, dp_nenn, QH_max |
| Kühler | `AA:AC` | V_nenn, dp_nenn, QK_nenn, T_KW_mittel |
| Dampfbefeuchter | `O:Q` | Dampftemperatur, max. Befeuchtungsleistung, E-/Fremddampf, Absalzverlust |
| Luftwäscher | `AD:AF` | V_nenn, dp_nenn, Absalzverlust, Pumpenart (Ventil/FU/HD) |
| Ventilator | `X:Z` bzw. `U:W` | V_max, dp_max, dp_konst, PE_max, Regelart (FU/Drallregler/ungeregelt), Rolle Zuluft oder Abluft |

### 2.2 Verteilung

| Karte | Herkunft | Zweck |
|---|---|---|
| Verteiler | in der Excel als Formel `S9 = V9` | ein Strang auf mehrere Gänge |
| Sammler | in der Excel als Formel `M9 = S9 + S31` | mehrere Gänge auf einen Strang |

Beide Karten haben dynamische Luft-Ports. Der Sammler mischt massenstromgewichtet
nach derselben Formel wie die Mischkammer.

**Aufteilung beim Verteiler.** Der Volumenstrom eines Gangs ergibt sich im
Rückwärtslauf aus dem, was stromabwärts angefordert wird — in der Regel vom Ventilator
dieses Gangs. Enthält ein Gang keinen Baustein, der den Volumenstrom festlegt, greift
der Parameter `Anteil` des betreffenden Ports: die Restmenge wird dann nach diesen
Anteilen verteilt. Fordert die Summe der Gänge mehr an, als der zuführende Strang
liefern kann, wird proportional gekürzt und eine Warnung protokolliert.

### 2.3 Räume

| Karte | Excel | Inhalt |
|---|---|---|
| Einfacher Raum | `AG31:AI50` | stationäre Mischbilanz aus Zuluftsträngen, Infiltration, Transmission und inneren Lasten |
| Raum | `AG70:AL134` | Geometrie, U-Werte, Fenster mit g-Faktor und Ausrichtung, Bauart in Wh/(m²·K), Solargewinne, Wandspeicher, exponentielle Aufheizkurve |
| Statische Heizung | `AH128/AH129` | Sollwert, Nennleistung; deckt die Unterdeckung des Raums |

Mehrere Räume sind mehrere Karten. Beide Raumtypen haben dynamische Zuluft- und
Abluft-Ports, sodass ein Raum von mehreren Geräten versorgt werden kann und ein Gerät
mehrere Räume bedient.

### 2.4 Regelung

| Karte | Excel | Verhalten |
|---|---|---|
| P-Regler | `K51:K61` u. a. | zweistufig (schnell und träge), integriert über die Iterationen |
| Sequenzregler | `R138:T148` (`SRegler2`) | eine Regelabweichung auf fünf Sequenzen (wärmer 3/2/1, kälter 1/2) |
| Hysterese-Regler | `U149:W159` (`HRegler`) | Zweipunkt mit Schaltdifferenz und Zustandsgedächtnis |
| Raum-/Zuluft-Kaskade | `O139:Q157` | außentemperaturgeführter Raumsollwert, Begrenzung der Zulufttemperatur, Sequenzausgänge |

### 2.5 Zeit und Betrieb

| Karte | Excel | Inhalt |
|---|---|---|
| Wochenzeitplan | `AK4:AN14` | je Wochentag von/bis |
| Wochen- und Monatsprofil | `AO4:AR28` | Wochenplan plus Monate ein/aus |
| Tageslastprofil | `AS6:AV32` | drei Lastgänge über 24 Stunden |
| Ferien und Sondertage | `AK18:AN28` | Zeiträume, die den Betrieb sperren |
| Anlagenbetrieb | `AL37/AL38` | verknüpft Zeitplan, Ferien und Tagesprofil zu Betriebssignal und Stellgrad |

### 2.6 Quellen und Senken

| Karte | Excel | Inhalt |
|---|---|---|
| Wetterdaten | `F2:H22` (`Wetter`) | liefert T_AU, x_AU und die fünf Strahlungswerte der aktuellen Stunde |
| Außenluft / Fortluft | — | Anschlusspunkte am Anfang und Ende eines Luftwegs |

### 2.7 Verbraucher und Auswertung

| Karte | Excel | Inhalt |
|---|---|---|
| Heizungspumpen | `AD138:AF145` | Pumpenleistung Allgemein, WWB, Kessel; Betrieb Heizung |
| Warmwasserbereitung | `AD147:AF156` | Speichervolumen, Jahresverbrauch, Sollwert, Speicherverlust |
| Zirkulation | `AD152:AF158` | Volumenstrom, Spreizung VL–RL, Pumpenleistung, Betriebszeit |
| Beleuchtung | `AK130:AL134` | spez. Leistung, Nennbeleuchtungsstärke; Wärmeeintrag und Strom |
| Enthalpie-/Feuchterechner | `U138:W148`, `X141:Z148` | Hilfsbaustein zur Zustandsumrechnung |
| Energiepreise und Bilanz | `AO30:AR42` | Preise Strom HT/NT, Wärme, Kälte, Wasser; HT-Zeitfenster |
| Datenlogger | `B26:D46` (`Logger`) | bis zu zehn frei gewählte Größen als Ergebnisspalten |
| Speicher | `C54:D67` (`Speicherwert`) | Zustandsübergabe von Stunde zu Stunde |

Die Beleuchtung steckt in der Excel fest im Raumblock. Sie wird als eigene Karte
herausgelöst, damit Räume mit unterschiedlicher Beleuchtung gerechnet werden können.
Die Rechenformel bleibt unverändert.

---

## 3. Aufbau eines Bausteins

Jeder Kartentyp ist genau eine Python-Datei unter `core/bausteine/`. Sie deklariert
alles über sich selbst; Palette, Parameterfenster, Ports und Ergebnisspalten werden
daraus erzeugt.

```python
KENNUNG = "erhitzer"
NAME    = "Erhitzer"
GRUPPE  = "Luftbehandlung"
SYMBOL  = "erhitzer.svg"

PARAMETER = [
    Param("V_nenn",  "V_nenn",  "m³/h", vorgabe=8200),
    Param("dp_nenn", "dp_nenn", "Pa",   vorgabe=240),
    Param("QH_max",  "QH_max",  "kW",   vorgabe=101),
]

PORTS = [
    Port("luft_ein",     LUFT,   EINGANG, rolle=ZULUFT),
    Port("luft_aus",     LUFT,   AUSGANG, rolle=ZULUFT),
    Port("stellgroesse", SIGNAL, EINGANG, rolle=STELLGROESSE),
    Port("QH",           SIGNAL, AUSGANG, rolle=MESSWERT),
]

AUSGABEN = ["T_aus", "F_aus", "QH", "dp"]

def berechne(ein, p, zustand):
    ...
```

**Ein Luft-Port** trägt immer dasselbe Bündel: Volumenstrom in m³/h, Temperatur in °C,
absolute Feuchte in g/kg und Druckverlust in Pa. **Ein Signal-Port** trägt eine Zahl.
Dadurch passt jeder Luftausgang an jeden Lufteingang, und beim Verbinden ist die
Datenzuordnung automatisch richtig.

**Eine neue Karte hinzufügen heißt: eine Datei anlegen.** Keine Änderung an Datenbank,
Editor oder Solver ist nötig. Das ist die zentrale Anforderung an die Wartbarkeit und
bestimmt mehrere Entwurfsentscheidungen weiter unten — insbesondere, dass
Kartenparameter als JSON gespeichert werden.

### 3.1 Ports

Ports werden **automatisch** erzeugt, sobald eine Karte auf die Leinwand kommt.
Von Hand wird nie ein Port angelegt.

**Rollen.** Neben der Art (Luft oder Signal) trägt jeder Port eine Rolle: Zuluft,
Abluft, Außenluft, Fortluft, Umluft, Stellgröße, Istwert, Sollwert, Messwert.
Die Rolle steuert die automatische Verdrahtung.

**Dynamische Ports.** Ein Port kann als `dynamisch` deklariert sein. Sobald der letzte
freie Port dieser Rolle belegt wird, wächst ein weiterer nach; beim Trennen schrumpft
die Karte wieder auf einen freien Port zurück. Dynamische Luft-Ports haben:
Verteiler, Sammler, Wärmerückgewinnung, Mischkammer und beide Raumtypen.

### 3.2 Automatische Verdrahtung

Verbunden werden **Karten, nicht Ports**. Ein Pfeil von Karte A nach Karte B löst
folgende Zuordnung aus:

1. Freie Ausgänge von A und freie Eingänge von B werden nach Rolle gepaart.
2. Für jedes Paar entsteht eine Port-Verbindung.
3. Bei Reglern entsteht zusätzlich die Rückrichtung: Stellgröße hin, Istwert zurück.
4. Bleibt eine Zuordnung mehrdeutig, wird die naheliegende gewählt und am Pfeil
   angezeigt; sie ist per Klick korrigierbar.

Beispiele: Erhitzer → Kühler verdrahtet den Zuluftweg. Raum → Wärmerückgewinnung
verdrahtet den Abluftweg und lässt den Zuluftweg für die Außenluft frei.
Regler → Erhitzer verdrahtet Stellgröße und Istwert in einem Zug.

In der Datenbank bleiben Verbindungen auf Port-Ebene gespeichert — das braucht der
Solver — sind aber unter einem Pfeil gruppiert, sodass Löschen den ganzen Strang
mitnimmt.

---

## 4. Rechenkern

### 4.1 Ablauf je Stunde

```
für jede Stunde des Zeitraums:
    Wetterwerte in die Wetterkarte schreiben
    Zeitpläne auswerten  ->  Betriebssignal
    Rückwärtslauf:  Volumenströme von den Ventilatoren zu den Quellen,
                    an Verzweigungen summiert
    Vorwärtslauf:   Zustände (T, x, dp) durch die Kette,
                    wiederholt bis alle Größen sich um < 0,001 ändern
                    (höchstens 100 Durchläufe)
    Bilanzgrößen und Loggerwerte festhalten
    Speicher: Endwerte -> Startwerte
```

Der **Rückwärtslauf** bildet nach, dass in der Excel der Volumenstrom vom Ventilator
zur Quelle durchgereicht wird (`S9 = V9`, `V9 = Y9`) und sich an Verzweigungen addiert
(`M9 = S9 + S31`).

Der **Vorwärtslauf** ist eine Gauß-Seidel-Iteration über die topologisch sortierten
Karten unter Auslassung der Rückkanten. Er bildet die iterative Neuberechnung von
Excel nach, einschließlich der Regler: deren Ausgang hängt in der Excel vom eigenen
Vorwert ab (`K51 = J57 − (Istwert − Sollwert)/Xp`, `J57 = clamp(K51)`), sie wirken
also als Integrierer über die Iterationen. Dieses Verhalten wird bewusst genauso
nachgebildet.

**Konvergenz.** Wird nach 100 Durchläufen nicht konvergiert, wird die Stunde mit den
letzten Werten protokolliert und eine Warnung mit Stunde und größter Abweichung
gespeichert. Die Simulation läuft weiter; die Warnungen erscheinen im Bericht.

**Zustandsgrößen** (Raumtemperatur, Wandtemperatur, Reglerzustände, Hysteresezustand)
liegen in einem eigenen Register je Karte und werden nach Konvergenz auf die
Startwerte der nächsten Stunde kopiert — die Entsprechung zu `Speicher()`.

### 4.2 Zyklen

Zyklen sind im Modell normal und beabsichtigt: die Wärmerückgewinnung koppelt Zu- und
Abluft, der Raum wirkt auf die Abluft zurück, jeder Regler ist eine Rückkopplung.
Der Solver bricht Zyklen an den Rückkanten auf und schließt sie über die Iteration.
Zyklen werden daher nicht als Fehler gemeldet.

### 4.3 Laufzeit

8760 Stunden mal etwa 30 Karten mal typischerweise 5 bis 20 Iterationen liegen im
Bereich weniger Sekunden. Der Lauf erfolgt trotzdem im Hintergrund mit
Fortschrittsanzeige und Abbruchmöglichkeit, weil auch mehrere Jahre hintereinander
gerechnet werden.

---

## 5. Datenbank

SQLite im Stil der übrigen Programme: WAL, Fremdschlüssel aktiv, `core/database.py`
mit `get_db`/`close_db` und Wiederholung bei Sperren.

### 5.1 Anlage und Karten

| Tabelle | Felder |
|---|---|
| `projekt` | `id`, `name`, `beschreibung`, `erstellt_am`, `geaendert_am` |
| `anlage` | `id`, `projekt_id`, `name`, `notiz`, `erstellt_am`, `geaendert_am` |
| `karte` | `id`, `anlage_id`, `typ`, `name`, `pos_x`, `pos_y`, `parameter` (JSON) |
| `port` | `id`, `karte_id`, `schluessel`, `art`, `richtung`, `rolle`, `nummer` |
| `pfeil` | `id`, `anlage_id`, `von_karte_id`, `nach_karte_id`, `stuetzpunkte` (JSON) |
| `verbindung` | `id`, `pfeil_id`, `von_port_id`, `nach_port_id` |

Eine Anlage ist eine Leinwand. Mehrere Anlagen im selben Projekt sind zugleich die
Varianten für den Vergleich.

`karte.parameter` liegt als JSON vor. Ein neuer Kartentyp erfordert dadurch keine
Schemaänderung.

`port` wird aus der Typdeklaration erzeugt; `nummer` unterscheidet die Ports
dynamischer Rollen.

`pfeil` ist die Sicht des Nutzers, `verbindung` die des Solvers. Löschen eines Pfeils
löscht seine Verbindungen mit.

### 5.2 Wetterdaten

| Tabelle | Felder |
|---|---|
| `wetterdatensatz` | `id`, `name`, `quelle`, `ort`, `breite`, `laenge`, `jahr`, `zeitzone`, `notiz`, `erstellt_am` |
| `wetterstunde` | `datensatz_id`, `stunde`, `zeitpunkt`, `t_au`, `x_au`, `str_s`, `str_o`, `str_w`, `str_n`, `str_h` |

Primärschlüssel von `wetterstunde` ist `(datensatz_id, stunde)`. Ein Datensatz je Ort
und Jahr; der Jahresvergleich ist damit die Auswahl mehrerer Datensätze.

### 5.3 Ergebnisse

| Tabelle | Felder |
|---|---|
| `simulation` | `id`, `anlage_id`, `wetterdatensatz_id`, `von_stunde`, `bis_stunde`, `status`, `gestartet_am`, `beendet_am`, `dauer_s`, `warnungen` (JSON) |
| `zeitreihe` | `id`, `simulation_id`, `karte_id`, `groesse`, `einheit`, `werte` (BLOB) |
| `bilanz` | `id`, `simulation_id`, `groesse`, `menge`, `einheit`, `preis`, `kosten` |

`zeitreihe.werte` ist ein binäres Feld mit 32-Bit-Gleitkommazahlen, eine je Stunde:
rund 35 KB für ein Jahr. Ein Diagramm lädt seine Reihe in einem Zugriff, und die
Datenbank wächst nicht auf Millionen Zeilen. Aggregate stehen in `bilanz` und bleiben
per SQL vergleichbar.

---

## 6. Weboberfläche

### 6.1 Editor

- **Links** die Palette, nach den sieben Gruppen sortiert, mit den Symbolen der Excel
  als SVG.
- **Mitte** die Leinwand: zoom- und verschiebbar, Karten per Ziehen aus der Palette,
  Pfeile per Ziehen von Karte zu Karte. Luftkanäle dick, Regelsignale dünn.
- **Rechts** das Parameterfenster der ausgewählten Karte, erzeugt aus deren
  Typdeklaration, mit Einheit und Wertebereich je Feld.
- Jede Änderung wird sofort gespeichert.
- Nach einem Lauf zeigt jede Karte ihre Werte an den Anschlüssen an — Temperatur,
  Feuchte, Volumenstrom, Leistung —, wie die farbigen Felder in der Excel.

### 6.2 Simulation starten

Ein Knopf oben. Davor werden Wetterdatensatz und Zeitraum gewählt, mit denselben
Schnellwahlen wie die Excel-Schaltflächen: ganzes Jahr, heißer Tag, kalter Tag,
feuchter Tag, eigener Zeitraum. Der Lauf zeigt Fortschritt und Restzeit und lässt sich
abbrechen.

### 6.3 Wetterdaten

1. **TRY-Datei hochladen** im Format des Blattes `Wetterdaten`: Kopf in Zeile 1–4,
   ab Zeile 5 je Stunde Datum als Excel-Zahl, Temperatur in °C, absolute Feuchte in
   g/kg, Strahlung S/O/W/N/H in W/m². `.xls`, `.xlsx` und CSV.
2. **Open-Meteo-Import** über Ort und Jahr.
3. **Aktuelles Jahr nachladen** für denselben Ort.

**Open-Meteo im Einzelnen.** Kostenlos, ohne Schlüssel, für nichtkommerzielle Nutzung.
Die Archiv-API (`archive-api.open-meteo.com/v1/archive`, ERA5) liefert Stundenwerte ab
1940. Abgerufen werden `temperature_2m`, `relative_humidity_2m`, `surface_pressure`
sowie `global_tilted_irradiance`. Die fünf Strahlungsspalten entstehen aus fünf
Abrufen mit `tilt`/`azimuth`: Süd (90°/0°), Ost (90°/−90°), West (90°/90°),
Nord (90°/180°) und horizontal (0°). Die absolute Feuchte wird aus relativer Feuchte,
Temperatur und Luftdruck berechnet — mit derselben Sättigungsdruckformel wie die
Excel, damit keine zweite Stoffdatenquelle entsteht.

### 6.4 Auswertung

- Jahresbilanz wie im Blatt `Ergebnis`: Menge mal Preis ergibt Kosten, je Zeile für
  Strom HT, Strom NT, Wärme, Kälte und Wasser.
- Verläufe als Diagramm: Außentemperatur, Raumtemperatur, Zulufttemperatur,
  Leistungen, Jahresdauerlinien.
- Vergleich mehrerer Läufe: Varianten derselben Anlage oder dieselbe Anlage über
  mehrere Wetterjahre, nebeneinander in Tabelle und Diagramm.
- Ausgabe als CSV und Excel.

### 6.5 Bericht

Zwei Ausgaben mit gleichem Inhalt und gleicher Gliederung:

- **HTML** — im Browser, druckbar, Diagramme als eingebettetes SVG.
- **PDF** — mit ReportLab erzeugt, im Stil des Berichts aus DIN-4108-2-Web
  (gleiche Farbpalette, gleiche Kopf- und Fußzeilen), Diagramme als Vektorgrafik über
  `reportlab.graphics`.

Beide Ausgaben speisen sich aus derselben Datenaufbereitung in `core/bericht.py`, damit
sie nicht auseinanderlaufen. Inhalt: Projekt- und Anlagenkopf, Anlagenschema als Bild,
Kartenliste mit Parametern, Wetterdatensatz, Jahresbilanz mit Kosten, Diagramme,
Konvergenzwarnungen.

---

## 7. Verzeichnisaufbau

```
rlt-simulation/
  app.py
  core/
    config.py
    database.py
    solver.py            Rückwärtslauf, Vorwärtslauf, Iteration, Speicher
    graph.py             Karten, Ports, Verdrahtung, topologische Sortierung
    bericht.py           gemeinsame Datenaufbereitung für HTML und PDF
    bericht_pdf.py       ReportLab
    bausteine/
      __init__.py        Registrierung
      basis.py           Param, Port, Luftzustand, Rollen
      wrg.py  mischkammer.py  erhitzer.py  kuehler.py  ...
    wetter/
      try_import.py
      open_meteo.py
    vorlagen/
      ax_sim_2_1.py      die Anlage aus der Excel, fertig verdrahtet
  routes/
    pages.py  anlagen.py  karten.py  simulation.py  wetter.py
    auswertung.py  bericht.py
  static/
    css/style.css
    js/editor.js  js/palette.js  js/diagramme.js
    symbole/*.svg
  templates/
  tests/
  requirements.txt
  README.md
```

Gestaltung nach dem Vorbild von kapa-planung: CSS-Variablen, helle Flächen, schmale
Ränder, Systemschriften, deutschsprachige Oberfläche.

---

## 8. Prüfung

**Bausteintests.** Je Kartentyp ein Test pro Formel, mit Sollwerten aus der Excel.
Diese Werte liegen bereits vor: die Mappe enthält einen durchgerechneten Zustand,
dessen Zwischenwerte in den Zellen stehen.

**Verdrahtungstests.** Automatische Zuordnung bei eindeutigen und mehrdeutigen Fällen,
Nachwachsen und Schrumpfen dynamischer Ports, Löschen eines Pfeils.

**Solvertests.** Konvergenz bei Zyklen, Volumenstromsummierung an Verzweigungen,
Zustandsübergabe zwischen Stunden.

**Vergleichstest gegen die Excel.** Die Vorlage „AX_SIM 2.1" wird mit den TRY-Daten aus
dem Blatt `Wetterdaten` über das volle Jahr gerechnet und gegen die Jahressummen aus
dem Blatt `Ergebnis` geprüft. Toleranz 0,5 Prozent je Bilanzgröße; zusätzlich ein
Stundenvergleich für einen kalten, einen heißen und einen feuchten Tag mit Toleranz
0,1 K beziehungsweise 0,1 g/kg. Dieser Test ist der Nachweis, dass der Nachbau
stimmt, und schützt künftige Änderungen.

---

## 9. Reihenfolge

**Erste Version** — Rechenkern und Editor gemeinsam:
Datenbank, Bausteinbibliothek mit allen 30 Karten, Solver, Editor mit Palette und
automatischer Verdrahtung, TRY-Upload, Simulationslauf, Jahresbilanz als Tabelle,
Vorlage „AX_SIM 2.1", Vergleichstest gegen die Excel.

**Danach** — Open-Meteo-Import, Jahres- und Variantenvergleich, Diagramme,
HTML- und PDF-Bericht, Ausgabe nach CSV und Excel.

Die Berichte stehen bewusst in der zweiten Stufe: sie setzen die Diagramme und den
Variantenvergleich voraus, die ihrerseits einen geprüften Rechenkern brauchen. Wird der
Bericht früher gebraucht, lässt er sich vorziehen, sobald der Vergleichstest gegen die
Excel besteht.

---

## Anhang A — Formeln je Baustein

Bezeichnungen: `V` Volumenstrom in m³/h, `T` Temperatur in °C, `x` absolute Feuchte in
g/kg, `dp` Druckverlust in Pa, `u` Stellgröße in Prozent, `h` Enthalpie in kJ/kg.

**Gemeinsame Stoffgleichungen**

```
p_S(T) = 611 · exp(−1,91275e−4 + 7,258e−2·T − 2,939e−4·T² + 9,841e−7·T³ − 1,92e−9·T⁴)
x_sätt(T) = 0,622 · p_S(T) / (100000 − p_S(T)) · 1000
h(T, x)   = 1,01·T + x/1000 · (2501 + 1,86·T)
rF(T, x)  = [x/1000 / (0,6222 + x/1000) · 100000] / p_S(T) · 100
```

**Wärmerückgewinnung** (`J151`–`J157`)

```
T_ZU = T_AU + η_t/100 · (T_AB − T_AU) · min(V_ZU,V_AB)/V_ZU · u/100 · (100−u_Byp)/100
x_ZU = x_AU + η_x/100 · (x_AB − x_AU) · min(V_ZU,V_AB)/V_ZU · u/100 · (100−u_Byp)/100
T_FO = T_AB − η_t/100 · (T_AB − T_AU) · min(V_ZU,V_AB)/V_AB · u/100 · (100−u_Byp)/100
x_FO = x_AB − η_x/100 · (x_AB − x_AU) · min(V_ZU,V_AB)/V_AB · u/100 · (100−u_Byp)/100
Q_WRG   = V_ZU/3600 · 1,2 · 1,007 · (T_ZU − T_AU)
dp_ZU   = (V_ZU/V_nenn)² · (dp_WRG·(100−u_Byp)/100 + dp_Byp·u_Byp/100)
```
Sind V_ZU oder V_AB null, bleiben Ein- und Austritt gleich.

**Mischkammer** (`M132`–`M134`)

```
r    = min(Umluftanteil, max. Umluftanteil)
T_MI = ((100−r)·T_AU + r·T_AB) / 100
x_MI = ((100−r)·x_AU + r·x_AB) / 100
```

**Erhitzer** (`M19`, `S131`, `S132`, `S135`)

```
QH    = u/100 · QH_max
T_aus = T_ein + 3600·QH / (1,2 · 1,007 · V)      für V > 0
x_aus = x_ein
dp    = dp_nenn · (V/V_nenn)²
```

**Kühler** (`AC117`–`AB135`)

```
T_O   = T_KW_mittel + 0,15 · (T_ein − T_KW_mittel)
T_aus = T_ein − u/100 · (T_ein − T_O)
x_aus = x_ein − u/100 · (x_ein − x_sätt(T_O))    falls x_sätt(T_O) < x_ein, sonst x_ein
QK    = V/3600 · 1,2 · (h(T_ein,x_ein) − h(T_aus,x_aus))
dp    = dp_nenn · (V/V_nenn)²
```
Warnung „Kühlleistung zu niedrig", wenn QK > QK_nenn.

**Dampfbefeuchter** (`Q120`–`P134`)

```
h_D    = 2676                                      bei Elektrodampf
h_D    = 2501,482 + 1,789736·T_D + 8,957546e−4·T_D² − 1,300254e−5·T_D³   bei Fremddampf
T_aus  = T_ein + u/100 · m_max · (h_D − 2256,9) / (V · 1,2 · 1,007)
x_aus  = min( x_sätt(T_ein), x_ein + 1000 · u/100 · m_max / (V · 1,2) )
Wasser = (100+Absalzverlust)/100 · u/100 · m_max    bei Elektrodampf, sonst u/100 · m_max
QH     = Wasser · (h_D − 42) / 3600
```
Warnung „Übersättigung", wenn x_aus die Sättigung erreicht.

**Luftwäscher** (`AF120`–`AE135`)

```
h_ein   = h(T_ein, x_ein)
x_sätt  =  0,0009·h_ein² + 0,1669·h_ein + 2,0433
t_sätt  = −0,0024·h_ein² + 0,5746·h_ein − 5,0241
T_aus   = T_ein − 0,9 · u/100 · (T_ein − t_sätt)
x_aus   = x_ein + 0,9 · u/100 · (x_sätt − x_ein)
Wasser  = V · 1,2 · (x_aus − x_ein)/1000 · (100+Absalzverlust)/100
PE_Pumpe= V_nenn · 1,2/3600 · 200/0,6/1000 · k     mit k = (u/100)² bei Ventil,
                                                   (u/100)^0,3 bei FU, 0,4·(u/100)² bei HD
dp      = dp_nenn · (V/V_nenn)²
```

**Ventilator** (`Z121`–`Y135`)

```
η       = V_max · dp_max / 3600000 / PE_max
η_teil  = η · (u/100)^0,8
V       = u/100 · V_max                       bei geregeltem Ventilator, sonst V_max
dp      = (dp_max − dp_konst) · (u/100)² + dp_konst
PE      = u/100 · V_max/3600000 · dp / η_teil                       bei Frequenzumrichter
PE      = 0,32·PE_max + 0,68 · (u/100 · V_max · dp)/3600000/η_teil  bei Drallregler
PE      = PE_max                                                    ungeregelt
T_aus   = T_ein + 3600·PE / (1,2 · 1,007 · V)
x_aus   = x_ein
```

**Einfacher Raum** (`AH45`–`AH50`)

```
T_frei = ( Σ(V_ZU,i · T_ZU,i)/3600·1,2·1,007 + Q_i + k·T_AU )
         / ( ΣV_ZU/3600·1,2·1,007 + k )                          falls ΣV_ZU ≥ ΣV_AB

T_frei = ( (ΣV_AB−ΣV_ZU)/3600·1,2·1,007·T_AU
           + Σ(V_ZU,i·T_ZU,i)/3600·1,2·1,007 + Q_i + k·T_AU )
         / ( (ΣV_AB−ΣV_ZU)/3600·1,2·1,007 + ΣV_ZU/3600·1,2·1,007 + k )   sonst

T_Raum  = max(T_frei, Sollwert der statischen Heizung)
x_Raum  = min( massenstromgewichtete Mischung + Feuchtelast·1000/(ΣV·1,2), 99,9 )
QH_stat = k·(Soll − T_AU) − Lüftungsbeiträge − Q_i      falls Soll > T_frei, sonst 0
```
`k` ist die spezifische Transmission in kW/K.

**Raum** (`AH112`–`AJ91`, `AK122`–`AK134`)

```
Grundfläche  = (a+c)/2 · (b+d)/2
Volumen      = Grundfläche · Höhe
sp.Trans AW  = Σ (Wandlänge·Höhe − Fensterfläche) · Anteil · U
sp.Trans FE  = Σ Fensterfläche · U
sp.Trans FB  = U_Boden · Grundfläche · Anteil
sp.Trans DA  = U_Dach · Dachfläche · Anteil
Luftwechsel  = 1,135 · (Außenwand + Dach + Fenster) / Volumen
sp. Verlust  = 0,34 · Luftwechsel · Volumen
Q_Solar      = Σ Fensterfläche · gewichtete Strahlung · g-Faktor · Verschattung / 1000
               gewichtet nach Ausrichtung: a = Ausrichtung/90, b = 1 − a
               über 22 °C Raumtemperatur nur 20 Prozent (Verschattung greift)
Q_Bel        = spez. Leistung · Grundfläche / 1000
C_Luft       = 1,005·1000/3600 · 1,2 · Volumen
A            = −( Innenwand·α + sp.Trans gesamt + sp. Verlust + V_ZU·1,005·1000/3600·1,2 )
B            = Q_Bel + Q_Solar + Innenwand·α·T_Wand + Transmissionsanteile
               + V_ZU·1,005·1000/3600·1,2·T_ZU + QH_stat
T_Raum_neu   = (T_Raum + B/A) · exp(A/C_Luft) − B/A
T_Wand_neu   = T_Wand + (Q_Wand_zu − Q_Wand_ab) / (Innenwand · Bauart / 3600)
x_Raum       = (V_ZU·x_ZU·1,2 + Feuchtelast·1000) / (V_ZU·1,2)
```
`T_Raum` und `T_Wand` sind Speichergrößen und werden über die Stunden fortgeschrieben.

**P-Regler** (`K51`–`J61`)

```
Stufe 1:  y1' = y1 − (Istwert1 − Sollwert1)/Xp1 ;  y1 = klemme(y1', 0, 100)
Stufe 2:  y2' = y2 − (Istwert2 − Sollwert2)/Xp2 ;  y2 = klemme(y2', 0, 100)
```
Der Rückgriff auf den eigenen Vorwert ist gewollt: über die Iterationen wirkt der
Regler integrierend, genau wie in der Excel.

**Sequenzregler** (`T138`–`S148`)

```
e     = 0                                falls unterer SW < Istwert < oberer SW
e     = e_vor + Δ                        sonst
Δ     = (Istwert − unterer SW)/10        falls Istwert < unterer SW
Δ     = (Istwert − oberer SW)/10         falls Istwert > oberer SW
e     = klemme(e, −300, 200)
wärmer3 = klemme(−(e+200), 0, 100)
wärmer2 = klemme(−(e+100), 0, 100)
wärmer1 = klemme(−e,       0, 100)
kälter1 = klemme( e,       0, 100)
kälter2 = klemme( e−100,   0, 100)
```

**Hysterese-Regler** (`V155`)

```
y = 100                       falls Istwert > Sollwert + Hysterese/2
y = 0                         falls Istwert < Sollwert − Hysterese/2
y = Vorzustand                dazwischen
```

**Raum-/Zuluft-Kaskade** (`P143`, `Q140`, `Q138`)

```
Sollwert = T_Raum_min                                             falls T_AU < T_AU_min
Sollwert = min( T_Raum_min + (T_AU − T_AU_min)·(T_Raum_max − T_Raum_min)
                            /(T_AU_max − T_AU_min), T_Raum_max )  sonst
Δ = (T_ZU − T_ZU_max)/3        falls T_ZU > T_ZU_max
Δ = (T_ZU − T_ZU_min)/3        falls T_ZU < T_ZU_min
Δ = (T_Raum − Sollwert)/3      sonst
e = klemme(e_vor + Δ, −300, 200)   →  fünf Sequenzausgänge wie beim Sequenzregler
```

**Zeitpläne** (`AN7`–`AP42`)

```
Wochenzeitplan  = 1, wenn Wochentag passt und von ≤ Tageszeit < bis
Ferien          = 1, wenn von ≤ Datum ≤ bis
Monatsprofil    = 1, wenn der Monat auf „ein" steht
Tageslastprofil = Lastgangwert der aktuellen Stunde
Betrieb         = Wochenzeitplan · (1 − Ferien)
Stellgrad       = Betrieb · Tageslastprofil · 100
Hochtarif       = 1, wenn Werktag und HT_von < Tageszeit < HT_bis
```

**Verbraucher** (`AE145`–`AE158`, `AK134`)

```
PE_Pumpen  = Betrieb_HZ · (P_allgemein + 0,5·P_WWB + 0,5·P_Kessel)
Speicherverlust = ((Speichervolumen/1000)^0,333)² · 5 · 8 · 20 / 1000
QH_WWB     = Jahresverbrauch·1000/8760 · 4,18 · (Sollwert − 10)/3600 + Speicherverlust
QH_ZIRK    = V_Zirk·1000/3600 · 4,18 · Spreizung · 0,75 · Betrieb_Zirk
PE_ZIRK    = P_Zirkpumpe · Betrieb_Zirk
Q_Bel      = spez. Leistung · Grundfläche / 1000
```

**Bilanz** (`C32`–`D31`)

```
Strom    = Σ aller elektrischen Leistungen (Ventilatoren, Pumpen, Beleuchtung)
Wärme    = Σ aller QH (Erhitzer, statische Heizung, Warmwasser, Zirkulation)
Kälte    = Σ aller QK
Wasser   = Σ aller Wasserverbräuche
Strom_HT = Strom, wenn Hochtarif, sonst 0
Strom_NT = Strom, wenn kein Hochtarif, sonst 0
```

---

## Anhang B — Herkunft der Angaben

Alle Formeln stammen aus `RLTSimulation_Vorlage_AX_SIM_2.1`, Blatt `Anlage`
(465 Formeln, ausgelesen am 2026-09-01), sowie aus den VBA-Modulen `Berechnungen`,
`Tabelle1` und `frm_Simulation`. Die Zellbezüge im Anhang verweisen auf dieses Blatt
und dienen als Nachweis beim Prüfen der Umsetzung.
