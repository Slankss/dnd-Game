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
   TURUN BAŞI  (round_service.ensure_open)
        │  bekleyen sahne YAYINLANIR: dünya yaması uygulanır, sahne akışa
        │  düşer, yeni seçenek havuzu doğar (3-8 seçenek, sabit değil)
        │  (release → _publish_scene)
        ▼
   TUR AÇILIR  (state["round"].status = "acik", süre sayacı başlar)
        │
        ├── Okan seçer  → sunucu turun d100'ünü atar → animasyon
        │   Okan fikrini değiştirir → AYNI zar, yeni karar
        ├── Emir seçer  → kendi zarı
        └── Celil seçmez → süre dolar
        │
        ▼
   "TURU GEÇ"  (oyuncu basar; ya da süre dolarsa sayaç gönderir)
        │  tüm seçimler TEK mesajda anlatıcıya gider
        ▼
   anlatıcı sahneyi yazar ──► sahne KUYRUĞA yazılır (yayınlanmaz)
        │  bu turda tetiklenenler de kuyruğa: gürültü, yolculuk, olaylar, beat
        ▼
   BİR SONRAKİ TURUN BAŞI ──► hepsi devreye girer
```

Önemli noktalar:

- **Hikaye YALNIZ sunulan seçeneklerle ilerler.** Oyuncu kendi planını yazamaz:
  `round_service.pick` yalnız `option_id` kabul eder, gövdede metin gelirse
  reddeder; `/api/message` (serbest metin turu) yalnız karakter oluşturma
  sürerken açıktır ve chargen bitince kapanır; `settings.round_mode` kapatılamaz.
  Hiçbir seçenek uymuyorsa tek çıkış **"bu turda bekle"**dir.
- Kaçış yolu kalmadığı için sunucu iki şeyi garanti eder: karakter başına en az
  5 seçenek ve her listede **en az bir düşük riskli seçenek** (güvenli /
  hazırlık / insani). Anlatıcı sadece ölümcül seçenekler yazarsa
  `options_service._ensure_safe_exit` sona güvenli bir çıkış ekler.
- **Zar seçim anında atılır** (`round_service.pick`), sunucuda, kriptografik
  RNG ile. Arayüzdeki animasyon sadece sonucu sunar; sonucu üretmez.
- **Karar değiştirilebilir, zar değiştirilemez.** Oyuncu turu geçene kadar
  başka bir seçeneğe geçebilir; turda **son seçtiği** karar işlenir. Zar tur
  başına ve oyuncu başına BİR KEZ atılır (`round_service._turn_roll`) — aksi
  halde beğenilmeyen zarı yenilemek için seçenek değiştirmek serbest kalırdı.
  Sunucu yanıtındaki `changed: true` bunu istemciye bildirir; arayüz zar
  animasyonunu yeniden oynatmaz.
- **Seçimler hafızada birikir**, modele gitmez. Model çağrısı yalnızca tur
  kapanırken bir kez yapılır — hem tutarlı bir sahne çıkar hem de kota yanar.
- **Turu oyuncu geçirir.** Herkes seçse bile tur kendiliğinden ilerlemez;
  `RoundBar`'daki **"Turu Geç"** düğmesine basılması gerekir. Masa kararları
  konuşabilsin ve isteyen son ana kadar fikrini değiştirebilsin diye.
- **Tek istisna süredir**: `settings.turn_seconds` (0 = süresiz) dolduğunda tur
  kendiliğinden gönderilir ve seçim yapmayanlar için anlatıcıdan **ani sahne**
  istenir: kararsızlığın kendisi bir olaya dönüşür, dünya beklemez.
- Aynı turu iki tarayıcı birden göndermeye kalkarsa sunucu ikincisini
  `{"skipped": true}` ile geri çevirir (kilit + `round_no` kontrolü).
- Model çağrısı hata verirse tur **açık kalır**; seçimler ve zarlar kaybolmaz.

`settings.round_mode` alanı eski kayıtlarla uyum için duruyor ama **kapatılamaz**:
serbest yazışma kipi kaldırıldı, `/api/settings` bunu 400 ile reddeder.

## 1b. Tur geçişi — hiçbir şey tetiklendiği turda devreye girmez

Kural: **bir turda üretilen her şey bir sonraki turun başında devreye girer.**
Oyuncu, kararını verdiği anda o karara sebep olmayan bir sürprizle
cezalandırılmasın; "ne oldu" bilgisi her zaman turun BAŞINDA gelsin.

Kuyruk `state["pending"]` altında düz JSON olarak durur (`models/pending.py`),
üç tür kayıt taşır:

| Tür | Ne zaman yazılır | Ne zaman devreye girer |
|---|---|---|
| `sahne` | Anlatıcı tur N'i çözdükten sonra (`commit`) | Tur N+1'in başında yayınlanır (`release` → `_publish_scene`) |
| `tehdit` | Tur N'de çıkan gürültü, yolculuk niyeti ve anlatıcının bildirdiği olaylar | Tur N+1'in karşılaşma zarına girer (`threat_service.prepare(carry=…)`) |
| `direktif` | Tur N'de vadesi gelen senarist beat'i (`director.take_due`) | Tur N+1'in sahnesini şekillendirir (`director.find`) |

Sonuçları:

- **Sahne yayını turun başındadır.** `commit` sahneyi yayınlamaz, kuyruğa yazar;
  yayını `ensure_open` yapar. İkisi aynı istekte peş peşe çalıştığı için oyuncu
  bekleme hissetmez — ama sunucu tur ortasında ölürse sahne kaybolmaz, ilk
  `/api/state` yoklamasında yayınlanır.
- **Gürültü bir tur sonra ödenir.** Tur N'de tüfek patlatan grup tur N'de değil,
  tur N+1'de sürüyle karşılaşır. Anlatıcıya giden tehdit bloğu bunu açıkça
  söyler: "bu blok GEÇEN turda olanların sonucudur".
- **Anlatıcının bildirdiği olaylar da ertelenir.** `threat.events` yaması
  (patlama/alarm/yangın) `world_patch._merge_threat` içinde uygulanmaz;
  `defer_events` listesine biriktirilip kuyruğa yazılır, göç bir sonraki turun
  başında olur.
- Yayın sırasında beklenmedik bir hata çıkarsa sahne düşer ama **sessizce
  değil**: akışa bir sistem satırı yazılır ve oyun tıkanmaz.

## 1c. Anlatıcı metninde seçenek listesi yasak

Sahne metni yalnızca **yaşananları ve sonuçlarını** anlatır. Karar seçenekleri
metinde değil, yalnızca seçenek panelinde gösterilir — aksi halde aynı liste iki
yerde okunuyor ve metindeki liste ile havuzdaki liste birbirini tutmuyordu.

İki katmanlı savunma:

1. **Prompt**: `scenario.SYSTEM_APPENDIX` → "ANLATICI METNİ — SEÇENEK LİSTESİ
   YASAK" ve `SCENARIO_TEXT` → SAHNE YAPISI 4. madde (sahne tek satırlık bir
   **DURUM** özetiyle biter).
2. **Sunucu**: `models/text.strip_option_block` sahne metninin sonundaki
   "SEÇENEKLER:" başlığını, madde madde (A)/B)/1.) yazılmış alternatifleri ve
   "(Oyuncular sadece sunulan seçeneklerden…)" kuyruğunu keser. Karakter
   oluşturma turlarında kesme YAPILMAZ — orada liste meşrudur, oyuncu yazarak
   seçer.

Metnin tamamı seçenekten ibaretse hiçbir şey kesilmez: boş sahne yayınlamaktansa
kuralı ihlal eden sahneyi yayınlamak yeğdir.

## 1d. Harcama — envanteri anlatıcı değil sunucu tutar

Silah sıkılıyor ama mermi azalmıyordu. Sebebi tek bir satırda: `Person.inventory`
düz bir isim listesiydi, **miktar kavramı yoktu**. Kusursuz bir anlatıcı bile
"12 → 9" yazamazdı, yazacak alan yoktu. Üstelik tüketim, yanıt metninden
okunmaya çalışılıyordu ("bu turda ateş etti mi?") — serbest metinden güvenilir
biçimde çıkarılamayacak bir bilgi.

Çözüm metni ayrıştırmak değil: oyuncu ne yapacağını zaten **seçiyor** ve seçim,
sahne yazılmadan **önce** belli.

**Veri.** `Person.inventory_counts` = `{"9mm fişek": 12}` (`models/inventory.py`).
Miktar isimden ayrı tutulur — sayı iki yerde dursaydı biri eskirdi. Envanterdeki
`"12 9mm fişek"` gibi eski kayıtlar yüklenirken otomatik ayrıştırılır
(`Person._backfill_counts`). Sayacı sıfırlanan kalem envanterden düşer ve
`lost_items`'a geçer.

**Dört katman** (`services/inventory_service.py`):

| Katman | Ne yapar | Nerede |
|---|---|---|
| Beyan | `Option.spend` = `{"9mm fişek": 2}`; sunucu turun çözümünde keser | `round_service.commit` → `InventoryService.apply` |
| Bildirim | Anlatıcıya "HARCAMA (sunucu kesti…)" zorunlu bloğu + "SAYILABİLİR STOK" listesi | `InventoryService.note` / `stock_note` |
| Süzgeç | Karşılanamayan seçenek **hiç sunulmaz**; mermisi bitene "ateş aç" çıkmaz | `options_service._affordable` |
| Güvenlik ağı | `spend` yazılmamışsa metinde ateş izi aranır, zar bandına göre 1-3 fişek düşer | `InventoryService._apply_one`, `looks_like_firing` |

Kenar durumlar:

- **Kuru tetik**: ateş eden hamle ama mermi yok → hiçbir şey kesilmez, anlatıcıya
  "ATEŞ EDEMEDİ, tetik boşa düştü (klik)" bildirilir. Süzgeç yüzünden nadirdir
  ama bir yolla olursa sahne tutarlı kalır.
- **Sayaçsız kalem**: "yarım saat", "kol gücü" gibi soyut bedeller ve henüz
  sayılmamış eşyalar seçeneği engellemez ve kesilmez — yoksa liste boşalırdı.
- **Çift kesim**: anlatıcıya "bu kalemleri state-update'te TEKRAR düşürme"
  denir; `spend` ile `inventory_remove` üst üste binmez.

## 1e. Eşyalar — sabit katalog ve hikaye eşyaları

Oyunda **iki tür eşya** vardır ve ayrı durmaları bilerektir.

### Sabit katalog (`data/items.json`)

Her oyunda AYNIDIR ve mekaniği vardır. 111 eşya, 11 kategori (`yakın silah`,
`menzilli silah`, `mühimmat`, `giyim`, `yiyecek`, `içecek`, `tıbbi`, `alet`,
`elektronik`, `yakıt`, `takas`), 21 yer türü. Salt okunur içerik dosyasıdır:
`/api/reset` silmez, tur akışı değiştirmez (`ItemsRepository` bir kez okur ve
dosya değişmedikçe bellekte tutar).

Bir eşyanın alanları:

```json
{"id": "9mm-tabanca", "ad": "9mm tabanca", "kategori": "menzilli silah",
 "nadirlik": "nadir", "taban": 1, "mermi": "9mm fişek",
 "bulunur": {"karakol": 55, "askeri": 45, "otel": 6, "konut": 5, "metro": 2}}
```

- **`bulunur`** = yer türüne göre bulunma ağırlığı. İstenen asimetri buradan
  gelir: 9mm tabanca karakolda 55, metro istasyonunda 2. Eşleşmeyen yer için
  `taban` geçerlidir.
- **`nadirlik`** ikinci bir frendir (`RARITY_FACTOR`: yaygın 1.0 · nadir 0.55 ·
  çok nadir 0.22) — çok nadir eşya doğru yerde bile kolay çıkmasın.
- **`doyum` / `susuzluk`** yiyecek ve içeceklerin açlık/susuzluk düşürme oranı
  (askeri tayın 55, konserve fasulye 30, su şişesi 35, damacana 70).
- **`sayilabilir` + `adet`** mühimmat/erzak gibi kalemler sayaçla gelir
  (§1d'deki `inventory_counts`).
- **`mermi`** menzilli silahın harcadığı mühimmatın adı.

**Yer türü tanıma** tehdit motoruyla aynı mantıktadır: yer ADI Türkçeye duyarlı
normalize edilir, anahtar kelimeler kök olarak aranır, en uzun eşleşme kazanır.
"Aile sağlığı merkezi" → `hastane`, "Eski metro istasyonu" → `metro`.

**Arama** (`ItemsService.search`): hamle metninde arama izi varsa
(`looks_like_searching`) sunucu katalogdan ağırlıklı, tekrarsız çekiliş yapar.
Kaç kalem çıkacağını **zar bandı** belirler (Felaket 0 · Kritik 2-4).
Bulunanlar envantere yazılır ve anlatıcıya "ARAMA SONUCU" zorunlu bloğuyla
bildirilir: listede olmayan bir şey buldurmak, bulunanı tekrar eklemek yasaktır.

### Bir mekan bir kez taranır

Kural kesindir ve üç yerde birden zorlanır:

| Katman | Ne yapar |
|---|---|
| Seçenek garantisi | Bulunulan yer taranmamışsa listede MUTLAKA bir "burayı tara" seçeneği olur — anlatıcı yazmadıysa `options_service._search_gate` ekler. Serbest hamle olmadığı için bu seçenek sunulmazsa mekanı arama imkanı hiç doğmaz. |
| Seçenek süzgeci | Yer bir kez tarandıysa arama seçeneklerinin **hepsi** listeden elenir. |
| Sunucu kapısı | Eski/bayat bir seçenek yine de seçilirse `search()` `already: True` döner, hiçbir şey çıkmaz ve anlatıcıya "ZATEN TARANMIŞ" bildirilir. |

Kötü zar da mekanı harcar: boş çıkan arama sonrası yer yine "tarandı" sayılır
("aceleyle bakıldı, işe yarar bir şey çıkmadı"). Bu, grubu tek bir depoda
oturmaktan çıkarıp haritaya iten temel baskıdır — yeni malzeme ancak yeni bir
yere giderek bulunur.

Kayıt `world_state.searched` = `{yer: {"found": n}}`. Oyuncu arayüzünde harita
panelinde taranan yerlerin yanında "tarandı" rozeti görünür, böylece seçeneğin
neden kaybolduğu belli olur.

**Anahtar kelime taraması** (`items_service.icerir`) iki listeyle çalışır:
`SEARCH_PHRASES` alt dize olarak, `SEARCH_VERBS` **tam kelime** olarak aranır.
Ayrımın sebebi somut bir hata: "arar" alt dize olarak "kararlı" içinde geçiyor
ve kararlılıkla kapı tutan karakter "arama yapmış" sayılıyordu. Aynı düzeltme
ateş (`inventory_service.FIRE_WORDS`) ve yeme kalıpları için de geçerli.

**Tüketim** (`ItemsService.consume`): harcanan kalem katalogda yiyecek/içecekse
`vitals.hunger` / `vitals.thirst` sunucuda düşer ve anlatıcıya "TÜKETİM" bloğu
gider. "Karnınız doydu" cümlesi göstergeyi değiştirmez. Anlatıcı `spend`
yazmayı unutur ama hamle "ye/iç" derse `auto_consume` envanterdeki en doyurucu
katalog kalemini tüketir — mermi güvenlik ağının aynısı.

### Hikaye eşyaları (`world_state.story_items`)

Bu oyuna özeldir, anlatıcı üretir, **yalnızca anlatı etkisi taşır**: açlık
doldurmaz, zar değiştirmez, mermi olmaz, sayaç açılmaz.

```json
{"story_items": {"Sarı zarf": {"sahip": "Okan", "nerede": "Okan'ın cebinde",
                               "not": "Mühürlü; üstünde sadece bir tarih var."}}}
```

- Sahibi belliyse adı envanterinde de görünür (`_merge_story_items`), ama
  katalog aramaları onu bulamaz ve `consume` ona bakmaz — mekanik yolların
  hepsi katalogdan geçer, katalogda olmayan eşya sessizce etkisizdir.
- Sunucu her turda "HİKAYE EŞYALARI" bloğuyla defteri anlatıcıya geri verir:
  on tur önce bulunan zarf unutulmasın.
- `null` yazmak defterden düşürür (yakıldı, verildi, kayboldu).

### Katalogu görmek ve genişletmek

Katalog iki yerden okunur: `GET /api/items` (herkese açık) ve
`GET /api/gm/items` (PIN'li, anlatıcı ekranı). İkisi de her eşyanın en olası üç
yerini hesaplanmış olarak döner.

Anlatıcı ekranındaki **Eşya kataloğu** paneli listeyi kategoriye/yere/ada göre
süzer ve yeni eşya eklemeyi sağlar (`POST /api/gm/items`). **Eklenen eşya
KALICIDIR**: `data/items.json`'a yazılır, yani oyunun durumuna değil içeriğine
girer. Sunucu yeniden başlasa, `/api/reset` çekilse, yeni oyun kurulsa bile
durur ve o andan itibaren her oyunda aranırken çıkabilir.

Doğrulama sunucudadır (`ItemsService.add_item`) — bozuk bir kayıt tek bir oyunu
değil hepsini etkilerdi: ad zorunlu ve tekil, kategori/nadirlik/yer türü
katalogda tanımlı olmalı, ağırlıklar 0-100, ve eşyanın en az bir yerde ya da
`taban` ile bulunabilir olması gerekir. Kimlik addan türetilir ve çakışırsa
sayı eklenir.

## 1f. Harita — şehirler, kategoriler, yollar, mesafeler

Harita eskiden anlatıcının ağzından büyüyordu: bir yer adı geçince kayıt
açılıyor, komşuluk "oradan buraya yürüdük" diye ekleniyordu. Coğrafyası olmayan
bir listeydi — mesafe kavramı yoktu, "yol" diye bir şey yoktu.

**Artık dünya oyunun başında bir kez üretilir ve sabittir** (`models/mapgen.py`,
içerik `data/places.json`):

1. **Şehirler** — düzleme dağıtılmış 2-5 kasaba/mahalle, her birinin merkezi ve
   yarıçapı var (`map.cities`).
2. **Mekanlar** — her şehre kentsel dokusuna uygun kategorilerden mekan serpilir;
   her mekanın `category` (katalogla AYNI 21 yer türü), `city` ve `x`/`y` (km)
   alanları olur. Şehir aralarına kır mekanları (çiftlik, benzinlik, koruluk)
   dağılır ve `city` alanları "<şehir> kırsalı" olur.
3. **Yollar** (`map.roads`) — şehir içinde en yakın 3 komşu cadde/ara sokakla,
   şehirler anayolla bağlanır. Her yolun `kind`, `km`, `status` ve `risk` alanı
   vardır. **İki yer arasında birden fazla yol olabilir** (hızlı anayol +
   uzun ama sessiz patika), tek yol olabilir ya da hiç olmayabilir.
4. **Mesafeler** — her yolun gerçek uzunluğu üretimde hesaplanır (kuş uçuşu ×
   yol türünün sapma katsayısı). Rota `WorldMap.route` ile Dijkstra'dan çözülür;
   maliyet `km × durum çarpanı`, yani tıkalı yol daha pahalı, çökük yol
   kullanılamaz. `distances_from` bir yerden diğerlerine mesafeleri yakından
   uzağa verir.

Üretim sonunda birleşim-bul ile **haritanın tek parça olduğu garanti edilir**:
ulaşılamayan mekan kalmaz (çökük yollar bağlantı sayılmaz).

### Harita büyüklüğü

`settings.map_size` — oyun **başlamadan önce** değiştirilebilir; harita bir kez
üretildikten sonra `/api/settings` bunu 400 ile reddeder (üretilmiş mesafeleri
ve keşifleri anlamsız kılardı).

| Ayar | Şehir | Mekan | Yayılım |
|---|---|---|---|
| küçük | 2 | 12-16 | 16 km |
| orta | 3 | 20-26 | 28 km |
| büyük | 5 | 32-42 | 48 km |

### Sis perdesi — harita hazır ama görünmüyor

Bilgi düzeylerine **`bilinmiyor`** eklendi (rank 0). Üretilen her mekan bu
düzeyde başlar ve `public_place` onlar için `None` döner: oyuncu gövdesine HİÇ
girmezler. Yollar da süzülür (`public_roads`) — iki ucu da bilinmeyen bir yol
çizilirse yerin varlığı sızardı.

Harita gezdikçe açılır: `WorldMap.go()` varılan yeri `keşfedildi` yapar ve
`reveal_neighbours` ile **yol komşularını `duyuldu`** yapar. Yani gittiğin yer
haritayı bir adım büyütür.

**Anlatıcı ekranı haritanın TAMAMINI görür.** `/api/gm/state` sansürsüz
`world_state` döndürdüğü için üretilen bütün mekanlar, yollar ve şehirler
oradadır; `/api/state` ise yalnız keşfedileni taşır. Arayüzde ayrım
`bilgiDuzeyi`'ne eklenen dördüncü düzeyle yapılır:

| | Oyuncu (`/`) | Anlatıcı (`/secrets`) |
|---|---|---|
| `bilinmiyor` | gövdeye hiç girmez | küçük, noktalı, %40 saydam düğüm + "grup bilmiyor" rozeti |
| `duyuldu` | silik soru işareti | aynı |
| `görüldü` / `keşfedildi` | tam çizim | aynı |

`MapCanvas` oyuncu kipinde `bilinmiyor` düğümlerini ve onlara giden yolları
**ikinci kez** süzer (`gm` false ise). Sunucu zaten göndermiyor; bu, elle
yüklenmiş bir kayıt bile sızmasın diye ikinci emniyet kemeri.

Harita paneli anlatıcı kipinde "N mekanı grup bilmiyor" sayacını gösterir —
GM bir bakışta dünyanın ne kadarının keşfedildiğini görür.

Anlatıcının yazdığı `known: "bilinmiyor"` bunu tetiklemez — takma ad tablosu
onu `duyuldu`ya çevirir; gerçek gizlilik yalnız üretecin `Place.hide()`
çağrısıyla kurulur. Anlatıcı bir yeri yamalarsa o yer otomatik `duyuldu` olur:
sahnede adı geçen yer haritadan gizli kalamaz.

### Anlatıcıya giden bloklar

`prompt_builder.map_note` yerleri **şehre göre gruplayarak** listeler ve kaç
yerin henüz duyulmadığını söyler. `distance_note` bulunulan yerden bilinen
yerlere km / durak / yol türü / riski verir, birden fazla güzergâh varsa
"ALTERNATİF GÜZERGÂH" satırıyla bunu bir seçim olarak sunmasını ister, çökük
yolları "KAPALI YOL" diye bildirir. Senaryo eki "yeni yer UYDURMA" kuralını
taşır.

### Çizim

`mapLayout.js` iki kipli: koordinat varsa **coğrafi** (gerçek yerine çizer),
yoksa eski **halkalı** BFS (koordinat alanı eklenmeden önce başlamış oyunlar).
Coğrafi kipte şehirler arası mesafe gerçek ölçekte kalır ama şehir İÇİ dağılım
4.2× büyütülerek çizilir — yoksa 48 km'lik bir bölgede 2 km'lik kasabanın on
mekanı üst üste binerdi. Bu bir çizim kararıdır: gösterilen km değerleri
sunucudan geldiği gibi durur. Yollar türlerine göre farklı kalınlık/desende
çizilir, aynı çiftin ikinci yolu yaylandırılır, çökük yol kırmızı kesik çizgi.

## 1f-2. Herkes yalnız kendi turunu görür

Bir oyuncu, BAŞKA oyuncuların ne **seçtiğini** de ne **seçebileceğini** de
göremez. İki ayrı maskeleme var:

| Ne gizlenir | Nerede | Görünen tek şey |
|---|---|---|
| Karar (`round.picks`) | `serializers.mask_picks` | kimin karar VERDİĞİ — tur ne zaman kapanacak bilinsin |
| Menü (`world_state.options`) | `serializers.mask_options` | yalnız kendi havuzu |
| Envanter (`characters.*.inventory`) | `serializers.mask_inventory` | `envanter_gizli: true` bayrağı |

Neden üçü de: kararlar açık olsaydı herkes son seçeni bekler, kararını ona göre
ayarlardı. Menü açık olsaydı "ben şunu seçeceğim, sen bunu al" pazarlığı turun
kendisinin yerine geçerdi. Envanter açık olsaydı "kimde kaç fişek kaldı" masada
sorulacak bir şey olmaktan çıkıp panelden okunan bir tabloya dönerdi.

Kimin kaç seçeneği olduğu bile paylaşılmaz — sayı da bir ipucudur (mermisi
bitenin listesi kısalır). Envanterde gizlenen alanlar `inventory`,
`inventory_counts` ve `lost_items`; **yara, gösterge, durum ve konum açık
kalır** — onlar bakınca zaten görülen şeyler. NPC envanterine dokunulmaz: o
dünyanın bilgisi, bir oyuncunun özeli değil.

Nerede uygulanıyor: `create_app` içindeki **tek bir** `after_request`. Uçları tek
tek işaretlemek yerine tek nokta seçildi — bir ucu işaretlemeyi unutmak sızıntı
demek olurdu. `round` ya da `world_state` taşıyan her JSON yanıt buradan geçer.

Muaf olanlar: **anlatıcı** (zaten her şeyi görmek için var) ve **TEK EKRAN
masası** (masadaki tek cihazın kendinden bir şey saklaması anlamsız).

Kararlar tur geçilince açılır: `commit` her seçimi `role: "user"` satırı olarak
oyuncu günlüğüne yazar (metin, kategori, zar ve bandıyla), sahne de zaten kimin
ne yaptığını anlatır.

## 1g. Effort — anlatıcı her tur aynı derinlikte düşünmez

`--effort` sabit değil, **tura göre** seçilir (`models/effort.decide`).

Ölçüm bunu gerektirdi: aynı tur `high` ile 12 851, `medium` ile 6 932 çıktı
jetonu harcıyor ve görünen sahne 2 045'e karşı 1 864 karakter — yani %3.
Aradaki fark üslupta değil **defter tutmada**: `high` sunucunun `MESAFELER`
bloğunda verdiği 80 m'yi korudu ve üç karakterin de yarasını takip etti,
`medium` mesafeyi 50 m'ye kaydırdı. Yani üst seviyenin karşılığı ancak
sürekliliğin pahalıya patladığı turlarda var.

Üst seviyeye çıkma nedenleri — hepsi turun çözümünde sunucuda **zaten** olan
sinyaller, modele sorulmaz:

| sinyal | nereden gelir |
| --- | --- |
| açılış / karakter devralma | `setup_service.start`, `turn_service.takeover` |
| karşılaşma oynanıyor | `threat_prep["encounter"].var` |
| senarist beat'i sahneye giriyor | kuyruktan çıkan `DIREKTIF` |
| gerilim yüksek | `world.tension` |
| ölüme yakın karakter | ağır/enfekte yara ya da 85+ gösterge |
| süre doldu, ani sahne yazılacak | `round_.waiting_for(...)` |
| anlatıcı elle sahne/sürpriz yazdırdı | `gm_service` yayın kipleri |

Seviye yükseldiğinde anlatıcı ekranına gerekçesiyle bir satır düşer
(`🧠 Anlatıcı bu turda high seviyede düşünüyor (karşılaşma oynanıyor).`).
Seviyeler `.env`'den gelir: `CLAUDE_EFFORT` taban, `CLAUDE_EFFORT_KEY` üst.
İkisi eşitlenirse effort yine sabitlenir; tanınmayan bir değer sessizce tabana
düşer, çünkü yazım hatası yüzünden CLI'ın çağrıyı reddetmesi turu kaybettirir.

Zaman aşımı bu yüzden 300 saniyedir: ölçülen `high` turu 186.9 saniye sürdü ve
eski 180 saniyelik tavan kritik turları düşürüyordu.

## 2. Seçenek havuzu

Anlatıcı her turun sonunda state-update bloğuna `options` yazar:

```json
{"options": {"Okan": [{"text": "Galeri ağzına in", "category": "riskli",
                       "cost": "2 fişek + gürültü"}]}}
```

Kurallar (motor eki, `scenario.SYSTEM_APPENDIX`):

| Kural | Nerede zorlanır |
|---|---|
| Karakter başına 3-8 seçenek (sabit değil) | `options_service.refresh` eksikleri tamamlar |
| Her listede en az bir düşük riskli çıkış | `options_service._ensure_safe_exit` |
| Sekiz kategoriden biri | `models/options.canon_category` (eş anlamlıları eşler) |
| Her listede en az 3 farklı kategori | prompt kuralı + jenerik tamamlama |
| Sahne dışındaki karaktere seçenek yok | `refresh(world, present_players)` |
| Kelimesi kelimesine tekrar yok | `options_service.recent_note` (havuz geçmişi) |

Kategoriler: `güvenli`, `riskli`, `gizemli`, `körü körüne`, `kurnaz`, `insani`,
`acımasız`, `hazırlık`. Kategori bir vaattir — seçimin ruhunu belirler ve zar
yorumuna girer (`[körü körüne]` bir hamlede karakter düşünmeden atılmıştır).

Oyuncunun serbest hamle yazma hakkı **yoktur**; kategori `serbest` yalnız eski
kayıtlarda kalmış olabilir. Sunulan ve seçilen HER seçenek
`data/options_pool.jsonl` dosyasına düşer — havuz hem tekrar denetimi hem de
öğrenme için kullanılır.

## 3. Öğrenme defteri (Claude yeteneği)

`data/learning.json` + `data/learning_events.jsonl`. Her tur şunlar kaydedilir:
seçilen kategori, zar ve bandı, havuzdan mı seçildiğI, süre aşımı, karar
süresi, o turda çıkan ölüm/yara/çözülen zorluk sayıları.

Bu ham sayaçlardan **dersler** üretilir (`learning_service._derive`) — hepsi
bir eşiğe bağlıdır, az veriden büyük sonuç çıkarılmaz:

- kategori payı %40'ı geçerse → "bu masa X oynuyor, aynı kalıbı tekrarlama"
- bir kategoride felaket oranı ≥%25 → "riski ÖNCEDEN sezdir"
- bekleme/düşük riskli seçim oranı ≥%50 → "seçeneklerin ya cazip değil ya fazla pahalı"
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
