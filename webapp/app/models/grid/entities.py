"""Haritada duran varlıklar: oyuncu, NPC, eşya, bina.

Kural (ÇOK ÖNEMLİ): **oyuncu harita dizisine yazılmaz.** Dizi yalnızca `Cell`
nesneleri tutar; oyuncunun kendi `x`/`y` koordinatı vardır ve bulunduğu
hücrenin `players` koleksiyonunda durur. Aynısı NPC, eşya ve bina için de
geçerlidir. Böylece:

  * bir varlığın yeri tek yerden okunur (kendi x/y'si),
  * bir hücrede kimin olduğu tek yerden okunur (hücrenin koleksiyonu),
  * hareket ederken haritanın tamamı değil, iki hücre dokunulur.

Yeni sistemler (görev, savaş, ticaret) buraya yeni bir `Entity` türü ekleyerek
büyür: `KIND_TO_COLLECTION`'a bir satır yazmak yeterlidir.
"""

from dataclasses import dataclass, field

# Varlık türleri — her biri hücrede AYRI bir koleksiyonda durur.
KIND_PLAYER = "player"
KIND_NPC = "npc"
KIND_ITEM = "item"
KIND_BUILDING = "building"

# Tür → hücredeki koleksiyon adı. Tanınmayan tür `others`'a düşer; böylece
# ileride eklenecek türler (tuzak, görev işareti, araç) kodu kırmaz.
KIND_TO_COLLECTION = {
    KIND_PLAYER: "players",
    KIND_NPC: "npcs",
    KIND_ITEM: "items",
    KIND_BUILDING: "buildings",
}
DEFAULT_COLLECTION = "others"


def collection_of(kind: str) -> str:
    return KIND_TO_COLLECTION.get(kind, DEFAULT_COLLECTION)


@dataclass
class Entity:
    """Haritadaki her şeyin ortak gövdesi.

    `id` hücre koleksiyonlarında anahtar olarak kullanılır: ekleme/çıkarma
    sözlük işlemidir, yani O(1).
    """

    id: str
    name: str = ""
    kind: str = KIND_PLAYER
    x: int = 0
    y: int = 0
    # Geçişi engelliyor mu (bina, kapalı kapı, ağır enkaz). Hücrenin
    # geçilebilirlik sayacı bunu kullanır — kontrol yine O(1) kalır.
    blocking: bool = False
    # Türe özel serbest alanlar (envanter, sağlık, görev durumu...). İleride
    # eklenecek sistemler modeli değiştirmeden buraya yazabilir.
    data: dict = field(default_factory=dict)

    @property
    def collection(self) -> str:
        return collection_of(self.kind)

    @property
    def position(self):
        return self.x, self.y

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind,
                "x": int(self.x), "y": int(self.y), "blocking": bool(self.blocking),
                "data": self.data}

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        data = data or {}
        kind = str(data.get("kind") or KIND_PLAYER)
        model = KIND_TO_CLASS.get(kind, cls)
        return model(
            id=str(data.get("id") or data.get("name") or ""),
            name=str(data.get("name") or ""),
            kind=kind,
            x=int(data.get("x") or 0),
            y=int(data.get("y") or 0),
            blocking=bool(data.get("blocking")),
            data=data.get("data") if isinstance(data.get("data"), dict) else {},
        )


@dataclass
class Player(Entity):
    """Oyuncu karakteri. Kadro adıyla eşleşir (`id` = karakter adı)."""

    kind: str = KIND_PLAYER


@dataclass
class Npc(Entity):
    kind: str = KIND_NPC


@dataclass
class Item(Entity):
    """Yerdeki eşya. Alınınca haritadan kaldırılır, envantere geçer."""

    kind: str = KIND_ITEM


@dataclass
class Building(Entity):
    """Bina/yapı. Varsayılan olarak geçişi engeller."""

    kind: str = KIND_BUILDING
    blocking: bool = True


KIND_TO_CLASS = {
    KIND_PLAYER: Player,
    KIND_NPC: Npc,
    KIND_ITEM: Item,
    KIND_BUILDING: Building,
}
