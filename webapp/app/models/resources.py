"""Grup stoğu — kategori > kalem > miktar.

Kişisel envanterden ayrıdır: burası deponun kendisi,
`characters.<isim>.inventory` ise üzerinde taşınan şeyler.
"""

import re
from dataclasses import dataclass, field

from .base import DictModel
from .text import canonical_name

# "+3" / "-12" gibi göreli miktar değişimleri
RESOURCE_DELTA_RE = re.compile(r"^\s*([+-])\s*(\d+(?:[.,]\d+)?)\s*$")


def as_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def tidy_qty(value):
    """3.0 -> 3, 2.5 -> 2.5, negatif -> 0 (stok eksiye düşemez)."""
    if value is None:
        return 0
    value = max(0, value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _delta(text, current):
    """"+9" / "-2" -> yeni miktar; göreli değişim değilse None."""
    m = RESOURCE_DELTA_RE.match(text)
    if not m:
        return None
    delta = float(m.group(2).replace(",", "."))
    return tidy_qty(current + (delta if m.group(1) == "+" else -delta))


@dataclass
class ResourceItem(DictModel):
    """Tek bir stok kalemi: {"qty": .., "unit": .., "notes": ..}."""

    KNOWN = ("qty", "unit", "notes")

    qty: object = None
    unit: object = None
    notes: object = None
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ResourceItem":
        data = data or {}
        item = cls()
        item.extra, item.key_order = cls._split(data)
        for name in cls.KNOWN:
            setattr(item, name, data.get(name))
        return item

    @classmethod
    def new(cls) -> "ResourceItem":
        item = cls(qty=0, unit="adet", notes="")
        item.key_order = list(cls.KNOWN)
        return item

    def to_dict(self) -> dict:
        return self._emit({name: getattr(self, name) for name in self.KNOWN})

    def apply_value(self, value) -> None:
        """Kalem değeri üç şekilde gelebilir: kesin sayı (12), göreli değişim
        ("-2"/"+9") ya da detaylı sözlük ({"qty": .., "unit": .., "notes": ..})."""
        current = as_number(self.qty) or 0
        num = as_number(value)
        if num is not None:
            self._set("qty", tidy_qty(num))
        elif isinstance(value, str):
            new_qty = _delta(value, current)
            if new_qty is not None:
                self._set("qty", new_qty)
            else:
                self._set("notes", value)  # "birkaç kutu" gibi serbest metin
        elif isinstance(value, dict):
            qty = value.get("qty")
            qty_num = as_number(qty)
            if qty_num is not None:
                self._set("qty", tidy_qty(qty_num))
            elif isinstance(qty, str):
                new_qty = _delta(qty, current)
                if new_qty is not None:
                    self._set("qty", new_qty)
            for name in ("unit", "notes"):
                if isinstance(value.get(name), str):
                    self._set(name, value[name])


class ResourcePool:
    """`world_state.resources` — kategori sözlüğü. Kategori/kalem sırası
    kayıttaki gibi korunur (sözlükler eklenme sırasını tutar)."""

    def __init__(self, categories=None):
        self.categories = categories or {}

    @classmethod
    def from_dict(cls, data: dict) -> "ResourcePool":
        pool = cls()
        for category, items in (data or {}).items():
            if not isinstance(items, dict):
                pool.categories[category] = items  # tanınmayan biçim: aynen taşı
                continue
            pool.categories[category] = {
                name: (ResourceItem.from_dict(raw) if isinstance(raw, dict) else raw)
                for name, raw in items.items()
            }
        return pool

    def to_dict(self) -> dict:
        out = {}
        for category, items in self.categories.items():
            if not isinstance(items, dict):
                out[category] = items
                continue
            out[category] = {
                name: (item.to_dict() if isinstance(item, ResourceItem) else item)
                for name, item in items.items()
            }
        return out

    @property
    def has_stock(self) -> bool:
        """Grubun gerçekten bir deposu var mı (boş kategoriler sayılmaz)."""
        return any(isinstance(items, dict) and items
                   for items in self.categories.values())

    def merge_patch(self, patch: dict) -> None:
        """Aynı kategori/kalem farklı büyük-küçük harfle yazılırsa ikinci bir
        kayıt açılmaz — mevcut anahtara yazılır (`canonical_name`)."""
        for category, items in (patch or {}).items():
            if not isinstance(items, dict):
                continue
            cat_key = canonical_name(self.categories, category) or category
            cat = self.categories.setdefault(cat_key, {})
            if not isinstance(cat, dict):
                continue
            for raw_name, value in items.items():
                item_key = canonical_name(cat, raw_name) or raw_name
                entry = cat.get(item_key)
                if not isinstance(entry, ResourceItem):
                    entry = cat[item_key] = ResourceItem.new()
                entry.apply_value(value)
