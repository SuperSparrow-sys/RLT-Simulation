# Entscheidungen rlt-simulation

ADR-light: was, wann, warum, verworfene Alternative. Neueste oben.

## 2026-09-13 — Farbpalette dieses Projekts wird Hausakzent

Was: `#1a73e8` mit der zugehörigen Material-Palette (`--surface #ffffff`,
`--text #3c4043`, `--border #dadce0`, Gefahr `#d93025`) ist Hausstandard; sie
liegt hier, in `kapa-planung` und in `watermarks-web` dreifach identisch vor.
Warum: eine vorhandene, in sich stimmige Palette komplett zu übernehmen ist
belastbarer, als die je häufigsten Einzelfarben zu einer Palette zu mischen, die
es nirgends gibt.
Verworfen: `#2563eb` aus `kompetenzboegen_eva`. Es ist als Statusfarbe häufiger,
aber nur in einem Projekt Akzent und bringt keine vollständige Palette mit.

## 2026-09-13 — Kein Linter nachgerüstet

Was: Ruff wurde hier nicht eingeführt, obwohl das Projekt gross ist.
Warum: der Setup-Auftrag verbietet Eingriffe in die Projekte, und eine
Ruff-Erstprüfung auf 35.000 Zeilen erzeugt eine Trefferliste, die niemand
beauftragt hat.
Verworfen: `pyproject.toml` mit Ruff anzulegen und die Treffer als offenen Punkt
zu führen.
