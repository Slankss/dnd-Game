"""Tur bazlı akış uçları. Bu katman İNCE: gövdeyi ayrıştır, servisi çağır.

  POST /api/round/pick    — bir oyuncunun seçimi (zar orada atılır)
  POST /api/round/wait    — seçim yapmadan turda beklemek
  POST /api/round/commit  — turu kapat ve toplu gönder ('elle' | 'sure')

KİMLİK: hangi karakterin oynadığını OTURUM söyler. Oyuncu oturumunda
gövdedeki `player` alanı yok sayılır; yalnız tek ekran kipinde (masa
oturumu) gövdedeki karakter kullanılır.
"""

from flask import Blueprint, jsonify, request

from app import services
from app.api.guards import acting_player, player_required

bp = Blueprint("round", __name__, url_prefix="/api/round")


@bp.post("/pick")
@player_required
def pick():
    body = request.get_json(force=True) or {}
    return jsonify(services.rounds.pick(
        acting_player(body.get("player")), body.get("option_id"), body.get("text")))


@bp.post("/wait")
@player_required
def wait():
    body = request.get_json(force=True) or {}
    return jsonify(services.rounds.cancel(acting_player(body.get("player"))))


@bp.post("/commit")
@player_required
def commit():
    """"Turu Geç" — herhangi bir oyuncu basabilir, tur ortaktır."""
    body = request.get_json(force=True) or {}
    return jsonify(services.rounds.commit(
        body.get("reason") or "elle", body.get("round_no")))
