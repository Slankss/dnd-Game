"""Seçenek havuzu — `data/options_pool.jsonl`.

Sunulan ve seçilen HER seçenek buraya düşer (ekleme-yapılan, asla silinmez):

  {"tip": "sunuldu", "tur": 12, "gun": 98, "player": "Okan",
   "category": "riskli", "text": "...", "ts": "..."}
  {"tip": "secildi",  "tur": 12, ..., "roll": 73, "band": "Güçlü Başarı"}

Havuz iki işe yarar: (1) öğrenme katmanı buradan besleniyor, (2) anlatıcıya
"bu masaya daha önce ne sunuldu, ne seçildi" özeti verilebiliyor — aynı üç
seçeneğin her turda tekrar etmesini bu engelliyor.
"""

import json
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
POOL_FILE = BASE_DIR / "data" / "options_pool.jsonl"

# Özet çıkarırken bakılan son kayıt sayısı.
RECENT = 400


class OptionsPoolRepository:
    def __init__(self, path=None):
        self.path = Path(path) if path else POOL_FILE

    def append(self, entry: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def append_many(self, entries) -> None:
        for entry in entries or []:
            self.append(entry)

    def read(self, limit: int = None) -> list:
        if not self.path.exists():
            return []
        rows = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows[-limit:] if limit else rows

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    # ------------------------------------------------------------- özet
    def recent_offered(self, player: str = None, limit: int = 12) -> list:
        """Son sunulan seçenek metinleri — anlatıcı tekrar etmesin diye."""
        rows = self.read(RECENT)
        texts = []
        for row in reversed(rows):
            if row.get("tip") != "sunuldu":
                continue
            if player and row.get("player") != player:
                continue
            text = (row.get("text") or "").strip()
            if text and text not in texts:
                texts.append(text)
            if len(texts) >= limit:
                break
        return texts

    def stats(self) -> dict:
        """Havuzun kaba istatistiği (anlatıcı ekranı için)."""
        rows = self.read()
        sunulan = [r for r in rows if r.get("tip") == "sunuldu"]
        secilen = [r for r in rows if r.get("tip") == "secildi"]
        return {
            "sunulan": len(sunulan),
            "secilen": len(secilen),
            "kategori_sunulan": dict(Counter(r.get("category") for r in sunulan if r.get("category"))),
            "kategori_secilen": dict(Counter(r.get("category") for r in secilen if r.get("category"))),
            "son_secimler": secilen[-10:],
        }
