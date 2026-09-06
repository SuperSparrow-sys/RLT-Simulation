"""Zehn realistische Anlagen als Pruefstand und als Vorfuehrmaterial.

Jede Datei baut eine Anlage einer anderen Bauart und traegt ihre eigenen
Erwartungsbaender (ERWARTUNG). Die Baender sind aus der Auslegung der Anlage
selbst hergeleitet - installierte Leistung, Luftmenge, Flaeche, Betriebszeit -,
nicht aus dem Gedaechtnis zitiert; die Herleitung steht jeweils daneben.

werkzeuge/anlagenpruefung.py rechnet alle durch und haelt die Ergebnisse gegen
diese Baender.
"""

MODULE = [
    "buero", "schule", "schwimmhalle", "museum", "krankenhaus",
    "produktionshalle", "rechenzentrum", "hotel", "verkaufsraum", "turnhalle",
]


def alle():
    """Alle Anlagenmodule, in der Reihenfolge von MODULE."""
    import importlib

    return {
        name: importlib.import_module(f"core.vorlagen.anlagen.{name}")
        for name in MODULE
    }
