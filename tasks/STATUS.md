# Status rlt-simulation

Stand 13.09.2026, erhoben aus Code und `~/projekte/tasks/INVENTUR.md`.

## Aktueller Stand

Letzter Commit `5dd37d6`, 09.09.2026, Branch `main`, Arbeitsbaum sauber.
35.402 Zeilen Python in 177 Dateien, 77 Testdateien mit `conftest.py` — nach
`automation-lohmener-str39` die zweitgrösste Testsuite im Haus. Kein Linter.
Factory `create_app()` (`app.py:80`), sieben Blueprints, `core/config.py` und
`core/database.py` wie im Hausstandard, WAL und `foreign_keys=ON`,
`retry_on_lock` (`core/database.py:193`).
Läuft als `rlt-simulation.service` auf `127.0.0.1:20006`.

## Offene Punkte

1. Hartkodierter `SECRET_KEY`-Fallback in `core/config.py:21`, git-getrackt.
2. Logging ist eingerichtet (`app.py:30-37`, `RotatingFileHandler`), im
   Anwendungscode stehen aber 14 `print` gegen drei Logger-Aufrufe
   (`routes/wetter.py:66,169`, `core/database.py:315`).
3. Ausgeliefert wird über den Flask-Entwicklungsserver (`app.py:108`), nicht
   über `waitress`.
4. Keine Authentifizierung. Für ein reines Rechenwerkzeug im Tailnet vertretbar,
   sobald Ergebnisse gespeichert und geteilt werden aber zu prüfen.
5. Die Palette dieses Projekts (`static/css/grundlage.css`) ist eine von drei
   eigenständigen Kopien derselben Material-Farben. Sie ist zur Hausfarbe
   erhoben worden; eine gemeinsame Token-Datei entsteht in einer späteren Phase.

## Nächster Schritt

Punkt 1, ein Einzeiler ohne Abhängigkeiten. Danach Punkt 2, weil die
Logging-Infrastruktur bereits steht und nur benutzt werden muss.
