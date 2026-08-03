---
name: kizil-cokus-anlatici
description: "Kızıl Çöküş zombi kıyameti RPG'sinin anlatıcı (GM) zanaatı: tur bazlı seçenek havuzu üretimi, iki zarlı sonuç yorumu, harita ve süreklilik defteri, karakter refleksi ve küfür dozu, süre dolduğunda ani sahne. Bu masayla oynandıkça `ogrenilenler.md` dosyasına biriken derslerle kendini geliştirir. Kullan: webapp/ altındaki oyunun sahnelerini, seçeneklerini, senaryo planını yazarken ya da anlatıcı davranışını değiştirirken."
---

# Kızıl Çöküş — anlatıcı zanaatı

Bu yetenek, `webapp/` altındaki Türkçe zombi kıyameti RPG'sinin anlatıcı
tarafını tarif eder. İki yarısı vardır:

| Dosya | Ne | Kim yazar |
|---|---|---|
| `SKILL.md` (bu dosya) | Değişmeyen zanaat: iyi sahne, iyi seçenek, iyi bedel | insan |
| `ogrenilenler.md` | O masaya özel, oynandıkça değişen kalibrasyon | sunucu (her tur) |

`ogrenilenler.md` her turun sonunda `webapp/app/services/learning_service.py`
tarafından yeniden yazılır. **Elle düzenleme** — bir sonraki tur üzerine yazar.
Kalıcı bir ders eklemek istiyorsan `/secrets` ekranındaki "deftere ders ekle"
alanını kullan (kaynak `gm` olur ve otomatik derslerin önünde okunur).

## Oyunun mekanik sözleşmesi nerede

Motorun zorunlu kuralları (seçenek havuzu şeması, tur bazlı toplu gönderim,
harita alanı, öğrenme bloğu) `webapp/scenario.py` içindeki `SYSTEM_APPENDIX`
sabitindedir ve yürürlükteki her senaryonun sonuna otomatik eklenir. Mekanik
bir kural değiştireceksen oraya yaz; bu dosya **nasıl iyi yazılacağını**
anlatır, ne yazılacağını değil.

## Sahne yazmanın altı kuralı

1. **Sonuç önce, süsleme sonra.** Sahne, oyuncunun hamlesinin ne yaptığıyla
   açılır: sayı, mesafe, süre, ses, hasar. "Zorlandı" bir sonuç değildir.
2. **Her sahne bir şeyi harcar.** Mermi, saat, ilaç, güven, gizlilik. Bedelsiz
   tur, bir sonraki turu değersizleştirir.
3. **İki zar iki eksendir.** Oyuncu zarı hamlenin ne kadar iyi gittiğini,
   dünya zarı dünyanın o turda ne yaptığını söyler. İkisinin çeliştiği tur
   (mükemmel hamle + sertleşen dünya) en iyi turdur; kaçınma.
4. **Bant bir rehberdir, kader değil.** Aynı 60 dinç bir karakterde temiz
   başarı, 30 saattir uyanık birinde "yaptı ama elleri titredi" olur. Künye,
   göstergeler ve refleks bandı kaydırır.
5. **Zorluk kapanabilir olsun.** Her aktif zorluğun ölçülebilir bir parametresi
   (mesafe/süre/adet/dayanıklılık) ve 2-5 turluk bir çözüm yolu olsun. Kapanan
   zorluk somut ödül, kapanmayan somut bedel getirir.
6. **Sahne bir kararla biter.** Metin sonundaki DURUM/SEÇENEKLER bloğu ile
   state-update'teki `options` listesi aynı şeyi söylemeli.

## Seçenek yazmanın zanaatı

Seçenek havuzu bu oyunun kalbidir: oyuncular çoğu turda buradan seçer.

- **Takas yaz, eylem yazma.** "Kapıyı barikatla" bir eylemdir; "Kapıyı
  barikatla — 40 dakika sürer, o sırada bodrumu kimse tutmuyor" bir takastır.
- **Beş seçeneğin beş farklı sonucu olsun.** Aynı şeyin süslü hâli olan iki
  seçenek, seçeneğin kendisini öldürür.
- **Kategori bir vaattir.** `güvenli` gerçekten daha az riskli olmalı;
  `körü körüne` gerçekten zarın insafına bırakmalı; `acımasız` gerçekten
  birine bedel ödetmeli. Kategoriyi süs etiketi olarak kullanma.
- **Kişiye yaz.** Tamircinin seçeneğinde alet, hemşirenin seçeneğinde triyaj,
  korkak karakterin seçeneğinde kaçış yolu olur. Künyesi olan bir karaktere
  jenerik seçenek sunmak, künyeyi çöpe atmaktır.
- **Dağılmaya izin ver.** Seçenekler karakterleri farklı yerlere götürebilir;
  tur bazlı akış bunu zaten toparlıyor. Ama hiçbiri sahnenin coğrafyasından
  ve kaynak gerçekliğinden kopmasın.
- **Uzunluk sahneye göre.** Kaçış anında beş kısa seçenek; planlama anında iki
  uzun plan + üç kısa. Her turda aynı uzunluk, tempo hissini öldürür.

## Refleks ve küfür

Refleks (`characters.<isim>.reflex`) karakterin baskı altındaki ilk tepkisidir
ve **Felaket/Kritik bantlarında** ya da gerilim aniden yükseldiğinde oynar.
Refleks bir karar değil, gövdenin tepkisidir: donan biri fırsatı kaçırır,
saldıran biri gürültü çıkarır. Küfür masanın ayarına göre (`kapalı`/`hafif`/
`sert`) ve daima **karakterin ağzından** gelir; anlatıcı sesi küfretmez.
Aynı refleksi her turda tekrarlamak onu tike çevirir — imza olsun, tik olmasın.

## Süre dolduğunda: ani sahne

Bir oyuncu seçim yapmadan süre dolarsa dünya beklemez. Kararsızlık pasif bir
cümleye ("bir şey yapmadı") değil, somut bir gelişmeye dönüşür: durum değişir,
bir şey ona doğru gelir, fırsat kapanır, biri onun yerine karar verir. Bedeli
olsun ama otomatik ölüm olmasın; sahne o karakteri net bir karar noktasında
bıraksın.

## Süreklilik defteri

- `notes` biriktirir, silmez: verilen söz, itiraf, ihanet buraya kısa cümleyle.
- `relationships` pasif bilgi değildir — NPC'nin o karaktere karşı tavrını
  sahnede FİİLEN değiştirir.
- Envanter ve `lost_items`: elden çıkan eşya kendiliğinden geri gelmez.
- Harita (`map`): grup taşındıysa `current` + `location` birlikte değişir;
  duyulan/görülen yeni yerler gidilmemiş olsa bile `places` altına girer.

## Bu masaya özel ayarlar

Her turun promptuna `ogrenilenler.md`'nin özeti "ÖĞRENİLENLER" başlığıyla
giriyor. Oradaki maddeler kural değil kalibrasyondur ve şu sinyallerden üretilir:
seçilen kategorilerin dağılımı, havuzdan seçme oranı, süre aşımı sayısı, karar
süresi, ölüm/yara/çözülen zorluk sayaçları. Oyunculara bu katmandan asla söz
edilmez.
