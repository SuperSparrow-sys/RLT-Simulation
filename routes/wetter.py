import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

from core.wetter import speicher, try_import

bp = Blueprint("wetter", __name__, url_prefix="/api/wetter")


@bp.get("")
def liste():
    return jsonify(speicher.datensaetze())


@bp.post("/upload")
def hochladen():
    datei = request.files.get("datei")
    if datei is None or not datei.filename:
        return jsonify({"fehler": "Keine Datei übermittelt"}), 400

    name = request.form.get("name") or Path(datei.filename).stem
    endung = Path(datei.filename).suffix.lower()

    with tempfile.NamedTemporaryFile(suffix=endung, delete=False) as ziel:
        datei.save(ziel.name)
        pfad = ziel.name

    try:
        stunden = try_import.lese_datei(pfad)
    except ValueError as fehler:
        return jsonify({"fehler": str(fehler)}), 400
    finally:
        Path(pfad).unlink(missing_ok=True)

    if not stunden:
        return jsonify({"fehler": "Die Datei enthält keine Stundenwerte"}), 400

    datensatz_id = speicher.datensatz_anlegen(name, "upload", stunden)
    return jsonify({"id": datensatz_id, "stunden": len(stunden)}), 201
