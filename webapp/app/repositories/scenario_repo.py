"""Senaryo kaynağı.

`scenario.py`'deki değerler varsayılandır. `data/scenario_override.json` varsa
(arayüzden "senaryo içe aktar" ile yüklenir) onun içeriği önceliklidir —
sunucuyu yeniden başlatmadan senaryo değiştirilebilir.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SCENARIO_OVERRIDE_FILE = BASE_DIR / "data" / "scenario_override.json"

# Senaryo dosyasında bulunması gereken alanlar (dışa/içe aktarma sözleşmesi).
SCENARIO_FIELDS = ("scenario_text", "initial_world_state", "default_players",
                   "opening_hooks", "start_item_suggestions")


def scenario_defaults() -> dict:
    """`scenario.py` bir İÇERİK dosyasıdır — buradan sadece okunur.
    Import gecikmeli: senaryo yüklenmeden model/test kodu çalışabilsin."""
    from scenario import (
        SCENARIO_TEXT,
        INITIAL_WORLD_STATE,
        DEFAULT_PLAYERS,
        OPENING_HOOKS,
        START_ITEM_SUGGESTIONS,
    )
    return {
        "scenario_text": SCENARIO_TEXT,
        "initial_world_state": INITIAL_WORLD_STATE,
        "default_players": DEFAULT_PLAYERS,
        "opening_hooks": OPENING_HOOKS,
        "start_item_suggestions": START_ITEM_SUGGESTIONS,
    }


class ScenarioRepository:
    def __init__(self, override_file=None, defaults=None):
        self.override_file = Path(override_file) if override_file else SCENARIO_OVERRIDE_FILE
        self._defaults = defaults

    @property
    def has_override(self) -> bool:
        return self.override_file.exists()

    def defaults(self) -> dict:
        if self._defaults is None:
            self._defaults = scenario_defaults()
        return self._defaults

    def load(self) -> dict:
        """Yürürlükteki senaryo. Override dosyasında eksik/boş kalan alan
        varsayılana düşer — yarım bir dosya oyunu bozmasın."""
        defaults = self.defaults()
        if not self.has_override:
            return dict(defaults)
        with open(self.override_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {name: data.get(name) or defaults[name] for name in SCENARIO_FIELDS}

    def save(self, payload: dict) -> None:
        """Senaryo içe aktarma — eksik alanlar varsayılanla tamamlanır."""
        defaults = self.defaults()
        body = {name: payload.get(name) or defaults[name] for name in SCENARIO_FIELDS}
        self.override_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.override_file.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=2)
        tmp.replace(self.override_file)

    def reset_default(self) -> None:
        """Override'ı siler; senaryo `scenario.py`'ye geri döner."""
        if self.override_file.exists():
            self.override_file.unlink()

    def initial_world_state(self) -> dict:
        """Yeni oyunun başlangıç dünyası — her çağrıda taze kopya."""
        return json.loads(json.dumps(self.load()["initial_world_state"]))
