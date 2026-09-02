# Rückgängig und Wiederholen

**Ziel:** Zwei Knöpfe im Editor, die jede Änderung an einer Anlage zurücknehmen
und wieder herstellen — Karte gelöscht, Verbindung getrennt, Parameter geändert,
Karte verschoben. Der vorherige Zustand muss **exakt** wieder da sein, nicht
ungefähr. Der Verlauf liegt in der Datenbank und überlebt das Schließen des
Browsers.

---

## 1. Die Entscheidung, die alles andere bestimmt

Es gibt zwei Wege, so etwas zu bauen.

**Der eine:** Zu jedem Vorgang die Umkehrung merken. „Karte gelöscht" merkt sich
die Karte und legt sie beim Zurücknehmen wieder an. Das ist sparsam, aber jede
Umkehrung muss einzeln richtig sein — und das Löschen einer Karte zieht ihre
Anschlüsse, ihre Pfeile und deren Verbindungen mit. Jeder neue Kartentyp, jede
neue Beziehung ist eine neue Gelegenheit, eine Umkehrung zu vergessen. Der
Fehler fällt dann nicht beim Bauen auf, sondern Wochen später beim Benutzer.

**Der andere:** Nach jeder Änderung den ganzen Zustand der Anlage festhalten.
Zurücknehmen heißt, einen früheren Zustand wieder einzuspielen. Das ist stumpf,
aber es kann nicht unvollständig sein — was nicht im Zustand steht, gehört auch
nicht dazu.

**Gemessen, bevor entschieden:** Der vollständige Zustand von Anlage 75
(42 Karten, 61 Pfeile, 369 Anschlüsse, 135 Verbindungen) ist als JSON
**69,6 KiB**, komprimiert **7,3 KiB**. Fünfzig Schritte kosten damit rund
370 KiB je Anlage.

**Also: vollständige Momentaufnahmen, komprimiert abgelegt.** Der Sparweg löst
ein Problem, das wir nicht haben, und erkauft es mit einer Fehlerquelle, die
uns bleibt.

---

## 2. Was ein Zustand ist

Der Zustand einer Anlage besteht aus den Zeilen dieser fünf Tabellen, soweit sie
zu dieser Anlage gehören:

| Tabelle | was darin steht |
|---|---|
| `anlage` | Name, Notiz |
| `karte` | Typ, Name, Position, Parameter |
| `port` | Anschlüsse je Karte, samt Nummer bei mitwachsenden |
| `pfeil` | Verbindungen zwischen Karten, Stützpunkte, Mehrdeutigkeit |
| `verbindung` | die einzelnen Anschlusspaare je Pfeil |

**Nicht dazu gehören:** Simulationsläufe, ihre Zeitreihen und Bilanzen,
Wetterdaten, das Projekt. Ein Rückgängig darf ein Rechenergebnis nicht
vernichten.

---

## 3. Der Punkt, an dem so etwas üblicherweise scheitert

**Die Kennungen müssen erhalten bleiben.** Nicht „eine Karte gleichen Typs an
gleicher Stelle", sondern dieselbe Karte mit derselben `id`.

Der Grund steht in `core/ergebnisse.py`: Die gespeicherten Zeitreihen eines
Simulationslaufs verweisen über `karte_id` auf die Karten. Bekäme eine
wiederhergestellte Karte eine neue Kennung, wären die Ergebnisse aller früheren
Läufe stumm — sie zeigten auf etwas, das es nicht mehr gibt. Dasselbe gilt für
`port` (Verbindungen verweisen darauf) und `pfeil`.

SQLite lässt das Einfügen mit ausdrücklicher Kennung zu, und der Zähler von
`AUTOINCREMENT` merkt sich seinen Höchststand — neu angelegte Karten bekommen
also auch nach einer Wiederherstellung keine schon vergebene Kennung.

**Zu prüfen beim Bauen:** Nach dem Zurücknehmen einer Löschung muss ein
Simulationslauf, der vor der Löschung entstand, seine Werte weiterhin der
richtigen Karte zuordnen. Das ist der Test, der diesen Entwurf trägt oder
widerlegt.

---

## 4. Ablage

Eine Tabelle je Anlage, mit einer Reihenfolge und einem Zeiger auf die
Gegenwart:

```
zustand
  id           INTEGER PRIMARY KEY
  anlage_id    INTEGER  -> anlage(id) ON DELETE CASCADE
  nummer       INTEGER  laufend je Anlage, 1, 2, 3, ...
  beschreibung TEXT     "Karte 'Erhitzer Halle' gelöscht"
  zeitpunkt    TEXT
  daten        BLOB     gzip(JSON)
```

Die Gegenwart ist eine Zahl je Anlage — welcher Zustand gerade gilt. Sie gehört
in die Tabelle `anlage` oder in eine kleine eigene; entscheide beim Bauen, was
weniger Sonderfälle erzeugt.

- **Zurück:** Zeiger um eins verkleinern, diesen Zustand einspielen.
- **Vor:** Zeiger um eins vergrößern, diesen Zustand einspielen.
- **Neue Änderung, während der Zeiger nicht am Ende steht:** Alles nach dem
  Zeiger wird gelöscht, die Änderung hängt sich an. Das ist das übliche
  Verhalten und das einzige, das niemanden überrascht.
- **Grenze:** Fünfzig Schritte je Anlage. Der älteste fällt weg. Der **erste**
  Zustand einer Anlage bleibt immer erhalten, damit man an den Anfang zurück
  kann.

`ON DELETE CASCADE` sorgt dafür, dass der Verlauf mit der Anlage verschwindet.

---

## 5. Wann festgehalten wird

Nach **jeder** Änderung am Zustand: Karte anlegen, ändern, löschen; Pfeil
anlegen, löschen; Verbindung setzen, lösen; Anlage umbenennen.

Alle diese Wege laufen bereits durch `core/anlagen.py` — das ist der einzige
Ort mit Datenbankzugriff für Anlagendaten. Das Festhalten gehört genau dorthin
und **nicht** in die Routen; sonst wird es beim nächsten neuen Endpunkt
vergessen.

**Zwei Fälle brauchen Sorgfalt:**

**Verschieben.** Eine Karte über die Leinwand zu ziehen erzeugt heute ein
`PATCH` je Loslassen — das ist in Ordnung. Aber ein Zustand je Verschiebung
füllt den Verlauf mit Belanglosem. Überleg, ob Verschiebungen einen eigenen
Schritt verdienen oder mit der nächsten inhaltlichen Änderung
zusammengefasst werden.

**Tippen in ein Parameterfeld.** Das Parameterfenster speichert beim Verlassen
eines Feldes, nicht bei jedem Zeichen — das ist schon der richtige Zuschnitt.
Prüf trotzdem, ob mehrere schnell aufeinanderfolgende Änderungen **desselben
Feldes** zu einem Schritt zusammengefasst gehören.

Der Maßstab: Ein Schritt ist, was der Benutzer als **eine** Handlung erlebt.

---

## 6. Einspielen

Ein Zustand wird in **einer** Transaktion eingespielt, sonst hinterlässt ein
Fehler in der Mitte eine halbe Anlage:

1. Verbindungen, Pfeile, Anschlüsse und Karten dieser Anlage löschen — in
   dieser Reihenfolge, von innen nach außen.
2. Karten, Anschlüsse, Pfeile, Verbindungen aus dem Zustand einfügen, mit
   ihren ursprünglichen Kennungen — in dieser Reihenfolge, von außen nach innen.
3. Den Namen der Anlage setzen.

Danach `PRAGMA foreign_key_check`. Bleibt etwas übrig, ist der Entwurf falsch
und nicht der Einzelfall.

**Das Einspielen erzeugt selbst keinen neuen Zustand** — sonst wüchse der
Verlauf bei jedem Zurücknehmen.

---

## 7. Was gleichzeitig passieren kann

**Ein laufender Simulationslauf.** Der Rechen-Thread lädt seinen Graphen einmal
beim Start und arbeitet damit weiter; ein Zurücknehmen währenddessen ändert
seine Rechnung nicht mehr. Aber am Ende schreibt er Ergebnisse, die auf
`karte_id` verweisen. Weil die Kennungen erhalten bleiben (Abschnitt 3),
passt das zusammen.

**Zu entscheiden:** Soll Rückgängig während eines Laufs trotzdem gesperrt sein?
Ich neige zu nein — es sperrt etwas, das nicht schadet, und acht Minuten sind
lang. Aber prüf den Fall, in dem der Lauf eine Karte bilanziert, die inzwischen
zurückgenommen wurde.

**Zwei Browserfenster auf derselben Anlage.** Das Programm ist für einen
Benutzer gedacht, aber zwei Fenster sind schnell offen. Nach einem Zurücknehmen
zeigt das andere Fenster einen überholten Stand. Entscheide, ob das
hinzunehmen ist — und wenn ja, sag es im Bericht, statt es zu übersehen.

---

## 8. Bedienung

Zwei Knöpfe in der Kopfleiste des Editors, links bei „← Start". Abgeblendet,
wenn es nichts zurückzunehmen beziehungsweise nichts zu wiederholen gibt.

Jeder Knopf nennt, was er tut — „Rückgängig: Karte 'Erhitzer Halle' gelöscht".
Am Schreibtisch als Kurzhinweis, auf dem iPad muss die Beschriftung ohne
Schweben erkennbar sein; das Programm hat dafür bereits Muster.

Tastatur: Strg+Z und Strg+Umschalt+Z, auf dem Mac ⌘Z. **Nicht**, wenn der Fokus
in einem Eingabefeld steht — dort gehört das Zurücknehmen dem Feld. Genau
dieser Fehler ist in diesem Projekt schon einmal aufgetreten: Die Entf-Taste
löschte die gewählte Karte, während der Benutzer in einem Textfeld tippte.

Nach dem Einspielen baut der Editor die Anlage neu auf. Ansicht und Zoomstufe
bleiben, wo sie sind — wer etwas zurücknimmt, will sehen, was sich ändert, und
nicht die Ansicht suchen.

---

## 9. Reihenfolge beim Bauen

1. **Tabelle und Zustandsverwaltung** in `core/`: festhalten, einspielen,
   Zeiger, Grenze. Ohne Oberfläche, mit Tests.
2. **Anbindung in `core/anlagen.py`**, an jedem ändernden Weg.
3. **Endpunkte** für zurück, vor und den Stand des Verlaufs.
4. **Bedienung** im Editor.
5. **Zusammenfassen** der Schritte (Abschnitt 5), zuletzt — es setzt voraus,
   dass alles andere steht.

---

## 10. Woran sich das messen lassen muss

Diese Prüfungen entscheiden, ob es taugt. Sie gehören in die Testreihe:

1. Karte löschen, zurücknehmen: Die Karte ist wieder da — **mit derselben
   Kennung**, mit denselben Anschlüssen, und alle Pfeile, die an ihr hingen,
   samt ihrer Verbindungen.
2. Verbindung trennen, zurücknehmen: Sie zeigt wieder auf dieselben Anschlüsse.
3. Parameter ändern, zurücknehmen, wiederholen: Der Wert wandert richtig hin
   und zurück, auch bei Listen und Tabellen.
4. Zehn Änderungen, zehnmal zurück: Der Zustand ist **byteweise** derselbe wie
   am Anfang. Das ist die schärfste Prüfung; sie fängt alles, was oben
   vergessen wurde.
5. Nach einem Zurücknehmen eine neue Änderung: Der Vorwärtsverlauf ist weg,
   die neue Änderung hängt richtig.
6. Simulationslauf, dann Karte löschen, dann zurücknehmen: Die Ergebnisse des
   Laufs zeigen weiterhin auf die richtige Karte.
7. Über die Grenze hinaus arbeiten: Der Verlauf wächst nicht unbegrenzt, der
   erste Zustand bleibt erreichbar.
8. Nach jedem Einspielen: `PRAGMA foreign_key_check` bleibt leer.

---

## 11. Was ausdrücklich nicht dazugehört

- **Rückgängig über Anlagen hinweg.** Der Verlauf gehört zu einer Anlage.
- **Das Löschen einer ganzen Anlage oder eines Projekts zurücknehmen.** Dort
  fragt das Programm bereits nach und nennt, was verloren geht.
- **Simulationsläufe zurücknehmen.** Ein Lauf ist ein Ergebnis, keine Änderung.
- **Mehrere Benutzer.** Das Programm ist ein Werkzeug im eigenen Netz für einen
  Benutzer; so war es entworfen.
