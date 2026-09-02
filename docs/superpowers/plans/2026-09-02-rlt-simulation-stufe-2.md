# RLT-Simulation — Stufe 2

**Ziel:** Aus einem Werkzeug, das eine Anlage rechnet, wird eines, mit dem man
arbeitet: Ergebnisse weitergeben, Jahre vergleichen, Zahlen weiterverarbeiten —
und sich dabei ohne Umwege durch das Programm bewegen.

**Grundlage:** `docs/superpowers/specs/2026-09-01-rlt-simulation-design.md`,
Abschnitt 9 („Reihenfolge") und 6.4/6.5.

**Stand bei Planbeginn:** 34 Kartentypen, 41 Endpunkte, 417 Tests (plus 8 lange
Jahresläufe). Der Rechenkern ist gegen die Original-Mappe geprüft: Strom 1,8 %,
Kälte 0,9 % Abweichung. Der Dienst läuft als `rlt-simulation.service` auf Port
20006 und ist im Tailnet erreichbar.

---

## 1. Was aus dem Entwurf noch offen ist

Der Entwurf sah für die zweite Stufe fünf Vorhaben vor. Zwei sind vorgezogen
worden, weil sie früher gebraucht wurden:

| Vorhaben aus dem Entwurf | Stand |
|---|---|
| Open-Meteo-Import | **fertig** — vorgezogen, ERA5 ab 1940, Abruf in unter einer Sekunde |
| HTML- und PDF-Bericht | **im Bau** — vorgezogen, eigene Zeichenschicht ohne Fremdbibliothek |
| Diagramme | teilweise, entsteht mit dem Bericht |
| Jahres- und Variantenvergleich | **offen** → Vorhaben B |
| Ausgabe nach CSV und Excel | **offen** → Vorhaben C |

Der Entwurf begründet die Reihenfolge damit, dass die Berichte Diagramme und
Variantenvergleich voraussetzen und diese einen geprüften Rechenkern. Der
Rechenkern ist inzwischen geprüft, deshalb ließ sich der Bericht vorziehen; die
Diagramme entstehen dabei als Nebenprodukt und tragen den Vergleich mit.

Dazu kommen zwei Vorhaben aus der Benutzung, die der Entwurf nicht kannte:
die Wege durch das Programm (A) und der Zustand der Eingangsseite (D).

---

## 2. Die Vorhaben

### A — Wege durch das Programm

**Warum.** Heute führt aus einer geöffneten Anlage kein Weg zurück außer über
die Adresszeile. Und nach einem Simulationslauf steht die Jahresbilanz im
Dialog, aber der Bericht ist von dort nicht erreichbar.

**Was gebaut wird.**

1. **Ein Weg zurück zur Startseite** aus jeder Anlage. In der Kopfleiste, links
   neben dem Anlagennamen, sodass er an derselben Stelle sitzt wie im
   Erklärbereich (`← Start`).
2. **Ein Weg zum Bericht** aus der Anlage heraus, sobald ein Lauf vorliegt.
   Nicht nur aus dem Simulationsdialog, der sich schließen lässt, sondern
   dauerhaft in der Kopfleiste — abgeblendet, solange kein Lauf existiert.

**Ausdrücklich nicht:** eine Gliederung am linken Rand über Anlagen, Wetterdaten
und Läufe. Das war mein Vorschlag; der Benutzer hat ihn verworfen. Der linke
Rand gehört im Editor der Palette.

**Dateien.** `templates/editor.html`, `static/js/editor.js`,
`static/js/simulation.js`, `static/css/style.css`.

**Abnahme.** Aus einer Anlage sind Startseite und Bericht mit je einem Klick
erreichbar. Der Weg zum Bericht ist abgeblendet, solange kein Lauf vorliegt, und
wird ohne Neuladen benutzbar, sobald einer fertig wird. Auf dem iPad im
Hochformat bleiben beide erreichbar, ohne die Leinwand zu verdrängen.

---

### B — Vergleich mehrerer Wetterjahre

**Warum.** Der Benutzer will wissen, wie sich dieselbe Anlage in einem kalten
gegen ein mildes Jahr verhält. Der Open-Meteo-Abruf liefert die Jahre dafür
bereits; es fehlt die Gegenüberstellung.

**Beschränkung, bewusst.** Verglichen werden Läufe **derselben Anlage** über
**verschiedene Wetterdatensätze**. Nicht verschiedene Anlagen gegeneinander —
das bräuchte zuerst das Duplizieren einer Anlage und ist ein eigenes Vorhaben.

**Was gebaut wird.**

1. Eine Auswahl mehrerer Wetterdatensätze und ein Lauf je Datensatz,
   nacheinander im Hintergrund. Das vorhandene Muster in `core/laeufe.py`
   trägt das bereits, einschließlich Fortschritt und Abbruch.
2. Eine Gegenüberstellung: je Zeile eine Bilanzgröße, je Spalte ein Jahr, dazu
   die Abweichung gegenüber dem ersten Jahr.
3. Ein Diagramm über die Jahre, aus derselben Zeichenschicht wie der Bericht.
4. Der Vergleich geht in den Bericht ein, wenn er vorliegt.

**Zu bedenken.** Ein Jahreslauf dauert rund acht Minuten. Drei Jahre sind eine
halbe Stunde. Der Fortschritt muss über die ganze Reihe hinweg lesbar sein
(„Jahr 2 von 3"), ein Abbruch muss die restlichen Jahre verhindern, und ein
Neuladen der Seite darf die Reihe nicht verlieren — dafür gibt es seit Stufe 1
die Wiederaufnahme über die Datenbank.

**Dateien.** `core/vergleich.py` (neu), `core/laeufe.py`, `core/ergebnisse.py`,
`routes/simulation.py`, `static/js/simulation.js`, `core/zeichnung.py`,
`tests/`.

**Abnahme.** Drei Jahre lassen sich in einem Zug rechnen; die Tabelle zeigt
Bilanz und Abweichung; ein Neuladen mitten in der Reihe verliert nichts; ein
Abbruch stoppt auch die noch nicht begonnenen Jahre.

---

### C — Ausgabe der Stundenwerte

**Warum.** Der Benutzer will die 8760 Stundenwerte in Excel weiterverarbeiten
und eigene Auswertungen darauf aufbauen.

**Was gebaut wird.** Eine Ausgabe je Lauf mit einer Zeile je Stunde: Zeitpunkt,
Außentemperatur, Außenfeuchte, die Bilanzgrößen und **alle Spalten, die am
Datenlogger benannt sind** — dieselben, die das Stundenprotokoll zeigt.

**Zwei Formate.** CSV mit Semikolon und Komma als Dezimalzeichen, damit Excel
es ohne Importdialog öffnet. Und `.xlsx`, geschrieben mit `openpyxl`, das
bereits im Projekt ist.

**Zu bedenken.** 8760 Zeilen sind für CSV unkritisch. Für `.xlsx` gehört
geprüft, ob der Speicherverbrauch beim Schreiben vertretbar bleibt —
`openpyxl` kennt einen Schreibmodus für große Mappen. Die Ausgabe darf den
Dienst nicht blockieren.

**Dateien.** `core/ausgabe.py` (neu), `routes/simulation.py`,
`static/js/simulation.js`, `tests/`.

**Abnahme.** Beide Ausgaben enthalten alle gerechneten Stunden und alle
benannten Datenlogger-Spalten. Die CSV-Datei öffnet sich in einer deutschen
Excel-Einstellung ohne Nachfrage korrekt. Das Herunterladen funktioniert auf
dem iPad.

---

### D — Eingangsseite und Bedienbarkeit

**Warum.** Die Startseite ist funktional, aber sie ist als Liste gewachsen und
nicht entworfen. Der Benutzer hat sie ausdrücklich benannt.

**Was zu prüfen und zu ändern ist.**

1. **Der erste Aufruf.** Wer das Programm zum ersten Mal öffnet, sieht Projekte,
   Wetterdaten und einen Verweis auf die Bausteine — aber keinen Weg, der ihn
   führt. Was ist der erste sinnvolle Schritt, und sagt die Seite ihn?
2. **Die Gewichtung.** Projekte und Anlagen sind das Wichtigste, Wetterdaten
   eine Voraussetzung, der Erklärbereich ein Angebot. Die Seite gewichtet
   heute alles gleich.
3. **Der Zustand einer Anlage.** „Noch nicht simuliert" gegen „zuletzt
   gerechnet am …, Wärme 437 MWh" — der zweite Fall sagt etwas, der erste ist
   ein Platzhalter.
4. **Die Wetterdaten.** Zwei gleichwertige Kästen für Hochladen und Abrufen;
   der Abruf ist inzwischen der bequemere Weg und sollte das zeigen.
5. **Auf dem iPad.** Die Seite ist bisher nur am Schreibtisch entworfen worden.

**Vorgehen.** Zuerst ansehen — mit Bildschirmaufnahmen, in mehreren Breiten,
mit leerer und mit gefüllter Datenbank. Dann entwerfen. Nicht umgekehrt.

**Dateien.** `templates/index.html`, `static/js/start.js`,
`static/css/style.css`, `tests/`.

**Abnahme.** Der erste Aufruf führt zu einem ersten Schritt. Eine Anlage zeigt
ihren letzten Lauf. Kein Textüberlauf, keine zu kleinen Bedienelemente, in
Tablet- wie in Schreibtischbreite geprüft.

---

## 3. Reihenfolge

1. **A — Wege durch das Programm.** Klein, unabhängig, macht alles Weitere
   erreichbar. Zuerst.
2. **D — Eingangsseite.** Ebenfalls unabhängig; berührt andere Dateien als A,
   kann daneben laufen.
3. **C — Ausgabe der Stundenwerte.** Braucht nur, was schon da ist.
4. **B — Vergleich mehrerer Jahre.** Zuletzt, weil er Zeichenschicht und
   Bericht voraussetzt und die längste Rechenzeit zum Prüfen braucht.

Der Bericht (HTML und PDF) läuft parallel und ist Voraussetzung für die
Diagramme in B.

---

## 4. Was bewusst nicht dazugehört

- **Eine Gliederung am linken Rand** über Anlagen, Wetterdaten und Läufe. Vom
  Benutzer verworfen.
- **Vergleich verschiedener Anlagen.** Bräuchte zuerst das Duplizieren einer
  Anlage. Eigenes Vorhaben, wenn es gebraucht wird.
- **Anmeldung und Mehrbenutzerbetrieb.** Das Programm ist ein Werkzeug im
  eigenen Netz für einen Benutzer; so war es entworfen.
- **Ein Anlagenschema im Bericht als Bild.** Der Entwurf nennt es; es setzt
  eine Ausgabe der Leinwand als Vektorgrafik voraus. Zurückgestellt, bis der
  Bericht steht und sich zeigt, ob es fehlt.

---

## 5. Bekannte Grenzen aus Stufe 1

Diese Punkte sind geprüft, verstanden und dokumentiert. Sie sind **keine**
Aufgaben dieser Stufe, aber wer hier arbeitet, sollte sie kennen.

- **Wärme und Wasser weichen von der Original-Mappe ab** (+33 % und +529 %).
  Ursache ist ein echter Grenzzyklus: Die Zweipunktregler der Luftwäscher
  regeln auf die Raumfeuchte, die ihr eigener Wäscher um mehrere g/kg anhebt,
  bei einer Schaltdifferenz von 0,1 g/kg. Gemessen bleibt die Restabweichung
  bei 100 Iterationen wie bei 2000 unverändert bei 100,0. Der aufgezeichnete
  Excel-Lauf ist selbst keine fertig gerechnete Lösung — `Anlage!C38` ist als
  `=AH46` definiert und trägt einen anderen Wert. Strom und Kälte stimmen auf
  unter 2 %.
- **Die Oberfläche hat keine automatisierten Tests.** Es gibt keinen
  JavaScript-Testläufer im Projekt und einer wäre eine neue Abhängigkeit.
  Geprüft wird mit Playwright aus dem Scratchpad heraus, nicht aus dem Projekt.
- **Mehrere Eigenschaften auf dem iPad sind nur nachgebildet geprüft.**
  Chromium kennt die WebKit-Gestenereignisse nicht. Die Sperre gegen das
  Aufziehen der Seite, das Zoomen der Leinwand über die Geste und das
  Beschneiden der Zeichenfläche wurden am Gerät vom Benutzer bestätigt; alles
  Weitere dort bleibt Restrisiko.
- **Bestehende Anlagen bekommen neue Anschlüsse nicht.** Ports entstehen beim
  Anlegen einer Karte; nur dynamische wachsen nach. Wird eine Karte um einen
  festen Anschluss erweitert, brauchen ältere Anlagen eine Datenwanderung oder
  müssen neu angelegt werden.

---

## 6. Regeln, die weiter gelten

- Keine neuen Abhängigkeiten. Flask, pytest, xlrd, openpyxl — sonst nichts.
- Reines JavaScript ohne Bauschritt, Farben nur über die CSS-Variablen,
  deutsche Beschriftungen.
- `core/anlagen.py` ist der einzige Ort mit Datenbankzugriff für Anlagendaten,
  `core/ergebnisse.py` für Ergebnisse, `core/wetter/speicher.py` für
  Wetterdaten. Kein SQL in `routes/`.
- Jede Karte trägt ihr Wissen selbst — Darstellungsart, Auswahlbeschriftungen,
  Wertebereiche. Kein Sonderfall für einen Kartentyp in der Oberfläche.
- Jeder `fetch` prüft `response.ok` und meldet Fehlschläge sichtbar.
  Benutzereigene Namen werden vor `innerHTML` maskiert.
- Eingabefehler ergeben 400 mit deutscher Meldung, unbekannte Kennungen 404.
  Ein 500 heißt „das Programm hat einen Fehler".
- Was nur von Hand oder nachgebildet geprüft werden konnte, steht offen im
  Bericht. Eine Behauptung ist keine Prüfung.
