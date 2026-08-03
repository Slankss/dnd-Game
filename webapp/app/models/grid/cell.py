"""Hücre (Cell) — haritanın tek bir koordinatı.

Harita dizisinin her elemanı primitif bir değer DEĞİL, bu nesnedir. Bir hücre
yalnızca KENDİ koordinatına ait bilgiyi tutar:

  * `terrain` / `passable` — zeminin kendisi
  * `players` / `npcs` / `items` / `buildings` / `others` — o karede duranlar

Koleksiyonlar sözlüktür (`{varlık_id: Entity}`): aynı karede birden fazla
oyuncu, NPC ve eşya bulunabilir, ekleme/çıkarma O(1)'dir.

Geçilebilirlik iki şeye bakar: zemin (`passable`) ve karede duran engelleyici
bir varlık olup olmadığı. İkincisi her seferinde koleksiyon taranarak değil,
ekleme/çıkarmada güncellenen bir SAYAÇLA (`blockers`) tutulur — kontrol O(1).
"""

from dataclasses import dataclass, field

from .entities import DEFAULT_COLLECTION, Entity, KIND_TO_COLLECTION

# Hücrede tutulan koleksiyonlar (sıra, serileştirmede de aynıdır).
COLLECTIONS = tuple(KIND_TO_COLLECTION.values()) + (DEFAULT_COLLECTION,)

# Zemin türleri — `passable` varsayılanını da belirler.
TERRAIN_PASSABLE = {
    "zemin": True,      # sıradan geçilebilir kare
    "yol": True,
    "moloz": True,      # geçilir ama yavaş (ileride hareket bedeli)
    "su": True,
    "çimen": True,
    "duvar": False,
    "enkaz": False,
    "uçurum": False,
    "boşluk": False,
}
DEFAULT_TERRAIN = "zemin"


@dataclass
class Cell:
    """`grid[y][x]` — tek bir koordinat."""

    x: int
    y: int
    terrain: str = DEFAULT_TERRAIN
    passable: bool = True
    # Karede duranlar. Anahtar varlık kimliği, değer varlığın kendisi.
    players: dict = field(default_factory=dict)
    npcs: dict = field(default_factory=dict)
    items: dict = field(default_factory=dict)
    buildings: dict = field(default_factory=dict)
    others: dict = field(default_factory=dict)
    # Karedeki engelleyici varlık sayısı (bina, kapalı kapı...). Geçilebilirlik
    # kontrolü bu sayaca bakar, koleksiyonları TARAMAZ.
    blockers: int = 0
    # Türe özel serbest alan (görev işareti, ışık, koku izi...).
    data: dict = field(default_factory=dict)

    # ------------------------------------------------------------ sorgular
    @property
    def is_passable(self) -> bool:
        """Zemin geçilebilir mi VE karede engelleyici varlık var mı — O(1)."""
        return bool(self.passable) and self.blockers == 0

    @property
    def is_empty(self) -> bool:
        return not any(getattr(self, name) for name in COLLECTIONS)

    def collection(self, name: str) -> dict:
        return getattr(self, name if name in COLLECTIONS else DEFAULT_COLLECTION)

    def contains(self, entity: Entity) -> bool:
        return entity.id in self.collection(entity.collection)

    def entities(self):
        """Karedeki tüm varlıklar (koleksiyon sırasıyla)."""
        for name in COLLECTIONS:
            yield from getattr(self, name).values()

    def blocking_entity(self):
        """Geçişi engelleyen ilk varlık — hareket sonucunda 'neden geçemedim'
        bilgisini vermek için. Yalnızca engel VARKEN çağrılır."""
        if not self.blockers:
            return None
        for entity in self.entities():
            if entity.blocking:
                return entity
        return None

    # ------------------------------------------------------------- yazma
    def add(self, entity: Entity) -> None:
        """Varlığı bu kareye ekler. O(1).

        Hücre varlığın koordinatını DEĞİŞTİRMEZ; koordinat varlığın kendi
        alanıdır ve hareket algoritmasının 6. adımında güncellenir."""
        target = self.collection(entity.collection)
        if entity.id in target:
            return
        target[entity.id] = entity
        if entity.blocking:
            self.blockers += 1

    def remove(self, entity: Entity) -> bool:
        """Varlığı bu kareden çıkarır. O(1). Karede yoksa False döner."""
        target = self.collection(entity.collection)
        if target.pop(entity.id, None) is None:
            return False
        if entity.blocking and self.blockers > 0:
            self.blockers -= 1
        return True

    # ---------------------------------------------------------- dönüşüm
    def to_dict(self) -> dict:
        """Kayıt biçimi: hücre yalnız ZEMİNİ yazar.

        Varlıklar burada TEKRARLANMAZ — haritanın varlık listesinde kendi
        x/y'leriyle dururlar ve yükleme sırasında hücrelere geri dağıtılırlar.
        Böylece tek gerçek kaynak korunur, kayıt da şişmez."""
        body = {"terrain": self.terrain, "passable": bool(self.passable)}
        if self.data:
            body["data"] = self.data
        return body

    @classmethod
    def from_dict(cls, x: int, y: int, data: dict) -> "Cell":
        data = data if isinstance(data, dict) else {}
        terrain = str(data.get("terrain") or DEFAULT_TERRAIN)
        passable = data.get("passable")
        if not isinstance(passable, bool):
            passable = TERRAIN_PASSABLE.get(terrain, True)
        return cls(x=x, y=y, terrain=terrain, passable=passable,
                   data=data.get("data") if isinstance(data.get("data"), dict) else {})
