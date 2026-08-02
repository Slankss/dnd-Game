"""Günlük dosyaları (JSONL).

  * `game_log.jsonl` — kalıcı, ekleme-yapılan (append-only) oyun geçmişi.
    state.json sadece güncel dünya durumunu tutar; tüm oynanış geçmişi burada.
  * `gm_log.jsonl`   — anlatıcının /secrets ekranından gönderdiği gizli
    yönetmen notları + model yanıtları; oyunculara asla gösterilmez.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
LOG_FILE = BASE_DIR / "data" / "game_log.jsonl"
GM_LOG_FILE = BASE_DIR / "data" / "gm_log.jsonl"


class JsonlLogRepository:
    """Satır başına bir JSON nesnesi tutan günlük."""

    def __init__(self, path=None):
        self.path = Path(path) if path else LOG_FILE

    def append(self, entry: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read(self) -> list:
        if not self.path.exists():
            return []
        entries = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # bozuk satır oyunu düşürmesin
        return entries

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def replace(self, entries) -> None:
        """Dosyayı baştan yazar — oyun içe aktarmada kullanılır."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            for entry in entries or []:
                if isinstance(entry, dict):
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def game_log(path=None) -> JsonlLogRepository:
    return JsonlLogRepository(path or LOG_FILE)


def gm_log(path=None) -> JsonlLogRepository:
    return JsonlLogRepository(path or GM_LOG_FILE)
