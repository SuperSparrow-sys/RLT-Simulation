from flask import Blueprint, Response, current_app, jsonify, request

from core import anlagen, ausgabe, ergebnisse, laeufe

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
    daten = request.get_json(force=True) or {}
    if "anlage_id" not in daten:
        return jsonify({"fehler": "Feld 'anlage_id' fehlt"}), 400
    if "wetterdatensatz_id" not in daten:
        return jsonify({"fehler": "Feld 'wetterdatensatz_id' fehlt"}), 400
    try:
        von = int(daten.get("von", 0))
        bis = int(daten.get("bis", 8760))
    except (TypeError, ValueError):
        return jsonify({"fehler": "'von' und 'bis' müssen ganze Zahlen sein"}), 400

    # Eine unbekannte anlage_id/wetterdatensatz_id fuehrt hier bewusst nicht
    # zu einem Fehler-Status - core.laeufe.starte() faengt das selbst ab und
    # legt den Lauf mit status='fehler' an (siehe dortiger Kommentar), damit
    # der Aufrufer immer eine Kennung bekommt und den Fehler ueber GET
    # /api/simulation/<kennung> genauso abfragt wie jeden anderen Abbruch.
    kennung = laeufe.starte(
        current_app._get_current_object(),
        daten["anlage_id"],
        daten["wetterdatensatz_id"],
        von, bis,
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
            "warnungen": ergebnisse.lade_warnungen(simulation_id),
            "baustein_warnungen": ergebnisse.lade_baustein_warnungen(simulation_id),
            "werte": ergebnisse.letzte_werte(simulation_id),
        }
    )


@bp.get("/<int:simulation_id>/protokoll")
def protokoll(simulation_id):
    """Das Stundenprotokoll der am Datenlogger angeschlossenen Werte - siehe
    ergebnisse.lade_protokoll(). Ein eigener Aufruf statt Teil von bilanz():
    anders als die Bilanz kann das Protokoll bei einem Jahreslauf mehrere
    Megabyte gross werden, und die meisten Anlagen aus den Vorlagen haben
    ueberhaupt keinen Datenlogger - es soll nicht bei jedem Oeffnen der
    Bilanz ungefragt mitkommen."""
    try:
        anlage_id = ergebnisse.simulation_anlage_id(simulation_id)
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404
    graph = anlagen.lade_graph(anlage_id)
    return jsonify({"spalten": ergebnisse.lade_protokoll(simulation_id, graph)})


def _ausgabedaten_oder_fehler(simulation_id):
    """Gemeinsamer Rahmen fuer die beiden Ausgabe-Routen: unbekannte
    simulation_id wird 404, ein Lauf ohne gespeichertes Ergebnis 409 (der
    Lauf existiert, ist aber noch nicht so weit) - dieselbe Unterscheidung wie
    routes/bericht.py._daten_oder_404(), nur mit jsonify() statt abort(),
    weil diese Routen (anders als die HTML-Berichtsseite) von fetch()/einem
    Download-Link aus aufgerufen werden."""
    try:
        return ausgabe.daten_fuer(simulation_id), None
    except KeyError as fehler:
        return None, (jsonify({"fehler": str(fehler)}), 404)
    except ausgabe.AusgabeNichtVerfuegbar as fehler:
        return None, (jsonify({"fehler": str(fehler)}), 409)


@bp.get("/<int:simulation_id>/stundenwerte.csv")
def stundenwerte_csv(simulation_id):
    """Die Stundenwerte des Laufs als CSV - siehe core.ausgabe.csv_bytes()
    fuer Trennzeichen, Dezimalzeichen und Kodierung."""
    daten, fehler = _ausgabedaten_oder_fehler(simulation_id)
    if fehler:
        return fehler
    rohdaten = ausgabe.csv_bytes(daten)
    name = ausgabe.dateiname(daten, "csv")
    # Nur 'text/csv', kein eigener charset-Zusatz: Flask haengt ihn fuer
    # 'text/*' selbst an (siehe Response.mimetype) - mit einem eigenen waere
    # der Header doppelt ('charset=utf-8; charset=utf-8').
    return Response(
        rohdaten, mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@bp.get("/<int:simulation_id>/stundenwerte.xlsx")
def stundenwerte_xlsx(simulation_id):
    """Die Stundenwerte des Laufs als Excel-Mappe - siehe core.ausgabe.xlsx_bytes()."""
    daten, fehler = _ausgabedaten_oder_fehler(simulation_id)
    if fehler:
        return fehler
    rohdaten = ausgabe.xlsx_bytes(daten)
    name = ausgabe.dateiname(daten, "xlsx")
    return Response(
        rohdaten,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
