"""Sayfa ve dosya servisi.

Arayüz artık Vue SPA: `/` (oyuncu) ve `/secrets` (anlatıcı) aynı build'i
döndürür, hangi ekranın açılacağına vue-router karar verir.
"""

from flask import Blueprint, send_from_directory

from app import config

bp = Blueprint("pages", __name__)

BUILD_MISSING = (
    "Arayüz derlenmemiş. webapp/frontend içinde `npm install && npm run build` "
    "çalıştırın (çıktı static/dist altına düşer)."
)


def _spa():
    if not (config.DIST_DIR / "index.html").exists():
        return BUILD_MISSING, 500
    return send_from_directory(config.DIST_DIR, "index.html")


@bp.route("/")
def index():
    return _spa()


@bp.route("/secrets")
def secrets_page():
    # Anlatıcı ekranı — oyuncu arayüzünden hiçbir yere bağlanmaz, ayrıca
    # PIN ile kilitlidir.
    return _spa()


@bp.route("/static/<path:filename>")
def static_files(filename):
    # Vite çıktısı (dist/...) ve kullanıcının kendi eklediği audio/ambient.mp3
    # gibi dosyalar buradan servis edilir.
    return send_from_directory(config.STATIC_DIR, filename)
