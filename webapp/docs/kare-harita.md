# Kare harita (ızgara) — veri modeli ve hareket algoritması

Sahnenin İÇİNİ tarif eden taktik katman. Yerler arası gezinme `map` katmanının
işidir (bkz. `tur-akisi-ve-ogrenme.md` §6); burası "şu an bulunduğumuz yerin
karesi kare hali"dir.

Kod: `app/models/grid/` (saf model) · `app/services/grid_service.py` (akış) ·
`app/api/grid.py` (uçlar) · `frontend/src/components/game/GridCanvas.vue` (çizim).

---

## 1. Veri modeli (sözleşme)

```
GridMap
  width, height
  grid : list[list[Cell]]        # grid[y][x] — her eleman bir Cell NESNESİ
  entities : dict[str, Entity]   # kimlik → varlık (O(1) erişim)

Cell (grid[y][x])                # yalnız KENDİ koordinatının bilgisi
  x, y, terrain, passable
  players   : {id: Entity}       # aynı karede birden fazla olabilir
  npcs      : {id: Entity}
  items     : {id: Entity}
  buildings : {id: Entity}
  others    : {id: Entity}       # ileride eklenecek türler
  blockers  : int                # engelleyici varlık sayacı (O(1) kontrol için)

Entity                           # Player | Npc | Item | Building
  id, name, kind, x, y, blocking, data
```

Kurallar:

- Harita **2 boyutludur** (X sütun, Y satır) ve **2D dizidir**: `grid[y][x]`.
  3D dizi yoktur; Y aşağı doğru büyür, bu yüzden kuzey `y - 1`'dir.
- Dizinin her elemanı **primitif değil, `Cell` nesnesidir**.
- **Oyuncular haritanın içine yazılmaz.** Her oyuncunun kendi `x`/`y`'si vardır;
  bulunduğu karenin `players` koleksiyonunda durur. Aynısı NPC, eşya ve bina
  için de geçerlidir.
- Aynı koordinatta birden fazla oyuncu, NPC ve eşya bulunabilir (koleksiyonlar
  sözlüktür, tek slot değil).
- Kayıt biçiminde de bu ayrım korunur: `cells` yalnız zemini yazar, varlıklar
  kendi `x`/`y`'leriyle ayrı listede durur ve yüklemede hücrelere dağıtılır.

## 2. Hareket algoritması

`app/models/grid/movement.py` → `move(grid_map, entity, direction)`; sıra
**sabittir**:

| # | Adım | Nerede |
|---|---|---|
| 1 | Hareket yönünü al | `direction_of(...)` (sözlük araması) |
| 2 | Yeni koordinatı hesapla | `yon.apply(x, y)` |
| 3 | Harita sınırlarını kontrol et | `grid_map.in_bounds(...)` |
| 4 | Hedef hücre geçilebilir mi | `hedef.is_passable` (zemin + `blockers`) |
| 5 | Varlığı mevcut hücreden kaldır | `mevcut.remove(entity)` |
| 6 | Varlığın koordinatını güncelle | `entity.x, entity.y = ...` |
| 7 | Varlığı hedef hücreye ekle | `hedef.add(entity)` |
| 8 | Hareket sonucunu döndür | `MoveResult` |

- **Karmaşıklık O(1)**: hücreye dizi indeksiyle erişilir, koleksiyon işlemleri
  sözlük ekleme/çıkarmadır, geçilebilirlik sayaçtan okunur. Ölçüm: 10×10 ve
  400×400 haritada hareket başına süre aynı (~6 µs, oran 1.08×).
- **Yalnız iki hücreye dokunulur** (kaynak + hedef); haritanın geri kalanı hiç
  okunmaz/yazılmaz.
- **Başarısız hareket haritayı değiştirmez**: 3. ve 4. adımdaki kontroller 5.
  adımdan önce gelir, yarım kalmış taşıma oluşamaz.
- Sonuç kodları: `tamam`, `sınır_dışı`, `geçilemez`, `geçersiz_yön`,
  `haritada_değil`. `MoveResult.met` hedef karede karşılaşılanları verir —
  savaş/etkileşim sistemleri buradan büyür.

## 3. Uçlar

| Yöntem | Yol | İstek | Yanıt |
|---|---|---|---|
| GET | `/api/grid` | — | `{grid, world_state, version}` (sahne yoksa kurulur) |
| POST | `/api/grid/move` | `{player, direction}` | `{ok, result, grid, version}` |

`direction`: `kuzey|güney|doğu|batı|kuzeydoğu|…` (ayrıca `n/s/e/w`, ok
yönleri, `[dx, dy]`).

## 4. Sahne kurulumu

`GridService.ensure_scene(world)`:

- Izgara grubun bulunduğu YERİN adıyla açılır (15×11, çeper duvar). Grup başka
  bir yere taşınırsa sahne o yerin adıyla yeniden kurulur.
- Hayatta olan her oyuncu karakteri için bir `Player` varlığı doğar; ölen
  karakter haritadan kaldırılır. Zaten haritada olan varlık YERİNDE bırakılır —
  sahne her turda sıfırlanmaz.
- Grubun yanındaki NPC'ler `Npc` olarak eklenir.

## 5. Anlatıcı/GM sahneyi nasıl şekillendirir

state-update (ya da `/api/gm/patch`) içindeki `grid` alanı:

```json
{"grid": {
  "terrain": [{"x": 5, "y": 5, "type": "duvar"}],
  "spawn":   [{"id": "varil", "name": "Yakıt varili", "kind": "item", "x": 4, "y": 5}],
  "remove":  ["varil"],
  "move":    [{"id": "Sevil", "direction": "kuzey"}]
}}
```

Oyuncu karakterleri bu yamayla **hareket ettirilemez ve silinemez**: onları
yalnız oyuncunun kendi hamlesi (`/api/grid/move`) oynatır.

## 6. Genişletme

Yeni bir varlık türü eklemek için `entities.py`'a bir sınıf ve
`KIND_TO_COLLECTION`'a bir satır yeter; `Cell`, `GridMap` ve hareket kodu
değişmez. Türe özel veriler `Entity.data` / `Cell.data` altında taşınır:

- **NPC davranışı**: `Npc.data["ai"]`, hareket için aynı `move()` çağrılır.
- **Görev**: `Cell.data["quest"]` ya da `others` koleksiyonunda bir işaret.
- **Bina**: `Building.blocking=True` → hücrenin `blockers` sayacı, geçilmez.
- **Savaş**: `MoveResult.met` ile aynı kareye girenler; menzil hesapları
  `entity.x/y` üzerinden.
- **Eşya**: `Item` haritadan `remove_entity` ile alınır, envantere yazılır.
