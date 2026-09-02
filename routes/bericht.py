"""Der Ergebnisbericht eines Simulationslaufs - Ansicht und PDF-Download.

Kein SQL hier: core.bericht liest ueber core.anlagen/core.ergebnisse/
core.wetter.speicher, wie ueberall in routes/ verlangt.
"""

from flask import Blueprint, Response, abort, render_template

from core import bericht

bp = Blueprint("bericht", __name__)


def _daten_oder_404(simulation_id):
    try:
        return bericht.daten_fuer(simulation_id)
    except KeyError:
        abort(404)
    except bericht.BerichtNichtVerfuegbar as fehler:
        abort(409, description=str(fehler))


@bp.get("/anlage/<int:anlage_id>/lauf/<int:simulation_id>/bericht")
def ansehen(anlage_id, simulation_id):
    # anlage_id ist Teil des Pfads (fuer eine sprechende, dem Editor
    # entsprechende URL), massgeblich fuer die Daten ist allein
    # simulation_id - sie traegt ihre Anlage schon in sich. Ein Aufruf mit
    # einer anlage_id, die nicht zum Lauf passt, zeigt trotzdem den
    # richtigen Bericht statt eines verwirrenden zweiten Fehlerfalls.
    daten = _daten_oder_404(simulation_id)
    diagramme = daten["diagramme"]
    svg = {
        "monat": diagramme["monat"].als_svg() if diagramme["monat"] else None,
        "dauerlinie": diagramme["dauerlinie"].als_svg() if diagramme["dauerlinie"] else None,
        "datenlogger": [
            {"titel": e["titel"], "svg": e["leinwand"].als_svg()}
            for e in diagramme["datenlogger"]
        ],
    }
    return render_template("bericht.html", daten=daten, svg=svg, format_zahl=bericht.format_zahl)


@bp.get("/anlage/<int:anlage_id>/lauf/<int:simulation_id>/bericht.pdf")
def pdf(anlage_id, simulation_id):
    daten = _daten_oder_404(simulation_id)
    rohdaten = bericht.baue_pdf(daten)
    dateiname = f"bericht-{daten['anlage']['name']}-lauf-{simulation_id}.pdf"
    dateiname = "".join(z for z in dateiname if z.isalnum() or z in "-_.") or "bericht.pdf"
    return Response(
        rohdaten, mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{dateiname}"'},
    )
