"""Der Erklärbereich: eine Erklärung je Kartentyp, mit ladbarer Beispielanlage.

Eigenes Blueprint statt Erweiterung von routes/anlagen.py oder routes/pages.py:
dort arbeiten parallel andere Änderungen, und dieser Bereich hat mit
Simulationsläufen oder dem Editor selbst nichts zu tun - nur mit dem Erklären
und dem Anlegen einer Anlage aus einer festen Vorlage.
"""

from flask import Blueprint, jsonify, render_template

from core.bausteine import basis
from core.lehrinhalte import beispielanlagen
from core.lehrinhalte.erklaerungen import ERKLAERUNGEN

bp = Blueprint("lehre", __name__)


@bp.route("/bausteine")
def seite():
    return render_template("bausteine.html")


@bp.get("/api/lehre/bausteine")
def bausteine_liste():
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
                    }
                    for p in klasse.PARAMETER
                ],
                "ports": [
                    {
                        "schluessel": p.schluessel, "art": p.art,
                        "richtung": p.richtung, "rolle": p.rolle,
                    }
                    for p in klasse.PORTS
                ],
                "beispiel_verfuegbar": klasse.KENNUNG in beispielanlagen.BAUPLAENE,
            }
        )
    eintraege.sort(key=lambda e: (e["gruppe"], e["name"]))
    return jsonify(eintraege)


@bp.post("/api/lehre/bausteine/<kennung>/anlage")
def beispielanlage_anlegen(kennung):
    try:
        projekt_id = beispielanlagen.projekt_bausteine()
        anlage_id = beispielanlagen.baue_beispiel(kennung, projekt_id)
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404
    return jsonify({"id": anlage_id}), 201
