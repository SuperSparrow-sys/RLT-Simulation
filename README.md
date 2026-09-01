# RLT-Simulation

Simulation raumlufttechnischer Anlagen als Flask-Webanwendung — Nachfolger der
Excel-Mappe `RLTSimulation_Vorlage_AX_SIM_2.1`.

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Starten

```bash
python3 app.py
```

Danach im Browser `http://127.0.0.1:5055` öffnen. Im lokalen Netz ist die Anwendung
über `http://<IP-Adresse>:5055` erreichbar. Beim ersten Start wird die
SQLite-Datenbank `rlt.db` angelegt.

Host, Port und Debugmodus lassen sich über Umgebungsvariablen anpassen:

| Variable      | Vorgabe   | Bedeutung                          |
|---------------|-----------|-------------------------------------|
| `RLT_HOST`    | `0.0.0.0` | Bind-Adresse                        |
| `RLT_PORT`    | `5055`    | Port                                 |
| `RLT_DEBUG`   | `1`       | Flask-Debugmodus (`1`/`true`/`yes` = an) |

## Dauerbetrieb

Auf dem Homeserver läuft die Anwendung als systemd-Dienst `rlt-simulation.service`
(Unit-Datei unter `/etc/systemd/system/rlt-simulation.service`) auf Port `20006`,
gebunden an `127.0.0.1` mit ausgeschaltetem Debugmodus. Erreichbar über
`https://homeserver.taila8377a.ts.net:20006`.

```bash
sudo systemctl status rlt-simulation.service
sudo systemctl restart rlt-simulation.service
journalctl -u rlt-simulation.service -f
```

## Tests

```bash
pytest
```

## Referenz

Unter `referenz/` liegen die ursprüngliche Excel-Mappe, ihre ausgelesenen Formeln und
die VBA-Module. Sie sind die fachliche Grundlage und die Prüfgrundlage der Umsetzung.
