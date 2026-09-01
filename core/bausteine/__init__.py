"""Bausteinbibliothek.

Beim Import werden alle Kartentypen geladen und registrieren sich selbst.
Ein neuer Kartentyp braucht nur eine neue Datei und eine Zeile in DIESE Liste.
"""

from core.bausteine import basis, stoffdaten  # noqa: F401

MODULE = ["erhitzer", "kuehler", "wrg", "mischkammer"]


def lade_alle():
    import importlib

    for name in MODULE:
        importlib.import_module(f"core.bausteine.{name}")
