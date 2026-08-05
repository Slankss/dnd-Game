"""Kare harita uçları. Bu katman İNCE: gövdeyi ayrıştır, servisi çağır.

  GET  /api/grid        — sahnenin güncel ızgarası (yoksa kurulur)
  POST /api/grid/move   — bir oyuncu karakterini bir kare hareket ettirir

Hareket eden karakteri OTURUM belirler (bkz. api/guards.acting_player).
"""

from flask import Blueprint, jsonify, request

from app import services
from app.api.guards import acting_player, login_required, player_required

bp = Blueprint("grid", __name__, url_prefix="/api/grid")


@bp.get("")
@login_required
def get_grid():
    return jsonify(services.grid.snapshot())


@bp.post("/move")
@player_required
def move():
    body = request.get_json(force=True) or {}
    return jsonify(services.grid.move(acting_player(body.get("player")),
                                      body.get("direction")))
