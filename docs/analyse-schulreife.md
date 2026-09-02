# Von der Nachbildung zum Lehrmittel

Analyse vom 2026-09-02. Sie beantwortet eine Frage: Was fehlt der
RLT-Simulation noch, damit sie an einer Schule benutzt werden kann — von
jemandem, der eine Lüftung noch nie ausgelegt hat, ohne dass daneben jemand
steht, der das Programm kennt?

Grundlage sind zwei Durchgänge: jeder Rechenschritt aller 34 Kartentypen
wurde einzeln gegen die Physik geprüft, und alle 34 Beispielanlagen wurden
über je eine Januar- und eine Juliwoche durchgerechnet und auf Endlichkeit,
Sättigung und Wertebereiche untersucht (`werkzeuge/beispielpruefung.py`).

Die Analyse trennt drei Dinge, die leicht durcheinandergeraten:

* **Fehler** — die Rechnung sagt etwas anderes, als die Physik hergibt.
* **Eigenschaften der Vorlage** — die Excel-Mappe rechnet so, und der
  Nachbau tut es ihr getreu nach. Das ist kein Fehler, muss aber
  dastehen, sonst hält es jemand für Physik.
* **Lücken im Lehrmittel** — die Rechnung stimmt, aber niemand kann sie
  nachvollziehen oder einen eigenen Fehler daran erkennen.

---

## 1. Gefundene Fehler (behoben)

### 1.1 Die Mischkammer verletzte die Mengenbilanz

Sie gab die Summe dessen aus, was an ihren beiden Eingängen angeboten wurde
(`V = V_AU + V_UM`), statt der Menge, die der Ventilator dahinter fordert.
Gemessen in `core/vorlagen/testanlage.py`: **7000 m³/h, wo 5000 gefordert
waren**. Erhitzer, Kühler und Befeuchter davor rechneten also mit vierzig
Prozent zu viel Luft; der Ventilator setzte die Menge danach still auf seine
eigene zurück, sodass der Fehler nirgends auffiel.

Zweitens mischte sie nach der Klappenstellung statt nach den tatsächlich
gezogenen Massen. Bei geschlossener Klappe trug die Umluft ihre 500 m³/h zum
Volumen bei, aber nichts zur Temperatur.

Behoben: Die Kammer gibt die geforderte Menge ab, zieht davon den
Umluftanteil von der Abluftseite — soweit diese ihn anbietet — und den Rest
von außen. Ausgewiesen wird der *wirksame* Anteil, nicht der geforderte.

*Warum das für eine Schule zählt:* Umluftbetrieb ist eines der ersten
Themen. Die Frage „wie viel Energie spart Umluft?" war mit dem alten Stand
nicht beantwortbar.

### 1.2 Der Verteiler ließ Luft verschwinden, die Umluft kam nie an

Zwei Folgefehler derselben Art, beide erst durch 1.1 sichtbar geworden:

* Der Verteiler gab **nur** an die Gänge ab, die etwas anforderten. Die
  Fortluft ist eine Senke und fordert nie — von 5000 m³/h Abluft gingen also
  3000 in die Umluft und 2000 lösten sich auf. Jetzt bekommt jeder fordernde
  Gang seinen Bedarf, und der Rest geht an die Gänge ohne Forderung.
* Der Rückwärtslauf ging **einmal** über die Karten. Bei einer Umluftschleife
  bricht die topologische Reihenfolge den Kreis, und der Verteiler wurde vor
  der Mischkammer bearbeitet — er kannte deren Forderung nicht und teilte
  nach seinem festen Schlüssel auf (40 statt der geforderten 60 % Umluft).
  Der Rückwärtslauf geht jetzt dreimal; er ist eine reine Summenrechnung ohne
  Physik, das kostet fast nichts.

### 1.3 Das Ergebnis hing an der Zahl der Rechendurchgänge

Ein Zweipunktregler, dessen Stellglied die geregelte Größe um mehr verändert
als seine Schaltdifferenz breit ist, pendelt in der Fixpunkt-Iteration
zwischen zwei Zuständen. Der Solver lief in so einem Fall bis zum Anschlag
und gab den **zuletzt** gerechneten Stand aus — also „die ganze Stunde an"
oder „die ganze Stunde aus", je nachdem ob `MAX_ITERATIONEN` gerade oder
ungerade ist.

Behoben: Der Zweitakt wird erkannt, ausgewiesen wird das Mittel beider
Zustände. Das ist die einzige Aussage, die eine Stundenrechnung über einen
schneller taktenden Regler machen kann, und sie hängt an der Anlage statt an
einer Einstellung. Solche Stunden stehen jetzt getrennt von den
Konvergenzwarnungen (`Lauf.takte`), weil es kein Rechenfehler ist.

Wirkung auf die Beispielanlagen: Der Hysterese-Regler konvergiert in allen
336 geprüften Stunden statt in 315.

### 1.4 Die Raumfeuchte rechnete bei stehender Luft in falschen Einheiten

Ohne Zuluft stand dort `F_AU + M·1000/Volumen` — das mischt g/h je m³ mit
g/kg und setzte den Raum außerdem auf die *Außen*feuchte zurück, als hätte
er über Nacht seinen Zustand vergessen.

Behoben: Die Feuchte folgt derselben geschlossenen Form wie die Temperatur,
mit der Raumluft als Speicher. Der Beharrungswert bleibt der der Excel;
nachgerechnet über das Referenzjahr ändern sich die Jahreszahlen um keine
Stelle.

### 1.5 Der Ventilator rechnete außerhalb seines Gültigkeitsbereichs

Der Druck fällt nur zum Teil mit dem Quadrat der Drehzahl (ein konstanter
Anteil bleibt stehen), während der Teillastwirkungsgrad mit u^0,8 fällt.
Zusammengesetzt ergibt das `P ~ u^0,2` — ein Ventilator bei 5 % Drehzahl
bräuchte danach noch **42 % seiner Nennleistung** und heizte die Luft um
11 K auf. Das ist keine Physik mehr, sondern eine Formel jenseits ihres
Gültigkeitsbereichs.

Behoben: Unterhalb von 30 % Drehzahl gilt der Wirkungsgrad, den die Formel
dort noch hergibt; die Leistung fällt darunter weiter linear mit der
Drehzahl. Anlagen im üblichen Regelbereich sind nicht betroffen — in der
Excel-Vorlage steht die Stellgröße fest auf 100 %.

### 1.6 Ein Regler lief gegen einen gesättigten Stellantrieb

In der Testanlage forderte der Frostschutzregler bis zu 29,5 kW, während die
statische Heizung still auf 8 kW begrenzte. Ein Regler, der seinen Sollwert
nie erreichen kann, läuft Durchgang um Durchgang weiter — das ist
Integrator-Windup und war die Ursache vieler nicht konvergierter Stunden.
Die Heizung ist jetzt auf 35 kW ausgelegt, passend zum Wärmebedarf der
500 m² großen Halle.

---

## 2. Eigenschaften der Vorlage (bleiben, sind benannt)

Diese Punkte sind **keine Fehler**. Sie stammen aus der Excel-Mappe, und der
Nachbau übernimmt sie, weil sein Zweck der Vergleich mit ihr ist. Sie
gehören aber in eine Analyse, damit niemand sie für allgemeingültige Physik
hält.

| Was | Wo | Wirkung |
|---|---|---|
| Gesamtdruck 100 000 Pa statt 101 325 Pa | `stoffdaten.x_saett` | Sättigungsfeuchte rund 1,2 % zu hoch |
| 0,622 gegen 0,6222 im selben Zusammenhang | `x_saett` / `rel_feuchte` | Rückrechnung trifft 99,96 % statt 100 % |
| cp der Luft dreifach: 1,007 / 1,01 / 1,005 kJ/(kg·K) | Erhitzer, Enthalpie, Raum | Unterschied unter 0,5 % |
| Bauteile **vor** dem Ventilator auf Nennstrom ausgelegt | `solver`, Außenluftkarte | Luftmenge springt am Ventilator |
| Wandspeicher teilt durch 3600 statt 1000 | `raum` | Wand gleicht sich rund 3,6-mal so schnell an |
| Druckverlust der Abluftseite anders geklammert | `wrg` | nur die Abluftseite betroffen |
| Zusätzlicher Faktor 1,2 in der Pumpenleistung | `luftwaescher` | Pumpenstrom rund 20 % höher als nach der üblichen Formel |
| Anlagenbetrieb steuert in AX_SIM 2.1 nichts | `vorlagen/ax_sim_2_1` | die Kette rechnet, wirkt aber auf nichts |

Der Kern der Vorlage — die exponentielle Lösung der Raumbilanz, die
Energiebilanz der Wärmerückgewinnung, die Enthalpiebilanz des Kühlers — ist
dagegen physikalisch geschlossen. Nachgerechnet: Die WRG gibt auf der
Abluftseite exakt die Leistung ab, die sie der Zuluft zuführt, auch bei
ungleichen Volumenströmen.

---

## 3. Was noch fehlte, damit es ein Lehrmittel ist

### 3.1 Ein vergessener Pfeil war unsichtbar

Die Bilanzkarte summiert, was **an ihr hängt**. Ein Erhitzer ohne Pfeil zur
Bilanz fehlt lautlos in der Jahressumme — die Zahl sieht richtig aus, ist
aber zu klein. Wer die Anlage nicht selbst gebaut hat, merkt das nie.

Gelöst: `core/pruefung.py` sucht solche stillen Fehler und beschreibt jeden
in einem Satz, der sagt, was zu tun ist. Der Simulationsdialog zeigt die
Befunde, **bevor** gerechnet wird. Es sind Hinweise, kein Riegel — eine
Anlage darf unvollständig sein, solange man weiß, dass sie es ist.

Geprüft wird: Verbraucher ohne Verbindung zur Bilanz, offener Luftweg,
Regler ohne Stellgröße, fehlende Wetterkarte. Reserveanschlüsse dynamischer
Karten sind ausgenommen — sonst stünde an jeder vollständig verdrahteten
Anlage eine Meldung, und niemand läse die Liste noch.

Am Bestand ausprobiert: Die Testanlage meldet nichts, AX_SIM 2.1 meldet
genau eine Sache, und die ist wahr (Punkt 2, letzte Zeile).

### 3.2 Der P-Regler hieß, was er nicht tut

Er verschiebt seine Stellgröße je Rechendurchgang um Abweichung ÷ Xp und
trifft damit am Ende einer Stunde **genau** den Sollwert. Eine bleibende
Regelabweichung, wie sie ein P-Regler im Lehrbuch hinterlässt, bleibt hier
nicht übrig — Xp bestimmt, wie schnell er ankommt, nicht wie weit er daneben
liegt. Wer im Unterricht „P-Regler ⇒ bleibende Regelabweichung" gelernt hat
und das hier nachprüfen will, findet es nicht.

Gelöst: Der Name bleibt (er stammt aus der Mappe, und mit ihr steht und
fällt der Vergleich), aber die Erklärung sagt es jetzt in zwei Sätzen dazu.

### 3.3 Eine Zahl im Code, an der man drehen möchte

Die Oberflächentemperatur des Kühlers wurde mit `T_KW + 0,15·(T_ein − T_KW)`
gerechnet — die 0,15 stand unbenannt im Quelltext. Sie ist keine
Naturkonstante, sondern beschreibt, wie gut ein bestimmter Kühler seine Luft
an das Kaltwasser heranführt: genau die Größe, an der eine Übung dreht
(„warum entfeuchtet mein Kühler nicht?").

Gelöst: Parameter `kontaktfaktor` mit demselben Vorgabewert; die Rechnung
bleibt unverändert.

### 3.4 Die Wärmerückgewinnung nannte nur die halbe Wahrheit

Ihre Ausgabe hieß „rückgewonnene Leistung", enthielt aber nur den sensiblen
Anteil. Bei einer Rückfeuchtzahl über null geht zusätzlich Latentwärme über,
die in der Zahl nicht steckt. Jetzt heißt die Ausgabe, was sie ist.

---

## 4. Was bewusst offen bleibt

**Der Befeuchtungskreis der Vorlage schwingt.** Die Zweipunktregler der
Luftwäscher regeln auf die Raumfeuchte, die ihr eigener Wäscher um mehrere
g/kg anhebt, gegen eine Schaltdifferenz von 0,1 g/kg. Das ist ein echter
Grenzzyklus; er löst sich durch keine Iterationszahl auf. Seit Punkt 1.2
wird dafür das Stundenmittel ausgewiesen statt eines ausgewürfelten
Zustands — die Zahl ist damit reproduzierbar, aber die Abweichung zur Excel
bleibt, weil die Excel ihrerseits an einer beliebigen Stelle abbricht. Für
den Unterricht ist gerade das ein gutes Beispiel: Eine Zweipunktregelung an
einer Größe, die das Stellglied sofort selbst verändert, ist eine
Fehlplanung, und man sieht sie hier.

**Die Excel ist in sich uneinheitlich.** Sie wurde mitten in einer Iteration
gespeichert; `C38` und `AH46` müssten gleich sein und sind es nicht. Ein
1:1-Abgleich kann deshalb nicht besser werden als die Vorlage selbst. Strom
(1,8 %) und Kälte (0,9 %) stimmen überein; Wärme und Wasser hängen am
schwingenden Kreis und werden getrennt als eigener Stand geführt.

**Nicht jede Stunde schwingt in 100 Durchgängen vollständig ein.** In der
Testanlage bleibt in einem Teil der Stunden eine Restabweichung stehen, die
mit mehr Durchgängen weiter schrumpft (gemessen an den Beispielanlagen:
0,47 bei 100, 0,28 bei 500, 0,09 bei 2000 Durchgängen). Das ist kein
Grenzzyklus, sondern eine langsame Annäherung — Ursache ist eine
Kreisverstärkung nahe eins. Alle physikalischen Prüfungen dieser Anlage
bestehen; die Restabweichung wird je Stunde ausgewiesen, statt verschwiegen
zu werden.

**`einfacher_raum` rechnet stationär.** Das ist sein Zweck — er ist die
einfache Alternative zum Raum mit Bauphysik. Er trägt den Namen zu Recht.

---

## 5. Prüfmittel, die es jetzt gibt

| Werkzeug | Was es prüft | Ergebnis heute |
|---|---|---|
| `werkzeuge/abgleich.py` | AX_SIM 2.1 gegen die Excel, ganzes Jahr | Strom 1,3 %, Kälte 0,9 %, **Wärme 8,5 % (vorher 32,8 %)** |
| `werkzeuge/plausibilitaet.py` | Testanlage über ein Jahr, 14 Prüfungen | alle physikalischen bestanden |
| `werkzeuge/beispielpruefung.py` | alle 34 Beispielanlagen, Januar- und Juliwoche | 34 Anlagen, 0 Befunde |
| `core/pruefung.py` | jede Anlage vor dem Lauf auf stille Verdrahtungsfehler | im Dialog sichtbar |
| Testreihe | 706 Tests, davon 3 mit vollem Jahreslauf | grün |

---

## 6. Wie eine Unterrichtsstunde damit abläuft

Die Analyse wäre unvollständig ohne die Probe aufs Exempel. Der Weg eines
Menschen, der das Programm zum ersten Mal öffnet:

1. **Startseite** — „Erster Einstieg" nennt drei Schritte in der Reihenfolge,
   die zum Ergebnis führt: Wetterdaten holen, Projekt und Anlage anlegen,
   rechnen lassen. Erledigte Schritte tragen einen Haken.
2. **Wetterdaten** — Ort wählen, Jahr ankreuzen, fertig; gemessen unter zwei
   Sekunden je Jahr über die Open-Meteo-Archive-Schnittstelle. Mehrere Jahre
   lassen sich später gegeneinander rechnen.
3. **Bausteine** (`/bausteine`) — jede der 34 Karten mit Beschreibung, ihren
   Anschlüssen und Parametern, dazu vier Handgriffe: Karten verbinden, einen
   Regler auf seinen Sollwert stellen, den Datenlogger einbauen, an
   Wetterdaten kommen. Zu jeder Karte lässt sich eine kleine, fertig
   verdrahtete Beispielanlage anlegen, die genau diesen einen Baustein in
   seinem Zusammenhang zeigt.
4. **Editor** — Anlage aus einer Vorlage oder leer; ein Pfeil zwischen zwei
   Karten verdrahtet die passenden Anschlüsse selbst. Rückgängig und
   Wiederholen stellen jeden Zustand exakt wieder her, auch nach dem
   Löschen einer Karte.
5. **Simulation** — vor dem Start die Hinweise zur Anlage, dann der Lauf mit
   Fortschritt; ein Jahr in rund zwölf Minuten.
6. **Bericht** — Jahresbilanz mit Kosten, Monatswerte, Jahresdauerlinie,
   Stundenverlauf und drei Viermonatsausschnitte mit wählbaren Spalten, als
   Seite und als PDF. Stundenwerte als CSV oder Excel zum Weiterrechnen.

Alle sechs Schritte wurden mit Bildschirmaufnahmen in drei Breiten
(1500, 1024, 390 Punkte) nachgeprüft: kein überlaufender Text, kein
Querscrollen, keine Skriptfehler.
