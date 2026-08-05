# Mimari — OOP / MVC geçişi

Tek dosyalık `server.py` (~2400 satır, düz fonksiyonlar) katmanlı bir pakete
bölünüyor. Amaç: her düzeltme için dosyanın tamamını taramak zorunda kalmamak.

**Bozulmayacak iki şey**: HTTP API sözleşmesi ve `data/state.json` biçimi.
Devam eden gerçek bir oyun var (Gün 98+); yeni kod eski kaydı olduğu gibi
açabilmeli.

---

## 1. Klasör düzeni

```
webapp/
  server.py                 # sadece giriş noktası: create_app().run(...)
  app/
    __init__.py             # create_app(): Flask, blueprint kaydı, config
    config.py               # yollar, env değişkenleri, sabitler
    models/                 # SAF alan modelleri — Flask yok, I/O yok
      __init__.py
      text.py               # norm_tr, canonical_name, clock aritmetiği
      dice.py               # Dice, WorldDice (bantlar + atış)
      vitals.py             # Vitals — drift, etiket, sınırlama
      wounds.py             # Wound, WoundList — enfeksiyon, iyileşme
      presence.py           # Presence, PresenceState — sahne katılımı
      person.py             # Person (Character/NPC ortak gövdesi)
      resources.py          # ResourcePool — +N/-N birleştirme
      challenges.py         # Challenge
      factions.py           # Faction — iki katmanlı görünürlük
      world.py              # WorldState — kök nesne, patch birleştirme
      worldmap.py           # WorldMap, Place, Road — şehir/koordinat/yol/mesafe
      mapgen.py             # harita üreteci: şehirler, mekanlar, yollar (oyun başı)
      threat.py             # zombi tehdidi: yoğunluk, gürültü, karşılaşma zarı
      grid/                 # kare harita: grid[y][x] Cell dizisi (bkz. kare-harita.md)
        coords.py           #   Direction — yön vektörleri
        cell.py             #   Cell — bir koordinatın zemini + içindekiler
        entities.py         #   Entity/Player/Npc/Item/Building
        grid_map.py         #   GridMap — 2D dizi + varlık kaydı
        movement.py         #   move() — 8 adımlı hareket algoritması (O(1))
      options.py            # Option, OptionBoard — seçenek havuzu (3-8, sabit değil, spend)
      inventory.py          # sayılabilir envanter (mermi/sargı/yakıt sayaçları)
      items.py              # sabit eşya kataloğu (yer türüne göre bulunma)
      round.py              # Round, Pick — tur bazlı akışın kaydı
      pending.py            # bekleyen yayın kuyruğu (her şey BİR SONRAKİ turda)
      learning.py           # Learning — öğrenme defteri (sayaçlar + dersler)
      plot.py               # Plot, Beat (senarist katmanı)
      conditions.py         # koşul motoru (mevcut director.matches)
    repositories/           # kalıcılık — dosya I/O burada, başka yerde yok
      state_repo.py         # state.json (atomik yazma, version sayacı)
      log_repo.py           # game_log.jsonl, gm_log.jsonl
      scenario_repo.py      # scenario_override.json + scenario.py varsayılanı
                            #   (+ SYSTEM_APPENDIX'i her senaryoya iliştirir)
      plot_repo.py          # plot.json
      learning_repo.py      # learning.json + learning_events.jsonl
      options_repo.py       # options_pool.jsonl (sunulan/seçilen seçenekler)
      items_repo.py         # items.json (sabit katalog; tek yazan GM ekranı)
      places_repo.py        # places.json (harita üreteci içeriği, SALT OKUNUR)
    services/               # iş akışı — modelleri ve repo'ları orkestre eder
      narrator_client.py    # claude CLI süreci (subprocess)
      prompt_builder.py     # modele giden tüm metin blokları
      state_update.py       # yanıttan state-update ayrıştırma/temizleme
      turn_service.py       # serbest metin turu + ortak tur sonu (finish_turn)
      round_service.py      # tur bazlı akış: seçim topla → "Turu Geç" → toplu
                            #   gönder; turun BAŞINDA bekleyenleri yayınlar
      options_service.py    # seçenek havuzu bakımı (eksik kalanı tamamlar)
      learning_service.py   # öğrenme defteri + Claude yeteneğine yazma
      worldgen_service.py   # her oyuna farklı başlangıç ve fraksiyonlar
      grid_service.py       # kare harita: sahne kurulumu + hareket
      threat_service.py     # karşılaşma zarı (girdiler GEÇEN turdan devreder)
      inventory_service.py  # harcama muhasebesi: seçeneğin bedelini sunucu keser
      items_service.py      # arama (yere göre loot) + tüketim (doyum/susuzluk)
      setup_service.py      # karakter kurulumu, oyunu başlatma, ayarlar
      gm_service.py         # anlatıcı notu, elle yama, kilit
      scenario_service.py   # senaryo/oyun dışa-içe aktarma
    api/                    # Flask blueprint'leri — İNCE olacak
      pages.py              # /, /secrets, /static/<path>
      game.py               # /api/state, /api/message, /api/start, /api/settings
      round.py              # /api/round/pick, /wait, /commit
      grid.py               # /api/grid, /api/grid/move
      gm.py                 # /api/gm/*
      scenario.py           # /api/scenario/*, /api/game/*
    serializers.py          # public_world_state (oyuncu) / gm görünümü
  scenario.py               # senaryo metni — YERİNDE KALIR (içerik dosyası)
  frontend/                 # Vue 3 + Vite kaynak (bkz. tasarim-sistemi.md)
  static/dist/              # Vite build çıktısı (Flask servis eder)
  static/audio/             # kullanıcının kendi müziği
  data/                     # state.json, *.jsonl, plot.json, learning.json
.claude/skills/kizil-cokus-anlatici/   # yetenek: SKILL.md (elle) +
                            #   ogrenilenler.md (her turda sunucu yazar)
```

`director.py` içeriği `app/models/conditions.py` ve `app/models/plot.py`'a
taşınır; eski dosya kaldırılır (import'u sadece `server.py` kullanıyordu).

## 2. Katman kuralları

1. **models/** hiçbir şeyi import etmez (stdlib hariç). Flask, dosya, ağ yok.
   Her sınıf `from_dict()` / `to_dict()` çiftiyle mevcut JSON biçimine birebir
   dönüşür — kayıt formatı değişmiyor.
2. **repositories/** sadece `models/` bilir. Dosya okuma/yazma yalnız burada.
3. **services/** `models/` + `repositories/` bilir. Flask `request`/`jsonify`
   kullanmaz; düz Python değeri döndürür, hata için özel istisna atar
   (`GameError(mesaj, status)`).
4. **api/** sadece `services/` çağırır: gövdeyi ayrıştır, servisi çağır,
   `jsonify` ile döndür. Bir blueprint fonksiyonu ~15 satırı geçmemeli.
5. Yorumlar ve hata mesajları **Türkçe** kalır (mevcut üslup).
6. Eşzamanlılık: tek `threading.Lock` (`app/repositories/state_repo.py`
   içinde) — tur akışı bugünkü gibi seri kalsın.

## 3. Alan modeli sözleşmesi (state.json ile birebir)

`WorldState` alanları: `day` (int), `time_of_day`, `clock`, `season`,
`weather`, `temperature`, `location`, `tension` (`düşük|orta|yüksek`),
`factions`, `characters`, `npcs`, `resources`, `challenges`,
`map`, `grid`, `zombie_sightings`, `story_items` (hikayeye özel, mekaniği
OLMAYAN eşyalar), `searched` (yer başına arama sayacı), `flags`, `narrator`,
`options`, `threat`,
`world_roll`, `world_roll_history`.

`state.json` kökünde ayrıca üç alan vardır: `settings`
(`{turn_seconds, profanity, round_mode, map_size}`), `round` (açık turun kaydı:
`{no, status, seconds, opened_ts, picks}`) ve `pending` (bir sonraki turun
başında devreye girecek kayıtlar: `{items: [{kind, due_round, data, ts}]}`,
bkz. `models/pending.py` ve `docs/tur-akisi-ve-ogrenme.md` §1b). Eski
kayıtlarda yoklarsa `StateRepository.backfill` varsayılanla doldurur.

`Person` (characters ve npcs): `background`, `traits`, `status`, `alive`,
`location`, `notes`, `inventory`, `inventory_counts` (sayılabilir kalemlerin
miktarı — sunucu tutar), `lost_items`, `relationships`, `wounds`,
`vitals`, `presence`, künye alanları (`profession`, `age`, `strength`,
`weakness`, `reflex`, `secret`).

Patch birleştirme kuralları (davranış AYNEN korunacak):
- `inventory` üzerine yazmaz, birleştirir; `lost_items` elden çıkanı hatırlar
- sayılabilir kalemde miktar İSİMDEN AYRILIR: `"12 fişek"` → liste `"fişek"`,
  sayaç `{"fişek": 12}`. Sayaç sıfırlanınca kalem envanterden düşer
  (bkz. `docs/tur-akisi-ve-ogrenme.md` §1d)
- `inventory_counts` ve `resources` `"+3"` / `"-12"` göreli değişimi destekler
- boş/None zaman alanı mevcut değeri korur
- model `characters` altına tanımadık isim yazarsa `npcs`'e yönlendirilir
- `presence.until` dolduğunda karakter sahneye döner
- `map` yaması yerleri/parti dağılımını birleştirir; `map.party` bu turda
  yazıldıysa sunucunun otomatik eşlemesi onun ÜZERİNE YAZMAZ
- `options` karakter başına TAMAMEN yenilenir (seçenekler o tura aittir) ve
  kadroda olmayan isim için yok sayılır
- `learning.lessons_add` öğrenme defterine düşer, dünya durumunda saklanmaz
- `grid` yaması zemin/varlık ekler, NPC oynatır; oyuncu karakterlerini
  HAREKET ETTİREMEZ (onlar yalnız `/api/grid/move` ile oynar)
- `threat` yaması yalnız `noise_add` ve `density` kabul eder; karşılaşmayı
  model YAZAMAZ, onu sunucunun zarı belirler (bkz. zombi-tehdidi.md)

## 4. HTTP API sözleşmesi (DEĞİŞMEZ)

| Yöntem | Yol | İstek | Yanıt |
|---|---|---|---|
| GET | `/` | — | oyuncu arayüzü (SPA) |
| GET | `/secrets` | — | anlatıcı arayüzü (aynı SPA, farklı rota) |
| GET | `/static/<path>` | — | dosya |
| GET | `/api/state?since=<v>` | — | `{version, changed}` ya da `{version, changed:true, world_state, log, started, characters_confirmed, chargen_done, default_players, start_item_suggestions, custom_scenario, group_label, group_display_name, settings, round}` |
| POST | `/api/setup-characters` | `{players:[{name,item,profession,age,strength,weakness,reflex,secret}]}` | `{world_state, characters_confirmed}` |
| POST | `/api/start` | — | `{gm_entry, world_state, started}` |
| POST | `/api/message` | `{player, text}` | `{user_entries, gm_entry, world_state, inventory_report, version}` — YALNIZ karakter oluşturma sürerken; chargen bitince 400 (serbest hamle yok) |
| POST | `/api/takeover` | `{dead_player, new_character}` | `{system_entry, gm_entry, world_state}` |
| POST | `/api/finish-chargen` | — | `{ok, world_state}` |
| POST | `/api/settings` | `{turn_seconds?, profanity?, map_size?}` | `{ok, settings, version, round}` — `round_mode: false` reddedilir; `map_size` yalnız oyun başlamadan önce değişir |
| POST | `/api/reset` | `{keep_learning?: true}` | `{ok, learning_kept}` |
| POST | `/api/round/pick` | `{player, option_id}` | `{ok, pick, roll, band, changed, round, all_picked, version}` — zar SEÇİM ANINDA ve tur başına BİR KEZ atılır; karar turu geçene kadar değiştirilebilir (`changed: true` = zar aynı kaldı); `text` gönderilirse 400 (hikaye yalnız sunulan seçeneklerle ilerler) |
| POST | `/api/round/wait` | `{player}` | `{ok, round, version}` — bu da bir seçimdir, değiştirilebilir |
| GET | `/api/items` | — | `{surum, kategoriler, yer_turleri, esyalar}` — SABİT eşya kataloğu (`data/items.json`), her eşyanın en olası üç yeriyle |
| GET | `/api/gm/items?pin` | — | aynı katalog, anlatıcı ekranı için |
| POST | `/api/gm/items` | `{pin, item}` | `{ok, item, catalog}` — kataloga KALICI eşya ekler: `data/items.json`'a yazılır, tüm oyunlarda geçerli olur |
| GET | `/api/grid` | — | `{grid, world_state, version}` — sahne yoksa kurulur |
| POST | `/api/grid/move` | `{player, direction}` | `{ok, result, grid, version}` — hareket algoritması: yön→koordinat→sınır→geçilebilirlik→kaldır→koordinat→ekle→sonuç |
| POST | `/api/round/commit` | `{reason: elle\|sure, round_no}` | `{ok, user_entries, gm_entry, world_state, round, timeouts, version}` ya da `{ok, skipped:true}` — "Turu Geç"; sahne kuyruğa yazılıp bir sonraki turun başında yayınlanır |
| POST | `/api/gm/unlock` | `{pin}` | `{ok}` / 403 |
| GET | `/api/gm/state?pin&since` | — | `{version, changed, world_state, gm_log, log, started, plot, round, settings, learning}` |
| POST | `/api/gm/lesson` | `{pin, text}` | `{ok, learning}` — deftere elle ders |
| POST | `/api/gm/note` | `{pin, text, mode: gizli\|sahne\|surpriz}` | `{note_entry, reply_entry, gm_entry, published, world_state}` — `note_entry`/`reply_entry` anlatıcı günlüğüne, `gm_entry` oyuncu akışına gider (gizli modda `null`) |
| POST | `/api/gm/patch` | `{pin, patch}` | `{ok, version, world_state}` |
| GET | `/api/scenario/export` | — | senaryo JSON |
| POST | `/api/scenario/import` | senaryo JSON | `{ok}` |
| POST | `/api/scenario/reset-default` | — | `{ok}` |
| GET | `/api/game/export` | — | `{state, log, gm_log}` |
| POST | `/api/game/import` | `{state, log, gm_log}` | `{ok}` |

Hata biçimi her yerde `{"error": "<Türkçe mesaj>"}` + uygun HTTP kodu
(400 doğrulama, 403 PIN, 502 model hatası, 504 zaman aşımı).

## 5. Geçiş kabulü

- `python -m py_compile` temiz, sunucu ayağa kalkıyor
- Canlı `data/state.json` (Gün 98+) yeni kodla açılıyor, alan kaybı yok:
  eski ve yeni `to_dict()` çıktısı karşılaştırılarak doğrulanır
- Her uç nokta eski yanıt şemasını döndürüyor
- Bir tur oynanıyor: zar → prompt → state-update → kayıt zinciri çalışıyor

## 9. Kimlik ve yetki

Oyun bir sunucuda çalışıp dışarı açılabildiği için kimlik **sunucunun bildiği
bir gerçek**, istemcinin iddia ettiği bir alan değil.

**Katmanlar** (mimarinin geri kalanıyla aynı sıra):

| katman | dosya | işi |
| --- | --- | --- |
| model | `models/accounts.py` | şifre özeti (scrypt), hesap defteri, şifre kuralı |
| repo | `repositories/accounts_repo.py` | `data/accounts.json` — atomik yazma, 0600 |
| servis | `services/auth_service.py` | sahiplenme, giriş, kaba kuvvet freni, rol kararı |
| api | `api/guards.py`, `api/auth.py` | Flask oturumu, `@player_required` / `@gm_required` |

`auth_service` Flask bilmez: kimlik sözlüğü alır, kimlik sözlüğü döndürür.
Oturumu kuran/okuyan tek yer `api/guards`.

**Üç rol:** `player` (yalnız kendi karakteri), `table` (tek ekran kipi — kadronun
tamamı adına oynar), `gm` (kurar/ayarlar/sahne yazar, hamle yapmaz).

**Kimlik nereden gelir.** `guards.acting_player(gövdedeki_ad)` karar verir:
oyuncu oturumunda gövdedeki ad **yok sayılır** ve oturumun karakteri kullanılır;
masa oturumunda gövdedeki ad kullanılır ama tek ekran kipi hâlâ açık olmalıdır.
Tek istisna ORTAK KARAR etiketidir — grubun sözü bir karaktere ait değildir,
her giriş yapmış oyuncu gönderebilir.

**Yetki dağılımı.** `/api/state`, `/api/items`, `/api/grid` giriş ister
(`login_required`). Hamleler `player_required`. Kurulum, başlatma, ayarlar,
sıfırlama, devralma, chargen kapatma, senaryo/oyun aktarma ve tüm `/api/gm/*`
uçları `gm_required` — dışarı açık bir sunucuda giren herkes oyunu
sıfırlayamamalı.

**Anlatıcı PIN'i artık her istekte taşınmıyor.** Bir kez `/api/auth/gm` ile
giriş yapılır, sonraki istekler oturum çerezinden yetkilenir; PIN adres
çubuğunda, sunucu kayıtlarında ve tarayıcı geçmişinde dolaşmaz. `gm_service`
metotlarından `pin` parametresi kalktı: servise gelen çağrı zaten yetkilidir.

**Oturum çerezi** `create_app` içinde kurulur: imzalı, HttpOnly, SameSite=Lax,
`COOKIE_SECURE` ile TLS'e kilitlenebilir. İmza anahtarı `.env`'den gelmezse
`data/secret_key` içinde üretilip saklanır — yeniden başlatma herkesi dışarı
atmasın.

**Hesaplar oyunun durumu değildir**: `/api/reset` oyunu sıfırlasa da insanlar
aynı insanlardır, `data/accounts.json` silinmez. İki dosya da `.gitignore`'da.
