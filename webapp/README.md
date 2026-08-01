# Kızıl Çöküş — Web Arayüzü

Zombi kıyamet oyununun web arayüzü. **Ayrı bir API anahtarına gerek yok** —
uygulama, bu bilgisayarda zaten `claude auth login` ile giriş yapmış olduğunuz
**Claude Pro/Max hesabınızı** kullanır. Backend, her oyuncu mesajında `claude`
CLI'ını arka planda (headless / `-p` modda, hiçbir dosya/kod aracı olmadan,
sadece metin üretimi için) çalıştırır.

## Nasıl çalışır

1. **Karakter kurulumu** — ilk açılışta kaç karakter oynayacağı ve isimleri
   sorulur (varsayılan öneri: Okan, Emir, Celil, Doğu — istediğiniz gibi
   değiştirin/ekleyin/çıkarın).
2. **Oyunu Başlat** butonuna basınca sunucu rastgele bir açılış olayı seçer
   (`scenario.py` içindeki `OPENING_HOOKS` listesinden) ve anlatıcıya sahneyi
   açtırır; ardından her karakter için kısa bir karakter oluşturma sorusu
   (2-3 seçenek) sunulur. Bu aşamada zar atılmaz.
3. Herkes karakterini kurduktan sonra normal oyun başlar: her oyuncu mesajı
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
- Web arayüzü 2.5 saniyede bir `/api/state` uç noktasını yoklayarak (polling)
  güncel günlüğü ve dünya durumunu gösterir — böylece tüm oyuncular aynı
  sayfada birbirinin hamlelerini görebilir.

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

## NPC'ler ve ilişkiler

Anlatıcı, hikaye boyunca önemli hale gelen isimli NPC'leri de "Karakterler"
panelinde gösterir (küçük bir "NPC" etiketiyle ayırt edilir). Hem oyuncu
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

- `server.py` — Flask backend, `claude` CLI çağrıları, zar mantığı, durum yönetimi, dışa/içe aktarma uç noktaları
- `scenario.py` — senaryo metni (system prompt), başlangıç dünya durumu, varsayılan karakter önerileri ve rastgele açılış olayları listesi — **oyunun içeriğini değiştirmek için bu dosyayı düzenleyin** (ya da arayüzden bir senaryo JSON'u içe aktarın)
- `static/index.html` — tek sayfalık arayüz (karakter kurulumu → oyunu başlat → canlı oyun/geçmiş sekmeleri + durum paneli + müzik/ayarlar)
- `static/audio/` — buraya kendi ambiyans/müzik dosyanızı (`ambient.mp3`) koyabilirsiniz
- `data/state.json` — güncel dünya durumu + Claude Code oturum ID'si — silerseniz oyun sıfırlanır
- `data/game_log.jsonl` — tüm oyun geçmişi, satır satır JSON (append-only) — asla üzerine yazılmaz
- `data/scenario_override.json` — içe aktarılmış özel senaryo varsa burada tutulur (yoksa `scenario.py`'deki varsayılan kullanılır)
- `data/gm_log.jsonl` — anlatıcının `/secrets` ekranından gönderdiği gizli notlar + yanıtları — oyunculara asla gösterilmez
- `static/secrets.html` — anlatıcı-only ekranın arayüzü
- `/api/reset` — arayüzdeki "Sıfırla" butonu bu uç noktayı çağırır, `data/state.json`, `data/game_log.jsonl` ve `data/gm_log.jsonl`'ı temizleyip karakter kurulum ekranına döner (Claude Code'un kendi oturum geçmişini silmez, sadece yeni bir oturum başlatılır)
