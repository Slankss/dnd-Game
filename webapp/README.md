# Kızıl Çöküş — Web Arayüzü

Zombi kıyamet oyununun web arayüzü. **Ayrı bir API anahtarına gerek yok** —
uygulama, bu bilgisayarda zaten `claude auth login` ile giriş yapmış olduğunuz
**Claude Pro/Max hesabınızı** kullanır. Backend, her oyuncu mesajında `claude`
CLI'ını arka planda (headless / `-p` modda, hiçbir dosya/kod aracı olmadan,
sadece metin üretimi için) çalıştırır.

## Nasıl çalışır

1. **Karakter oluşturma** — ilk açılışta her karakter için bir künye
   doldurulur: **isim, meslek, yaş, güçlü yan, zayıf yan, sır ve başlangıç
   eşyası**. Meslek/güçlü/zayıf yan anlatıcı için bağlayıcıdır: zar aynı
   gelse bile güçlü yana giren işte sonuç daha iyi, zayıf yana denk gelen
   işte bedel daha ağır olur. İsim dışındaki alanlar zorunlu değil.
2. **Oyunu Başlat** butonuna basınca sunucu rastgele bir açılış olayı seçer
   (`scenario.py` içindeki `OPENING_HOOKS` listesinden) ve anlatıcı sahneyi
   açar. Künyeler dolduysa oyun içi karakter oluşturma turu atlanır ve
   hikaye doğrudan başlar; künye boş bırakıldıysa anlatıcı eskisi gibi her
   karakter için 2-3 seçenekli soru sorar. Bu turda zar atılmaz.
3. Karakterler hazır olduğunda normal oyun başlar: her oyuncu mesajı
   öncesi sunucu 1-100 arası **gerçek bir zar** atar (kriptografik RNG) ve
   `claude -p ...` komutunu bu zar sonucu + güncel dünya durumuyla birlikte
   çağırır.
- Oturum sürekliliği Claude Code'un kendi `--resume` mekanizmasıyla sağlanır —
  sunucu konuşma geçmişini kendi başına biriktirip API'ye yeniden göndermez;
  Claude Code bunu zaten kendi tarafında tutar.
- Anlatıcının yanıtındaki gizli `state-update` bloğu (fraksiyon durumu, gün
  sayısı, karakterlerin geçmişi/durumu vb.) ayrıştırılıp `data/state.json`
  içine kaydedilir; oyunculara asla gösterilmez.
- **Tüm oyun geçmişi** `data/game_log.jsonl` dosyasına satır satır (append-only)
  kaydedilir — bu dosya asla üzerine yazılmaz, sadece eklenir. Web arayüzünde
  "Oyun Geçmişi" sekmesi bu geçmişin tamamını gösterir; kenar çubuğundaki
  "Son Olaylar" paneli ise son birkaç olayın kısa özetini verir.
- Arayüz durumu **sürüm bazlı yoklamayla** tazeler: her istek `?since=<sürüm>`
  gönderir, durum değişmediyse sunucu ağır gövdeyi hiç kurmaz. Sunucu
  yanıt vermezse yoklama durmaz, aralığı kademeli açılır (tavan 30 sn) ve
  arayüzde bağlantı durumu görünür. Sekme arkadayken yoklama askıya alınır.

## Kurulum ve çalıştırma

```bash
cd webapp
./run.sh
```

`run.sh` sanal ortamı kurar, bağımlılıkları yükler ve `claude auth status`
ile giriş yapılmış olduğunu kontrol eder. Giriş yapılmamışsa önce terminalde:

```bash
claude auth login
```

çalıştırın (tarayıcı açılır, claude.ai hesabınızla giriş yaparsınız).

Sunucu ayağa kalktıktan sonra tarayıcıda **http://localhost:5050** adresini
açın. Celil ve Emir aynı bilgisayardan/ağdan bu adrese girip kendi isimlerini
seçerek oynayabilir.

### Arayüzü değiştirmek

Oynamak için gerekmez — `static/dist` depoda hazır gelir. Arayüz kaynağını
değiştirdiyseniz:

```bash
cd frontend
npm install
npm run build        # çıktı: ../static/dist
npm run dev          # geliştirme sunucusu, /api istekleri :5050'ye proxy'lenir
```

## Önemli: kullanım kotası

Bu, Claude Code'u (bu aracın kendisini) arka planda çalıştırdığı için, oyun
sırasında yapılan her tur **Pro/Max planınızın Claude Code kullanım kotasını**
tüketir — normal Claude Code (kodlama) kullanımınızla aynı havuzu paylaşır.
Yoğun oynarsanız günlük/haftalık kotanızın bir kısmını oyun için harcamış
olursunuz. Bunu ayarlamak için `webapp/.env` dosyasında (yoksa
`.env.example`'dan kopyalayın):

```
CLAUDE_MODEL=sonnet   # varsayılan; 'opus' daha güçlü ama kotayı daha hızlı tüketir, 'haiku' en hafifi
CLAUDE_EFFORT=medium  # low = daha hızlı/hafif, xhigh/max = daha derin ama yavaş
```

Bir tur genelde 20–90 saniye sürer (modelin "düşünme" derinliğine göre
değişir) — bu play-by-post tarzı bir oyun için normal bir tempo.

## Ortak stok yoktur (klan/topluluk/sayım olmadan)

Oyun **boş bir `resources` ile başlar**. Ortada bir klan, topluluk ya da depo
yokken stok da yoktur — grubun sahip olduğu tek şey karakterlerin sırtındaki
kişisel eşyalardır. Anlatıcıya hem senaryo metninde hem her turun promptunda
"ORTAK STOK: YOK, depodan söz etme, `resources`'a kalem yazma" denir.

Stok ancak iki yolla doğar:
1. Grup bir topluluk/klan kurar ya da bir topluluğa katılır (ortak depo
   gerçekten var olur),
2. Oyuncular açıkça sayım ister ("elimizde ne var, sayalım") ve sahnede
   fiilen sayılan şeyler kaydedilir.

Stok doğana kadar kenar çubuğundaki "Grup Kaynakları" paneli hiç
görünmez; ilk kalem girdiğinde kendiliğinden açılır.

## Eşya sürekliliği

Bir karakter bir eşyayı attığında/verdiğinde/kaybettiğinde o eşya
`inventory`'den çıkar ve `lost_items` altına yazılır. Model sonraki bir turda
hafızasından eski tam listeyi yeniden yazsa bile sunucu o eşyayı geri
almaz ([app/models/person.py](app/models/person.py) → `Person.merge_inventory`) — daha önce atılan bir
madalyon saatler sonra kendiliğinden cebe dönemez. Eşya ancak anlatıcı
`inventory_add` ile açıkça geri verirse (karakter o yere dönüp fiilen
alırsa) envantere geri girer. Karşılaştırma büyük/küçük harfe duyarsızdır.

Ayrıca her turda modele "X ARTIK ŞUNLARA SAHİP DEĞİL" listesi verilir; o
listedeki bir eşyayı sahnede kullandırmak hata sayılır.

## Yaralar ve enfeksiyon

Yaralar `characters.<isim>.wounds` altında **iyileşene kadar kalıcı** olarak
tutulur — her yara için `desc`, `severity` (hafif/orta/ağır/kritik),
`infection_risk` (0-100), `treated`, `notes` ve açıldığı gün/saat.

Enfeksiyon da göstergeler gibi sunucunun sorumluluğunda
([app/models/wounds.py](app/models/wounds.py) → `WorldState.advance_infections`): tedavi edilmemiş bir yaranın
riski saat başına ağırlığına göre yükselir (hafif +0.6 … kritik +3.0), tedavi
edilmiş bir yara ise saatte −1.0 ile temizlenir. Anlatıcı unutsa bile yara
ilerler. 60'ı geçince belirtiler başlar, 85'i geçince ölümcül bir `challenges`
kaydına dönüşmesi istenir.

Ayrıca `normalize_wound_status`, açık yarası olan bir karakterin `status`
alanı "İyi" kalmışsa bunu otomatik düzeltir ("Yaralı" / "Ağır yaralı" /
"Enfekte olabilir") — anlatıcı bu adımı sık atlıyor ve oyuncu kenar çubuğunda
sapasağlam görünüyordu.

Yaralar karakter kartında tek satırlık özet, popup'ta enfeksiyon çubuğuyla
birlikte tam liste, anlatıcı ekranında ise hepsi ayrıntısıyla görünür.

> Not: Türkçe metinlerde eşleştirme `_norm_tr()` ile yapılır. Düz
> `casefold()` burada sessizce yanlış çalışıyor — `"İyi".casefold()`
> `"i̇yi"` üretir ve `"iyi"` ile eşleşmez.

## Hayatta kalma göstergeleri (yorgunluk / açlık / susuzluk / stres)

Her karakterin `vitals` bloğu var — hepsinde **0 = gayet iyi, 100 =
dayanılmaz**: `fatigue`, `hunger`, `thirst`, `stress`, `awake_hours`,
`condition`.

Bu sayılar zar gibi **sunucunun sorumluluğunda**. Anlatıcı saati ilerlettikçe
sunucu geçen oyun-içi süreyi hesaplayıp göstergeleri kendiliğinden yükseltir
([app/models/vitals.py](app/models/vitals.py) → `WorldState.apply_vitals_drift`): uyanık geçen her saat
yorgunluğa +4, açlığa +3.5, susuzluğa +5 ekler. Yani fatigue ~25 saatte,
susuzluk ~20 saatte tavan yapar. Model unutsa bile göstergeler ilerler.

Düşmesi için bir **sebep** gerekir. Bir karakter uyuduğunda/yediğinde/
içtiğinde anlatıcı `vitals` alanını state-update ile yazar ve o değer
sunucunun otomatik artışını ezer — ama yiyecek/su `resources` içinden
gerçekten düşülmek zorundadır.

En önemlisi: **bu sayılar zar yorumunu kaydırır.** 40+ belirgin etki, 65+
bandı bir kademe aşağı, 85+ neredeyse kesin bedelli. Künyedeki zayıf yan bu
eşikleri düşürür, güçlü yan yükseltir. Gece nöbetinden çıkmış uykusuz bir
karakter aynı zarla dinç halinden çok daha kötü bir sonuç alır — elleri
titrer, ses çıkarır, bir şeyi düşürür.

Göstergeler kenar çubuğundaki karakter kartında (sadece 40'ı geçenler
rozet olarak) ve karaktere tıklayınca açılan popup'ta çubuk olarak görünür;
anlatıcı ekranında hepsi her karakter için listelenir. Gruba katılıp
birlikte hareket eden NPC'ler için de takip edilir.

## Karakter sırları

Künyedeki **sır** alanı sadece anlatıcıya aittir. Sunucu bu alanı
`public_world_state()` içinde ayıklar — oyuncu arayüzüne giden hiçbir
yanıtta yer almaz, dolayısıyla aynı ekranı paylaşan diğer oyuncular göremez.
`/secrets` ekranında ise her karakterin altında 🔒 SIR satırı olarak görünür.

Anlatıcıya sırrı **asla açıklamaması**, bunun yerine hikayenin gizli motoru
olarak kullanması söylenir: sırra dokunan sahneler, açığa çıkma riski,
o karakteri zorlayan seçimler. Sır ancak oyuncusu kendi mesajında açıklarsa
ya da hikayede inandırıcı biçimde ifşa olursa ortaya çıkar.

## NPC'ler ve ilişkiler

"Karakterler" paneli **Oyuncular** ve **NPC'ler** olmak üzere iki sekmeye
ayrılmıştır; her sekmenin başlığında o gruptaki kişi sayısı görünür. Anlatıcı,
hikaye boyunca önemli hale gelen isimli NPC'leri NPC'ler sekmesine ekler
(henüz kimseyle tanışılmadıysa sekme bunu söyler). Hem oyuncu
karakterlerinin hem NPC'lerin **ilişkileri** (kiminle iyi/kötü, güvenilir/
şüpheli) takip edilir ve anlatıcıya bunları sahnede **gerçekten
kullanması** — iyi ilişkisi olan biri yardımsever, kötü ilişkisi olan biri
şüpheci/düşmanca davranması — talimatı verilmiştir. Herhangi bir karaktere/
NPC'ye tıklayınca açılan popup'ta geçmiş, özellikler, sağlık, konum,
envanter ve ilişkiler görülebilir.

## Ölüm ve karakter devralma

Bir oyuncu karakteri hikayede kalıcı olarak ölürse anlatıcı onu
`alive: false` olarak işaretler. O andan itibaren:

- Karakter kenar çubuğunda **💀 ÖLÜ** etiketiyle (üstü çizili, soluk) görünür
  ve "Kimsin?" seçicisinden kalkar — o karakter adına artık mesaj gönderilemez.
- Alt kısımda kırmızı bir bant çıkar: **"Karakter Devral"**. Butona basınca
  hikayede o ana kadar tanışılmış, **hayatta olan NPC'lerin** listesi açılır
  (geçmişi, özellikleri, sağlığı, konumuyla birlikte).
- Seçilen NPC oyuncu karakterine dönüşür — geçmişi, envanteri ve ilişkileri
  aynen korunarak `npcs`'ten `characters`'a taşınır — ve anlatıcı kısa bir
  geçiş sahnesi yazar (zar atılmaz). Ölen karakter listede ölü olarak kalır,
  altında "🔁 yerine \<isim\> oynanıyor" yazar.

Devralınabilecek bir NPC henüz yoksa (grup kimseyle tanışmamışsa) popup bunu
söyler; anlatıcı hikayede yeni birini sahneye soktuğunda liste dolar.

## Oyuncu kadrosu kilidi

Oyuncu karakterlerinin listesi kurulum ekranında **bir kez** belirlenir ve
anlatıcı bu listeyi genişletemez:

- Her turda modele kadro ("SABİT LİSTE") + ölmüş karakterler ayrıca
  hatırlatılır, ve senaryo metninde isim uydurma/isim değiştirme açıkça
  yasaklanmıştır.
- Buna rağmen model `characters` altına tanımadık bir isim yazarsa sunucu o
  kaydı sessizce `npcs`'e taşır; `npcs` altına yazılmış gerçek bir oyuncu
  karakteri de `characters`'a geri alınır. Aynı kişinin farklı büyük/küçük
  harfle ("celil" / "Celil") ikinci bir kayıt açması da engellenir.
- Devralma (yukarıya bak) bu kilidin tek istisnasıdır — kadroya yeni isim
  sadece bu yolla, oyuncunun onayıyla girer.

## Oyun yapısı: problem-çözüm, roman değil

Anlatıcı "kitap okur gibi" ilerlemesin diye üç mekanizma var:

**1. Aktif zorluklar (`challenges`)** — oyunun omurgası. Her an sahnede en az
bir somut, ölçülebilir, süreli problem olmalı: *"Kuzey tünelinden ~40 kişilik
sürü, 3 tur içinde kapıda; barikat %20, elde 23 fişek."* Her zorluğun
`clock` (kalan süre), `progress` (ilerleme), `severity`, `consequence`
(çözülmezse ne olur) alanları var ve **her turda güncelleniyor**. Bir zorluk
tek zarla çözülmez — 2-5 tur süren bir süreç. Kapanınca somut ödül ya da
`consequence`'ın gerçekten uygulanması. Oyuncu arayüzünde "Aktif Zorluklar"
paneli, anlatıcı ekranında ayrıca `gm_notes` ile.

**2. Sahne yapısı** — her normal tur 250-450 kelime ve dört şeyi içermek
zorunda: SONUÇ (hamle ne yaptı, zar bandına bağlı, sayı/mesafe/süre ile),
BEDEL/KAZANÇ (fiilen ne değişti), DURUM (zorluğun ölçülebilir hali), KARAR.
Yanıt şu blokla biter:

```
**DURUM:** <aktif tehdit + somut parametre>
**SEÇENEKLER:**
A) <eylem> — bedeli/riski: <somut>
B) ...   C) ...   Ç) Kendi planını yaz.
```

Seçenekler gerçek takaslar sunmalı (hız↔güvenlik, kaynak↔zaman,
gizlilik↔güç), aynı şeyin süslü hali değil.

**3. Bulmacalar (`narrator.puzzles`)** — çözülecek gizemler. `progress`
(0-100), `clues_found`, `next_step`, `solution` alanlarıyla takip edilir.
İlerleme sadece oyuncular somut bir şey yaptığında ve zar izin verdiğinde
artar; en az 3-4 turluk süreç. Anlatıcı ekranında ilerleme çubuğu +
gerçek cevap görünür — oyunculara asla.

## Dünya zarı (sadece /secrets görür)

Her normal turda oyuncunun zarından **ayrı** ikinci bir d100 atılır. Oyuncu
zarı hamlenin ne kadar iyi gittiğini, dünya zarı ise dünyanın o turda ne
yaptığını belirler:

| Bant | Ne olur |
|---|---|
| 1-10 **Lehte Kırılma** | Dünya oyuncular lehine döner — beklenmedik kaynak, gecikme, dağılan tehdit |
| 11-35 **Durgun** | Tehditler ilerlemez, nefes payı |
| 36-65 **Sızıntı** | Aktif zorluk bir adım ilerler, küçük komplikasyon |
| 66-88 **Baskı** | Zorluk belirgin ilerler (süre kısalır, sayı artar) ya da yeni zorluk doğar |
| 89-100 **Kriz** | Yeni büyük tehdit patlar ya da mevcut zorluk en kötü aşamasına sıçrar |

Böylece mükemmel bir hamle sert bir dünyayla, beceriksiz bir hamle sakin bir
dünyayla çakışabilir. Zar `/secrets` ekranında son 10 atışlık geçmişiyle
görünür; oyunculara **hiç** gösterilmez ve anlatıcı metninde ondan söz etmez.

> **Not:** `narrator` bölümü (özet, bulmaca çözümleri, planlanan olaylar)
> eskiden `/api/state` ile her oyuncunun tarayıcısına gidiyordu. Artık
> oyuncuya giden tüm yanıtlar `narrator`, `world_roll`, `world_roll_history`
> ve zorlukların `gm_notes` alanı ayıklanarak dönüyor.

## Zaman, gün dönümü ve hava

Dünya durumunda zaman gerçekten akar: `day`, `time_of_day`
(şafak/sabah/öğle/ikindi/akşam/gece/gece yarısı), `clock` ("HH:MM"),
`season`, `weather`, `temperature`. Anlatıcı her turda bunları
`state-update` ile ilerletir; başlık çubuğunda
`Gün 97 · 02:30 gece · ince yağmur, 7°C · konum` olarak görünür.

- **Süre:** her aksiyon saati kendi gerçekçi süresi kadar ilerletir — kapı
  dinlemek 5 dakika, barikat kurmak 2 saat, keşif yarım gün.
- **Gün dönümü:** saat gece yarısını geçince `day` 1 artar ve o turda kısa
  bir muhasebe yapılır — günlük yiyecek/su tüketimi, hayvanların verdiği ya
  da kaybedilen şeyler, tarımın ilerlemesi, yaralıların iyileşmesi. Gün
  geçtiği halde hiçbir sayının değişmemesi hata sayılır.
- **Hava:** dekor değil, mekanik — yağmur izleri siler ama ateşi zorlaştırır,
  sis pusuyu kolaylaştırır, don mahsulü öldürür, fırtına nöbeti imkânsız
  kılar. Değişimi dünya zarına ve mevsime bağlıdır.
- Aktif zorlukların `clock` alanı bu akan zamanla tutarlı tutulur.

Alanlar sonradan eklendi; devam eden bir oyunda eksiklerse `load_state`
senaryonun başlangıç değerleriyle doldurur. Model bir alanı boş gönderirse
mevcut değer korunur — dünya saati sıfırlanmaz.

## Sahne katılımı — herkes her turda sahnede değildir

Her karakterin bir `presence` kaydı var: `sahnede` (varsayılan), `uyuyor`,
`uzakta`, `baygın`, `esir`. Sahne dışındaki karaktere anlatıcı replik, aksiyon
ya da karar yazmaz; ortak kararlara da katmaz. Ondan bir tur boyunca hiç ses
çıkmaması normaldir — anlatıcının bunu her turda açıklaması gerekmez. Sahnede
olanların da hepsine sırayla söz verilmez; sadece o anki aksiyona gerçekten
karışanlar yazılır.

```json
{"characters": {"Okan": {"presence": {
  "state": "uyuyor", "note": "revirde",
  "until": {"day_gte": 99, "clock_gte": "06:00"}}}}}
```

`until` bir randevudur: koşul dolduğunda sunucu karakteri kendiliğinden sahneye
döndürür ve anlatıcıya "geri döndü" diye bildirir. Koşulu `director.matches`
değerlendirir — beat tetikleyicileriyle aynı motor (`day_gte`, `clock_gte`,
`location_in`, `tension_gte`, `flags_set`/`flags_unset`, `world_roll_lte/gte`).
`day_gte` ile `clock_gte` birlikte verilirse tek bir an olarak okunur, yani
gece yarısı dönümü randevuyu bozmaz.

Bir oyuncu sahne dışındaki karakteriyle mesaj yazarsa o karakter uyanmış/dönmüş
sayılır ve sunucu onu sahneye alır. Uyuyan karakterin yorgunluğu ve stresi
geçen süreye göre kendiliğinden **düşer** (açlık/susuzluk uykuda da artar),
`awake_hours` sıfırlanır.

Oyuncu ekranında kart üstünde rozet (😴/🚶/💫/⛓️), `/secrets` ekranında ayrıca
dönüş koşulunun özeti görünür.

## Fraksiyonların iki katmanı

Her fraksiyon kaydı iki katman tutar:

| Alan | Kim görür |
|---|---|
| `disposition` + `notes` | **Gerçek** tavır ve anlatıcı notu — sadece `/secrets` |
| `known` + `public_notes` | Oyuncuların fiilen öğrendiği — oyun ekranı |

`/api/state` fraksiyonları oyuncuya çevirirken `known`/`public_notes`
alanlarını `disposition`/`notes` yerine koyar; gerçek tavır hiç sızmaz.
Anlatıcı tavır değiştiğinde `disposition`'ı her zaman günceller, `known` ise
sadece oyuncular somut bir şey öğrendiğinde değişir.

## Anlatıcı müdahalesi — üç mod

`/secrets` ekranındaki "Senaryoya Müdahale" panelinde üç mod var. Modu
seçmek, müdahalenin oyunculara görünüp görünmeyeceğini belirler — böylece
iki ayrı sohbet oluşmaz, her şey tek hikayede kalır:

| Mod | Ne olur |
|---|---|
| 🔒 **Gizli yönlendirme** | Sadece anlatıcı ekranında kalır. Anlatıcı o turda oyunculara hiçbir şey yazmaz, talimatı sonraki turlarda uygular. |
| 🎭 **Sahne olarak yayınla** | Yazdığınız olay anında oyuncuların akışına sahne olarak düşer. Anlatıcı sizden ya da müdahaleden hiç söz etmez, zar atılmaz. |
| 🎲 **Sürpriz olay üret** | Olayı anlatıcı kendisi icat eder — kendi `upcoming_events` planları, çözülmemiş bulmacalar, fraksiyon tavırları, ilişkiler ve azalan kaynaklardan besleneni seçer — ve oyunculara yayınlar. Metin kutusu boş bırakılabilir; yazarsanız yön verirsiniz. |

Her turda modele "oyuncuların ekranında görünen son akış" ayrıca düz metin
olarak veriliyor ve iki kanalın farkı açıkça anlatılıyor — böylece anlatıcı
hikayeyi, oyuncuların hiç görmediği bir GM onayından devam ettirmiyor.

## Uydurma eşya koruması

Anlatıcıya her turda "ENVANTER GERÇEĞİ" bloğu gidiyor: hangi karakterin
üzerinde fiilen ne olduğu düz metin olarak listeleniyor. Kural net —
bir karakter yalnızca kendi envanterindeki eşyayı, grup stoğundan sahnede
fiilen aldığı bir şeyi ya da ortamda gerçekten bulunan bir nesneyi
kullanabilir. Oyuncu "bıçağımı çekiyorum" yazsa bile bıçağı yoksa bu
gerçekleşmez; anlatıcı kuru bir ret yerine sahnede gerçekçi biçimde düzeltir.
Aynı kural mühimmat/ilaç gibi grup kaynakları için de geçerli.

## Ham JSON sızıntısı koruması

Modelin `state-update` bloğu ne oyuncu ekranına ne anlatıcı ekranına
düşmemeli. Temizleme üç kademeli: (1) etiketi ne olursa olsun içinde JSON
nesnesi olan tüm ``` blokları, (2) fence'i unutulmuş ham JSON nesneleri
(süslü parantez eşleştiren tarayıcı; sadece gerçekten JSON olan ve bilinen
durum alanı içeren bloklar silinir, normal metne dokunulmaz), (3) boşta
kalan fence kalıntıları. Bozuk JSON parse edilemese bile metinden silinir.

## Karakter oluşturmayı bitirme

Biri hiç cevap vermezse oyun sonsuza kadar karakter oluşturma aşamasında
takılı kalıyordu (zar atılmıyor, ortak karar açılmıyordu). Artık alt kısımda
**"✔ Oluşturmayı bitir, oyuna geç"** bandı var — basınca `flags.chargen_done`
işaretlenir ve normal oyun mekaniği açılır. Ortak Karar butonu ise oyun
başladığı andan itibaren kullanılabilir.

## Senaryo / oyun dışa-içe aktarma

Üst çubuktaki **⚙** menüsünden:
- **Senaryoyu Dışa/İçe Aktar** — `scenario.py`'nin içeriğini (dünya metni,
  başlangıç durumu, açılış olayları) bir JSON dosyası olarak indirir/yükler.
  Yeni bir senaryo içe aktarmak mevcut oyunu sıfırlar. "Varsayılana Dön" ile
  içe aktarılan senaryo silinip `scenario.py`'deki orijinale dönülür.
- **Oyunu Dışa/İçe Aktar** — güncel dünya durumu + tüm oyun geçmişini bir
  JSON dosyası olarak yedekler/geri yükler. **Not:** içe aktarma her zaman
  yeni bir Claude oturumu başlatır (ham konuşma hafızası değil, ama tüm
  dünya durumu/envanter/ilişkiler/geçmiş korunur) — böylece farklı
  bilgisayarlar arasında da güvenle taşınabilir.

## Ortak karar ve çoklu karakter turları

Oyuncu seçicide isim listesinin altında her zaman bir **🤝 Ortak Karar
(Grup)** seçeneği vardır (karakter oluşturma bitince görünür) — bunu
seçip yazdığınız mesaj, tek bir karakterin değil TÜM grubun ortak kararı/
aksiyonu olarak ele alınır (yine de bir zar atılır, ama bu grubun
koordinasyonunun ne kadar iyi gittiğini temsil eder).

Ayrıca **tek mesajda birden fazla karakterin AYNI ANDA farklı aksiyonlar
almasını** da yazabilirsiniz — her satıra ayrı ayrı `İsim: aksiyon` yazın:

```
Celil: kapıyı zorluyor
Emir: aynı anda radyodan yardım çağırıyor
```

Sunucu her karakter için AYRI bir zar atar (biri Felaket çekerken diğeri
Kritik çekebilir) ve anlatıcı ikisini de tek bir sahnede birleştirir. Bu,
hangi oyuncu seçili olursa olsun otomatik algılanır — sadece her satırın
"İsim:" ile başlaması ve en az iki farklı, gerçek karakter ismi içermesi
yeterli.

## Anlatıcı Ekranı (/secrets) — sadece oyunu yöneten kişi için

Ana oyun arayüzüne hiçbir bağlantı vermeyen, ayrı bir sayfa:
**http://localhost:5050/secrets**

Bu ekran (basit bir PIN ile korunur — varsayılan `1453`, `.env`'de
`GM_PIN` ile değiştirin) şunları gösterir, oyunculara ASLA görünmez:
- **Senaryo Özeti** — hikayenin şu anki durumunun anlatıcı tarafından
  tutulan güncel özeti.
- **Bulmacalar** — hikayede bir bulmaca/gizem varsa çözülüp çözülmediği.
- **Karakter Durumu ve Güven** — her karakterin tam geçmişi, envanteri ve
  başkalarıyla ilişkisi (güven/gerginlik).
- **NPC İlişkileri** ve **Fraksiyon Tavırları**.
- **Yaklaşan Olaylar** — anlatıcının kendi taslak planı (taahhüt değil).
- **Yönetmen Notu** — buradan, oyunculara görünmeyen, doğrudan anlatıcıya
  giden gizli bir talimat gönderebilirsiniz (ör. "yakında X ihanet etsin",
  "bu bulmacayı 2 tur içinde çözülebilir yap"). Bu, ana oyun sohbetine bir
  oyuncu gibi değil, senaryoyu yöneten kişi olarak müdahale etmenizi
  sağlar — ayrı bir günlükte (`data/gm_log.jsonl`) tutulur, oyuncu
  ekranına hiç yansımaz.

Not: PIN gerçek bir güvenlik önlemi değil, aynı ağdaki oyuncuların
yanlışlıkla spoiler görmesini engelleyen hafif bir kapı.

## Arka plan müziği

Üst çubuktaki 🔇/🔊 düğmesi arka plan atmosferini açar/kapatır. Telif
hakkı nedeniyle gerçek bir dizi/film müziği gömülü değildir — varsayılan
olarak tamamen tarayıcıda üretilen (Web Audio API), telifsiz karanlık bir
ambient ses çalar. Kendi yasal olarak sahip olduğunuz bir ses dosyanız
varsa `static/audio/ambient.mp3` (veya `.ogg`) olarak koyun — düğme
otomatik olarak onu kullanır.

## Dosyalar

- `server.py` — giriş noktası (uygulamayı `app/` paketinden kurup çalıştırır)
- `app/` — katmanlı backend: `models/` (saf alan modelleri), `repositories/` (dosya kalıcılığı), `services/` (tur akışı, kurulum, anlatıcı, senaryo), `api/` (Flask blueprint'leri), `serializers.py` (oyuncuya giden görünüm). Ayrıntı: `docs/mimari.md`
- `frontend/` — Vue 3 + Vite + Tailwind arayüz kaynağı (`npm install && npm run build` → `static/dist`)
- `static/dist/` — derlenmiş arayüz; **depoya dahildir**, oyun Node kurulu olmayan makinede de çalışır
- `docs/` — mimari, tasarım sistemi ve senarist katmanı planı
- `director.py` — koşul motoru (`matches`: gün/saat randevusu, konum, gerilim, bayrak, dünya zarı) + olay örgüsü planı (`data/plot.json`) yardımcıları. Sahne katılımının `until` koşulunu ve ileride beat tetikleyicilerini bu modül çözer
- `docs/senarist-yetenegi.md` — senarist katmanının faz planı (hangi faz uygulandı, sırada ne var)
- `scenario.py` — senaryo metni (system prompt), başlangıç dünya durumu, varsayılan karakter önerileri ve rastgele açılış olayları listesi — **oyunun içeriğini değiştirmek için bu dosyayı düzenleyin** (ya da arayüzden bir senaryo JSON'u içe aktarın)
- `static/audio/` — buraya kendi ambiyans/müzik dosyanızı (`ambient.mp3`) koyabilirsiniz
- `data/state.json` — güncel dünya durumu + Claude Code oturum ID'si — silerseniz oyun sıfırlanır
- `data/game_log.jsonl` — tüm oyun geçmişi, satır satır JSON (append-only) — asla üzerine yazılmaz
- `data/scenario_override.json` — içe aktarılmış özel senaryo varsa burada tutulur (yoksa `scenario.py`'deki varsayılan kullanılır)
- `data/gm_log.jsonl` — anlatıcının `/secrets` ekranından gönderdiği gizli notlar + yanıtları — oyunculara asla gösterilmez
- `/api/reset` — arayüzdeki "Sıfırla" butonu bu uç noktayı çağırır, `data/state.json`, `data/game_log.jsonl` ve `data/gm_log.jsonl`'ı temizleyip karakter kurulum ekranına döner (Claude Code'un kendi oturum geçmişini silmez, sadece yeni bir oturum başlatılır)
