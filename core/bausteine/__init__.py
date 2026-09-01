"""Bausteinbibliothek.

Beim Import werden alle Kartentypen geladen und registrieren sich selbst.
Ein neuer Kartentyp braucht nur eine neue Datei und eine Zeile in DIESE Liste.
"""

from core.bausteine import basis, stoffdaten  # noqa: F401

MODULE = [
    "erhitzer", "kuehler", "wrg", "mischkammer",
    "dampfbefeuchter", "luftwaescher", "ventilator",
    "verteiler", "sammler", "aussenluft", "fortluft", "wetterkarte",
    "einfacher_raum", "statische_heizung", "raum",
    "p_regler", "sequenzregler", "hysterese_regler", "kaskade",
    "wochenzeitplan", "ferien", "monatsprofil", "tageslastprofil", "anlagenbetrieb",
    "heizungspumpen", "warmwasser", "zirkulation", "beleuchtung", "enthalpierechner", "bilanz", "datenlogger",
]


def lade_alle():
    import importlib

    for name in MODULE:
        importlib.import_module(f"core.bausteine.{name}")
