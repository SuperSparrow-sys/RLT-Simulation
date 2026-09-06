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

# Grenzen der Fixpunkt-Iteration. Beide Zahlen sind aus der Referenzmappe
# abgelesen, nicht gewaehlt: RLTSimulation_Vorlage_AX_SIM_2.1.xls speichert in
# jedem ihrer drei Blattstroeme uebereinstimmend ITERATION = 1, CALCCOUNT = 100
# und DELTA = 0,001 - in Excel die Felder "Iterative Berechnung", "Maximale
# Iterationszahl" und "Maximale Aenderung". tests/test_rechengrenzen.py liest
# sie dort erneut aus und schlaegt an, wenn hier etwas anderes steht.
# (Das aufgezeichnete Makro in referenz/vba-module.txt setzt Iteration auf
# False - ein Ueberbleibsel, nicht der Stand, mit dem die Mappe rechnet.)
#
# Die Iterationszahl ist dabei mehr als eine Abbruchbedingung. P- und
# Hysterese-Regler beziehen sich auf ihren eigenen Vorwert
# (ZUSTAND_UEBER_ITERATION) und wirken ueber die Durchgaenge integrierend - so
# rechnet die Mappe, und so ist es uebernommen. Damit gehoert die Zahl der
# Durchgaenge zum Modell: Gemessen an AX_SIM 2.1 ueber eine Januarwoche
# erreicht die Stellgroesse des Vorerhitzers nach 100 Durchgaengen erst rund
# 81 % und steigt weiter; erlaubt man 1000, sinkt die Waerme dieser Woche von
# 7964 auf 7889 kWh (-0,9 %) und die Kaelte von 86 auf 8 kWh. Wer hier
# hochsetzt, um "besser zu konvergieren", rechnet eine andere Anlage als die
# Mappe und muss den Abgleich neu bewerten.
#
# Wie viele Stunden den Anschlag erreicht haben, verschweigt der Lauf nicht: die
# Simulation zaehlt sie mit (Lauf.gemittelte_stunden) und weist sie im Bericht
# aus.
MAX_ITERATIONEN = 100
MAX_AENDERUNG = 0.001
