"""Der Erklärbereich: eine Erklärung je Kartentyp, mit ladbarer Beispielanlage.

Eigenes Blueprint statt Erweiterung von routes/anlagen.py oder routes/pages.py:
dort arbeiten parallel andere Änderungen, und dieser Bereich hat mit
Simulationsläufen oder dem Editor selbst nichts zu tun - nur mit dem Erklären
und dem Anlegen einer Anlage aus einer festen Vorlage.
"""

import re

from flask import Blueprint, jsonify, render_template

from core.bausteine import basis
from core.lehrinhalte import beispielanlagen
from core.lehrinhalte.erklaerungen import ERKLAERUNGEN

bp = Blueprint("lehre", __name__)


@bp.route("/bausteine")
def seite():
    """Die Erklärseite - fertig gefüllt, nicht als Gerüst.

    Sie holte ihre Kartentypen bis zum Umbau der Oberfläche erst nach dem
    Laden über /api/lehre/bausteine und baute die Kacheln im Browser. Bis die
    Antwort da war, stand auf der Seite "Bausteine werden geladen …" - und in
    keinem Abzug der Seite war ihr eigentlicher Inhalt zu sehen. Dieselbe
    Umstellung wie bei Startseite (routes/pages.py) und Anlagenkatalog
    (routes/katalog.py).
    """
    eintraege = _eintraege()
    nach_gruppe = {}
    for eintrag in eintraege:
        nach_gruppe.setdefault(eintrag["gruppe"], []).append(eintrag)
    gruppen = [(name, _anker(name), liste) for name, liste in nach_gruppe.items()]
    return render_template(
        "bausteine.html",
        gruppen=gruppen,
        anzahl=len(eintraege),
        art_label=ART_LABEL,
        richtung_label=RICHTUNG_LABEL,
    )


# Die Beschriftungen, in denen die Seite von einem Anschluss spricht. Sie
# standen in static/js/bausteine.js, solange die Kacheln dort entstanden.
ART_LABEL = {"luft": "Luft", "signal": "Signal"}
RICHTUNG_LABEL = {"ein": "Eingang", "aus": "Ausgang"}


def _anker(gruppe):
    """Sprungziel eines Gruppenabschnitts - alles, was kein Buchstabe und
    keine Ziffer ist, wird zu einem Bindestrich."""
    return "gruppe-" + re.sub(r"[^a-z0-9]+", "-", gruppe.lower())


@bp.get("/api/lehre/bausteine")
def bausteine_liste():
    """Dieselbe Liste als JSON.

    Die Seite selbst braucht sie nicht mehr (siehe seite()); die Schnittstelle
    bleibt, weil sie den Kartenbestand maschinenlesbar beschreibt und die
    Tests ihn darüber prüfen.
    """
    return jsonify(_eintraege())


def _eintraege():
    """Alle Kartentypen mit Erklärtext und den lebenden Angaben ihrer Klasse
    (Parameter, Anschlüsse, Gruppe, Symbol) - so kann der Text nie von dem
    abweichen, was die Karte tatsächlich anbietet."""
    eintraege = []
    for klasse in basis.alle():
        text = ERKLAERUNGEN.get(klasse.KENNUNG)
        if text is None:
            continue  # eine neue Karte ohne Erklärung fehlt lieber sichtbar, als falsch zu wirken
        eintraege.append(
            {
                "kennung": klasse.KENNUNG,
                "name": klasse.NAME,
                "gruppe": klasse.GRUPPE,
                "symbol": klasse.SYMBOL,
                "beschreibung": text["beschreibung"],
                "hinweis": text.get("hinweis", ""),
                "parameter": [
                    {
                        "schluessel": p.schluessel, "label": p.label,
                        "einheit": p.einheit, "auswahl": list(p.auswahl),
                        "hinweis": p.hinweis,
                    }
                    for p in klasse.PARAMETER
                ],
                # Dieselbe Beschriftung wie im Parameterfenster des Editors
                # (core.anlagen._port_label) - beide fragen die Karte selbst.
                "ports": [
                    {
                        "schluessel": p.schluessel, "art": p.art,
                        "richtung": p.richtung, "rolle": p.rolle,
                        "label": basis.port_label(klasse, p.schluessel, p.rolle),
                    }
                    for p in klasse.PORTS
                ],
                "beispiel_verfuegbar": klasse.KENNUNG in beispielanlagen.BAUPLAENE,
            }
        )
    eintraege.sort(key=lambda e: (e["gruppe"], e["name"]))
    return eintraege


@bp.post("/api/lehre/bausteine/<kennung>/anlage")
def beispielanlage_anlegen(kennung):
    try:
        projekt_id = beispielanlagen.projekt_bausteine()
        anlage_id = beispielanlagen.baue_beispiel(kennung, projekt_id)
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404
    return jsonify({"id": anlage_id}), 201
