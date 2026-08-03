"""Kare harita akışı: sahneyi kur, oyuncuyu hareket ettir.

Bu servis `app/models/grid` paketinin ÜSTÜNDE durur ve yalnızca sıralamayı
yapar: kilidi al → haritayı yükle → modeldeki hareket algoritmasını çağır →
kaydet. Hareketin kendisi (yön → koordinat → sınır → geçilebilirlik → kaldır →
koordinat güncelle → ekle → sonuç) `models/grid/movement.py`'dedir ve burada
tekrarlanmaz.

Sahne kurulumu:
  * ızgara, grubun bulunduğu yerin adıyla açılır (kenarları duvardır),
  * hayatta olan her oyuncu karakteri için bir `Player` varlığı doğar,
  * gruba katılmış NPC'ler `Npc` olarak eklenir.
Var olan varlıkların konumu KORUNUR — sahne her turda sıfırlanmaz.
"""

from app.errors import ValidationError
from app.models.grid import (
    GridMap,
    KIND_NPC,
    KIND_PLAYER,
    Npc,
    Player,
    direction_of,
    move,
)
from app.repositories.state_repo import LOCK, StateRepository
from app.serializers import public_world_state

# Varsayılan sahne ölçüsü (sütun × satır).
SCENE_WIDTH = 15
SCENE_HEIGHT = 11


class GridService:
    """`/api/grid/move` ve sahne kurulumu."""

    def __init__(self, state_repo=None):
        self.state_repo = state_repo or StateRepository()

    # ------------------------------------------------------------- kurulum
    def ensure_scene(self, world, width: int = SCENE_WIDTH,
                     height: int = SCENE_HEIGHT) -> GridMap:
        """Sahne ızgarasını hazırlar ve kadroyu haritaya yerleştirir.

        Kaydı DEĞİŞTİREBİLİR; çağıran state'i kaydetmelidir."""
        yer = world.location or "sahne"
        grid = world.ensure_grid(width, height, name=yer)
        if grid.name != yer:
            # Grup başka bir yere taşındı: sahne yenilenir, kadro yeni haritaya
            # doğar. (Yerler arası geçiş `map` katmanının işi; burası o yerin
            # İÇİNİ tarif eder.)
            grid = world.grid = GridMap.blank(width, height, name=yer)

        self._draw_walls(grid)
        self._spawn_cast(world, grid)
        return grid

    @staticmethod
    def _draw_walls(grid: GridMap) -> None:
        """Sahnenin dış çeperi duvardır — kimse haritadan çıkamaz."""
        for x in range(grid.width):
            grid.set_terrain(x, 0, "duvar")
            grid.set_terrain(x, grid.height - 1, "duvar")
        for y in range(grid.height):
            grid.set_terrain(0, y, "duvar")
            grid.set_terrain(grid.width - 1, y, "duvar")

    @staticmethod
    def _spawn_cast(world, grid: GridMap) -> None:
        """Hayatta olan kadro ve gruptaki NPC'ler haritada bulunsun.

        Zaten haritada olan varlık YERİNDE bırakılır; ölen varlık kaldırılır."""
        orta_y = grid.height // 2
        sira = 0
        for ad, kisi in (world.characters or {}).items():
            var = grid.entity(ad)
            if not kisi.is_alive:
                if var is not None:
                    grid.remove_entity(var)
                continue
            if var is not None:
                continue
            # Ortadan başlayarak yan yana diz; dolu kare varsa bir sağa kay.
            x = 1 + (sira % max(1, grid.width - 2))
            grid.place(Player(id=ad, name=ad), x, orta_y)
            sira += 1

        for ad, kisi in (world.npcs or {}).items():
            if not kisi.is_alive or grid.entity(ad) is not None:
                continue
            # Yalnız sahnedeki (grubun yanındaki) NPC'ler haritaya girer.
            if (kisi.location or "") != (world.location or ""):
                continue
            grid.place(Npc(id=ad, name=ad), max(1, grid.width - 2), orta_y)

    # ------------------------------------------------------------- hareket
    def move(self, player, direction) -> dict:
        """Bir oyuncu karakterini bir kare hareket ettirir."""
        player = (player or "").strip()
        if not player:
            raise ValidationError("Karakter seçilmedi.")
        if direction_of(direction) is None:
            raise ValidationError(
                "Yön anlaşılmadı — kuzey, güney, doğu, batı (ya da çaprazları)."
            )

        with LOCK:
            state = self.state_repo.load()
            if not state["started"]:
                raise ValidationError("Oyun henüz başlamadı.")
            world = StateRepository.world_of(state)
            kisi = (world.characters or {}).get(player)
            if kisi is None:
                raise ValidationError(f"{player} kadroda yok.")
            if not kisi.is_alive:
                raise ValidationError(f"{player} öldü — hareket edemez.")

            grid = self.ensure_scene(world)
            entity = grid.entity(player)
            if entity is None:
                raise ValidationError(f"{player} bu sahnede değil.")

            # Hareket algoritması modeldedir; burada yalnız çağrılır.
            sonuc = move(grid, entity, direction)

            StateRepository.store_world(state, world)
            version = self.state_repo.save(state)

        return {"ok": sonuc.ok, "result": sonuc.to_dict(),
                "grid": state["world_state"].get("grid"),
                "version": version}

    # -------------------------------------------------------------- durum
    def snapshot(self) -> dict:
        """Sahnenin güncel hali (arayüz ilk açılışta bunu ister)."""
        with LOCK:
            state = self.state_repo.load()
            world = StateRepository.world_of(state)
            if not state["started"]:
                return {"grid": None, "version": int(state.get("version", 0))}
            self.ensure_scene(world)
            StateRepository.store_world(state, world)
            version = self.state_repo.save(state)
        return {"grid": state["world_state"].get("grid"),
                "world_state": public_world_state(state["world_state"]),
                "version": version}
