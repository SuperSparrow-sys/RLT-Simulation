from flask import Blueprint, jsonify, request

from core import anlagen, ergebnisse, laeufe, vorlagen

bp = Blueprint("anlagen", __name__, url_prefix="/api")


@bp.get("/palette")
def palette():
    return jsonify(anlagen.palette())


@bp.get("/projekte")
def projekte():
    return jsonify(anlagen.projekte())


@bp.get("/anlagen")
def anlagen_liste():
    projekt_id = request.args.get("projekt_id", type=int)
    return jsonify(anlagen.anlagen_von(projekt_id))


@bp.post("/projekte")
def projekt_anlegen():
    daten = request.get_json(force=True)
    projekt_id = anlagen.projekt_anlegen(daten["name"], daten.get("beschreibung", ""))
    return jsonify({"id": projekt_id}), 201


@bp.post("/anlagen")
def anlage_anlegen():
    daten = request.get_json(force=True)
    anlage_id = anlagen.anlage_anlegen(daten["projekt_id"], daten["name"])
    return jsonify({"id": anlage_id}), 201


@bp.get("/vorlagen")
def vorlagen_liste():
    return jsonify(vorlagen.alle())


@bp.post("/anlagen/aus_vorlage")
def anlage_aus_vorlage():
    daten = request.get_json(force=True)
    try:
        anlage_id = vorlagen.baue(
            daten["vorlage"], daten["projekt_id"], daten.get("name", "Neue Anlage")
        )
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 400
    return jsonify({"id": anlage_id}), 201


@bp.get("/anlagen/<int:anlage_id>")
def anlage_lesen(anlage_id):
    return jsonify(anlagen.als_json(anlage_id))


@bp.get("/anlagen/<int:anlage_id>/simulationen")
def simulationen(anlage_id):
    return jsonify(ergebnisse.simulationen_von(anlage_id))


@bp.get("/anlagen/<int:anlage_id>/laufende_simulation")
def laufende_simulation(anlage_id):
    """Fuer die Editorseite nach einem Neuladen: laeuft fuer diese Anlage
    gerade ein Lauf? 'null', wenn nicht - sonst Kennung und Stand, damit die
    Seite genau dessen Fortschrittsanzeige (statt einer fremden oder gar
    keiner) wieder aufbauen kann. Eigener Endpunkt statt einer Erweiterung
    von /simulationen: dort geht es um die Liste vergangener Laeufe fuer den
    Startdialog, hier um die punktuelle Frage 'laeuft gerade etwas', die die
    Seite bei jedem Laden unabhaengig vom Dialog stellt."""
    return jsonify(laeufe.laufender_auftrag(anlage_id))


@bp.post("/karten")
def karte_anlegen():
    daten = request.get_json(force=True)
    karte_id = anlagen.karte_anlegen(
        daten["anlage_id"], daten["typ"],
        daten.get("pos_x", 0.0), daten.get("pos_y", 0.0),
    )
    karten = anlagen.als_json(daten["anlage_id"])["karten"]
    return jsonify(next(k for k in karten if k["id"] == karte_id)), 201


@bp.patch("/karten/<int:karte_id>")
def karte_aendern(karte_id):
    daten = request.get_json(force=True)
    try:
        anlagen.karte_aendern(
            karte_id,
            pos_x=daten.get("pos_x"), pos_y=daten.get("pos_y"),
            parameter=daten.get("parameter"), name=daten.get("name"),
        )
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404
    return jsonify({"ok": True})


@bp.delete("/karten/<int:karte_id>")
def karte_loeschen(karte_id):
    anlagen.karte_loeschen(karte_id)
    return jsonify({"ok": True})


@bp.post("/pfeile")
def pfeil_anlegen():
    daten = request.get_json(force=True)
    try:
        pfeil = anlagen.pfeil_anlegen(
            daten["anlage_id"], daten["von_karte_id"], daten["nach_karte_id"]
        )
    except ValueError as fehler:
        return jsonify({"fehler": str(fehler)}), 400
    return jsonify(pfeil), 201


@bp.delete("/pfeile/<int:pfeil_id>")
def pfeil_loeschen(pfeil_id):
    anlagen.pfeil_loeschen(pfeil_id)
    return jsonify({"ok": True})


@bp.post("/verbindungen")
def verbindung_anlegen():
    daten = request.get_json(force=True)
    try:
        pfeil = anlagen.verbindung_anlegen(
            daten["anlage_id"], daten["von_port_id"], daten["nach_port_id"]
        )
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404
    except ValueError as fehler:
        return jsonify({"fehler": str(fehler)}), 400
    return jsonify(pfeil), 201
