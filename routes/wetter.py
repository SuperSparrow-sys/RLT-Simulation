import tempfile
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from core.wetter import openmeteo, speicher, try_import

bp = Blueprint("wetter", __name__, url_prefix="/api/wetter")


@bp.get("")
def liste():
    return jsonify(speicher.datensaetze())


@bp.patch("/<int:datensatz_id>")
def umbenennen(datensatz_id):
    daten = request.get_json(force=True)
    try:
        speicher.datensatz_umbenennen(datensatz_id, daten["name"])
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404
    return jsonify({"ok": True})


@bp.delete("/<int:datensatz_id>")
def loeschen(datensatz_id):
    try:
        speicher.datensatz_loeschen(datensatz_id)
    except ValueError as fehler:
        return jsonify({"fehler": str(fehler)}), 400
    return jsonify({"ok": True})


@bp.post("/abrufen")
def abrufen():
    """Ruft ein Jahr Wetterdaten fuer einen Ort ueber die Open-Meteo Archive-API
    ab und legt sie genauso ab wie ein Datei-Upload. Dauert - bei fuenf parallel
    geschickten Teilabfragen - in aller Regel nur wenige Sekunden; ein eigener
    Hintergrundlauf mit Fortschrittsanzeige (wie core.laeufe fuer Simulationen)
    waere hier ueberdimensioniert, siehe wetter-api-report.md.
    """
    daten = request.get_json(silent=True) or {}

    try:
        breite = float(daten["breite"])
        laenge = float(daten["laenge"])
        jahr = int(daten["jahr"])
    except (KeyError, TypeError, ValueError):
        return jsonify({
            "fehler": "Breite, Länge und Jahr werden benötigt (Breite/Länge als "
                      "Dezimalzahl, Jahr als Ganzzahl)"
        }), 400

    ort = (daten.get("ort") or "").strip()
    name = (daten.get("name") or "").strip() or f"{ort or f'{breite}, {laenge}'} {jahr}"

    try:
        stunden = openmeteo.abrufen(breite, laenge, jahr, ort=ort)
    except openmeteo.WetterEingabeFehler as fehler:
        return jsonify({"fehler": str(fehler)}), 400
    except openmeteo.WetterAbrufFehler as fehler:
        current_app.logger.warning("Wetterabruf gescheitert: %s", fehler)
        return jsonify({"fehler": str(fehler)}), 502

    datensatz_id = speicher.datensatz_anlegen(
        name, "open-meteo", stunden, ort=ort, breite=breite, laenge=laenge, jahr=jahr,
        notiz=f"Abgerufen von Open-Meteo (Archive-API) für "
              f"{ort or f'{breite}, {laenge}'}, Jahr {jahr}",
    )
    return jsonify({"id": datensatz_id, "stunden": len(stunden)}), 201


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
