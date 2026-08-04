"""Anlatıcı (GM) uçları — hepsi PIN ile korunur.

PIN kontrolü servis katmanında yapılır (AuthError atar), böylece kural tek
yerde durur.
"""

from flask import Blueprint, jsonify, request

from app import services

bp = Blueprint("gm", __name__, url_prefix="/api/gm")


@bp.post("/unlock")
def unlock():
    body = request.get_json(force=True) or {}
    return jsonify(services.gm.unlock(body.get("pin")))


@bp.get("/state")
def gm_state():
    return jsonify(services.gm.snapshot(request.args.get("pin"), request.args.get("since")))


@bp.post("/note")
def gm_note():
    body = request.get_json(force=True) or {}
    return jsonify(services.gm.note(body.get("pin"), body.get("text"), body.get("mode")))


@bp.post("/lesson")
def gm_lesson():
    body = request.get_json(force=True) or {}
    return jsonify(services.gm.add_lesson(body.get("pin"), body.get("text")))


@bp.get("/items")
def gm_items():
    """Sabit eşya kataloğu — anlatıcı ekranı için (yer türleri dahil)."""
    return jsonify(services.gm.items_catalog(request.args.get("pin")))


@bp.post("/items")
def gm_add_item():
    """Katalogu KALICI olarak genişletir: eklenen eşya tüm oyunlarda geçerli."""
    body = request.get_json(force=True) or {}
    return jsonify(services.gm.add_item(body.get("pin"), body.get("item")))


@bp.post("/patch")
def gm_patch():
    body = request.get_json(force=True) or {}
    return jsonify(services.gm.patch(body.get("pin"), body.get("patch")))
