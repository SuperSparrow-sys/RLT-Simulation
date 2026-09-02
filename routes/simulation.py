from flask import Blueprint, Response, current_app, jsonify, request

from core import anlagen, ausgabe, ergebnisse, laeufe, vergleich

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


# ---------------------------------------------------------------------------
# Reihen: derselbe Anlagenlauf ueber mehrere Wetterjahre, nacheinander
# (Vergleich mehrerer Wetterjahre - siehe core/laeufe.py und core/vergleich.py).
# Eigene, statische Pfadsegmente ("reihe") vor den Laufkennungen oben - eine
# Reihen-Kennung ist wie eine Laufkennung ein 32-stelliger Hex-String und
# koennte sonst mit /<kennung> kollidieren; Werkzeug bevorzugt zwar ohnehin
# statische Segmente vor dynamischen, die eigenen Pfade unten machen das aber
# unabhaengig davon eindeutig.
# ---------------------------------------------------------------------------

@bp.post("/reihe")
def reihe_starten():
    daten = request.get_json(force=True) or {}
    if "anlage_id" not in daten:
        return jsonify({"fehler": "Feld 'anlage_id' fehlt"}), 400
    wetterdatensatz_ids = daten.get("wetterdatensatz_ids")
    if not isinstance(wetterdatensatz_ids, list) or not wetterdatensatz_ids:
        return jsonify(
            {"fehler": "Feld 'wetterdatensatz_ids' muss eine nicht leere Liste sein"}
        ), 400
    try:
        wetterdatensatz_ids = [int(x) for x in wetterdatensatz_ids]
        von = int(daten.get("von", 0))
        bis = int(daten.get("bis", 8760))
    except (TypeError, ValueError):
        return jsonify(
            {"fehler": "'wetterdatensatz_ids', 'von' und 'bis' müssen ganze Zahlen sein"}
        ), 400

    # Unbekannte anlage_id/wetterdatensatz_id fuehren hier bewusst nicht zu
    # einem Fehler-Status - dieselbe Begruendung wie starten() oben: jedes
    # Jahr faengt einen solchen Fehlschlag selbst ab (core.laeufe._reihe_laufen)
    # und macht mit dem naechsten weiter, statt die ganze Reihe abzulehnen.
    reihen_kennung = laeufe.starte_reihe(
        current_app._get_current_object(),
        daten["anlage_id"], wetterdatensatz_ids, von, bis,
    )
    return jsonify({"reihen_kennung": reihen_kennung}), 202


@bp.get("/reihe/laufend/<int:anlage_id>")
def reihe_laufend(anlage_id):
    """Fuer die Editorseite nach einem Neuladen: laeuft fuer diese Anlage
    gerade eine Reihe? 'null', wenn nicht - sonst Kennung und Stand, analog
    zu /api/anlagen/<id>/laufende_simulation fuer einen einzelnen Lauf."""
    return jsonify(laeufe.laufende_reihe_auftrag(anlage_id))


@bp.get("/reihe/<reihen_kennung>")
def reihe_stand(reihen_kennung):
    return jsonify(laeufe.reihen_stand(reihen_kennung))


@bp.post("/reihe/<reihen_kennung>/abbrechen")
def reihe_abbrechen(reihen_kennung):
    laeufe.reihe_abbrechen(reihen_kennung)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Vergleich: Gegenueberstellung bereits vorliegender Laeufe (core/vergleich.py)
# - unabhaengig davon, ob sie einzeln oder als Reihe entstanden sind.
# ---------------------------------------------------------------------------

def _simulation_ids_aus_anfrage():
    """Liest 'ids' aus der Query ("12,13,14") - (Liste, Fehlerantwort). Genau
    eines der beiden ist None."""
    roh = request.args.get("ids", "")
    try:
        ids = [int(teil) for teil in roh.split(",") if teil.strip()]
    except ValueError:
        return None, (
            jsonify({"fehler": "'ids' muss eine kommagetrennte Liste von Zahlen sein"}),
            400,
        )
    return ids, None


@bp.get("/vergleich")
def vergleich_route():
    ids, fehlerantwort = _simulation_ids_aus_anfrage()
    if fehlerantwort:
        return fehlerantwort
    try:
        daten = vergleich.vergleichsdaten(ids)
    except vergleich.VergleichNichtMoeglich as fehler:
        return jsonify({"fehler": str(fehler)}), 400
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404
    return jsonify(daten)


@bp.get("/vergleich/diagramm.svg")
def vergleich_diagramm_svg():
    ids, fehlerantwort = _simulation_ids_aus_anfrage()
    if fehlerantwort:
        return fehlerantwort
    try:
        daten = vergleich.vergleichsdaten(ids)
    except vergleich.VergleichNichtMoeglich as fehler:
        return jsonify({"fehler": str(fehler)}), 400
    except KeyError as fehler:
        return jsonify({"fehler": str(fehler)}), 404
    leinwand = vergleich.diagramm(daten)
    if leinwand is None:
        return jsonify({"fehler": "Kein Lauf der Auswahl hat ein Ergebnis."}), 404
    return Response(leinwand.als_svg(), mimetype="image/svg+xml")


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
