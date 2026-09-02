import os

from flask import Blueprint, current_app, render_template, send_from_directory

from core import anlagen

bp = Blueprint("pages", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/favicon.ico")
def favicon():
    # Browser fragen dieses Pfad ungefragt an, unabhaengig vom <link rel="icon">
    # in den Vorlagen - ohne diese Route lieferte er bislang 404.
    return send_from_directory(
        os.path.join(current_app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@bp.route("/anlage/<int:anlage_id>")
def editor(anlage_id):
    # Ohne diese Pruefung rendert der Editor fuer JEDE Zahl, auch eine
    # Anlage, die es nie gab oder die inzwischen geloescht wurde - er zeigt
    # dann "Diese Anlage ist noch leer.", ununterscheidbar von einer echten,
    # frisch angelegten Anlage. Eine eigene Seite statt eines stillen
    # Redirects auf die Startseite: der Link selbst war falsch oder veraltet,
    # das soll sichtbar bleiben statt kommentarlos woanders hinzufuehren.
    if not anlagen.anlage_existiert(anlage_id):
        return render_template("anlage_nicht_gefunden.html", anlage_id=anlage_id), 404
    return render_template("editor.html", anlage_id=anlage_id)
