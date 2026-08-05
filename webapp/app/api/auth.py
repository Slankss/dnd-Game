"""Kimlik uçları. Bu katman İNCE: gövdeyi ayrıştır, servisi çağır, oturumu kur.

  GET  /api/auth/me      — kimim, hangi karakterler sahipsiz
  POST /api/auth/login   — karakterle giriş (ilk girişte oyun kodu + şifre kurar)
  POST /api/auth/table   — TEK EKRAN girişi: oyun kodu, karakter yok
  POST /api/auth/gm      — anlatıcı girişi (PIN)
  POST /api/auth/logout  — oturumu kapat
"""

from flask import Blueprint, jsonify, request

from app import services
from app.api.guards import cikis_yap, giris_yap, kimlik

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _ip() -> str:
    """Kaba kuvvet frenine anahtar. Ters vekil arkasındaysa gerçek istemci
    X-Forwarded-For'un İLK adresidir; yoksa doğrudan bağlantının adresi."""
    iletilen = request.headers.get("X-Forwarded-For", "")
    if iletilen:
        return iletilen.split(",")[0].strip()
    return request.remote_addr or "?"


@bp.get("/me")
def me():
    return jsonify(services.auth.me(kimlik()))


@bp.post("/login")
def login():
    body = request.get_json(force=True) or {}
    veri = services.auth.login(body.get("player"), body.get("password"),
                               code=body.get("code"), ip=_ip())
    giris_yap(veri)
    return jsonify({**services.auth.me(kimlik()), "claimed": veri.get("claimed", False)})


@bp.post("/table")
def table_login():
    """Tek ekran: masadaki cihaz kadronun tamamı adına oynar."""
    body = request.get_json(force=True) or {}
    giris_yap(services.auth.table_login(body.get("code"), ip=_ip()))
    return jsonify(services.auth.me(kimlik()))


@bp.post("/gm")
def gm_login():
    body = request.get_json(force=True) or {}
    giris_yap(services.auth.gm_login(body.get("pin"), ip=_ip()))
    return jsonify(services.auth.me(kimlik()))


@bp.post("/logout")
def logout():
    cikis_yap()
    return jsonify(services.auth.me(kimlik()))
