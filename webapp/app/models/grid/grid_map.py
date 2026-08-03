"""Izgara harita — `grid[y][x]` biçiminde 2D dizi.

Veri modeli (sözleşme):

    grid: list[list[Cell]]        # satır listesi; her eleman bir Cell NESNESİ
    entities: dict[str, Entity]   # kimlik → varlık (O(1) erişim)

Oyuncular haritanın içine YAZILMAZ: her varlığın kendi `x`/`y`'si vardır,
bulunduğu karenin ilgili koleksiyonunda durur. Harita bunu iki taraflı tutar
(hücre → varlıklar, varlık → koordinat) ve iki taraf yalnızca `place`,
`remove_entity` ve `movement.move` üzerinden değişir.

Karmaşıklık: hücreye erişim dizi indeksi (O(1)), varlık ekleme/çıkarma sözlük
işlemi (O(1)). Hareket ederken haritanın geri kalanına DOKUNULMAZ.
"""

from dataclasses import dataclass, field

from .cell import Cell, DEFAULT_TERRAIN, TERRAIN_PASSABLE
from .entities import Entity, KIND_PLAYER

# Kayıt biçimi sürümü — ileride şema değişirse göç buradan okunur.
VERSION = 1


@dataclass
class GridMap:
    """Bir sahnenin/bölgenin kare haritası."""

    width: int = 0
    height: int = 0
    grid: list = field(default_factory=list)        # list[list[Cell]]
    entities: dict = field(default_factory=dict)    # {id: Entity}
    name: str = ""
    version: int = VERSION

    # -------------------------------------------------------------- kurulum
    @classmethod
    def blank(cls, width: int, height: int, name: str = "",
              terrain: str = DEFAULT_TERRAIN) -> "GridMap":
        """Boş harita: `height` satır × `width` sütun Cell nesnesi."""
        width, height = max(1, int(width)), max(1, int(height))
        passable = TERRAIN_PASSABLE.get(terrain, True)
        grid = [
            [Cell(x=x, y=y, terrain=terrain, passable=passable) for x in range(width)]
            for y in range(height)
        ]
        return cls(width=width, height=height, grid=grid, name=name)

    # -------------------------------------------------------------- sorgular
    def in_bounds(self, x: int, y: int) -> bool:
        """Adım 3 — harita sınırları içinde mi. O(1)."""
        return 0 <= x < self.width and 0 <= y < self.height

    def cell(self, x: int, y: int):
        """Koordinattaki hücre; sınır dışında None. O(1)."""
        if not self.in_bounds(x, y):
            return None
        return self.grid[y][x]

    def is_passable(self, x: int, y: int) -> bool:
        """Adım 4 — hedef hücre geçilebilir mi. O(1)."""
        cell = self.cell(x, y)
        return bool(cell and cell.is_passable)

    def entity(self, entity_id: str):
        return self.entities.get(entity_id)

    def players(self) -> list:
        return [e for e in self.entities.values() if e.kind == KIND_PLAYER]

    def cell_of(self, entity: Entity):
        """Varlığın ŞU AN durduğu hücre (kendi koordinatından). O(1)."""
        return self.cell(entity.x, entity.y)

    # --------------------------------------------------------------- yazma
    def place(self, entity: Entity, x: int = None, y: int = None) -> bool:
        """Varlığı haritaya koyar (ya da başka bir kareye taşır).

        Hareket algoritmasının dışında kullanılır: doğuş (spawn), ışınlanma,
        yeni bina/eşya bırakma. Adım sırası hareketle aynıdır: önce eski
        kareden çıkar, sonra koordinatı yaz, sonra yeni kareye ekle."""
        hedef_x = entity.x if x is None else int(x)
        hedef_y = entity.y if y is None else int(y)
        if not self.in_bounds(hedef_x, hedef_y):
            return False

        onceki = self.cell_of(entity)
        if onceki is not None:
            onceki.remove(entity)

        entity.x, entity.y = hedef_x, hedef_y
        self.entities[entity.id] = entity
        self.grid[hedef_y][hedef_x].add(entity)
        return True

    def remove_entity(self, entity) -> bool:
        """Varlığı haritadan tamamen kaldırır (ölüm, eşyanın alınması). O(1)."""
        if isinstance(entity, str):
            entity = self.entities.get(entity)
        if entity is None:
            return False
        cell = self.cell_of(entity)
        if cell is not None:
            cell.remove(entity)
        self.entities.pop(entity.id, None)
        return True

    def set_terrain(self, x: int, y: int, terrain: str, passable=None) -> bool:
        """Zemini değiştirir (barikat kurmak, duvar yıkmak). O(1)."""
        cell = self.cell(x, y)
        if cell is None:
            return False
        cell.terrain = terrain
        cell.passable = (TERRAIN_PASSABLE.get(terrain, True)
                         if passable is None else bool(passable))
        return True

    # ------------------------------------------------------------- dönüşüm
    def to_dict(self) -> dict:
        """Kayıt biçimi. Hücreler yalnız zemini, varlıklar kendi x/y'lerini
        taşır — oyuncu konumu dizinin içine YAZILMAZ."""
        return {
            "version": self.version,
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "cells": [[cell.to_dict() for cell in row] for row in self.grid],
            "entities": [e.to_dict() for e in self.entities.values()],
        }

    @classmethod
    def from_dict(cls, data) -> "GridMap":
        """Kayıttan kurar ve varlıkları kendi koordinatlarındaki hücrelere
        dağıtır (iki taraflı yapı yeniden kurulur)."""
        data = data if isinstance(data, dict) else {}
        width = int(data.get("width") or 0)
        height = int(data.get("height") or 0)
        rows = data.get("cells") if isinstance(data.get("cells"), list) else []
        if not width or not height:
            height = len(rows)
            width = len(rows[0]) if rows and isinstance(rows[0], list) else 0
        if not width or not height:
            return cls.blank(1, 1, name=str(data.get("name") or ""))

        grid = []
        for y in range(height):
            row = rows[y] if y < len(rows) and isinstance(rows[y], list) else []
            grid.append([
                Cell.from_dict(x, y, row[x] if x < len(row) else None)
                for x in range(width)
            ])

        world = cls(width=width, height=height, grid=grid,
                    name=str(data.get("name") or ""),
                    version=int(data.get("version") or VERSION))

        for raw in data.get("entities") or []:
            if not isinstance(raw, dict):
                continue
            entity = Entity.from_dict(raw)
            if not entity.id or not world.in_bounds(entity.x, entity.y):
                continue
            world.entities[entity.id] = entity
            world.grid[entity.y][entity.x].add(entity)
        return world
