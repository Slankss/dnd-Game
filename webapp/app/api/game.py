"""Oyun uçları. Bu katman İNCE: gövdeyi ayrıştır, servisi çağır, döndür.

İş kuralı, doğrulama ve hata mesajı servis katmanına aittir; buradaki her
fonksiyon birkaç satır olmalı.
"""

from flask import Blueprint, jsonify, request

from app import services

bp = Blueprint("game", __name__, url_prefix="/api")


@bp.get("/state")
def get_state():
    return jsonify(services.game.snapshot(request.args.get("since")))


@bp.get("/items")
def get_items():
    """Sabit eşya kataloğu — her oyunda aynıdır, salt okunur."""
    return jsonify(services.items.public_catalog())


@bp.post("/setup-characters")
def setup_characters():
    body = request.get_json(force=True) or {}
    return jsonify(services.game.setup_characters(body.get("players")))


@bp.post("/start")
def start_game():
    return jsonify(services.game.start())


@bp.post("/message")
def post_message():
    body = request.get_json(force=True) or {}
    return jsonify(services.turn.play(body.get("player"), body.get("text")))


@bp.post("/takeover")
def takeover_character():
    body = request.get_json(force=True) or {}
    return jsonify(services.turn.takeover(body.get("dead_player"), body.get("new_character")))


@bp.post("/finish-chargen")
def finish_chargen():
    return jsonify(services.game.finish_chargen())


@bp.post("/settings")
def update_settings():
    body = request.get_json(force=True) or {}
    return jsonify(services.game.update_settings(body))


@bp.post("/reset")
def reset_state():
    body = request.get_json(silent=True) or {}
    # Öğrenme defteri varsayılan olarak korunur (bkz. GameService.reset).
    return jsonify(services.game.reset(keep_learning=body.get("keep_learning", True)))
