# Zehn realistische Anlagen und ihre Pruefung

Stand: 2026-09-06

## Ziel

Das Programm soll vertriebstauglich werden. Vier Bedingungen, vom Benutzer
genannt:

1. Jede Anlage rechnet ein volles Jahr fehlerfrei durch - kein Abbruch, kein
   taktender Regler, keine Konvergenzfehler, keine physikalisch unmoegliche
   Zahl.
2. Die Zahlen halten dem Urteil eines Fachmanns stand.
3. Der Zusammenbau ist narrensicher: Karten lassen sich nicht unbemerkt falsch
   verdrahten.
4. Die Anlagen bleiben als auswaehlbare Vorlagen im Programm.

Bisher gibt es zwei Vorlagen (AX_SIM 2.1 als Nachbau der Excel, Testanlage
Technikhalle als Pruefmassstab) und 34 Ein-Karten-Beispielanlagen. Zwei Anlagen
sind zu wenig, um zu wissen, ob die Rechenkette traegt: beide sind an derselben
Hand entstanden und teilen deshalb dieselben blinden Flecken.

## Die zehn Anlagen

Jede fordert Karten und Regelaufgaben, die die anderen nicht fordern.

| Anlage | Flaeche | Luftmenge | Fordert besonders |
|--------|---------|-----------|-------------------|
| Buerogebaeude, VAV | 2000 m2 | 8 000 m3/h | WRG-Plattentauscher, Kaskade, Wochenzeitplan |
| Schule | 1500 m2 | 12 000 m3/h | Hoher Luftwechsel, Ferien, Monatsprofil |
| Schwimmhalle | 500 m2 | 15 000 m3/h | Sehr hohe Feuchtelast, Entfeuchtung ueber den Kuehler, viel Umluft |
| Museum/Archiv | 800 m2 | 4 000 m3/h | Enges Feuchteband in beide Richtungen, 24/7 |
| Krankenhaus/OP | 300 m2 | 6 000 m3/h | 100 % Aussenluft ohne Umluft, 20-facher Luftwechsel |
| Produktionshalle | 3000 m2 | 20 000 m3/h | Luftwaescher (adiabate Kuehlung), Verteiler/Sammler auf zwei Zonen |
| Rechenzentrum | 400 m2 | 10 000 m3/h | Nur Kuehlung, hohe sensible Last, freie Kuehlung ueber die Mischkammer |
| Hotel | 4000 m2 | 6 000 m3/h | Warmwasser, Zirkulation, Heizungspumpen |
| Verkaufsraum | 1200 m2 | 7 000 m3/h | Hohe Beleuchtungslast, lange Oeffnungszeiten |
| Turnhalle | 900 m2 | 9 000 m3/h | Stossweise Belegung ueber das Tageslastprofil |

Zusammen decken sie alle 34 Kartentypen ab. Die meisten Funde sind bei
Schwimmhalle und Museum zu erwarten: Feuchteregelung in beide Richtungen ist
der Fall, in dem sich eine Rechenkette am ehesten verheddert.

## Aufbau

```
core/vorlagen/bauhilfe.py      die drei Schliessungen karte/pfeil/verbinde, einmal
core/vorlagen/anlagen/         je eine Datei je Anlage
werkzeuge/anlagenpruefung.py   rechnet alle durch und schreibt einen Bericht
tests/test_anlagen_vorlagen.py schnelle Probe ueber repraesentative Wochen
```

`karte`, `pfeil` und `verbinde` stehen heute als Schliessungen in jeder Vorlage.
Bei zwoelf Vorlagen waeren das zwoelf Kopien derselben sechs Zeilen; sie ziehen
in `core/vorlagen/bauhilfe.py`. Die beiden vorhandenen Vorlagen folgen nach.

Aus `werkzeuge/plausibilitaet.py` wird der anlagenunabhaengige Teil
herausgeloest: `rechne_jahr(app, vorlage)` neben dem heutigen
`rechne_testjahr(app)`. Die 14 vorhandenen Pruefungen finden ihre Karten
ohnehin ueber den Typ und liefern leere Reihen, wenn eine Karte fehlt - sie
gelten damit fuer jede Anlage. Zwei getrennte Massstaebe wuerden auseinander
laufen.

## Erwartungsbaender

Jede Anlagendatei traegt ihre Kennzahlenbaender samt Herleitung:

```python
ERWARTUNG = {
    "heizwaerme_kwh_m2a": (15, 60),
    "luftwechsel_1h": (1.0, 2.0),
}
```

Hergeleitet aus der Auslegung der Anlage selbst - installierte Leistung,
Luftmenge, Flaeche, Betriebszeit -, nicht aus dem Gedaechtnis zitiert. Wo eine
Zahl unsicher ist, steht das ausdruecklich in der Datei, statt dass eine
Schwelle erfunden wird. Eine erfundene Schwelle ist schlimmer als keine: sie
sieht nach Pruefung aus und ist keine.

Dazu Verhaeltnispruefungen, die ohne Absolutwerte gelten und deshalb auch dann
tragen, wenn ein Band daneben liegt:

- Die Schwimmhalle entfeuchtet mehr als das Buero.
- Dieselbe Anlage ohne WRG braucht mehr Waerme als mit.
- Ferien und Wochenenden senken den Verbrauch.
- Das Rechenzentrum heizt im Sommer nicht.

## Zusammenbau

`core/graph.py._paare()` entscheidet bei mehreren gleichrangigen Anschluessen
nach der Reihenfolge, in der die Ports angelegt wurden - nicht danach, welcher
Anschluss fachlich gemeint ist. Das steht so im Docstring von
`core/vorlagen/testanlage.py` und war dort schon einmal die Ursache einer
falschen Verdrahtung. Zehn Anlagen sind der Pruefstand, der zeigt, wie oft es
zuschlaegt.

Der Pruefstand meldet je Anlage:

- Pflichteingaenge ohne Quelle
- Eingaenge mit mehr als einer Quelle
- Karten ohne jede Verbindung
- automatisch gezogene Verbindungen, die einen anderen Anschluss treffen als
  den, der fachlich gemeint ist

## Laufzeit

Zehn Jahreslaeufe sind rund 80 Minuten und je etwa 450 MB. Als Teil der
normalen Testreihe unbrauchbar. Darum dieselbe Teilung wie bei
`werkzeuge/plausibilitaet.py`: ein Werkzeug fuer den vollen Durchlauf auf
Zuruf, und in der Testreihe eine schnelle Probe ueber repraesentative Wochen
(je eine Winter-, Uebergangs- und Sommerwoche), die dieselben Pruefungen
anlegt.

## Reihenfolge

1. `bauhilfe.py`, die beiden vorhandenen Vorlagen darauf umstellen
2. Buero und Schwimmhalle bauen, Pruefstand daran entwickeln
3. Die uebrigen acht bauen
4. Alles durchrechnen, jeden Fund beheben
5. Die zehn in `core/vorlagen/__init__.py` eintragen

## Nachpruefung von Hand

Ausdrueckliche Vorgabe des Benutzers: Am Ende werden die Ergebnisse selbst
nachgeprueft, nicht nur das Urteil des Pruefwerkzeugs uebernommen. Pruefwerkzeug
und geprueftes Programm stammen aus derselben Hand und teilen dieselben
Denkfehler; eine Pruefung auf einer leeren Reihe besteht immer.

Nachgeprueft wird gegen etwas, das nicht aus dem eigenen Code stammt:

- Handrechnung der Luftmengenbilanz und der Heizleistung bei Auslegungs-
  temperatur
- Erhaltungsgroessen: Summe der Stundenwerte gegen die Jahresbilanz, Luftmengen
  an Verteiler und Sammler
- Vergleich zweier Anlagen, deren Unterschied sich vorhersagen laesst
- Blick auf Jahresgaenge und Vorzeichen, nicht nur auf Bestanden/Nicht bestanden

Der Bericht sagt am Ende ausdruecklich, was von Hand nachgerechnet wurde und
was allein das Programm gemeldet hat.

## Nicht Teil dieser Arbeit

- Neue Kartentypen
- Aenderungen an AX_SIM 2.1 (Nachbau der Excel, Massstab des Abgleichs)
- Auslegungsrechnung nach Norm
