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
      plot.py               # Plot, Beat (senarist katmanı)
      conditions.py         # koşul motoru (mevcut director.matches)
    repositories/           # kalıcılık — dosya I/O burada, başka yerde yok
      state_repo.py         # state.json (atomik yazma, version sayacı)
      log_repo.py           # game_log.jsonl, gm_log.jsonl
      scenario_repo.py      # scenario_override.json + scenario.py varsayılanı
      plot_repo.py          # plot.json
    services/               # iş akışı — modelleri ve repo'ları orkestre eder
      narrator_client.py    # claude CLI süreci (subprocess)
      prompt_builder.py     # modele giden tüm metin blokları
      state_update.py       # yanıttan state-update ayrıştırma/temizleme
      turn_service.py       # bir oyuncu turunun tam akışı
      setup_service.py      # karakter kurulumu, oyunu başlatma, devralma
      gm_service.py         # anlatıcı notu, elle yama, kilit
      scenario_service.py   # senaryo/oyun dışa-içe aktarma
    api/                    # Flask blueprint'leri — İNCE olacak
      pages.py              # /, /secrets, /static/<path>
      game.py               # /api/state, /api/message, /api/start, ...
      gm.py                 # /api/gm/*
      scenario.py           # /api/scenario/*, /api/game/*
    serializers.py          # public_world_state (oyuncu) / gm görünümü
  scenario.py               # senaryo metni — YERİNDE KALIR (içerik dosyası)
  frontend/                 # Vue 3 + Vite kaynak (bkz. tasarim-sistemi.md)
  static/dist/              # Vite build çıktısı (Flask servis eder)
  static/audio/             # kullanıcının kendi müziği
  data/                     # state.json, *.jsonl, plot.json
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
`zombie_sightings`, `flags`, `narrator`, `world_roll`, `world_roll_history`.

`Person` (characters ve npcs): `background`, `traits`, `status`, `alive`,
`location`, `notes`, `inventory`, `lost_items`, `relationships`, `wounds`,
`vitals`, `presence`, künye alanları (`profession`, `age`, `strength`,
`weakness`, `secret`).

Patch birleştirme kuralları (davranış AYNEN korunacak):
- `inventory` üzerine yazmaz, birleştirir; `lost_items` elden çıkanı hatırlar
- `resources` `"+3"` / `"-12"` göreli değişimi destekler
- boş/None zaman alanı mevcut değeri korur
- model `characters` altına tanımadık isim yazarsa `npcs`'e yönlendirilir
- `presence.until` dolduğunda karakter sahneye döner

## 4. HTTP API sözleşmesi (DEĞİŞMEZ)

| Yöntem | Yol | İstek | Yanıt |
|---|---|---|---|
| GET | `/` | — | oyuncu arayüzü (SPA) |
| GET | `/secrets` | — | anlatıcı arayüzü (aynı SPA, farklı rota) |
| GET | `/static/<path>` | — | dosya |
| GET | `/api/state?since=<v>` | — | `{version, changed}` ya da `{version, changed:true, world_state, log, started, characters_confirmed, chargen_done, default_players, start_item_suggestions, custom_scenario, group_label, group_display_name}` |
| POST | `/api/setup-characters` | `{players:[{name,item,profession,age,strength,weakness,secret}]}` | `{world_state, characters_confirmed}` |
| POST | `/api/start` | — | `{gm_entry, world_state, started}` |
| POST | `/api/message` | `{player, text}` | `{user_entries, gm_entry, world_state, inventory_report, version}` |
| POST | `/api/takeover` | `{dead_player, new_character}` | `{system_entry, gm_entry, world_state}` |
| POST | `/api/finish-chargen` | — | `{ok, world_state}` |
| POST | `/api/reset` | — | `{ok}` |
| POST | `/api/gm/unlock` | `{pin}` | `{ok}` / 403 |
| GET | `/api/gm/state?pin&since` | — | `{version, changed, world_state, gm_log, log, started}` |
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
