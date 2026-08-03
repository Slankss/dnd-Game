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

## 4. Türler ve mutasyonlar

`scenario.ZOMBIE_TYPES`: her tür için ağırlık, hangi yoğunluk bandında
göründüğü, kaçıncı günden sonra ortaya çıktığı (`min_gun`), gece çarpanı ve
anlatıcıya verilen davranış künyesi. Sürü karışımı buradan ağırlıklı çekilir:

- Taze Ölü (her yerde) · Koşucu (gece ×1,3) · Sürüngen (pusu)
- Çığlıkçı (20. günden sonra, gece ×2 — öldürülmezse karşılaşma büyür)
- Şişkin (30+), Kabuklu (45+), Sarmaşık (60+), İkiz Gövde (70+, yalnız yoğun
  bölgeler), Alfa (110+, çok nadir)

Küçük karşılaşmada 1-2, kalabalıkta 3 tür karışır; anlatıcı türlerin davranış
künyesini uygulamak zorundadır.

## 5. Anlatıcı ne yazar

Sadece muhasebe: `"threat": {"noise_add": <10-35>, "density": {"<yer>": <0-100>}}`
— bu turda çıkan ses ve temizlenen/kalabalıklaşan bölge. Karşılaşmanın
kendisini state-update'e yazmaz; onu sunucu zaten kaydeder.

## 6. Oyuncular ne görür

Kenar çubuğundaki **Zombi tehdidi** paneli: bölge yoğunluğu, kendi gürültüleri,
bölgenin dikkati, son karşılaşma ve "yolda/yerleşik" durumu. Böylece "dikkatli
seyahat et" ölçülebilir bir karar olur.

Sızıntı koruması: yoğunluk yalnızca **keşfedilmiş** yerler için gönderilir
(`serializers.public_threat`). Gidilmemiş bir yerin ne kadar kalabalık olduğu
oyuncuya hiç ulaşmaz — o bilgi ancak keşifle öğrenilir.
