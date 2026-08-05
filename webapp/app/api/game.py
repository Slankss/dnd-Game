"""Oyun uçları. Bu katman İNCE: gövdeyi ayrıştır, servisi çağır, döndür.

İş kuralı, doğrulama ve hata mesajı servis katmanına aittir; buradaki her
fonksiyon birkaç satır olmalı.

YETKİ: kurulum, başlatma, ayar ve sıfırlama ANLATICIYA aittir — dışarı açık
bir sunucuda giren herkesin oyunu sıfırlayabilmesi kabul edilemez. Hamle
yapan uçlar kimliği oturumdan okur (bkz. api/guards).
"""

from flask import Blueprint, jsonify, request

from app import services
from app.api.guards import acting_player, gm_required, login_required, player_required

bp = Blueprint("game", __name__, url_prefix="/api")


@bp.get("/state")
@login_required
def get_state():
    return jsonify(services.game.snapshot(request.args.get("since")))


@bp.get("/items")
@login_required
def get_items():
    """Sabit eşya kataloğu — her oyunda aynıdır, salt okunur."""
    return jsonify(services.items.public_catalog())


@bp.post("/setup-characters")
@gm_required
def setup_characters():
    body = request.get_json(force=True) or {}
    return jsonify(services.game.setup_characters(body.get("players")))


@bp.post("/start")
@gm_required
def start_game():
    return jsonify(services.game.start())


@bp.post("/message")
@player_required
def post_message():
    """SADECE karakter oluşturma turları. Kimin yazdığını oturum söyler;
    tek ekran kipinde gövdedeki karakter kullanılır."""
    body = request.get_json(force=True) or {}
    return jsonify(services.turn.play(acting_player(body.get("player")),
                                      body.get("text")))


@bp.post("/takeover")
@gm_required
def takeover_character():
    """Ölen karakterin oyuncusu bir NPC'yi devralır — anlatıcı yürütür."""
    body = request.get_json(force=True) or {}
    return jsonify(services.turn.takeover(body.get("dead_player"), body.get("new_character")))


@bp.post("/finish-chargen")
@gm_required
def finish_chargen():
    return jsonify(services.game.finish_chargen())


@bp.post("/settings")
@gm_required
def update_settings():
    body = request.get_json(force=True) or {}
    return jsonify(services.game.update_settings(body))


@bp.post("/reset")
@gm_required
def reset_state():
    body = request.get_json(silent=True) or {}
    # Öğrenme defteri varsayılan olarak korunur (bkz. GameService.reset).
    return jsonify(services.game.reset(keep_learning=body.get("keep_learning", True)))
