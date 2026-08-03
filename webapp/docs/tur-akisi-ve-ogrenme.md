# Tur bazlı akış, seçenek havuzu ve öğrenme katmanı

Bu belge üç yeni sistemi anlatır: oyunun **tur bazlı** hale gelmesi, her
karaktere sunulan **seçenek havuzu** ve oyunun kendi oynanışından ders çıkaran
**öğrenme defteri**. Mimari kurallar için `mimari.md`, arayüz için
`tasarim-sistemi.md`.

---

## 1. Tur bazlı akış

Eskiden her mesaj anında modele gidiyordu: ilk yazan turu açıyor, diğerleri
onun sahnesine yetişmeye çalışıyordu. Artık bir tur şöyle işler:

```
anlatıcı sahneyi yazar ──► her karaktere 5-10 seçenek bırakır
        │
        ▼
   TUR AÇILIR  (state["round"].status = "acik", süre sayacı başlar)
        │
        ├── Okan seçer  → sunucu d100 atar → zar animasyonla gösterilir → kilit
        ├── Emir seçer  → kendi zarı
        └── Celil seçmez → süre dolar
        │
        ▼
   TUR GÖNDERİLİR (tek mesaj, tüm seçimler + zarlar birlikte)
        │
        ▼
   anlatıcı hepsini aynı sahnede çözer ──► yeni seçenekler ──► yeni tur
```

Önemli noktalar:

- **Zar seçim anında atılır** (`round_service.pick`), sunucuda, kriptografik
  RNG ile. Arayüzdeki animasyon sadece sonucu sunar; sonucu üretmez. Zar
  atıldıktan sonra seçim değiştirilemez.
- **Seçimler hafızada birikir**, modele gitmez. Model çağrısı yalnızca tur
  kapanırken bir kez yapılır — hem tutarlı bir sahne çıkar hem de kota yanar.
- **Herkes seçince tur kendiliğinden gönderilir.** Kimse beklemek zorunda
  değilse "Turu şimdi gönder" düğmesi de vardır.
- **Süre dolarsa** (`settings.turn_seconds`, 0 = süresiz) tur yine gönderilir
  ve seçim yapmayanlar için anlatıcıdan **ani sahne** istenir: kararsızlığın
  kendisi bir olaya dönüşür, dünya beklemez.
- Aynı turu iki tarayıcı birden göndermeye kalkarsa sunucu ikincisini
  `{"skipped": true}` ile geri çevirir (kilit + `round_no` kontrolü).
- Model çağrısı hata verirse tur **açık kalır**; seçimler ve zarlar kaybolmaz.

Serbest yazışmaya dönmek isteyen masalar için `settings.round_mode = false`:
o zaman eski `/api/message` akışı (ve "Ortak Karar" düğmesi) geçerlidir.

## 2. Seçenek havuzu

Anlatıcı her turun sonunda state-update bloğuna `options` yazar:

```json
{"options": {"Okan": [{"text": "Galeri ağzına in", "category": "riskli",
                       "cost": "2 fişek + gürültü"}]}}
```

Kurallar (motor eki, `scenario.SYSTEM_APPENDIX`):

| Kural | Nerede zorlanır |
|---|---|
| Karakter başına 5-10 seçenek | `options_service.refresh` eksikleri tamamlar |
| Sekiz kategoriden biri | `models/options.canon_category` (eş anlamlıları eşler) |
| Her listede en az 3 farklı kategori | prompt kuralı + jenerik tamamlama |
| Sahne dışındaki karaktere seçenek yok | `refresh(world, present_players)` |
| Kelimesi kelimesine tekrar yok | `options_service.recent_note` (havuz geçmişi) |

Kategoriler: `güvenli`, `riskli`, `gizemli`, `körü körüne`, `kurnaz`, `insani`,
`acımasız`, `hazırlık`. Kategori bir vaattir — seçimin ruhunu belirler ve zar
yorumuna girer (`[körü körüne]` bir hamlede karakter düşünmeden atılmıştır).

Oyuncu her zaman **kendi hamlesini** yazabilir; o zaman kategori `serbest`
olur. Sunulan ve seçilen HER seçenek `data/options_pool.jsonl` dosyasına
düşer — havuz hem tekrar denetimi hem de öğrenme için kullanılır.

## 3. Öğrenme defteri (Claude yeteneği)

`data/learning.json` + `data/learning_events.jsonl`. Her tur şunlar kaydedilir:
seçilen kategori, zar ve bandı, havuzdan mı seçildiğI, süre aşımı, karar
süresi, o turda çıkan ölüm/yara/çözülen zorluk sayıları.

Bu ham sayaçlardan **dersler** üretilir (`learning_service._derive`) — hepsi
bir eşiğe bağlıdır, az veriden büyük sonuç çıkarılmaz:

- kategori payı %40'ı geçerse → "bu masa X oynuyor, aynı kalıbı tekrarlama"
- bir kategoride felaket oranı ≥%25 → "riski ÖNCEDEN sezdir"
- serbest metin oranı ≥%50 → "seçeneklerin sahneye bağlı değil"
- süre 3+ kez dolduysa → "seçenekleri kısalt"
- 12+ tur zorluk kapanmadıysa → "zorlukları kapanabilir tut"

Anlatıcı da kendi gözlemini ekleyebilir (`learning.lessons_add`), GM ise
`/secrets` ekranından elle yazabilir; elle yazılanlar otomatiklerin önünde
prompt'a girer.

Dersler her turda **ÖĞRENİLENLER** bloğu olarak prompt'a döner ve aynı anda
`.claude/skills/kizil-cokus-anlatici/ogrenilenler.md` dosyasına yazılır. Yani
öğrenilenler bu sunucunun dışında da yaşar: bir sonraki Claude Code oturumu
yeteneği yükler ve masayla ilgili aynı bilgiyle devam eder.

Ek model çağrısı **yoktur**: ders üretimi koddadır, bu yüzden her turda
çalışabilir ve bedeli sıfırdır.

Oyunu sıfırlamak defteri SİLMEZ (`/api/reset` → `keep_learning: true`
varsayılan). Gerçekten sıfırdan başlamak için `keep_learning: false`.

## 4. Her oyun farklı başlar

`worldgen_service` her `/api/start` çağrısında:

- `scenario.START_LOCATIONS` havuzundan **daha önce kullanılmamış** bir
  başlangıç noktası seçer (ad, tür, tarif ve o mekânın YAPISAL ZAAFI). Sabit
  "eski metro istasyonu" kaldırıldı.
- `FACTION_NAMES` × `FACTION_ARCHETYPES` çaprazından 4-6 fraksiyon üretir; ad
  kullanılmışsa atlanır, arketip eşleşmesi her oyunda değişir (bir oyunda
  çete olan ad, başka oyunda telsizci ağı olabilir). Özel bir senaryo içe
  aktarılmışsa onun fraksiyonları da isim havuzuna katılır ve kendi gizli
  yüzleriyle korunur.
- Üretilen dünya öğrenme defterine not edilir (`used_starts`, `used_factions`)
  ve anlatıcı günlüğüne `role: "worldgen"` girdisi olarak yazılır.

## 5. Motor eki (`SYSTEM_APPENDIX`)

Seçenek havuzu, tur akışı, harita, refleks/küfür ve öğrenme kuralları
**senaryoya değil motora** aittir. Bu yüzden `scenario.SYSTEM_APPENDIX` ayrı
durur ve `ScenarioRepository.load()` onu yürürlükteki her senaryo metnine
(varsayılan ya da içe aktarılmış) ekler. Böylece bu mekanikleri hiç bilmeyen
eski bir senaryo dosyası içe aktarılsa bile oyun doğru çalışır. Ek, kendi
işaretini (`APPENDIX_MARKER`) taşır: iki kez eklenmez.

## 6. Harita, refleks ve küfür

- **Harita** (`world_state.map`): `current` (grubun konumu), `places` (bilinen
  yerler: tür, durum, tehlike, komşuluk) ve `party` (kim nerede). Anlatıcı
  state-update ile yazar; sunucu ayrıca `location` ve karakterlerin `location`
  alanından haritayı besler, ama bu turda yazılmış `party` kaydının üzerine
  yazmaz.
- **Refleks** (`characters.<isim>.reflex`): kurulum ekranından gelir, baskı
  altındaki ilk tepkidir. Felaket/Kritik bantlarda ve gerilim yükseldiğinde
  anlatıcı bunu fiilen oynatır.
- **Küfür dozu** (`settings.profanity`): `kapalı` | `hafif` | `sert`. Her tur
  prompt'a "KÜFÜR AYARI" satırı olarak girer. Küfür anlatıcının değil,
  karakterlerin ağzından çıkar; nefret söylemi hiçbir dozda yoktur.
