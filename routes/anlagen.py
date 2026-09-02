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
    daten = request.get_json(force=True) or {}
    if not daten.get("name"):
        return jsonify({"fehler": "Feld 'name' fehlt oder ist leer"}), 400
    projekt_id = anlagen.projekt_anlegen(daten["name"], daten.get("beschreibung", ""))
    return jsonify({"id": projekt_id}), 201


@bp.post("/anlagen")
def anlage_anlegen():
    daten = request.get_json(force=True) or {}
    if not daten.get("name"):
        return jsonify({"fehler": "Feld 'name' fehlt oder ist leer"}), 400
    if "projekt_id" not in daten:
        return jsonify({"fehler": "Feld 'projekt_id' fehlt"}), 400
    try:
        anlage_id = anlagen.anlage_anlegen(daten["projekt_id"], daten["name"])
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404
    return jsonify({"id": anlage_id}), 201


@bp.patch("/projekte/<int:projekt_id>")
def projekt_umbenennen(projekt_id):
    daten = request.get_json(force=True) or {}
    if not daten.get("name"):
        return jsonify({"fehler": "Feld 'name' fehlt oder ist leer"}), 400
    try:
        anlagen.projekt_umbenennen(projekt_id, daten["name"])
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404
    return jsonify({"ok": True})


@bp.delete("/projekte/<int:projekt_id>")
def projekt_loeschen(projekt_id):
    # Erst jeden laufenden Lauf der betroffenen Anlagen sauber abbrechen,
    # dann erst loeschen - siehe core.laeufe.abbrich_vor_loeschen().
    laeufe.abbrich_vor_loeschen(projekt_id=projekt_id)
    anlagen.projekt_loeschen(projekt_id)
    return jsonify({"ok": True})


@bp.patch("/anlagen/<int:anlage_id>")
def anlage_umbenennen(anlage_id):
    daten = request.get_json(force=True) or {}
    if not daten.get("name"):
        return jsonify({"fehler": "Feld 'name' fehlt oder ist leer"}), 400
    try:
        anlagen.anlage_umbenennen(anlage_id, daten["name"])
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404
    return jsonify({"ok": True})


@bp.delete("/anlagen/<int:anlage_id>")
def anlage_loeschen(anlage_id):
    laeufe.abbrich_vor_loeschen(anlage_id=anlage_id)
    anlagen.anlage_loeschen(anlage_id)
    return jsonify({"ok": True})


@bp.get("/vorlagen")
def vorlagen_liste():
    return jsonify(vorlagen.alle())


@bp.post("/anlagen/aus_vorlage")
def anlage_aus_vorlage():
    daten = request.get_json(force=True) or {}
    if not daten.get("vorlage"):
        return jsonify({"fehler": "Feld 'vorlage' fehlt oder ist leer"}), 400
    if "projekt_id" not in daten:
        return jsonify({"fehler": "Feld 'projekt_id' fehlt"}), 400
    try:
        anlage_id = vorlagen.baue(
            daten["vorlage"], daten["projekt_id"], daten.get("name", "Neue Anlage")
        )
    except KeyError as fehler:
        # 'vorlage' gibt es nicht (core.vorlagen.baue) oder 'projekt_id' gibt
        # es nicht (core.anlagen.anlage_anlegen, ueber das jede Vorlage ihre
        # Anlage anlegt) - beides eine unbekannte Kennung, kein Eingabefehler.
        return jsonify({"fehler": str(fehler)}), 404
    return jsonify({"id": anlage_id}), 201


@bp.get("/anlagen/<int:anlage_id>")
def anlage_lesen(anlage_id):
    try:
        return jsonify(anlagen.als_json(anlage_id))
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404


@bp.get("/anlagen/<int:anlage_id>/messwerte")
def messwerte(anlage_id):
    """Alle Messwerte dieser Anlage - fuer die Auswahl 'Istwert/Sollwert kommt
    von: <Karte> -> <Messwert>' beim gezielten Verdrahten eines Reglers (siehe
    core.anlagen.messwerte_von)."""
    return jsonify(anlagen.messwerte_von(anlage_id))


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
    daten = request.get_json(force=True) or {}
    if "anlage_id" not in daten:
        return jsonify({"fehler": "Feld 'anlage_id' fehlt"}), 400
    if not daten.get("typ"):
        return jsonify({"fehler": "Feld 'typ' fehlt oder ist leer"}), 400
    try:
        karte_id = anlagen.karte_anlegen(
            daten["anlage_id"], daten["typ"],
            daten.get("pos_x", 0.0), daten.get("pos_y", 0.0),
        )
    except KeyError as fehler:
        # 'typ' gibt es nicht (core.bausteine.basis.hole) oder 'anlage_id'
        # gibt es nicht (core.anlagen.karte_anlegen) - beides eine unbekannte
        # Kennung, kein Eingabefehler.
        return jsonify({"fehler": str(fehler)}), 404
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
    except anlagen.UngueltigeParameter as fehler:
        return jsonify({"fehler": str(fehler), "feldfehler": fehler.fehler}), 400
    return jsonify({"ok": True})


@bp.delete("/karten/<int:karte_id>")
def karte_loeschen(karte_id):
    anlagen.karte_loeschen(karte_id)
    return jsonify({"ok": True})


@bp.post("/pfeile")
def pfeil_anlegen():
    daten = request.get_json(force=True) or {}
    for feld in ("anlage_id", "von_karte_id", "nach_karte_id"):
        if feld not in daten:
            return jsonify({"fehler": f"Feld '{feld}' fehlt"}), 400
    try:
        pfeil = anlagen.pfeil_anlegen(
            daten["anlage_id"], daten["von_karte_id"], daten["nach_karte_id"]
        )
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404
    except ValueError as fehler:
        return jsonify({"fehler": str(fehler)}), 400
    return jsonify(pfeil), 201


@bp.delete("/pfeile/<int:pfeil_id>")
def pfeil_loeschen(pfeil_id):
    anlagen.pfeil_loeschen(pfeil_id)
    return jsonify({"ok": True})


@bp.post("/verbindungen")
def verbindung_anlegen():
    daten = request.get_json(force=True) or {}
    for feld in ("anlage_id", "von_port_id", "nach_port_id"):
        if feld not in daten:
            return jsonify({"fehler": f"Feld '{feld}' fehlt"}), 400
    try:
        pfeil = anlagen.verbindung_anlegen(
            daten["anlage_id"], daten["von_port_id"], daten["nach_port_id"]
        )
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404
    except ValueError as fehler:
        return jsonify({"fehler": str(fehler)}), 400
    return jsonify(pfeil), 201
