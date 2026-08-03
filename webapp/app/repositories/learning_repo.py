"""Öğrenme defteri — `data/learning.json` + `data/learning_events.jsonl`.

İki dosya, iki amaç:
  * `learning.json`        — özet defter (sayaçlar + dersler). Üzerine yazılır.
  * `learning_events.jsonl` — ham olay akışı, ekleme-yapılan. Asla silinmez;
    ileride daha iyi bir ders çıkarma yöntemi yazıldığında geçmişin tamamı
    yeniden işlenebilsin diye durur.
"""

import json
from pathlib import Path

from ..models.learning import DEFAULT_LEARNING, Learning

BASE_DIR = Path(__file__).resolve().parents[2]
LEARNING_FILE = BASE_DIR / "data" / "learning.json"
EVENTS_FILE = BASE_DIR / "data" / "learning_events.jsonl"


class LearningRepository:
    def __init__(self, learning_file=None, events_file=None):
        self.learning_file = Path(learning_file) if learning_file else LEARNING_FILE
        self.events_file = Path(events_file) if events_file else EVENTS_FILE

    # ------------------------------------------------------------- okuma
    def load_raw(self) -> dict:
        if not self.learning_file.exists():
            return json.loads(json.dumps(DEFAULT_LEARNING))
        try:
            data = json.loads(self.learning_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return json.loads(json.dumps(DEFAULT_LEARNING))
        return data if isinstance(data, dict) else json.loads(json.dumps(DEFAULT_LEARNING))

    def load(self) -> Learning:
        return Learning.from_dict(self.load_raw())

    # ------------------------------------------------------------- yazma
    def save(self, store) -> None:
        """Atomik yazma — yarım kalan bir yazma defteri bozmasın."""
        body = store.to_dict() if isinstance(store, Learning) else store
        self.learning_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.learning_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.learning_file)

    def append_event(self, event: dict) -> None:
        self.events_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def read_events(self, limit: int = None) -> list:
        if not self.events_file.exists():
            return []
        rows = []
        with open(self.events_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows[-limit:] if limit else rows
