"""Mitgelieferte Anlagenvorlagen."""

from core import verlauf
from core.vorlagen import anlagen as _anlagen
from core.vorlagen import ax_sim_2_1, testanlage

# Die beiden grossen Vorlagen zuerst - AX_SIM 2.1 als Nachbau der Excel, die
# Testanlage als Massstab der Plausibilitaetspruefung -, danach die zehn
# Bauarten aus core/vorlagen/anlagen/. Sie decken zusammen alle Kartentypen ab
# und dienen sowohl der Pruefung (werkzeuge/anlagenpruefung.py) als auch dem
# Vorfuehren: Zu jeder gaengigen Aufgabe laesst sich eine passende Anlage
# oeffnen und rechnen.
VORLAGEN = {"ax_sim_2_1": ax_sim_2_1, "testanlage": testanlage}
VORLAGEN.update(_anlagen.alle())


def alle():
    return {
        kennung: {"name": modul.NAME, "beschreibung": modul.BESCHREIBUNG}
        for kennung, modul in VORLAGEN.items()
    }


def baue(kennung, projekt_id, name):
    """Baut eine Anlage aus einer Vorlage.

    Ohne Verlauf (verlauf.stumm): der Aufbau ist ueber hundert einzelne
    Schreibvorgaenge, aber EINE Handlung der Anwenderin. Der fertige
    Zustand wird zum Ausgangszustand, sobald sie das erste Mal selbst etwas
    aendert - siehe core/verlauf.py, stumm()."""
    if kennung not in VORLAGEN:
        raise KeyError(f"Die Vorlage '{kennung}' gibt es nicht")
    with verlauf.stumm():
        return VORLAGEN[kennung].baue(projekt_id, name)
