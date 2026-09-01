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

## Tests

```bash
pytest
```

## Referenz

Unter `referenz/` liegen die ursprüngliche Excel-Mappe, ihre ausgelesenen Formeln und
die VBA-Module. Sie sind die fachliche Grundlage und die Prüfgrundlage der Umsetzung.
