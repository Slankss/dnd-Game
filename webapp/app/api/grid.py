"""Kare harita uçları. Bu katman İNCE: gövdeyi ayrıştır, servisi çağır.

  GET  /api/grid        — sahnenin güncel ızgarası (yoksa kurulur)
  POST /api/grid/move   — bir oyuncu karakterini bir kare hareket ettirir
"""

from flask import Blueprint, jsonify, request

from app import services

bp = Blueprint("grid", __name__, url_prefix="/api/grid")


@bp.get("")
def get_grid():
    return jsonify(services.grid.snapshot())


@bp.post("/move")
def move():
    body = request.get_json(force=True) or {}
    return jsonify(services.grid.move(body.get("player"), body.get("direction")))
