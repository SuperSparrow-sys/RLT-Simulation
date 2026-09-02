"""Der Ergebnisbericht eines Simulationslaufs - Ansicht und PDF-Download.

Kein SQL hier: core.bericht liest ueber core.anlagen/core.ergebnisse/
core.wetter.speicher, wie ueberall in routes/ verlangt.
"""

from flask import Blueprint, Response, abort, render_template, request, url_for

from core import bericht

bp = Blueprint("bericht", __name__)


def _daten_oder_404(simulation_id, ausgewaehlte_reihen):
    try:
        return bericht.daten_fuer(simulation_id, ausgewaehlte_reihen)
    except KeyError:
        abort(404)
    except bericht.BerichtNichtVerfuegbar as fehler:
        abort(409, description=str(fehler))


def _ausgewaehlte_reihen():
    """Die vom Auswahlformular uebermittelten Schluessel (siehe
    templates/bericht.html, Formular 'form-reihen-auswahl') - None, solange
    noch keine eigene Auswahl abgeschickt wurde (dann zeigt core.bericht die
    Vorgabe), sonst die (auch leere) Liste der angehakten Kaestchen. Der
    Marker-Parameter 'auswahl' unterscheidet beide Faelle: ohne ihn fehlt
    'reihe' schlicht, weil noch nie abgeschickt wurde; mit ihm, aber ohne
    'reihe', hat der Benutzer ausdruecklich alle Haken entfernt."""
    if "auswahl" not in request.args:
        return None
    return request.args.getlist("reihe")


def _auswahl_query():
    """Dieselbe Auswahl als Query-Parameter fuer den PDF-Knopf (siehe
    ansehen()) - so bekommt das serverseitig erzeugte PDF exakt die Reihen,
    die gerade in der HTML-Fassung zu sehen sind, ohne dass der Benutzer sie
    ein zweites Mal treffen muesste."""
    reihen = _ausgewaehlte_reihen()
    return {} if reihen is None else {"auswahl": "1", "reihe": reihen}


@bp.get("/anlage/<int:anlage_id>/lauf/<int:simulation_id>/bericht")
def ansehen(anlage_id, simulation_id):
    # anlage_id ist Teil des Pfads (fuer eine sprechende, dem Editor
    # entsprechende URL), massgeblich fuer die Daten ist allein
    # simulation_id - sie traegt ihre Anlage schon in sich. Ein Aufruf mit
    # einer anlage_id, die nicht zum Lauf passt, zeigt trotzdem den
    # richtigen Bericht statt eines verwirrenden zweiten Fehlerfalls.
    daten = _daten_oder_404(simulation_id, _ausgewaehlte_reihen())
    diagramme = daten["diagramme"]
    svg = {
        "monat": diagramme["monat"].als_svg() if diagramme["monat"] else None,
        "dauerlinie": diagramme["dauerlinie"].als_svg() if diagramme["dauerlinie"] else None,
        "datenlogger": [
            {"titel": e["titel"], "svg": e["leinwand"].als_svg()}
            for e in diagramme["datenlogger"]
        ],
        "jahr_stunden": diagramme["jahr_stunden"].als_svg() if diagramme["jahr_stunden"] else None,
        "vier_monats_ausschnitte": [
            a.als_svg() for a in diagramme["vier_monats_ausschnitte"]
        ],
        # Vorhaben B: nur gesetzt, wenn dieser Lauf Teil einer Reihe ist
        # (siehe core.bericht._vergleich_fuer()) - sonst None, das Formular
        # in templates/bericht.html blendet den ganzen Abschnitt dann aus.
        "vergleich": diagramme["vergleich"].als_svg() if diagramme.get("vergleich") else None,
    }
    pdf_href = url_for(
        "bericht.pdf", anlage_id=anlage_id, simulation_id=simulation_id, **_auswahl_query()
    )
    return render_template(
        "bericht.html", daten=daten, svg=svg, format_zahl=bericht.format_zahl,
        pdf_href=pdf_href,
    )


@bp.get("/anlage/<int:anlage_id>/lauf/<int:simulation_id>/bericht.pdf")
def pdf(anlage_id, simulation_id):
    daten = _daten_oder_404(simulation_id, _ausgewaehlte_reihen())
    rohdaten = bericht.baue_pdf(daten)
    dateiname = f"bericht-{daten['anlage']['name']}-lauf-{simulation_id}.pdf"
    dateiname = "".join(z for z in dateiname if z.isalnum() or z in "-_.") or "bericht.pdf"
    return Response(
        rohdaten, mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{dateiname}"'},
    )
