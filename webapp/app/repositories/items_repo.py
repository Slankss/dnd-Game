"""Sabit eşya kataloğu — `data/items.json`.

Katalog oyunun İÇERİĞİDİR, durumu değil: `/api/reset` onu silmez, tur akışı
onu değiştirmez, her oyun aynı katalogla başlar. Bu yüzden bir kez okunup
bellekte tutulur (dosya değişirse kendiliğinden yeniden okunur).

Tek yazma yolu anlatıcı ekranıdır: GM yeni bir eşya eklediğinde kayıt bu
dosyaya yazılır ve o andan itibaren TÜM OYUNLAR için geçerli olur — eklenen
eşya kalıcıdır, oyuna değil oyunun kendisine aittir.
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

    # -------------------------------------------------------------- yazma
    def save_raw(self, data: dict) -> None:
        """Atomik yazma: yarım kalan bir yazma katalogu bozmasın.

        Katalog nadiren ve yalnız anlatıcı ekranından değişir; yazdıktan sonra
        bellek kopyası düşürülür ki sonraki okuma dosyadan gelsin."""
        self.items_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.items_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        tmp.replace(self.items_file)
        self._catalog = None
        self._mtime = None

    def append_item(self, item: dict) -> dict:
        """Katalogun sonuna yeni bir eşya ekler ve diske yazar.

        Dönen: eklenen kayıt (id atanmış haliyle). Çağıran doğrulamayı yapmış
        olmalı (`ItemsService.add_item`)."""
        data = self.load_raw()
        esyalar = data.get("esyalar")
        if not isinstance(esyalar, list):
            esyalar = data["esyalar"] = []
        esyalar.append(item)
        self.save_raw(data)
        return item
