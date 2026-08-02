"""Flask uygulama fabrikası.

server.py sadece bunu çağırır. Blueprint'ler `app/api/` altında, iş kuralı
`app/services/` altında, veri `app/models/` + `app/repositories/` altındadır.
"""

from flask import Flask, jsonify

from app.errors import GameError


def create_app() -> Flask:
    # static_folder=None: statik dosyaları kendi rotamız servis ediyor
    # (static/dist Vite çıktısı + kullanıcının audio klasörü).
    flask_app = Flask(__name__, static_folder=None)

    from app.api import game, gm, pages, scenario
    flask_app.register_blueprint(pages.bp)
    flask_app.register_blueprint(game.bp)
    flask_app.register_blueprint(gm.bp)
    flask_app.register_blueprint(scenario.bp)

    @flask_app.errorhandler(GameError)
    def _game_error(exc: GameError):
        # Servis katmanının Türkçe mesajı doğrudan kullanıcıya gider.
        return jsonify({"error": exc.message}), exc.status

    return flask_app
