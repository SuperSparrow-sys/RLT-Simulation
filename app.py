import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask

from core import config
from core.database import close_db, init_db


def _protokoll_einrichten(app):
    """Haengt den Datei-Handler fuer app.logger genau einmal an.

    Flasks app.logger ist ueber logging.getLogger(app.name) an einen nach
    Namen global geteilten Logger gebunden - jeder weitere create_app()-
    Aufruf traefe also auf denselben Logger wie der vorherige. Ohne diese
    Absicherung haengt jeder Aufruf einen weiteren RotatingFileHandler an,
    und jede spaetere Meldung erscheint entsprechend oft im Protokoll (die
    Testreihe allein ruft create_app() dutzendfach auf).
    """
    ziel = Path(config.LOG_FILE).resolve()
    bereits_eingerichtet = any(
        isinstance(h, RotatingFileHandler) and Path(h.baseFilename) == ziel
        for h in app.logger.handlers
    )
    if bereits_eingerichtet:
        return

    ziel.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        str(ziel), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    app.logger.addHandler(handler)
    app.logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))


def _html_nie_ablegen(app):
    """Verbietet dem Browser, eine HTML-Seite abzulegen - egal ueber welchen
    Weg sie entstand (render_template, Flasks eigene Fehlerseiten fuer
    abort(...), 404 fuer eine falsche/veraltete Adresse).

    Ohne 'Cache-Control' legt der Browser eine Seite nach eigenem Ermessen
    ab (heuristische Freischaltung, RFC 7234 4.2.2) - beobachtet wurde
    genau das: die Startseite kam zwei Tage spaeter wortwoertlich aus dem
    Ablageort zurueck, ohne Fehler und ohne dass ein 'Neu laden' noetig
    ausgesehen haette. 'no-store' statt nur 'no-cache': die Seite darf gar
    nicht erst abgelegt werden, nicht nur "ohne Rueckfrage beim Server
    verwendet werden" - bei vier kleinen Seiten ist der Preis (immer ein
    voller Abruf) vernachlaessigbar, der Schaden eines veralteten Standes
    war es nicht.

    Bewusst NICHT fuer statische Dateien (Skripte, Formatvorlagen,
    Symbole): die laufen weiterhin ueber Flasks eigene Auslieferung mit
    'Cache-Control: no-cache' plus ETag/Last-Modified (siehe Kommentar in
    routes/pages.py bzw. den Kopfzeilen in wege-report.md) - das erzwingt
    laut HTTP-Spezifikation eine Rueckfrage beim Server vor jeder
    Verwendung, eine geaenderte Datei kommt darueber ebenso sicher wieder
    frisch. Ein an sich denkbarer zweiter Weg (eine Fassungskennung im
    Dateiverweis, z.B. ?v=<Hash>) wurde bewusst NICHT gewaehlt: die
    eigentliche Gefahr - eine Seite trifft auf eine Skriptfassung, fuer
    die sie nicht geschrieben ist - ist bereits durch 'no-store' auf der
    Seite selbst gebannt, denn die Seite liefert bei jedem Laden neu genau
    die Verweise, die zu ihr passen. Ein Registrierungsmechanismus fuer
    Fassungskennungen haette in JEDER Vorlage angefasst werden muessen
    (auch templates/index.html, das nicht in diesem Zustaendigkeitsbereich
    liegt) fuer einen Nutzen, den 'no-cache' + ETag im Normalfall schon
    liefert.
    """

    @app.after_request
    def setze_cache_control(antwort):
        if antwort.mimetype == "text/html":
            antwort.headers["Cache-Control"] = "no-store"
        return antwort


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY

    _protokoll_einrichten(app)
    _html_nie_ablegen(app)

    app.teardown_appcontext(close_db)

    from routes import anlagen as anlagen_routen, bericht, lehre, pages, simulation
    from routes import wetter as wetter_routen

    app.register_blueprint(pages.bp)
    app.register_blueprint(anlagen_routen.bp)
    app.register_blueprint(wetter_routen.bp)
    app.register_blueprint(simulation.bp)
    app.register_blueprint(lehre.bp)
    app.register_blueprint(bericht.bp)

    with app.app_context():
        init_db()

    return app


if __name__ == "__main__":
    create_app().run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
