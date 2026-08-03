"""Tur bazlı akış uçları. Bu katman İNCE: gövdeyi ayrıştır, servisi çağır.

  POST /api/round/pick    — bir oyuncunun seçimi (zar orada atılır)
  POST /api/round/wait    — seçim yapmadan turda beklemek
  POST /api/round/commit  — turu kapat ve toplu gönder ('elle' | 'sure')
"""

from flask import Blueprint, jsonify, request

from app import services

bp = Blueprint("round", __name__, url_prefix="/api/round")


@bp.post("/pick")
def pick():
    body = request.get_json(force=True) or {}
    return jsonify(services.rounds.pick(
        body.get("player"), body.get("option_id"), body.get("text")))


@bp.post("/wait")
def wait():
    body = request.get_json(force=True) or {}
    return jsonify(services.rounds.cancel(body.get("player")))


@bp.post("/commit")
def commit():
    body = request.get_json(force=True) or {}
    return jsonify(services.rounds.commit(
        body.get("reason") or "elle", body.get("round_no")))
