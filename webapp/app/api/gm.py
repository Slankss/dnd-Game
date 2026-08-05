"""Anlatıcı (GM) uçları — hepsi anlatıcı OTURUMU ister.

Eskiden PIN her istekte gövdede/sorguda taşınıyordu; artık bir kez
`/api/auth/gm` ile giriş yapılır ve yetki oturumdan okunur (bkz. api/guards).
Böylece PIN adres çubuğunda, sunucu kayıtlarında ve tarayıcı geçmişinde
dolaşmaz.
"""

from flask import Blueprint, jsonify, request

from app import services
from app.api.guards import gm_required

bp = Blueprint("gm", __name__, url_prefix="/api/gm")


@bp.get("/state")
@gm_required
def gm_state():
    return jsonify(services.gm.snapshot(request.args.get("since")))


@bp.post("/note")
@gm_required
def gm_note():
    body = request.get_json(force=True) or {}
    return jsonify(services.gm.note(body.get("text"), body.get("mode")))


@bp.post("/lesson")
@gm_required
def gm_lesson():
    body = request.get_json(force=True) or {}
    return jsonify(services.gm.add_lesson(body.get("text")))


@bp.get("/items")
@gm_required
def gm_items():
    """Sabit eşya kataloğu — anlatıcı ekranı için (yer türleri dahil)."""
    return jsonify(services.gm.items_catalog())


@bp.post("/items")
@gm_required
def gm_add_item():
    """Katalogu KALICI olarak genişletir: eklenen eşya tüm oyunlarda geçerli."""
    body = request.get_json(force=True) or {}
    return jsonify(services.gm.add_item(body.get("item")))


@bp.post("/patch")
@gm_required
def gm_patch():
    body = request.get_json(force=True) or {}
    return jsonify(services.gm.patch(body.get("patch")))


# ------------------------------------------------------------------ hesaplar
@bp.get("/accounts")
@gm_required
def gm_accounts():
    """Kim karakterini sahiplenmiş, kim hiç girmemiş + oyun kodu."""
    return jsonify(services.auth.accounts_overview())


@bp.post("/accounts/release")
@gm_required
def gm_release_account():
    """Şifresini unutan oyuncunun sahipliğini bırakır; oyuncu yeniden
    sahiplenip yeni şifre belirler."""
    body = request.get_json(force=True) or {}
    return jsonify(services.auth.release(body.get("player")))
