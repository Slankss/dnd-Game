"""Sabit eşya kataloğu — `data/items.json`.

Diğer depoların aksine bu depo SALT OKUNURDUR: katalog oyunun içeriğidir,
durumu değil. `/api/reset` onu silmez, tur akışı onu değiştirmez. Bu yüzden
bir kez okunup bellekte tutulur (dosya değişirse `reload()` çağrılır).
"""

import json
from pathlib import Path

from ..models.items import ItemCatalog

BASE_DIR = Path(__file__).resolve().parents[2]
ITEMS_FILE = BASE_DIR / "data" / "items.json"


class ItemsRepository:
    def __init__(self, items_file=None):
        self.items_file = Path(items_file) if items_file else ITEMS_FILE
        self._catalog = None
        self._mtime = None

    def load_raw(self) -> dict:
        """Bozuk/eksik katalog oyunu düşürmez: boş katalogla devam edilir
        (arama sonuç vermez, hikaye eşyaları çalışmaya devam eder)."""
        if not self.items_file.exists():
            return {}
        try:
            data = json.loads(self.items_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def load(self) -> ItemCatalog:
        """Katalog — dosya değişmediyse bellekten."""
        try:
            mtime = self.items_file.stat().st_mtime
        except OSError:
            mtime = None
        if self._catalog is None or mtime != self._mtime:
            self._catalog = ItemCatalog(self.load_raw())
            self._mtime = mtime
        return self._catalog

    def reload(self) -> ItemCatalog:
        self._catalog = None
        return self.load()
