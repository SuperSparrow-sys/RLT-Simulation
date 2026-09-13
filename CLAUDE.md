# rlt-simulation

Stundenweise Jahressimulation raumlufttechnischer Anlagen: Anlage im Editor aus
Bauteilen, Reglern, Räumen und Zeitplänen zusammenstecken und durchrechnen.

@tasks/STATUS.md

- Klasse: eigenes Werkzeug, freie Hand. Keine Verbindung zu realer Hardware.
- Dienst `rlt-simulation.service` auf `127.0.0.1:20006`, nicht neu starten.
  Das Portregister im Vault führt 20006 falsch als `sportfest`.
- Layout entspricht dem Hausstandard; Referenz für Rechenergebnisse ist die
  Excel-Mappe unter `referenz/`.
