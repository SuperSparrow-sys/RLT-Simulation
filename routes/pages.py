import os

from flask import Blueprint, current_app, render_template, send_from_directory

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
    return render_template("editor.html", anlage_id=anlage_id)
