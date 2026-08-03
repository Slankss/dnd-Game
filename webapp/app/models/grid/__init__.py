"""Izgara harita paketi — 2D (X, Y) koordinat sistemi.

Veri modeli:

    GridMap.grid : list[list[Cell]]   →  grid[y][x], her eleman bir Cell NESNESİ
    Cell         : kendi koordinatının zemini + o karede duranlar
    Entity       : kendi x/y'sini taşır; harita dizisine YAZILMAZ

Hareket `movement.move(grid_map, entity, direction)` ile yapılır ve sabit bir
sırayı izler (yön → koordinat → sınır → geçilebilirlik → kaldır → koordinat
güncelle → ekle → sonuç). Tüm adımlar O(1)'dir ve yalnızca iki hücreye
dokunulur.

Genişletme: yeni bir varlık türü `entities.py`'a bir sınıf + `KIND_TO_COLLECTION`
satırı olarak eklenir; hücre, harita ve hareket kodu değişmez.
"""

from .cell import Cell, COLLECTIONS, DEFAULT_TERRAIN, TERRAIN_PASSABLE
from .coords import DIRECTIONS, Direction, direction_of
from .entities import (
    Building,
    Entity,
    Item,
    KIND_BUILDING,
    KIND_ITEM,
    KIND_NPC,
    KIND_PLAYER,
    Npc,
    Player,
)
from .grid_map import GridMap
from .movement import (
    BAD_DIRECTION,
    BLOCKED,
    MoveResult,
    NOT_ON_MAP,
    OK,
    OUT_OF_BOUNDS,
    move,
)

__all__ = [
    "Cell", "COLLECTIONS", "DEFAULT_TERRAIN", "TERRAIN_PASSABLE",
    "Direction", "DIRECTIONS", "direction_of",
    "Entity", "Player", "Npc", "Item", "Building",
    "KIND_PLAYER", "KIND_NPC", "KIND_ITEM", "KIND_BUILDING",
    "GridMap", "move", "MoveResult",
    "OK", "BAD_DIRECTION", "OUT_OF_BOUNDS", "BLOCKED", "NOT_ON_MAP",
]
