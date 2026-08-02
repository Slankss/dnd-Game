"""Senaryo ve oyun dışa/içe aktarma uçları."""

from flask import Blueprint, jsonify, request

from app import services

bp = Blueprint("scenario", __name__, url_prefix="/api")


@bp.get("/scenario/export")
def export_scenario():
    return jsonify(services.scenario.export_scenario())


@bp.post("/scenario/import")
def import_scenario():
    return jsonify(services.scenario.import_scenario(request.get_json(force=True) or {}))


@bp.post("/scenario/reset-default")
def reset_scenario_to_default():
    return jsonify(services.scenario.reset_scenario())


@bp.get("/game/export")
def export_game():
    return jsonify(services.scenario.export_game())


@bp.post("/game/import")
def import_game():
    return jsonify(services.scenario.import_game(request.get_json(force=True) or {}))
