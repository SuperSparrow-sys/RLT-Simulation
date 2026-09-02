from flask import Blueprint, current_app, jsonify, request

from core import ergebnisse, laeufe

bp = Blueprint("simulation", __name__, url_prefix="/api/simulation")

# Die Bereiche der Excel-Schaltflaechen (Anlage!Tabelle1). Dort zaehlen die
# Datenzeilen ab 5, hier ab 0 - daher jeweils 5 abgezogen: 820/843, 5860/5883,
# 5380/5403, 5/8765.
SCHNELLWAHL = {
    "jahr": (0, 8760),
    "kalter_tag": (815, 839),
    "heisser_tag": (5855, 5879),
    "feuchter_tag": (5375, 5399),
}


@bp.get("/schnellwahl")
def schnellwahl():
    return jsonify(
        {name: {"von": von, "bis": bis} for name, (von, bis) in SCHNELLWAHL.items()}
    )


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


@bp.delete("/<int:simulation_id>")
def loeschen(simulation_id):
    try:
        ergebnisse.simulation_loeschen(simulation_id)
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404
    except ValueError as fehler:
        return jsonify({"fehler": str(fehler)}), 400
    return jsonify({"ok": True})


@bp.get("/<int:simulation_id>/bilanz")
def bilanz(simulation_id):
    return jsonify(
        {
            "bilanz": ergebnisse.lade_bilanz(simulation_id),
            "reihen": ergebnisse.reihen(simulation_id),
            "warnungen": ergebnisse.lade_warnungen(simulation_id),
            "werte": ergebnisse.letzte_werte(simulation_id),
        }
    )
