"""Zentrale Einstellungen der RLT-Simulation."""

import os
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent

DB_PATH = WURZEL / "rlt.db"
LOG_FILE = WURZEL / "rlt.log"
LOG_LEVEL = os.environ.get("RLT_LOG_LEVEL", "INFO")

PORT = int(os.environ.get("RLT_PORT", "5055"))
SECRET_KEY = os.environ.get("RLT_SECRET_KEY", "rlt-simulation-lokal")

SQLITE_RETRY_MAX = 5
SQLITE_RETRY_BACKOFF = 0.05

# Grenzen der Fixpunkt-Iteration, entsprechend Application.Iteration in der Excel
MAX_ITERATIONEN = 100
MAX_AENDERUNG = 0.001
