"""Harita üreteci — oyun başında BÜTÜN dünya kurulur.

Eskiden harita anlatıcının ağzından büyüyordu: bir yer adı geçince kayıt
açılıyor, komşuluk "oradan buraya yürüdük" diye ekleniyordu. Sonuç, coğrafyası
olmayan bir listeydi — mesafe kavramı yoktu, iki yer arasında "yol" diye bir
şey yoktu, aynı bölge her turda başka bir şekle giriyordu.

Artık dünya oyunun başında bir kez üretilir ve sabittir:

  1. **Şehirler** — harita düzlemine dağıtılmış 2-5 kasaba/mahalle. Her birinin
     kendi merkezi ve yarıçapı vardır.
  2. **Mekanlar** — her şehre, kentsel dokusuna uygun kategorilerden (karakol,
     market, hastane, konut…) mekanlar serpilir; her mekanın ADI, KATEGORİSİ,
     BAĞLI OLDUĞU ŞEHİR ve KOORDİNATI olur. Şehirler arasına da kır mekanları
     (çiftlik, benzinlik, koruluk) dağılır.
  3. **Yollar** — şehir içinde yakın mekanlar birbirine bağlanır (cadde/ara
     sokak), şehirler anayolla bağlanır. İki yer arasında BİRDEN FAZLA yol
     olabilir (hızlı anayol + uzun ama sessiz patika), tek yol olabilir (tek
     köprü) ya da hiç olmayabilir.
  4. **Mesafeler** — üretimden sonra her yolun gerçek uzunluğu hesaplanır
     (kuş uçuşu × yol türünün sapma katsayısı). Rota mesafeleri bu yollardan
     Dijkstra ile çözülür (`WorldMap.route`).

Oyuncu bu haritanın tamamını GÖRMEZ: üretilen her yer `bilinmiyor` düzeyinde
başlar ve oyuncuya giden gövdeye hiç girmez (bkz. `public_place`). Grup
gezdikçe yerler `duyuldu → görüldü → keşfedildi` diye açılır. Yani dünya
baştan tutarlı ve ölçülüdür ama keşif duygusu durur.

Bu modül SAF: dosya okumaz, rastgeleliği çağırandan alır (test edilebilsin).
İçerik `data/places.json`'dan gelir.
"""

import math

#: Harita büyüklüğü ayarları — `settings.map_size`.
MAP_SIZES = {
    "küçük": {"sehir": 2, "mekan": (12, 16), "yayilim": 16.0, "sehir_yaricap": 1.6},
    "orta": {"sehir": 3, "mekan": (20, 26), "yayilim": 28.0, "sehir_yaricap": 2.0},
    "büyük": {"sehir": 5, "mekan": (32, 42), "yayilim": 48.0, "sehir_yaricap": 2.4},
}
DEFAULT_SIZE = "orta"

#: Şehir içi mekanların birbirine bağlanma sayısı (en yakın N komşu).
CITY_DEGREE = 3
#: Bir şehir içindeki bağlantının ikinci (alternatif) yol alma olasılığı.
ALT_ROAD_CHANCE = 0.22
#: Şehirler arası bağlantının ikinci güzergâh alma olasılığı.
ALT_HIGHWAY_CHANCE = 0.45
#: Bir yolun bozuk (tıkalı/barikatlı/çökük) çıkma olasılığı.
BLOCKED_CHANCE = 0.18

#: Şehir içi yol türleri (mesafeye göre seçilir).
CITY_ROADS = ("ara sokak", "cadde")
#: Kır ve şehirlerarası yol türleri.
RURAL_ROADS = ("kır yolu", "anayol")
#: Alternatif güzergâhta kullanılan, yavaş ama sessiz türler.
ALT_ROADS = ("patika", "ara sokak", "demiryolu")


def size_of(name) -> dict:
    """Ayar adından harita ölçüsü (tanınmayan değer 'orta'ya düşer)."""
    return MAP_SIZES.get(str(name or "").strip().lower(), MAP_SIZES[DEFAULT_SIZE])


def _mesafe(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class MapGenerator:
    """`data/places.json` içeriğiyle harita kuran üreteç."""

    def __init__(self, content: dict, rng):
        content = content if isinstance(content, dict) else {}
        self.sehirler = content.get("sehirler") or []
        self.ilceler = content.get("ilceler") or ["Merkez"]
        self.ozel_adlar = content.get("ozel_adlar") or ["Umut"]
        self.kategoriler = content.get("kategoriler") or {}
        self.yol_turleri = content.get("yol_turleri") or {}
        self.yol_durumlari = content.get("yol_durumlari") or {}
        self.rng = rng

    # ------------------------------------------------------------ yardımcı
    def _yol_bilgisi(self, kind: str) -> dict:
        return self.yol_turleri.get(kind) or {"sapma": 1.3, "risk": 2, "not": ""}

    def _ad_uret(self, kategori: str, sehir: str, kullanilan: set) -> str:
        """Kategoriye uygun, katalogda tekrar etmeyen bir mekan adı."""
        bilgi = self.kategoriler.get(kategori) or {}
        sablonlar = bilgi.get("sablon") or ["{ilce} {kategori}"]
        for _ in range(40):
            sablon = self.rng.choice(sablonlar)
            ad = sablon.format(
                ilce=self.rng.choice(self.ilceler),
                sehir=sehir,
                ozel=self.rng.choice(self.ozel_adlar),
                kategori=bilgi.get("ad") or kategori,
            )
            if ad not in kullanilan:
                return ad
        # Havuz tükendiyse şehir adıyla ayrıştır — çakışma olmaz.
        i = 2
        temel = f"{sehir} {bilgi.get('ad') or kategori}"
        ad = temel
        while ad in kullanilan:
            ad = f"{temel} {i}"
            i += 1
        return ad

    def _kategori_sec(self, kirsal: bool) -> str:
        """Kentsel/kırsal dokuya göre ağırlıklı kategori çekilişi."""
        alan = "kir" if kirsal else "kent"
        havuz = [(ad, float((bilgi or {}).get(alan) or 0))
                 for ad, bilgi in self.kategoriler.items()]
        havuz = [(ad, w) for ad, w in havuz if w > 0]
        toplam = sum(w for _, w in havuz)
        if not toplam:
            return next(iter(self.kategoriler), "konut")
        esik = self.rng.random() * toplam
        birikim = 0.0
        for ad, w in havuz:
            birikim += w
            if birikim >= esik:
                return ad
        return havuz[-1][0]

    # -------------------------------------------------------------- üretim
    def generate(self, size: str = DEFAULT_SIZE) -> dict:
        """Bütün haritayı üretir.

        Dönen: {"size", "cities", "places", "roads"} — düz sözlükler; çağıran
        bunları `WorldMap`'e yazar."""
        olcu = size_of(size)
        sehirler = self._sehirleri_dag(olcu)
        mekanlar = self._mekanlari_dag(sehirler, olcu)
        yollar = self._yollari_kur(sehirler, mekanlar, olcu)
        return {
            "size": str(size or DEFAULT_SIZE),
            "cities": sehirler,
            "places": mekanlar,
            "roads": yollar,
        }

    def _sehirleri_dag(self, olcu: dict) -> dict:
        """Şehir merkezlerini düzleme dağıtır (birbirine çok yakın olmasın)."""
        sayi = min(olcu["sehir"], len(self.sehirler)) or 1
        secilen = self.rng.sample(self.sehirler, sayi)
        yayilim = olcu["yayilim"]
        en_az = yayilim / (sayi + 0.5)
        merkezler = []
        for _ in range(sayi):
            for _deneme in range(60):
                nokta = (self.rng.uniform(-yayilim / 2, yayilim / 2),
                         self.rng.uniform(-yayilim / 2, yayilim / 2))
                if all(_mesafe(nokta, m) >= en_az for m in merkezler):
                    merkezler.append(nokta)
                    break
            else:
                merkezler.append((self.rng.uniform(-yayilim / 2, yayilim / 2),
                                  self.rng.uniform(-yayilim / 2, yayilim / 2)))
        out = {}
        for bilgi, (x, y) in zip(secilen, merkezler):
            out[bilgi["ad"]] = {
                "tur": bilgi.get("tur") or "kasaba",
                "not": bilgi.get("not") or "",
                "x": round(x, 2),
                "y": round(y, 2),
            }
        return out

    def _mekanlari_dag(self, sehirler: dict, olcu: dict) -> dict:
        """Mekanları şehirlere ve şehir aralarına serper."""
        alt, ust = olcu["mekan"]
        toplam = self.rng.randint(alt, ust)
        adlar = list(sehirler)
        # Mekanların ~%78'i şehirlerde, kalanı kırda (şehirler arası boşluk).
        kentli = max(len(adlar), int(round(toplam * 0.78)))
        kirsal = max(1, toplam - kentli)

        mekanlar, kullanilan = {}, set()
        yaricap = olcu["sehir_yaricap"]

        # Her şehre en az bir mekan; kalanı ağırlıklı dağılır.
        pay = [1] * len(adlar)
        for i in range(kentli - len(adlar)):
            pay[self.rng.randrange(len(adlar))] += 1

        for sehir, adet in zip(adlar, pay):
            merkez = (sehirler[sehir]["x"], sehirler[sehir]["y"])
            for _ in range(adet):
                kategori = self._kategori_sec(kirsal=False)
                ad = self._ad_uret(kategori, sehir, kullanilan)
                kullanilan.add(ad)
                aci = self.rng.uniform(0, math.tau)
                # sqrt: merkeze doğru yığılmasın, alan üzerinde eşit dağılsın
                uzaklik = yaricap * math.sqrt(self.rng.random())
                mekanlar[ad] = {
                    "category": kategori,
                    "city": sehir,
                    "x": round(merkez[0] + math.cos(aci) * uzaklik, 2),
                    "y": round(merkez[1] + math.sin(aci) * uzaklik, 2),
                }

        # Kır mekanları: iki şehir arasındaki hatta serpiştirilir.
        for _ in range(kirsal):
            kategori = self._kategori_sec(kirsal=True)
            if len(adlar) >= 2:
                a, b = self.rng.sample(adlar, 2)
                pa = (sehirler[a]["x"], sehirler[a]["y"])
                pb = (sehirler[b]["x"], sehirler[b]["y"])
                t = self.rng.uniform(0.25, 0.75)
                x = pa[0] + (pb[0] - pa[0]) * t + self.rng.uniform(-2.5, 2.5)
                y = pa[1] + (pb[1] - pa[1]) * t + self.rng.uniform(-2.5, 2.5)
                yakin = a if t < 0.5 else b
            else:
                merkez = (sehirler[adlar[0]]["x"], sehirler[adlar[0]]["y"])
                aci = self.rng.uniform(0, math.tau)
                d = yaricap * self.rng.uniform(1.8, 3.2)
                x, y = merkez[0] + math.cos(aci) * d, merkez[1] + math.sin(aci) * d
                yakin = adlar[0]
            ad = self._ad_uret(kategori, yakin, kullanilan)
            kullanilan.add(ad)
            mekanlar[ad] = {
                "category": kategori,
                # Kır mekanı bir şehre BAĞLI değildir ama en yakın yerleşimle
                # anılır: "Akyazı yolu üzerindeki çiftlik".
                "city": f"{yakin} kırsalı",
                "x": round(x, 2),
                "y": round(y, 2),
            }
        return mekanlar

    def _yollari_kur(self, sehirler: dict, mekanlar: dict, olcu: dict) -> list:
        """Şehir içi ve şehirlerarası yolları kurar, uzunlukları hesaplar."""
        yollar = []
        nokta = {ad: (m["x"], m["y"]) for ad, m in mekanlar.items()}

        def yol_ekle(a, b, kind, uzatma=1.0):
            if a == b:
                return
            bilgi = self._yol_bilgisi(kind)
            km = _mesafe(nokta[a], nokta[b]) * float(bilgi.get("sapma") or 1.3) * uzatma
            durum = "açık"
            if self.rng.random() < BLOCKED_CHANCE:
                durum = self.rng.choice(["tıkalı", "tıkalı", "barikatlı", "çökük"])
            yollar.append({
                "a": a, "b": b, "kind": kind, "km": round(max(0.05, km), 2),
                "status": durum, "risk": int(bilgi.get("risk") or 2),
                "notes": bilgi.get("not") or "", "known": "bilinmiyor",
            })

        # --- şehir içi: her mekan en yakın birkaç komşusuna bağlanır ---
        sehir_uyeleri = {}
        for ad, m in mekanlar.items():
            sehir_uyeleri.setdefault(m["city"], []).append(ad)

        for uyeler in sehir_uyeleri.values():
            for ad in uyeler:
                yakinlar = sorted(
                    (o for o in uyeler if o != ad),
                    key=lambda o: _mesafe(nokta[ad], nokta[o]))[:CITY_DEGREE]
                for komsu in yakinlar:
                    if any(set((y["a"], y["b"])) == {ad, komsu} for y in yollar):
                        continue
                    uzunluk = _mesafe(nokta[ad], nokta[komsu])
                    kind = CITY_ROADS[1] if uzunluk > 1.0 else CITY_ROADS[0]
                    yol_ekle(ad, komsu, kind)
                    # Bazen ikinci bir güzergâh: uzun ama başka türden.
                    if self.rng.random() < ALT_ROAD_CHANCE:
                        yol_ekle(ad, komsu, self.rng.choice(ALT_ROADS),
                                 uzatma=self.rng.uniform(1.2, 1.7))

        # --- şehirlerarası: her şehir en yakın şehre anayolla bağlanır ---
        sehir_adlari = list(sehirler)
        for i, sehir in enumerate(sehir_adlari):
            for diger in sehir_adlari[i + 1:]:
                a = self._kapi(sehir_uyeleri, sehir, sehirler[diger], nokta)
                b = self._kapi(sehir_uyeleri, diger, sehirler[sehir], nokta)
                if not a or not b:
                    continue
                # Uzak şehirler doğrudan bağlanmaz: en yakın iki şehir bağlanır,
                # gerisi zincirle. Aksi halde harita tam graf olurdu.
                if _mesafe(nokta[a], nokta[b]) > olcu["yayilim"] * 0.62:
                    continue
                yol_ekle(a, b, RURAL_ROADS[1])
                if self.rng.random() < ALT_HIGHWAY_CHANCE:
                    yol_ekle(a, b, self.rng.choice(["kır yolu", "demiryolu", "patika"]),
                             uzatma=self.rng.uniform(1.25, 1.8))

        # --- kır mekanları en yakın iki yere bağlanır ---
        for ad, m in mekanlar.items():
            if not str(m["city"]).endswith("kırsalı"):
                continue
            yakinlar = sorted((o for o in mekanlar if o != ad),
                              key=lambda o: _mesafe(nokta[ad], nokta[o]))[:2]
            for komsu in yakinlar:
                if any(set((y["a"], y["b"])) == {ad, komsu} for y in yollar):
                    continue
                yol_ekle(ad, komsu, self.rng.choice(RURAL_ROADS))

        self._baglantiyi_garantile(yollar, mekanlar, nokta)
        return yollar

    @staticmethod
    def _kapi(sehir_uyeleri: dict, sehir: str, hedef: dict, nokta: dict):
        """Şehrin hedefe en YAKIN mekanı — anayolun bağlanacağı kapı.

        Anayol şehrin ortasına değil kenarına bağlanır: giriş çıkış noktası
        olması hem gerçekçi hem de oyunda anlamlı (şehre girmeden geçebilirsin)."""
        uyeler = sehir_uyeleri.get(sehir) or []
        if not uyeler:
            return None
        hedef_nokta = (hedef["x"], hedef["y"])
        return min(uyeler, key=lambda ad: _mesafe(nokta[ad], hedef_nokta))

    def _baglantiyi_garantile(self, yollar: list, mekanlar: dict, nokta: dict) -> None:
        """Kopuk kalan grupları en yakın komşularına bağlar.

        Ulaşılamayan bir mekan oyunda "var ama gidilemez" demektir; keşif
        mekaniği için haritanın tek parça olması gerekir. Çökük yollar burada
        bağlantı sayılmaz — yoksa tek geçidi çökmüş bir bölge ada kalırdı."""
        ebeveyn = {ad: ad for ad in mekanlar}

        def kok(x):
            while ebeveyn[x] != x:
                ebeveyn[x] = ebeveyn[ebeveyn[x]]
                x = ebeveyn[x]
            return x

        def birlestir(x, y):
            rx, ry = kok(x), kok(y)
            if rx != ry:
                ebeveyn[rx] = ry

        for yol in yollar:
            if yol["status"] != "çökük":
                birlestir(yol["a"], yol["b"])

        gruplar = {}
        for ad in mekanlar:
            gruplar.setdefault(kok(ad), []).append(ad)

        while len(gruplar) > 1:
            anahtarlar = list(gruplar)
            temel = gruplar[anahtarlar[0]]
            en_iyi = None
            for ad in temel:
                for diger_anahtar in anahtarlar[1:]:
                    for hedef in gruplar[diger_anahtar]:
                        d = _mesafe(nokta[ad], nokta[hedef])
                        if en_iyi is None or d < en_iyi[0]:
                            en_iyi = (d, ad, hedef)
            if en_iyi is None:
                break
            _d, a, b = en_iyi
            bilgi = self._yol_bilgisi("kır yolu")
            yollar.append({
                "a": a, "b": b, "kind": "kır yolu",
                "km": round(max(0.05, _d * float(bilgi.get("sapma") or 1.3)), 2),
                "status": "açık", "risk": int(bilgi.get("risk") or 2),
                "notes": bilgi.get("not") or "", "known": "bilinmiyor",
            })
            birlestir(a, b)
            gruplar = {}
            for ad in mekanlar:
                gruplar.setdefault(kok(ad), []).append(ad)
