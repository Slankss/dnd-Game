"""Senaryo ve oyun dışa/içe aktarma.

Senaryo değiştirmek oyunu baştan başlatır (eski dünya durumu yeni senaryoda
geçerli değildir); oyun içe aktarmak ise dünya durumunu/geçmişi korur ama
Claude oturumunu tazeler.
"""

from scenario import DEFAULT_PLAYERS, OPENING_HOOKS, START_ITEM_SUGGESTIONS

from app.errors import ValidationError
from app.repositories import log_repo
from app.repositories.scenario_repo import ScenarioRepository
from app.repositories.state_repo import LOCK, StateRepository
from app.serializers import public_world_state


class ScenarioService:
    """`/api/scenario/*` ve `/api/game/*`."""

    def __init__(self, state_repo=None, scenario_repo=None, game_log=None, gm_log=None):
        self.scenario_repo = scenario_repo or ScenarioRepository()
        self.state_repo = state_repo or StateRepository(scenario_repo=self.scenario_repo)
        self.game_log = game_log or log_repo.game_log()
        self.gm_log = gm_log or log_repo.gm_log()

    # ------------------------------------------------------- senaryo dışa/içe
    def export_scenario(self) -> dict:
        return self.scenario_repo.load()

    def import_scenario(self, body: dict) -> dict:
        body = body or {}
        if not isinstance(body.get("scenario_text"), str) or not body["scenario_text"].strip():
            raise ValidationError("Geçersiz senaryo dosyası: 'scenario_text' eksik.")
        if not isinstance(body.get("initial_world_state"), dict):
            raise ValidationError("Geçersiz senaryo dosyası: 'initial_world_state' eksik.")

        payload = {
            "scenario_text": body["scenario_text"],
            "initial_world_state": body["initial_world_state"],
            "default_players": body.get("default_players") or DEFAULT_PLAYERS,
            "opening_hooks": body.get("opening_hooks") or OPENING_HOOKS,
            "start_item_suggestions": body.get("start_item_suggestions") or START_ITEM_SUGGESTIONS,
        }
        with LOCK:
            self.scenario_repo.save(payload)
            # yeni senaryo = oyun baştan başlar (eski dünya durumu artık geçerli değil)
            state = self.state_repo.default_state()
            self.state_repo.save(state)
            self.game_log.clear()
            self.gm_log.clear()
        return {"ok": True}

    def reset_scenario(self) -> dict:
        with LOCK:
            self.scenario_repo.reset_default()
            state = self.state_repo.default_state()
            self.state_repo.save(state)
            self.game_log.clear()
            self.gm_log.clear()
        return {"ok": True}

    # ---------------------------------------------------------- oyun dışa/içe
    def export_game(self) -> dict:
        with LOCK:
            state = self.state_repo.load()
            log = self.game_log.read()
            gm_log = self.gm_log.read()
        return {"state": state, "log": log, "gm_log": gm_log}

    def import_game(self, body: dict) -> dict:
        body = body or {}
        imported_state = body.get("state")
        imported_log = body.get("log")
        if not isinstance(imported_state, dict) or "world_state" not in imported_state:
            raise ValidationError("Geçersiz oyun dosyası: 'state.world_state' eksik.")
        if not isinstance(imported_log, list):
            raise ValidationError("Geçersiz oyun dosyası: 'log' bir liste olmalı.")

        with LOCK:
            base = self.state_repo.default_state()
            base.update(imported_state)
            # Oturum ID'si başka bir bilgisayarda/durumda geçerli olmayabilir —
            # her içe aktarma güvenle yeni bir Claude oturumuyla devam etsin diye
            # her zaman sıfırlanır. Dünya durumu/envanter/ilişkiler/geçmiş korunur.
            base["session_id"] = None
            max_id = max([e.get("id", 0) for e in imported_log if isinstance(e, dict)], default=0)
            base["next_id"] = max(base.get("next_id", 1), max_id + 1)
            self.state_repo.save(base)

            self.game_log.replace(imported_log)

            imported_gm_log = body.get("gm_log")
            if isinstance(imported_gm_log, list):
                self.gm_log.replace(imported_gm_log)

        return {
            "ok": True,
            "world_state": public_world_state(base["world_state"]),
            "started": base["started"],
            "characters_confirmed": base["characters_confirmed"],
        }
