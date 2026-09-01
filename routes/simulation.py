from flask import Blueprint, current_app, jsonify, request

from core import ergebnisse, laeufe

bp = Blueprint("simulation", __name__, url_prefix="/api/simulation")


@bp.post("")
def starten():
    daten = request.get_json(force=True)
    kennung = laeufe.starte(
        current_app._get_current_object(),
        daten["anlage_id"],
        daten["wetterdatensatz_id"],
        int(daten.get("von", 0)),
        int(daten.get("bis", 8760)),
    )
    return jsonify({"kennung": kennung}), 202


@bp.get("/<kennung>")
def stand(kennung):
    return jsonify(laeufe.stand(kennung))


@bp.post("/<kennung>/abbrechen")
def abbrechen(kennung):
    laeufe.abbrechen(kennung)
    return jsonify({"ok": True})


@bp.get("/<int:simulation_id>/bilanz")
def bilanz(simulation_id):
    return jsonify(
        {
            "bilanz": ergebnisse.lade_bilanz(simulation_id),
            "reihen": ergebnisse.reihen(simulation_id),
        }
    )
