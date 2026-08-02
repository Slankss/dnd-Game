# Senarist yeteneği — uygulama planı

Bu belge başka bir Claude oturumunda uygulanmak üzere yazıldı. Okuyan oturumun bu
projeye dair hiçbir ön bilgisi olmadığı varsayılır.

Proje: `C:\GITHUB\dnd-Game\webapp` — Flask sunucu + `claude` CLI ile yürüyen,
Türkçe zombi kıyameti RPG'si. Oyuncular `/`, anlatıcı (GM) `/secrets` ekranını
kullanır. Kod ve yorumlar Türkçe.

---

## 1. Amaç

Bugün anlatıcı **reaktif**: her tur, o anki `world_state` ile sahne yazar.
Uzun vadeli olay örgüsü tutamaz, ileriye randevu koyamaz, ektiği ipucunu 10 tur
sonra hasat edemez.

Hedef: **senarist** katmanı. Planı önceden yazan, plana bakıp doğru turda
müdahale eden, ama oyuncu ajansını öldürmeyen bir yetenek.

Kritik ayrım — bu bir "ikinci anlatıcı" değil:

| | Anlatıcı (mevcut) | Senarist (yeni) |
|---|---|---|
| Ne zaman | Her turda | Arada bir (elle veya N turda bir) |
| Çıktı | Oyuncuya giden sahne | `plot.json` — oyuncu asla görmez |
| Kim tetikler | Oyuncu mesajı | Kod (vade) veya GM butonu |
| Sıcaklık | Gecikmeye duyarlı | Yavaş olabilir |

---

## 2. Bugünkü durum — dokunulacak yerler

Satır numaraları 2026-08-02 tarihli `server.py` (~1630 satır) içindir; kaymış
olabilir, isimden ara.

| Yer | Ne yapar | Plandaki rolü |
|---|---|---|
| `post_message()` — `server.py:1000` | Oyuncu turu; prompt + `extra_system` kurar, `call_claude` çağırır, state-update uygular | Direktif enjeksiyonu burada |
| `extra_system` kurulumu — `:1070` (çoklu karakter) ve `:1147` (tek/grup) | Üç dal var: chargen, çoklu, tek. Chargen dalına dokunma | İki dala da direktif eklenecek |
| `:1200-1202` | `extract_state_update` + `deep_merge_world_state` | Beat ateşlemesinin `on_fire` etkisi buradan sonra işlenir |
| `call_claude()` — `:790` | `claude -p --tools "" --output-format json`; `session_id` varsa `--resume`, yoksa `--system-prompt <senaryo>` | Senarist ÇAĞRISI bunu kullanamaz, aşağıya bak |
| `roster_note` `:510`, `inventory_note` `:457`, `world_dice_note` `:108`, `visible_timeline_note` `:425` | Prompt'a metin bloğu üreten yardımcılar | `directive_note()` aynı desende yazılacak |
| `GM_ONLY_FIELDS` — `:628` | `public_world_state()` bunları oyuncudan siler | `plot` buraya eklenecek |
| `STATE_KEYS` — `:698` | Fence'i unutulmuş ham JSON'ı tanıma sözlüğü | `plot` buraya da eklenecek |
| `deep_merge_world_state()` — `:533` | state-update yaması uygular | Beat durumu güncellemesi buradan geçebilir |
| `TIME_FIELDS` — `:147` | `time_of_day/clock/season/weather/temperature` | Tetikleyicilerin zaman ekseni |
| `roll_world_dice()` — `:96` | Tur başına bir d100, sadece GM görür | Tetikleyicilerin şans ekseni |
| `gm_note()` — `:1410` | GM müdahalesi; `gizli` / `sahne` / `surpriz` modları | Senarist paneli bunun yanına oturur |
| `gm_state()` — `:1384`, `gm_patch()` — `:1346` | GM ekranının okuma/yazma uçları | Plan UI'ı bunları genişletir |
| `data/state.json` | Tek kalıcı durum dosyası, `version` sayacı ile poll | `plot.json` kardeşi olacak |

### Kritik kısıt — senarist ÇAĞRISI ayrı oturum olmalı

`call_claude` iki nedenle senarist için kullanılamaz:

1. `--tools ""` — CLI'da araç yok. Yani Claude Code **skill'leri otomatik
   yüklenmez**. `.claude/skills/senarist/SKILL.md` koysan bile model onu asla
   okuyamaz. Çözüm: SKILL.md diskten okunup `--system-prompt` olarak verilir.
2. `--resume session_id` — anlatıcının kalıcı hikâye oturumu. Senaristi oraya
   sokmak, planlama gevezeliğini hikâye bağlamına bulaştırır.

Senarist için ayrı bir fonksiyon: `call_scenarist(prompt, system_prompt)` —
`session_id` yok, her seferinde taze oturum, girdisi tamamen prompt'tan gelir.

---

## 3. Veri modeli — `data/plot.json`

```json
{
  "version": 1,
  "updated_day": 98,
  "threads": {
    "tarik_kimlik": {
      "premise": "Tarık aslında Emir; Arınma Cemaati'nin lideri.",
      "status": "aktif",
      "reveal_target_day": 104
    }
  },
  "beats": [
    {
      "id": "muhur_ipucu",
      "thread": "tarik_kimlik",
      "when": {
        "day_gte": 101,
        "location_in": ["Kalan Umut kampı"],
        "tension_gte": "orta",
        "flags_set": ["sevil_guveni"],
        "flags_unset": ["muhur_gorulmus"],
        "world_roll_lte": 40
      },
      "directive": "Sevil'in çadırında Arınma Cemaati mührü görünür olsun. Açık söyleme, sadece göster. Oyuncular fark etmezse zorlama.",
      "on_fire": {"flags": {"muhur_gorulmus": true}},
      "expires_day": 106,
      "state": "pending",
      "fired_day": null
    }
  ],
  "seeds": ["Okan'ın ıslak defteri henüz okunmadı"]
}
```

Kurallar:

- `when` alanları **VE** ile bağlanır. Boş `when` = bir sonraki turda ateşler.
- `state`: `pending` | `fired` | `expired` | `vetoed`.
- `directive` sahneyi **dayatmaz**, koşulu tarif eder. "Şu şöyle bitsin" yazma —
  oyuncu ajansını öldüren şey bu.
- `expires_day` zorunlu. Vadesiz beat 20 tur sonra alakasız yerde patlar.
- Tur başına **en fazla bir** beat ateşler (öncelik: en eski `expires_day`).
  Aynı anda üç direktif giden bir sahne okunmaz hale gelir.

Not: `world_state.narrator.upcoming_events` bugün serbest metin olarak benzer
bir işi güya yapıyor ama deterministik değil. Faz 5'te ya `plot.json`'a devredin
ya da "senaristin taslak defteri" olarak bırakın — ikisini birden koşullu
tetikleyici kaynağı yapmayın.

---

## 4. Fazlar

Her faz tek başına çalışır durumda bitmeli. Faz 1 bitince oyun zaten kazançlı —
sonraki fazlar gelmese de sistem tutarlı kalır.

### Faz 0 — İskelet (davranış değişmez)

- `director.py`: `load_plot()`, `save_plot()`, `DEFAULT_PLOT`.
- `data/plot.json` yoksa boş şablonla üretilir.
- `plot` alanını `GM_ONLY_FIELDS` ve `STATE_KEYS` listelerine ekle.
  (Not: plan `state.json`'un içinde değil, ayrı dosyada durur. `GM_ONLY_FIELDS`
  eklemesi, ileride özet halinde `world_state`'e yansıtılırsa oyuncuya sızmasın
  diye savunma amaçlıdır.)
- **Kabul**: `py_compile` temiz, sunucu açılıyor, oyun eskisi gibi çalışıyor,
  `plot.json` oluşmuş.

### Faz 1 — Tetikleyici motoru + direktif enjeksiyonu

Kalbi bu. Beat'ler bu fazda **elle** `plot.json`'a yazılır; senarist yok.

- `director.py`:
  - `evaluate(plot, world_state, world_entry) -> beat | None` — koşul kontrolü.
    `tension` sıralı karşılaştırması için `düşük < orta < yüksek` haritası gerek.
  - `expire(plot, day)` — `day > expires_day` olanları `expired` yap.
  - `directive_note(beat) -> str` — prompt bloğu, mevcut `*_note()` deseninde.
- `server.py` / `post_message`:
  - Zar atıldıktan (`world_entry`) hemen sonra `expire` + `evaluate`.
  - Ateşleyen beat varsa `directive_note(beat)` metnini `extra_system` içine,
    `UPKEEP_REMINDER`'dan **önce** ekle — iki dala da (`:1070`, `:1147`);
    chargen dalına ekleme.
  - Model cevabı işlendikten sonra (`:1202` civarı): beat'i `fired` işaretle,
    `fired_day` yaz, `on_fire.flags` varsa `world_state["flags"]`'e uygula,
    `save_plot()`.
  - Ateşleme kaydı `gm_log`'a düşsün ki GM ne olduğunu görsün.
- **Kabul**: elle yazılmış bir beat, koşulu sağlanan turda prompt'a giriyor ve
  sahnede karşılığı görünüyor; ikinci turda tekrar ateşlemiyor; koşulu hiç
  sağlanmayan beat `expires_day` sonrası `expired` oluyor; oyuncu `/api/state`
  cevabında plan izi yok.

### Faz 2 — GM paneli

- `GET /api/gm/plot`, `POST /api/gm/plot` (PIN kontrolü `gm_note` desenine
  birebir uysun). İşlemler: beat ekle, düzenle, `veto`, "şimdi ateşle"
  (koşulu atlayıp bir sonraki tura zorla).
- `static/secrets.html`: bekleyen / ateşlenmiş / çürümüş beat listesi.
  Mevcut `challenges` ve dünya zarı panellerinin yanına, aynı CSS diliyle.
- **Kabul**: GM tarayıcıdan beat ekleyip veto edebiliyor, sunucu yeniden
  başlatılınca kayıp yok.

### Faz 3 — Senarist çağrısı (planı model yazar)

- `.claude/skills/senarist/SKILL.md` — **zanaat bilgisi**: iyi beat nasıl yazılır,
  ekim-hasat aralığı, foreshadow dozu, ton, "sonuç dayatma" yasağı. Mekanik
  kural buraya girmez (o kodda).
- `director.py`: `call_scenarist()` — ayrı `claude -p` süreci, `--system-prompt`
  olarak SKILL.md + JSON şema, `--resume` YOK.
  Girdi: `plot.json` + `narrator.plot_summary` + son N tur özeti + `world_state`.
  Çıktı: yeni/güncellenmiş beat listesi (JSON).
- Model çıktısı **doğrulanmadan** yazılmaz: bilinmeyen alan at, `expires_day`
  yoksa varsayılan koy, `id` çakışmasını çöz.
- Tetikleme sırası: önce `/secrets`'ta **"Plan üret"** butonu (deterministik,
  ucuz test). Otomatik vade (her N turda bir) ondan sonra, ayarı kapatılabilir
  şekilde.
- **Kabul**: butona basınca `plot.json` mantıklı beat'lerle doluyor, bozuk çıktı
  dosyayı bozmuyor, oyuncu turu bu sırada bloke olmuyor.

### Faz 4 — Süreklilik denetçisi

Gerçek bir ağrıyı çözer: envanterden atılan madalyonun üç sahne sonra geri
gelmesi gibi hatalar (bkz. `data/gm_log.jsonl` geçmişi).

- Tur sonrası ucuz ikinci çağrı: son sahne + envanter + `plot.json` + son 6 tur.
- Çıktı: `{"conflicts": [{"severity": "...", "detail": "..."}]}`.
- Çelişki varsa `gm_log`'a uyarı; oyuncu görmez. Otomatik düzeltme YOK — kararı
  GM verir.
- Oyuncu cevabını geciktirmesin: turu döndürdükten sonra çalışsın.
- **Kabul**: bilerek üretilmiş çelişki (elle silinmiş eşyayı sahnede kullandır)
  `/secrets`'ta uyarı olarak görünüyor.

### Faz 5 — Cila

- Beat'lerin `challenges` ile bağı: ateşlenen beat challenge açsın/ilerletsin.
- `world_roll` koşullu beat'ler (`world_roll_lte`) canlı testten geçsin.
- `narrator.upcoming_events` ile çakışmayı çöz (bkz. Bölüm 3 notu).
- `webapp/README.md`'ye "Senarist katmanı" bölümü; `data/plot.json` dışa/içe
  aktarma uçlarına (`/api/game/export`, `:1611`) dahil edilsin.

---

## 5. Test yöntemi

Bu projede test altyapısı yok. Mevcut pratik: geçici betikle sunucuyu import
edip fonksiyonu doğrudan çağırmak. Aynısını sürdür:

```python
import sys
sys.path.insert(0, r"C:\GITHUB\dnd-Game\webapp")
import director

plot = director.load_plot()
ws = {"day": 101, "location": "Kalan Umut kampı", "tension": "orta",
      "flags": {"sevil_guveni": True}}
print(director.evaluate(plot, ws, {"roll": 30}))
```

Her fazdan sonra: `python -m py_compile server.py director.py`, sonra sunucuyu
başlatıp bir tur oyna. Canlı `data/state.json` üstünde deneme yapmadan önce
kopyala — içinde devam eden gerçek bir oyun var (Gün 98 civarı).

---

## 6. Riskler

- **Ajans ölümü** — plan her turda devreye girerse oyuncu ne yaparsa yapsın aynı
  sahneye çıkar. Panzehir: tur başına tek beat, `directive` koşul tarif eder,
  `expires_day` zorunlu.
- **Gecikme** — senarist ve denetçi çağrıları oyuncu turunu bekletirse oyun
  hantallaşır. İkisi de sıcak yolun dışında kalmalı.
- **Sızıntı** — plan `/api/state` ile oyuncuya giderse tüm sürprizler yanar.
  `GM_ONLY_FIELDS` + ayrı dosya + Faz 1 kabul testi bunu korur.
- **Maliyet** — her tur ekstra iki çağrı pahalı. Senarist elle/vadeli, denetçi
  kısa prompt.
- **Şema kayması** — model uydurma alanlı beat üretir. `plot.json`'a yazmadan
  önce beyaz liste ile süz.

---

## 7. Karar bekleyen konular

Uygulayan oturum bunları sahibine sorsun, kendi kafasına göre seçmesin:

1. Senarist otomatik mi çalışsın (her N tur), yoksa sadece GM butonuyla mı?
2. Ateşlenen beat oyuncuya belli olsun mu (ör. `challenges`'ta yeni satır), yoksa
   tamamen görünmez mi kalsın?
3. Denetçi hangi modelle koşsun — anlatıcıyla aynı mı, daha ucuz olan mı?
