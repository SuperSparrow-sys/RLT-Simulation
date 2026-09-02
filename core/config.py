"""Zentrale Einstellungen der RLT-Simulation."""

import os
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent

DB_PATH = WURZEL / "rlt.db"
LOG_FILE = WURZEL / "rlt.log"
LOG_LEVEL = os.environ.get("RLT_LOG_LEVEL", "INFO")

# Sicher als Voreinstellung: nur lokal erreichbar, Debugkonsole (Werkzeug,
# also Codeausfuehrung ueber den Browser) aus. Wer den Entwicklungsmodus mit
# offener Debugkonsole will, schaltet ihn ausdruecklich ein (RLT_DEBUG=1) -
# und dann am besten auch RLT_HOST nur so weit wie noetig oeffnen, nicht
# gleich auf 0.0.0.0. Die systemd-Unit (siehe rlt-simulation.service) setzt
# beides ohnehin explizit, diese Vorgaben greifen nur bei "python3 app.py".
HOST = os.environ.get("RLT_HOST", "127.0.0.1")
PORT = int(os.environ.get("RLT_PORT", "5055"))
DEBUG = os.environ.get("RLT_DEBUG", "0").lower() in ("1", "true", "yes")
SECRET_KEY = os.environ.get("RLT_SECRET_KEY", "rlt-simulation-lokal")

SQLITE_RETRY_MAX = 5
SQLITE_RETRY_BACKOFF = 0.05

# Grenzen der Fixpunkt-Iteration, entsprechend Application.Iteration in der Excel
MAX_ITERATIONEN = 100
MAX_AENDERUNG = 0.001
