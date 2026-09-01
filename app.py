import logging
from logging.handlers import RotatingFileHandler

from flask import Flask

from core import config
from core.database import close_db, init_db


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY

    config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        str(config.LOG_FILE), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    app.logger.addHandler(handler)
    app.logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    app.teardown_appcontext(close_db)

    from routes import anlagen as anlagen_routen, pages
    from routes import wetter as wetter_routen

    app.register_blueprint(pages.bp)
    app.register_blueprint(anlagen_routen.bp)
    app.register_blueprint(wetter_routen.bp)

    with app.app_context():
        init_db()

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=config.PORT, debug=True)
