"""Hareket algoritması.

Sıra SABİTTİR ve bu dosyada birebir uygulanır:

    1. Hareket yönünü al.
    2. Yeni koordinatı hesapla.
    3. Harita sınırlarını kontrol et.
    4. Hedef hücrenin geçilebilir olup olmadığını kontrol et.
    5. Varlığı mevcut hücreden kaldır.
    6. Varlığın koordinatını güncelle.
    7. Varlığı hedef hücreye ekle.
    8. Hareket sonucunu döndür.

Her adım O(1)'dir: yön sözlükten okunur, hücreye dizi indeksiyle erişilir,
koleksiyon işlemleri sözlük ekleme/çıkarmadır. Harita üzerindeki DİĞER
hücrelere dokunulmaz — yalnız kaynak ve hedef hücre değişir.

Başarısız bir hareket haritayı HİÇ değiştirmez: 3. ve 4. adımdaki kontroller
5. adımdan (kaldırma) önce yapılır, yani yarım kalmış bir taşıma oluşamaz.
"""

from dataclasses import dataclass, field

from .coords import direction_of

# Sonuç kodları — arayüz ve anlatıcı metni bunlara bakar.
OK = "tamam"
BAD_DIRECTION = "geçersiz_yön"
OUT_OF_BOUNDS = "sınır_dışı"
BLOCKED = "geçilemez"
NOT_ON_MAP = "haritada_değil"


@dataclass
class MoveResult:
    """8. adım — hareketin sonucu."""

    ok: bool
    reason: str
    entity_id: str = ""
    direction: str = ""
    from_x: int = 0
    from_y: int = 0
    to_x: int = 0
    to_y: int = 0
    # Geçilemedi ise engelin ne olduğu (bina/NPC adı ya da zemin türü).
    blocked_by: str = ""
    # Hedef karede karşılaşılanlar — savaş/etkileşim sistemleri bunu kullanır.
    met: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "reason": self.reason, "entity_id": self.entity_id,
                "direction": self.direction,
                "from": {"x": self.from_x, "y": self.from_y},
                "to": {"x": self.to_x, "y": self.to_y},
                "blocked_by": self.blocked_by, "met": self.met}


def move(grid_map, entity, direction) -> MoveResult:
    """Bir varlığı bir kare hareket ettirir.

    @param grid_map GridMap
    @param entity   Entity ya da varlık kimliği
    @param direction "kuzey" | "n" | Direction | (dx, dy)
    """
    # --- 1) Hareket yönünü al ------------------------------------------------
    yon = direction_of(direction)
    if isinstance(entity, str):
        entity = grid_map.entity(entity)
    if entity is None:
        return MoveResult(False, NOT_ON_MAP, direction=str(direction))
    if yon is None:
        return MoveResult(False, BAD_DIRECTION, entity_id=entity.id,
                          direction=str(direction),
                          from_x=entity.x, from_y=entity.y,
                          to_x=entity.x, to_y=entity.y)

    baslangic_x, baslangic_y = entity.x, entity.y

    # --- 2) Yeni koordinatı hesapla -----------------------------------------
    hedef_x, hedef_y = yon.apply(baslangic_x, baslangic_y)

    # --- 3) Harita sınırlarını kontrol et -----------------------------------
    if not grid_map.in_bounds(hedef_x, hedef_y):
        return MoveResult(False, OUT_OF_BOUNDS, entity_id=entity.id,
                          direction=yon.name,
                          from_x=baslangic_x, from_y=baslangic_y,
                          to_x=hedef_x, to_y=hedef_y,
                          blocked_by="harita sınırı")

    hedef_hucre = grid_map.grid[hedef_y][hedef_x]

    # --- 4) Hedef hücre geçilebilir mi --------------------------------------
    if not hedef_hucre.is_passable:
        engel = hedef_hucre.blocking_entity()
        return MoveResult(False, BLOCKED, entity_id=entity.id,
                          direction=yon.name,
                          from_x=baslangic_x, from_y=baslangic_y,
                          to_x=hedef_x, to_y=hedef_y,
                          blocked_by=(engel.name or engel.id) if engel
                          else hedef_hucre.terrain)

    # --- 5) Varlığı mevcut hücreden kaldır ----------------------------------
    mevcut_hucre = grid_map.cell(baslangic_x, baslangic_y)
    if mevcut_hucre is not None:
        mevcut_hucre.remove(entity)

    # --- 6) Varlığın koordinatını güncelle ----------------------------------
    entity.x, entity.y = hedef_x, hedef_y
    grid_map.entities[entity.id] = entity

    # --- 7) Varlığı hedef hücreye ekle --------------------------------------
    hedef_hucre.add(entity)

    # --- 8) Hareket sonucunu döndür -----------------------------------------
    return MoveResult(True, OK, entity_id=entity.id, direction=yon.name,
                      from_x=baslangic_x, from_y=baslangic_y,
                      to_x=hedef_x, to_y=hedef_y,
                      met=[e.name or e.id for e in hedef_hucre.entities()
                           if e.id != entity.id])
