"""Harita üreteci içeriği — `data/places.json`.

Katalog gibi bu da SALT OKUNUR bir içerik dosyasıdır: şehir adları, ilçe
adları, kategori başına mekan adı şablonları ve yol türleri. Oyun başında
harita bundan üretilir (bkz. `models/mapgen.py`); oyun sırasında değişmez.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
PLACES_FILE = BASE_DIR / "data" / "places.json"


class PlacesRepository:
    def __init__(self, places_file=None):
        self.places_file = Path(places_file) if places_file else PLACES_FILE
        self._content = None
        self._mtime = None

    def load(self) -> dict:
        """İçerik sözlüğü. Bozuk/eksik dosya oyunu düşürmez: boş içerikle
        üreteç tek bir varsayılan şehir kurar ve oyun yine başlar."""
        try:
            mtime = self.places_file.stat().st_mtime
        except OSError:
            mtime = None
        if self._content is None or mtime != self._mtime:
            try:
                data = json.loads(self.places_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
            self._content = data if isinstance(data, dict) else {}
            self._mtime = mtime
        return self._content
