# Zombi tehdidi — karşılaşma motoru

Kod: `app/models/threat.py` (hesap) · `app/services/threat_service.py` (akış) ·
`scenario.py → ZOMBIE_TYPES / PLACE_DENSITY` (içerik) ·
`frontend/src/components/game/ThreatPanel.vue` (gösterge).

## 1. Neden sunucu tarafında

Anlatıcıya "zombiler daha sık olsun" demek işe yaramıyordu: metin ricası her
turda farklı yorumlanıyor, yolculuk da çoğu zaman güvenli bir geçiş sahnesine
dönüşüyordu. Artık karşılaşma **sunucunun attığı gerçek bir zardır**. Kaç ölü,
hangi türler, ne mesafede, hangi yönden ve kimin önce fark ettiği sunucuda
belirlenir; anlatıcıya ZORUNLU bir blok olarak verilir. Anlatıcının sayıyı
azaltma ya da "uzaklaştılar" deyip kapatma imkânı yoktur.

## 2. Girdiler

| Girdi | Nereden gelir | Etkisi |
|---|---|---|
| **yoğunluk** (0-100) | Yerin türünden (`PLACE_DENSITY`) + addan türeyen sabit sapma. Oynandıkça değişir. | Yol 68, metro ~82, hastane ~74, orman ~30 |
| **gürültü** (0-100) | Oyuncu hamlesindeki anahtar sözcükler (silah, araç, bağırma…) + anlatıcının `threat.noise_add` bildirimi | En güçlü ikinci çarpan; saatler içinde söner |
| **dikkat/heat** (0-100) | Yaşanan karşılaşmalar biriktirir | Sessiz kalınca düşer |
| **yolculuk** | Hamledeki yola çıkma ifadeleri **ya da** geçen turda konumun değişmiş olması | Tabanı 8'den 44'e çıkarır |
| gece · sis/fırtına · yağmur · gerilim · sessizlik serisi | Dünya durumu | ±5-12 puan |

Yolculuk bayrağı **yapışkan değildir**: grup bir yere varınca yerleşik sayılır.

## 3. Ölçülen denge (500 turluk simülasyon)

| Durum | Temas | Ortalama sürü | Sürü (25+) |
|---|---:|---:|---:|
| Sığınak (yoğ. 40), sessiz, gündüz | %25 | 7,4 | — |
| Sığınak (yoğ. 40), sessiz, gece | %32 | 6,8 | — |
| Sığınak (yoğ. 65), gürültülü | %67 | 7,8 | — |
| **Yol (yoğ. 68), gündüz** | **%73** | **14,6** | %7 |
| **Yol (yoğ. 68), gece** | **%79** | **14,6** | %6 |
| Yol (yoğ. 30), kırsal | %55 | 9,6 | %5 |

Okunuşu: yolda geçen turların dörtte üçünde ölülerle temas var, ortalama 15
ölü; "kaç!" anlamına gelen sürü ise turların ~%7'sinde — hatırlanır kalması
için nadir. Sığınakta sessiz durmak gerçekten güvenli, gürültü çıkarmak
gerçekten pahalı.

Ayarlar `app/models/threat.py` başındaki sabitlerde (BASE_TRAVEL, W_NOISE,
NIGHT_BONUS…) toplu durur; hepsi yüzde puanıdır ve tek yerden ayarlanır.

## 4. Nüfus akışı — olaylara göre göç (ÇOK ÖNEMLİ)

Yoğunluk sabit bir tablo değil, **akan bir nüfustur**. Bir bölgede ses/patlama
olduğunda oranın yoğunluğu yoktan artmaz: ölüler **komşu bölgelerden çekilir**
ve o bölgeler boşalır.

```
A depoda patlama (güç 45)          önce            sonra
  Köprü          (olay yeri)        56       →     100   (+44)
  Sanayi hattı   (1. komşu)         60       →      43   (−17)
  Kuzey deposu   (1. komşu)         56       →      40   (−16)
  Sığınak        (2. komşu)         32       →      28   ( −4)
```

Kurallar:

- **Kaynaklar komşuluk grafiğinden gelir** (`map.places.<yer>.links`; tek yönlü
  yazılsa bile çift yönlü sayılır). 1. derece komşu tam ağırlıkla, 2. derece
  %45 ağırlıkla verir. **Kalabalık komşu daha çok verir** — ses her yerden aynı
  duyulur ama gelen sayısı oradaki nüfusla orantılıdır.
- **Nüfus korunur**: hedefin aldığı, kaynakların verdiği kadardır. Hedef 100'e
  dayanmışsa çekim kapasiteyle sınırlanır (yoksa komşular boşalır ama gelenler
  tavanda buharlaşırdı). Modellenmemiş kırsaldan küçük bir ek pay (%20) gelir.
- **Hiçbir bölge tamamen boşalmaz**: taban 6.
- **Yayılma (difüzyon)**: her turda geçen saat kadar, komşu bölgeler arasındaki
  fark yavaşça kapanır (saatte %3). Böylece patlamadan sonra boşalan sokaklar
  günler içinde yeniden dolar; temizlenen bir bina sonsuza dek güvenli kalmaz.

Göçü tetikleyen üç şey:

| Kaynak | Nasıl |
|---|---|
| Grubun gürültüsü | 10+ puanlık ses, bulunulan bölgeye çekim yapar |
| Karşılaşma | Yaşanan temas, o bölgeye ölü toplar (×0,35) |
| Anlatıcının bildirdiği olay | `threat.events` → patlama ×1,6 · alarm ×1,4 · yangın ×1,2 · silah ×1,0 · araç ×0,9 |

Olay grubun bulunduğu yerde olmak **zorunda değildir**: uzaktaki bir patlama da
haritayı değiştirir, o yöne giden yolları boşaltır ve bir sonraki turun
karşılaşma ihtimalini gerçekten düşürür/yükseltir.

## 5. Türler ve mutasyonlar

`scenario.ZOMBIE_TYPES`: her tür için ağırlık, hangi yoğunluk bandında
göründüğü, kaçıncı günden sonra ortaya çıktığı (`min_gun`), gece çarpanı ve
anlatıcıya verilen davranış künyesi. Sürü karışımı buradan ağırlıklı çekilir:

- Taze Ölü (her yerde) · Koşucu (gece ×1,3) · Sürüngen (pusu)
- Çığlıkçı (20. günden sonra, gece ×2 — öldürülmezse karşılaşma büyür)
- Şişkin (30+), Kabuklu (45+), Sarmaşık (60+), İkiz Gövde (70+, yalnız yoğun
  bölgeler), Alfa (110+, çok nadir)

Küçük karşılaşmada 1-2, kalabalıkta 3 tür karışır; anlatıcı türlerin davranış
künyesini uygulamak zorundadır.

## 6. Anlatıcı ne yazar

Sadece muhasebe:

```json
"threat": {
  "noise_add": 25,
  "density": {"Kuzey deposu": 30},
  "events": [{"type": "patlama", "place": "Köprü", "strength": 45}]
}
```

`noise_add` bu turda çıkan ses, `density` temizlenen/kalabalıklaşan bölge,
`events` ise ölü çeken olay (göçü sunucu hesaplar). Karşılaşmanın kendisini
state-update'e yazmaz; onu sunucu zaten kaydeder.

## 7. Oyuncular ne görür

Kenar çubuğundaki **Zombi tehdidi** paneli: bölge yoğunluğu, kendi gürültüleri,
bölgenin dikkati, son karşılaşma, son göç hareketi ("patlama → Köprü'ye çekildi;
Sanayi hattı −17 boşaldı") ve "yolda/yerleşik" durumu. Haritada her bilinen
yerin çevresinde bir **yoğunluk halkası** var; büyük görünümde seçilen yerin
yoğunluk çubuğu ve o yere/yerden olan göç yazılı. Böylece "dikkatli seyahat et"
ölçülebilir bir karar olur.

Sızıntı koruması: yoğunluk yalnızca **keşfedilmiş** yerler için gönderilir
(`serializers.public_threat`); göç kayıtlarında da yalnız bilinen yer adları
görünür. Gidilmemiş bir yerin ne kadar kalabalık olduğu oyuncuya hiç ulaşmaz —
o bilgi ancak keşifle öğrenilir.
