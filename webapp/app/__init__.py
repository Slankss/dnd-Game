"""Flask uygulama fabrikası.

server.py sadece bunu çağırır. Blueprint'ler `app/api/` altında, iş kuralı
`app/services/` altında, veri `app/models/` + `app/repositories/` altındadır.

Oyun dışarı açık bir sunucuda çalışabildiği için oturum çerezi burada
kurulur: imzalı, HttpOnly, SameSite=Lax. İmza anahtarı .env'den gelmezse
`data/secret_key` içinde üretilip saklanır — sunucuyu yeniden başlatmak
herkesi dışarı atmasın.
"""

import secrets
from datetime import timedelta

from flask import Flask, jsonify

from app import config
from app.errors import GameError


def _secret_key() -> bytes:
    """Sıra: .env → data/secret_key → yeni üret ve sakla.

    Anahtar dosyası depoya girmez (.gitignore) ve yalnız sahibine okunur."""
    if config.SECRET_KEY:
        return config.SECRET_KEY.encode("utf-8")
    yol = config.SECRET_KEY_FILE
    try:
        if yol.exists():
            ham = yol.read_bytes().strip()
            if ham:
                return ham
    except OSError:
        pass
    anahtar = secrets.token_hex(32).encode("ascii")
    try:
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_bytes(anahtar)
        yol.chmod(0o600)
    except OSError:
        # Yazılamıyorsa oyun yine çalışır; yalnız yeniden başlatmada
        # oturumlar düşer.
        pass
    return anahtar


def create_app() -> Flask:
    # static_folder=None: statik dosyaları kendi rotamız servis ediyor
    # (static/dist Vite çıktısı + kullanıcının audio klasörü).
    flask_app = Flask(__name__, static_folder=None)

    flask_app.config.update(
        SECRET_KEY=_secret_key(),
        SESSION_COOKIE_NAME="kizil_cokus",
        SESSION_COOKIE_HTTPONLY=True,
        # Lax: oyun kendi sekmesinde açılır, çapraz site POST'u beklenmiyor.
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=config.COOKIE_SECURE,
        PERMANENT_SESSION_LIFETIME=timedelta(days=config.SESSION_DAYS),
        # Türkçe hata mesajları JSON'da okunabilir kalsın.
        JSON_AS_ASCII=False,
    )

    from app.api import auth, game, gm, grid, pages, round, scenario
    flask_app.register_blueprint(pages.bp)
    flask_app.register_blueprint(auth.bp)
    flask_app.register_blueprint(game.bp)
    flask_app.register_blueprint(round.bp)
    flask_app.register_blueprint(grid.bp)
    flask_app.register_blueprint(gm.bp)
    flask_app.register_blueprint(scenario.bp)

    @flask_app.errorhandler(GameError)
    def _game_error(exc: GameError):
        # Servis katmanının Türkçe mesajı doğrudan kullanıcıya gider.
        return jsonify({"error": exc.message}), exc.status

    return flask_app
