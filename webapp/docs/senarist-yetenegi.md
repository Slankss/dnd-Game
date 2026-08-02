# Senarist yeteneği — uygulama planı

Proje: `C:\GITHUB\dnd-Game\webapp` — Flask sunucu + `claude` CLI ile yürüyen,
Türkçe zombi kıyameti RPG'si. Oyuncular `/`, anlatıcı (GM) `/secrets` ekranını
kullanır. Kod ve yorumlar Türkçe.

Durum: **Faz 0 ve Faz 1 uygulandı** (aşağıda ✅). Kalan fazlar plandır.

> Satır numarası vermiyoruz — depo başka makinelerden de güncelleniyor
> (`v1.1` ile vitals/yaralar/künyeler geldi ve tüm numaralar kaydı). Kancalar
> fonksiyon adıyla anılıyor.

---

## 1. Amaç

Anlatıcı **reaktif**: her tur, o anki `world_state` ile sahne yazar. Uzun
vadeli olay örgüsü tutamaz, ileriye randevu koyamaz, ektiği ipucunu 10 tur
sonra hasat edemez.

Hedef: **senarist** katmanı — planı önceden yazan, doğru turda müdahale eden,
ama oyuncu ajansını öldürmeyen bir yetenek.

| | Anlatıcı (mevcut) | Senarist (yeni) |
|---|---|---|
| Ne zaman | Her turda | Arada bir (elle veya N turda bir) |
| Çıktı | Oyuncuya giden sahne | `plot.json` — oyuncu asla görmez |
| Kim tetikler | Oyuncu mesajı | Kod (koşul) veya GM butonu |
| Sıcaklık | Gecikmeye duyarlı | Yavaş olabilir |

---

## 2. Ortak makine: koşul motoru

Planın kalbi tek bir fikir: **koşullu randevu**. İki ayrı ihtiyaç aynı motoru
kullanır, bu yüzden `director.py` tek yerde durur:

- **Sahne katılımı** — "Okan 06:00'da uyanır" (`presence.until`)
- **Olay örgüsü** — "gün 101'den sonra kampta mühür görünür" (`beat.when`)

`director.matches(when, ctx)` — desteklenen alanlar (hepsi VE ile bağlanır,
bilinmeyen alan yok sayılır):

| Alan | Örnek |
|---|---|
| `day_gte` / `day_lte` | `{"day_gte": 101}` |
| `clock_gte` / `clock_lte` | `{"clock_gte": "06:00"}` |
| `location_in` | `{"location_in": ["Kalan Umut kampı"]}` (kısmi, Türkçe duyarsız) |
| `tension_gte` | `{"tension_gte": "yüksek"}` |
| `flags_set` / `flags_unset` | `{"flags_set": ["sevil_guveni"]}` |
| `world_roll_lte` / `_gte` | `{"world_roll_lte": 40}` |

`day_gte` + `clock_gte` birlikte verilirse **tek randevu anı** olarak okunur
(gün ve saat ayrı ayrı karşılaştırılsaydı, gün 100 saat 02:00'de koşul sonsuza
kadar sağlanmaz olurdu — uyuyan karakter hiç uyanmazdı).

---

## 3. ✅ Faz 0 — İskelet

`webapp/director.py` eklendi: koşul motoru (`build_context`, `matches`,
`describe_when`), Türkçe normalleştirme (`norm_tr`) ve plan dosyası
yardımcıları (`load_plot`, `save_plot`, `DEFAULT_PLOT` → `data/plot.json`).

`server`'ı import ETMEZ (döngüsel import olurdu); bu yüzden `norm_tr`
`server._norm_tr`'nin bilinçli kopyasıdır.

---

## 4. ✅ Faz 1 — Sahne katılımı (presence)

**Sorun**: anlatıcı her turda her karakterden bir şey duymak zorundaymış gibi
davranıyordu. Oysa biri uyuyor, biri erzak aramaya gitmiş, biri esir olabilir —
ve sahnede olan biri de her turda konuşmak zorunda değildir.

**Veri** — `world_state.characters.<isim>.presence`:

```json
{"state": "uyuyor", "note": "revirde",
 "until": {"day_gte": 99, "clock_gte": "06:00"},
 "since_day": 98, "since_clock": "22:10"}
```

`state`: `sahnede` (varsayılan) · `uyuyor` · `uzakta` · `baygın` · `esir`.
Model başka kelime yazarsa (`uykuda`, `tutsak`, `sahne dışı`…) `PRESENCE_ALIASES`
ile eşlenir; tanınmayan değer `sahnede`'ye düşer. Ölüm ayrı eksendir (`alive`).

**Sunucu** (`server.py`):

- `ensure_presence` / `presence_state` / `present_players` / `absent_players`
- `_merge_presence` — `_merge_person_like` içinden çağrılır, yani `presence`
  normal state-update yolundan gelir. Düz string de kabul edilir
  (`"presence": "uyuyor"`). Hal değişince eski `until` düşer.
- `resolve_presence(ws, world_entry)` — turun başında çalışır; `until` koşulu
  dolan herkesi sahneye döndürür ve listesini prompt'a verir.
- `bring_to_scene(ws, isim)` — oyuncu sahne dışındaki karakteriyle mesaj
  yazdıysa, mesajın kendisi "uyandım/döndüm" demektir.
- `presence_note(ws, returned, rejoined)` — her turda prompt'a giren SAHNE
  KADROSU bloğu: kim sahnede, kim değil, kim döndü + iki kural (sahne
  dışındakine replik yazma; sahnedekilerin hepsine sırayla söz verme).
  `post_message`'ın iki normal dalına ve `gm_note`'un ortak kuyruğuna eklendi
  (karakter oluşturma dalları hariç — orada herkes sahnededir).
- `UPKEEP_REMINDER` madde (8) — `presence` yazma sorumluluğu.
- `apply_vitals_drift` — uyuyan karakter için `VITALS_SLEEP_PER_HOUR`:
  yorgunluk/stres düşer, `awake_hours` sıfırlanır, açlık/susuzluk uykuda da
  artmaya devam eder.

**Senaryo** (`scenario.py`): "SAHNE KATILIMI" bölümü (7 kural),
`state-update` şemasına `presence`, `CHARACTER_TEMPLATE`'e varsayılan alan.

**Arayüz**: oyuncu kartında rozet (😴 uyuyor / 🚶 sahne dışında / 💫 baygın /
⛓️ esir) + not satırı; `/secrets`'ta ayrıca dönüş koşulunun özeti.

**Test**: `scratchpad/t_presence.py` — koşul motoru (randevu, gün dönümü,
konum, bayrak, zar), presence birleştirme, otomatik uyandırma, oyuncu
mesajıyla dönüş, uyku telafisi, prompt bloğu. Hepsi geçiyor.

---

## 5. Faz 2 — Beat tetikleyici + direktif enjeksiyonu

Plan `data/plot.json`'da; bu fazda beat'ler **elle** yazılır (senarist yok).

```json
{"version": 1, "updated_day": 98,
 "threads": {"tarik_kimlik": {"premise": "Tarık aslında Emir…", "status": "aktif"}},
 "beats": [{
   "id": "muhur_ipucu", "thread": "tarik_kimlik",
   "when": {"day_gte": 101, "location_in": ["Kalan Umut kampı"], "flags_unset": ["muhur_gorulmus"]},
   "directive": "Sevil'in çadırında Arınma Cemaati mührü görünsün. Açık söyleme, sadece göster. Fark etmezlerse zorlama.",
   "on_fire": {"flags": {"muhur_gorulmus": true}},
   "expires_day": 106, "state": "pending", "fired_day": null}],
 "seeds": ["Okan'ın ıslak defteri henüz okunmadı"]}
```

Yapılacak:

- `director.evaluate(plot, ctx)` — ateşleyecek beat'i seçer; `director.expire(plot, day)`
- Tur başına **en fazla bir** beat (öncelik: en yakın `expires_day`). Üç
  direktif aynı sahneye girerse okunmaz olur.
- `directive_note(beat)` prompt bloğu, `presence_note` deseninde
- `post_message`: zar atıldıktan sonra değerlendir; model cevabı işlendikten
  sonra `fired` işaretle, `on_fire.flags`'i uygula, `save_plot`
- `state`: `pending` | `fired` | `expired` | `vetoed`; `expires_day` zorunlu
- `plot`'u `GM_ONLY_FIELDS`'a ekle (ileride `world_state`'e özet yansırsa sızmasın)

**Kabul**: elle yazılan beat koşulu sağlanan turda sahneye giriyor, ikinci kez
ateşlemiyor, vadesi dolan `expired` oluyor, `/api/state` cevabında plan izi yok.

## Faz 3 — GM paneli

`GET/POST /api/gm/plot` (PIN kontrolü `gm_note` desenine birebir uysun): beat
ekle/düzenle/veto/"şimdi ateşle". `/secrets`'ta bekleyen–ateşlenmiş–çürümüş
listesi; sahne dışındaki karakterleri elle döndürme düğmesi de buraya.

## Faz 4 — Senarist çağrısı (planı model yazar)

- `.claude/skills/senarist/SKILL.md` — **zanaat bilgisi**: iyi beat nasıl
  yazılır, ekim-hasat aralığı, foreshadow dozu, "sonuç dayatma" yasağı.
  Mekanik kural buraya girmez (o kodda).
- **Kısıt**: `call_claude` `--tools ""` ile çalışıyor, yani Claude Code
  skill'leri otomatik yüklenmez. SKILL.md diskten okunup `--system-prompt`
  olarak verilecek.
- **Kısıt**: anlatıcının oturumu `--resume` ile sürüyor; senarist oraya
  girmemeli (planlama gevezeliği hikâye bağlamına bulaşır). Ayrı,
  oturumsuz `call_scenarist()`.
- Çıktı doğrulanmadan yazılmaz: bilinmeyen alan at, `expires_day` yoksa
  varsayılan koy, `id` çakışmasını çöz.
- Önce `/secrets`'ta "Plan üret" düğmesi; otomatik vade (her N tur) sonra ve
  kapatılabilir olsun.

## Faz 5 — Süreklilik denetçisi

Tur sonrası ucuz ikinci çağrı: son sahne + envanter + `plot.json` + son 6 tur →
`{"conflicts": [...]}` → `gm_log`'a uyarı. Otomatik düzeltme yok, karar GM'in.
Oyuncu cevabını geciktirmesin (tur döndükten sonra çalışsın).

## Faz 6 — Cila

Beat ↔ `challenges` bağı; `world_roll` koşullu beat'lerin canlı testi;
`narrator.upcoming_events` ile çakışmanın çözümü (ikisi birden tetikleyici
kaynağı olmasın); `data/plot.json`'un `/api/game/export`'a dahil edilmesi.

---

## 6. Test yöntemi

Test altyapısı yok; pratik, sunucuyu import edip fonksiyonu doğrudan çağırmak:

```python
import sys
sys.path.insert(0, r"C:\GITHUB\dnd-Game\webapp")
import director, server
ctx = director.build_context({"day": 101, "location": "Kalan Umut kampı"})
print(director.matches({"day_gte": 101}, ctx))
```

Her fazdan sonra `python -m py_compile server.py director.py scenario.py`,
sonra bir tur oyna. Canlı `data/state.json` üstünde deneme yapmadan önce
kopyala — içinde devam eden gerçek bir oyun var.

---

## 7. Riskler

- **Ajans ölümü** — plan her turda devreye girerse oyuncu ne yaparsa yapsın
  aynı sahneye çıkar. Panzehir: tur başına tek beat, `directive` koşul tarif
  eder (sonuç dayatmaz), `expires_day` zorunlu.
- **Gecikme** — senarist ve denetçi sıcak yolun dışında kalmalı.
- **Sızıntı** — plan `/api/state` ile oyuncuya giderse sürprizler yanar.
- **Şema kayması** — model uydurma alanlı beat üretir; beyaz listeyle süz.
- **Maliyet** — senarist elle/vadeli, denetçi kısa prompt.

## 8. Karar bekleyenler

1. Senarist otomatik mi çalışsın (her N tur), yoksa sadece GM butonuyla mı?
2. Ateşlenen beat oyuncuya belli olsun mu (ör. yeni `challenges` satırı), yoksa
   tamamen görünmez mi?
3. Denetçi hangi modelle koşsun — anlatıcıyla aynı mı, daha ucuz olan mı?
