import tempfile
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

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
    except Exception:
        # Beschaedigte oder falsch benannte Dateien melden je nach Bibliothek sehr
        # verschiedene Fehler - xlrd, openpyxl und das Auspacken des Zip-Behaelters
        # haben nichts gemeinsam. Wer eine kaputte Datei hochlaedt, soll einen Satz
        # lesen und keine Fehlerseite.
        current_app.logger.exception("Wetterdatei nicht lesbar: %s", datei.filename)
        return jsonify({
            "fehler": "Die Datei liess sich nicht lesen. Erwartet wird eine "
                      "TRY-Datei im Format des Blattes 'Wetterdaten'."
        }), 400
    finally:
        Path(pfad).unlink(missing_ok=True)

    if not stunden:
        return jsonify({"fehler": "Die Datei enthält keine Stundenwerte"}), 400

    datensatz_id = speicher.datensatz_anlegen(name, "upload", stunden)
    return jsonify({"id": datensatz_id, "stunden": len(stunden)}), 201
