# RLT-Simulation

Stundenweise Jahressimulation raumlufttechnischer Anlagen als Flask-Webanwendung —
Nachfolger der Excel-Mappe `RLTSimulation_Vorlage_AX_SIM_2.1` (siehe `referenz/`).
Eine Anlage wird im Editor aus Karten (Bauteile, Regler, Räume, Zeitpläne, …)
zusammengesteckt und verdrahtet, danach über einem Wetterjahr durchgerechnet.

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Starten (Entwicklung)

```bash
python3 app.py
```

Danach im Browser `http://127.0.0.1:5055` öffnen. Beim ersten Start wird die
SQLite-Datenbank `rlt.db` angelegt. Host, Port und Debugmodus lassen sich über
Umgebungsvariablen anpassen:

| Variable      | Vorgabe     | Bedeutung                                |
|---------------|-------------|-------------------------------------------|
| `RLT_HOST`    | `127.0.0.1` | Bind-Adresse                               |
| `RLT_PORT`    | `5055`      | Port                                       |
| `RLT_DEBUG`   | `0`         | Flask-Debugmodus (`1`/`true`/`yes` = an)   |

Die Vorgaben sind bewusst sicher: nur lokal erreichbar, Debugkonsole aus. Die
Werkzeug-Debugkonsole erlaubt beliebige Codeausführung im Browser - wer sie
braucht, schaltet sie ausdrücklich ein (`RLT_DEBUG=1`) und öffnet `RLT_HOST`
nur so weit, wie es der eigene Rechner erfordert (z.B. `0.0.0.0`, wenn von
einem anderen Gerät im selben Netz zugegriffen werden soll) - nicht auf einem
Rechner, der auch von außerhalb des eigenen Arbeitsplatzes erreichbar ist
(Tailscale, Portweiterleitung, o.ä.).

## Dauerbetrieb

Auf dem Homeserver läuft die Anwendung als systemd-Dienst `rlt-simulation.service`
(Unit-Datei unter `/etc/systemd/system/rlt-simulation.service`) auf Port `20006`,
gebunden an `127.0.0.1` mit ausgeschaltetem Debugmodus.

```bash
sudo systemctl status rlt-simulation.service
sudo systemctl restart rlt-simulation.service   # nach jeder Python-Änderung nötig
journalctl -u rlt-simulation.service -f
```

Statische Dateien (`static/`, `templates/`) werden bei jeder Anfrage neu gelesen -
ein Neustart des Dienstes ist für sie nicht nötig, für Änderungen an Python-Code
schon.

## Tests

```bash
./venv/bin/python -m pytest -q -m "not slow"
```

Die Marke `slow` kennzeichnet Tests, die eine volle Jahressimulation (8760 Stunden)
rechnen und deshalb einige Minuten dauern - im normalen Durchlauf ausgeschlossen.
Für den vollständigen Lauf inklusive dieser Tests:

```bash
./venv/bin/python -m pytest -q
```

## Aufbau

- `core/bausteine/` - die Kartentypen. Jede Datei ist ein Kartentyp; er deklariert
  seine Parameter, Anschlüsse und seine Rechenformel vollständig selbst
  (`core/bausteine/basis.py`). Palette, Parameterfenster und Ergebnisspalten
  entstehen daraus, ohne Sonderfälle je Kartentyp.
- `core/anlagen.py` - Projekte, Anlagen, Karten, Pfeile: lesen, schreiben, prüfen.
- `core/solver.py` - rechnet eine Anlage stundenweise über ein Wetterjahr.
- `core/vorlagen/` - fertige Beispielanlagen (u.a. der Nachbau der Excel-Mappe).
- `core/wetter/` - Wetterdatensätze: Speicherung, Upload-Import, Open-Meteo-Abruf.
- `routes/` - die HTTP-Schnittstelle (Flask-Blueprints) über `core/`.
- `static/`, `templates/` - die Oberfläche: reines JavaScript/CSS, kein Rahmenwerk.
- `werkzeuge/` - Abgleich- und Prüfskripte gegen die Excel-Referenz, kein Teil der
  laufenden Anwendung.

## Erklärbereich (`/bausteine`)

Eine eigene Seite, erreichbar über den Link „Bausteine“ auf der Startseite. Sie
erklärt jeden Kartentyp (Zweck, Anschlüsse, Parameter, Besonderheiten) und lässt
sich zu jedem eine kleine, fertig verdrahtete Beispielanlage anlegen, die genau
diese eine Karte in ihrem natürlichen Zusammenhang zeigt - gedacht für jemanden,
der ohne Vorkenntnisse eine Anlage zusammenstellen will.

## Wetterdaten

Ein Simulationslauf braucht immer einen Wetterdatensatz, wählbar beim Start eines
Laufs. Auf der Startseite gibt es zwei Wege, einen zu bekommen:

- **Datei hochladen** - eine TRY-Datei (Testreferenzjahr) als `.xls`, `.xlsx` oder
  `.csv`, z.B. vom DWD oder einem anderen Anbieter besorgt.
- **Online abrufen** - ein volles Kalenderjahr für einen Ort (Auswahl oder eigene
  Koordinaten) direkt über die Open-Meteo-Archive-API, kostenlos und ohne
  Anmeldung.

Beide Wege landen in derselben Liste auf der Startseite.

## Referenz

Unter `referenz/` liegen die ursprüngliche Excel-Mappe, ihre ausgelesenen Formeln
und die VBA-Module. Sie sind die fachliche Grundlage und die Prüfgrundlage der
Umsetzung - `werkzeuge/abgleich.py` und `werkzeuge/referenz_export.py` vergleichen
Simulationsergebnisse gegen sie.
