"""Senaryo ve oyun dışa/içe aktarma uçları — hepsi ANLATICIYA ait.

Senaryo metni oyunun gizli motorudur, oyun kaydı ise dünyanın tamamıdır:
ikisi de oyuncuya açık olamaz.
"""

from flask import Blueprint, jsonify, request

from app import services
from app.api.guards import gm_required

bp = Blueprint("scenario", __name__, url_prefix="/api")


@bp.get("/scenario/export")
@gm_required
def export_scenario():
    return jsonify(services.scenario.export_scenario())


@bp.post("/scenario/import")
@gm_required
def import_scenario():
    return jsonify(services.scenario.import_scenario(request.get_json(force=True) or {}))


@bp.post("/scenario/reset-default")
@gm_required
def reset_scenario_to_default():
    return jsonify(services.scenario.reset_scenario())


@bp.get("/game/export")
@gm_required
def export_game():
    return jsonify(services.scenario.export_game())


@bp.post("/game/import")
@gm_required
def import_game():
    return jsonify(services.scenario.import_game(request.get_json(force=True) or {}))
