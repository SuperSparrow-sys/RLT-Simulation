"""Mitgelieferte Anlagenvorlagen."""

import re

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


#: Zeilen der Auslegung: vier Leerzeichen, ein Stichwort, dann der Wert.
_STICHWORT = re.compile(r"^ {4}(\S.*?) {2,}(.*)$")
#: Fortsetzungszeile derselben Angabe - weiter eingerueckt, ohne Stichwort.
_FORTSETZUNG = re.compile(r"^ {8,}(\S.*)$")


def _auslegung(modul):
    """Die Auslegung aus dem Kopfkommentar einer Anlagenvorlage.

    Jede Vorlage rechnet in ihrem Docstring vor, warum ihre Bauteile die
    Groesse haben, die sie haben - Heizlast aus Transmission und Lueftung,
    Kuehllast aus den inneren Lasten, Ventilatorleistung aus Luftmenge und
    Druck. Das ist das Wertvollste an diesen Vorlagen und stand bisher
    ausschliesslich im Quelltext; wer die Anwendung benutzte, sah davon
    nichts.

    Gelesen wird der Abschnitt ab der Zeile "AUSLEGUNG". Er ist in allen
    Vorlagen gleich gebaut: vier Leerzeichen, ein Stichwort, dann der Wert;
    weiter eingerueckte Zeilen setzen dieselbe Angabe fort. Zurueck kommt eine
    Liste aus {"stichwort", "zeilen"} - die Oberflaeche entscheidet, wie sie
    das zeigt.

    Findet sich kein solcher Abschnitt (AX_SIM 2.1 und die Testanlage sind
    keine Auslegung, sondern eine Nachbildung und ein Pruefstand), kommt eine
    leere Liste zurueck.
    """
    text = (modul.__doc__ or "").split("\n")
    for i, zeile in enumerate(text):
        if zeile.strip().startswith("AUSLEGUNG"):
            rest = text[i + 1:]
            break
    else:
        return []

    angaben = []
    for zeile in rest:
        if not zeile.strip():
            continue
        treffer = _STICHWORT.match(zeile)
        if treffer:
            angaben.append({
                "stichwort": treffer.group(1).strip(),
                "zeilen": [treffer.group(2).strip()],
            })
            continue
        weiter = _FORTSETZUNG.match(zeile)
        if weiter and angaben:
            angaben[-1]["zeilen"].append(weiter.group(1).strip())
    return angaben


def _einleitung(modul):
    """Der erklaerende Absatz zwischen der Titelzeile und der Auslegung."""
    text = (modul.__doc__ or "").split("\n")
    zeilen = []
    for zeile in text[1:]:
        if zeile.strip().startswith("AUSLEGUNG"):
            break
        zeilen.append(zeile.strip())
    return " ".join(z for z in zeilen if z)


def alle():
    """Alle Vorlagen mit dem, was der Anlagenkatalog von ihnen zeigt.

    'name' und 'beschreibung' sind die kurzen Angaben, die schon der Dialog
    zum Anlegen einer Anlage benutzt. Alles weitere ist fuer die Katalogseite:
    die Eckdaten, aus denen sich der Luftwechsel ergibt, die vorgerechnete
    Auslegung aus dem Kopfkommentar und die Erwartungsbaender, gegen die
    werkzeuge/anlagenpruefung.py die Anlage jaehrlich rechnet.
    """
    katalog = {}
    for kennung, modul in VORLAGEN.items():
        flaeche = getattr(modul, "FLAECHE_M2", None)
        luftmenge = getattr(modul, "LUFTMENGE_M3H", None)
        hoehe = getattr(modul, "HOEHE_M", None)
        katalog[kennung] = {
            "name": modul.NAME,
            "gruppe": getattr(modul, "GRUPPE", "Weitere"),
            "beschreibung": modul.BESCHREIBUNG,
            "einleitung": _einleitung(modul),
            "flaeche_m2": flaeche,
            "luftmenge_m3h": luftmenge,
            "hoehe_m": hoehe,
            "luftwechsel_1h": (
                luftmenge / (flaeche * hoehe)
                if flaeche and luftmenge and hoehe else None
            ),
            "auslegung": _auslegung(modul),
            "erwartung": {
                name: list(band)
                for name, band in getattr(modul, "ERWARTUNG", {}).items()
            },
        }
    return katalog


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
