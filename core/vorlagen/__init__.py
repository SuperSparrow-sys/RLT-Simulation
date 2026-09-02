"""Mitgelieferte Anlagenvorlagen."""

from core.vorlagen import ax_sim_2_1, testanlage

VORLAGEN = {"ax_sim_2_1": ax_sim_2_1, "testanlage": testanlage}


def alle():
    return {
        kennung: {"name": modul.NAME, "beschreibung": modul.BESCHREIBUNG}
        for kennung, modul in VORLAGEN.items()
    }


def baue(kennung, projekt_id, name):
    if kennung not in VORLAGEN:
        raise KeyError(f"Die Vorlage '{kennung}' gibt es nicht")
    return VORLAGEN[kennung].baue(projekt_id, name)
