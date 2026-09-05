import tempfile
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from core.wetter import einlesen, openmeteo, speicher

bp = Blueprint("wetter", __name__, url_prefix="/api/wetter")


@bp.get("")
def liste():
    return jsonify(speicher.datensaetze())


@bp.patch("/<int:datensatz_id>")
def umbenennen(datensatz_id):
    daten = request.get_json(force=True) or {}
    if not daten.get("name"):
        return jsonify({"fehler": "Feld 'name' fehlt oder ist leer"}), 400
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
    """Nimmt eine oder mehrere Wetterdateien an und legt je Datei einen
    Datensatz an.

    Der uebliche Weg ist ein ganzer Ordner: der Browser sammelt daraus die
    lesbaren Dateien und schickt nur die angekreuzten (static/js/start.js).
    Ein Einzelupload ist der Sonderfall mit genau einer Datei; damit aeltere
    Aufrufer weiterlaufen, traegt die Antwort dann zusaetzlich 'id' und
    'stunden' unmittelbar.

    'fehler' ist wie ueberall sonst in dieser Schnittstelle eine Meldung als
    Text und nur bei einem Fehlschlag da; was einzelne Dateien betrifft, steht
    unter 'dateifehler'.

    Jede Datei wird fuer sich verarbeitet. Eine unlesbare darf die uebrigen
    nicht mitreissen - wer sechs Testreferenzjahre hochlaedt und bei einem
    einen Uebertragungsfehler hat, soll die anderen fuenf behalten und
    erfahren, welches gefehlt hat.
    """
    dateien = [d for d in request.files.getlist("datei") if d and d.filename]
    if not dateien:
        return jsonify({"fehler": "Keine Datei übermittelt"}), 400

    ort = (request.form.get("ort") or "").strip()
    # Ein mitgegebener Name kann nur fuer eine einzelne Datei gelten - sonst
    # hiessen alle Datensaetze gleich.
    vorgegebener_name = (request.form.get("name") or "").strip() if len(dateien) == 1 else ""

    angelegt = []
    fehler = []
    for datei in dateien:
        try:
            angelegt.append(_datei_uebernehmen(datei, ort, vorgegebener_name))
        except ValueError as ausnahme:
            fehler.append({"datei": datei.filename, "fehler": str(ausnahme)})

    if not angelegt:
        # Bei einer einzelnen Datei ist deren Meldung die ganze Wahrheit; bei
        # mehreren waere eine Aneinanderreihung unlesbar.
        meldung = (
            fehler[0]["fehler"] if len(fehler) == 1
            else f"Keine der {len(fehler)} Dateien ließ sich lesen."
        )
        return jsonify({"fehler": meldung, "datensaetze": [], "dateifehler": fehler}), 400

    antwort = {"datensaetze": angelegt, "dateifehler": fehler}
    if len(angelegt) == 1:
        antwort["id"] = angelegt[0]["id"]
        antwort["stunden"] = angelegt[0]["stunden"]
    return jsonify(antwort), 201


def _datei_uebernehmen(datei, ort, vorgegebener_name):
    """Liest eine hochgeladene Datei und legt ihren Datensatz an.

    Wirft ValueError mit einer verstaendlichen deutschen Meldung, wenn die
    Datei nicht lesbar ist - der Aufrufer sammelt diese Meldungen je Datei.
    """
    endung = Path(datei.filename).suffix.lower()
    if endung in einlesen.ARCHIVENDUNGEN:
        raise ValueError(
            "Archive werden nicht ausgepackt. Bitte das Archiv entpacken und "
            "den entpackten Ordner auswählen – die Dateien darin werden dann "
            "gefunden, auch in Unterordnern."
        )
    if endung not in einlesen.ENDUNGEN:
        benannt = endung or "ohne Endung"
        raise ValueError(
            f"'{benannt}' wird nicht gelesen. Erwartet werden "
            f"{', '.join(einlesen.ENDUNGEN)}."
        )

    # Unter ihrem urspruenglichen Namen ablegen, nicht unter einem zufaelligen:
    # ein TRY traegt Schluesseljahr und Art im Dateinamen (Handbuch Kap. 2), und
    # der Leser braucht das Jahr - die Datenzeilen selbst nennen keines. Mit
    # einem Namen wie "tmp8f3k.dat" bekaeme jedes Zukunfts-TRY stillschweigend
    # das Vorgabejahr 2015.
    with tempfile.TemporaryDirectory() as ordner:
        pfad = Path(ordner) / _sicherer_dateiname(datei.filename, endung)
        datei.save(str(pfad))
        try:
            stunden = einlesen.lese_datei(pfad)
            kopf = einlesen.beschreibung(pfad)
        except ValueError:
            # Kommt schon mit einer verstaendlichen Meldung - unveraendert weiter.
            raise
        except Exception as ausnahme:
            # Beschaedigte oder falsch benannte Dateien melden je nach Bibliothek sehr
            # verschiedene Fehler - xlrd, openpyxl und das Auspacken des Zip-Behaelters
            # haben nichts gemeinsam. Wer eine kaputte Datei hochlaedt, soll einen Satz
            # lesen und keine Fehlerseite.
            current_app.logger.exception("Wetterdatei nicht lesbar: %s", datei.filename)
            raise ValueError(
                "Die Datei ließ sich nicht lesen. Erwartet wird ein DWD-Testreferenzjahr "
                "(.dat) oder eine Tabelle im Format des Blattes 'Wetterdaten'."
            ) from ausnahme

    if not stunden:
        raise ValueError("Die Datei enthält keine Stundenwerte")

    name = vorgegebener_name or _name_finden(datei.filename, kopf)
    datensatz_id = speicher.datensatz_anlegen(
        name, "upload", stunden, ort=ort,
        breite=kopf.get("breite"), laenge=kopf.get("laenge"),
        jahr=kopf.get("jahr"), notiz=kopf.get("notiz", ""),
    )
    return {
        "datei": datei.filename,
        "id": datensatz_id,
        "name": name,
        "stunden": len(stunden),
    }


def _sicherer_dateiname(dateiname, endung):
    """Der Dateiname kommt vom Browser und darf nicht ungeprueft in einen Pfad.

    secure_filename streicht Pfadanteile und Sonderzeichen; bleibt dabei nichts
    Brauchbares uebrig (etwa bei einem rein kyrillischen Namen), tritt ein
    Ersatzname ein - dann fehlt zwar die Kennung aus dem Namen, aber die Datei
    laesst sich trotzdem lesen.
    """
    name = secure_filename(Path(dateiname).name)
    if not name:
        name = f"wetterdatei{endung}"
    if not name.lower().endswith(endung):
        name += endung
    return name


def _name_finden(dateiname, kopf):
    """Ein TRY traegt Jahr und Art im Namen ('2015 – mittleres Jahr'); der Ort
    steht am Datensatz und wuerde hier nur doppelt stehen. Alles andere behaelt
    seinen Dateinamen."""
    if kopf.get("jahr") and kopf.get("art"):
        return f"{kopf['jahr']} – {kopf['art']}"
    return Path(dateiname).stem
