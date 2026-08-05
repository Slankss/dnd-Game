"""Flask uygulama fabrikası.

server.py sadece bunu çağırır. Blueprint'ler `app/api/` altında, iş kuralı
`app/services/` altında, veri `app/models/` + `app/repositories/` altındadır.

Oyun dışarı açık bir sunucuda çalışabildiği için oturum çerezi burada
kurulur: imzalı, HttpOnly, SameSite=Lax. İmza anahtarı .env'den gelmezse
`data/secret_key` içinde üretilip saklanır — sunucuyu yeniden başlatmak
herkesi dışarı atmasın.
"""

import json
import secrets
from datetime import timedelta

from flask import Flask, jsonify

from app import config
from app.errors import GameError
from app.serializers import mask_picks


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
    from app.api.guards import kimlik
    from app.services.auth_service import ROL_ANLATICI, ROL_MASA, ROL_OYUNCU

    flask_app.register_blueprint(pages.bp)
    flask_app.register_blueprint(auth.bp)
    flask_app.register_blueprint(game.bp)
    flask_app.register_blueprint(round.bp)
    flask_app.register_blueprint(grid.bp)
    flask_app.register_blueprint(gm.bp)
    flask_app.register_blueprint(scenario.bp)

    @flask_app.after_request
    def _kararlari_gizle(response):
        """Açık turda başka oyuncuların KARARI gövdeye hiç girmez.

        Tek yerde yapılıyor: bir ucu işaretlemeyi unutmak sızıntı demek
        olurdu. `round` anahtarı taşıyan her JSON yanıt buradan geçer;
        anlatıcı ve tek ekran masası için maskeleme uygulanmaz.
        """
        if not response.is_json:
            return response
        try:
            body = response.get_json(silent=True)
        except Exception:
            return response
        if not isinstance(body, dict) or not isinstance(body.get("round"), dict):
            return response
        kim = kimlik()
        rol = kim.get("role")
        maskeli = mask_picks(
            body["round"],
            viewer=kim.get("player") if rol == ROL_OYUNCU else None,
            reveal=rol in (ROL_ANLATICI, ROL_MASA),
        )
        if maskeli is not body["round"]:
            response.set_data(json.dumps({**body, "round": maskeli},
                                         ensure_ascii=False))
        return response

    @flask_app.errorhandler(GameError)
    def _game_error(exc: GameError):
        # Servis katmanının Türkçe mesajı doğrudan kullanıcıya gider.
        return jsonify({"error": exc.message}), exc.status

    return flask_app
