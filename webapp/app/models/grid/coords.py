"""Koordinat sistemi ve yönler.

Harita 2 boyutludur: **X sütun, Y satırdır** ve dizi `map[y][x]` biçiminde
indekslenir. Y aşağı doğru büyür (ekrandaki satır sırası gibi), bu yüzden
kuzey `y - 1`, güney `y + 1`'dir.

Yönler burada tek yerde tanımlıdır: hareket algoritmasının ilk adımı ("hareket
yönünü al") bu tablodan okur, başka hiçbir modül yön vektörü hesaplamaz.
"""

from dataclasses import dataclass

from ..text import norm_tr


@dataclass(frozen=True)
class Direction:
    """Bir yön: adı ve (dx, dy) vektörü. Değişmezdir (frozen)."""

    name: str
    dx: int
    dy: int

    def apply(self, x: int, y: int):
        """Adım 2 — yeni koordinatı hesapla. O(1)."""
        return x + self.dx, y + self.dy


# Sekiz yön. Çapraz yönler de tek adımdır; hareket algoritması değişmez.
NORTH = Direction("kuzey", 0, -1)
SOUTH = Direction("güney", 0, 1)
EAST = Direction("doğu", 1, 0)
WEST = Direction("batı", -1, 0)
NORTHEAST = Direction("kuzeydoğu", 1, -1)
NORTHWEST = Direction("kuzeybatı", -1, -1)
SOUTHEAST = Direction("güneydoğu", 1, 1)
SOUTHWEST = Direction("güneybatı", -1, 1)

DIRECTIONS = (NORTH, SOUTH, EAST, WEST, NORTHEAST, NORTHWEST, SOUTHEAST, SOUTHWEST)

# Arayüzden/anlatıcıdan gelebilecek yazımlar. Tanınmayan değer None döner ve
# hareket "geçersiz yön" sonucuyla biter — sessizce yanlış yöne gidilmez.
_ALIASES = {}
for _d in DIRECTIONS:
    _ALIASES[norm_tr(_d.name)] = _d
_ALIASES.update({
    norm_tr(k): v for k, v in {
        "n": NORTH, "yukarı": NORTH, "yukari": NORTH, "up": NORTH, "north": NORTH,
        "s": SOUTH, "aşağı": SOUTH, "asagi": SOUTH, "down": SOUTH, "south": SOUTH,
        "e": EAST, "sağ": EAST, "sag": EAST, "right": EAST, "east": EAST,
        "w": WEST, "sol": WEST, "left": WEST, "west": WEST,
        "ne": NORTHEAST, "nw": NORTHWEST, "se": SOUTHEAST, "sw": SOUTHWEST,
    }.items()
})


def direction_of(value):
    """Serbest metni yöne çevirir; tanınmazsa None. O(1) (sözlük araması)."""
    if isinstance(value, Direction):
        return value
    if isinstance(value, (list, tuple)) and len(value) == 2:
        for d in DIRECTIONS:
            if (d.dx, d.dy) == (int(value[0]), int(value[1])):
                return d
        return None
    if not isinstance(value, str):
        return None
    return _ALIASES.get(norm_tr(value))
