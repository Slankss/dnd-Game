"""Zombi tehdidi — karşılaşma motorunun VERİ ve HESAP katmanı.

Sorun: anlatıcıya "zombiler sık olsun" demek yetmiyor; metin ricası her turda
aynı şekilde yorumlanmıyor ve yolculuk güvenli bir geçiş sahnesine dönüşüyordu.
Bu yüzden karşılaşma artık **sunucunun attığı gerçek bir zar**dır: kaç zombi,
hangi türler, ne mesafede, hangi yönden — hepsi burada belirlenir ve anlatıcıya
zorunlu bir blok olarak verilir.

Modelin üç girdisi var:

  * **yoğunluk** — bulunulan yerin (ya da yolun) kendi ölü nüfusu (0-100).
    Yer türünden gelir, oynandıkça değişir: temizlenen bina düşer, gürültü
    çekilen mahalle yükselir.
  * **gürültü** — grubun çıkardığı ses (0-100). Silah sesi, araç, kırılan kapı
    yükseltir; sessiz geçen zaman söndürür.
  * **dikkat (heat)** — bölgenin gruba yönelmiş ilgisi. Karşılaşmalar ve
    gürültü biriktirir, uzun sessizlik düşürür.

Buna zaman (gece), hava (sis/fırtına), gerilim ve **yolculuk** eklenir.
Yolculuk en büyük çarpandır: açık alanda saklanacak yer yoktur.
"""

import secrets
from dataclasses import dataclass, field

from .text import norm_tr

# --------------------------------------------------------------------- ayarlar

# Karşılaşma ihtimalinin bileşenleri (yüzde puanı olarak).
BASE_TRAVEL = 44          # yolculukta taban
BASE_SETTLED = 8          # yerleşik/sığınakta taban
W_DENSITY_TRAVEL = 0.38   # yol yoğunluğunun katkısı
W_DENSITY_SETTLED = 0.34  # bulunulan yerin yoğunluk katkısı
W_NOISE = 0.42            # gürültünün katkısı
W_HEAT = 0.22             # bölgenin dikkatinin katkısı
NIGHT_BONUS = 12
FOG_BONUS = 9             # sis/fırtına: görüş kapanır, üstüne binilir
RAIN_MALUS = -5           # yağmur sesi maskeler
TENSION_BONUS = {"düşük": 0, "orta": 5, "yüksek": 10}
QUIET_STREAK_BONUS = 7    # sessiz geçen her tur (3. turdan sonra) baskıyı artırır
QUIET_STREAK_CAP = 21
# Tavan bilerek 100 değil: en kötü koşulda bile sessiz geçen bir tur
# mümkün olsun, yoksa gerilim düzleşiyor.
CHANCE_MIN, CHANCE_MAX = 6, 88

# Gürültü sönümü: sessiz geçen her oyun-içi saatte bu kadar düşer.
NOISE_DECAY_PER_HOUR = 14
HEAT_DECAY_PER_HOUR = 10

# Belirgin gürültü kaynakları — oyuncunun hamle metninden yakalanır. Anlatıcı
# ayrıca `threat.noise_add` ile kendi ölçüsünü yazabilir.
NOISE_KEYWORDS = (
    (("ateş et", "ateş aç", "silah", "tabanca", "tüfek", "vur ", "sık ", "namlu"), 26),
    (("patla", "bomba", "el bombası", "dinamit", "molotof"), 34),
    (("araba", "araç", "kamyon", "motor", "jeneratör", "korna", "motosiklet"), 24),
    (("bağır", "çığlık", "seslen", "haykır", "düdük", "siren", "alarm"), 18),
    (("kır ", "kırıyor", "parçala", "balyoz", "levye", "cam", "kapıyı zorla"), 12),
    (("koş", "kaç", "sprint"), 8),
)

# Yolculuk niyeti — bu turda yola çıkıldığını gösteren ifadeler.
TRAVEL_KEYWORDS = (
    "yola çık", "yola koyul", "git ", "gidiyor", "gidelim", "yürü", "ilerle",
    "keşfe", "keşif", "araştırmaya git", "yolculuk", "rotayı", "yola",
    "dışarı çık", "kasabaya", "şehre", "mahalleye", "tarafa geç", "geçelim",
    "ulaşmaya", "varmaya", "doğru hareket",
)

# Karşılaşma şiddeti bantları: (ad, taban adet aralığı, mesafe aralığı m).
SEVERITIES = (
    ("iz", (0, 0), (0, 0)),
    ("tekil", (1, 3), (25, 90)),
    ("küme", (4, 9), (20, 70)),
    ("kalabalık", (10, 24), (30, 120)),
    ("sürü", (25, 70), (40, 200)),
)

APPROACHES = (
    "rüzgâr altından — kokunuzu almışlar",
    "arkanızdan, geldiğiniz yönden",
    "yandaki dar geçitten",
    "önünüzdeki açıklığın karşı ucundan",
    "yukarıdan/üst kattan",
    "molozun altından, ayak hizasından",
)


def clamp(value, low=0, high=100) -> int:
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        return low
    return max(low, min(high, value))


def density_band(density: int) -> str:
    if density >= 66:
        return "yüksek"
    if density >= 38:
        return "orta"
    return "düşük"


def _hash(text: str) -> int:
    h = 0x811c9dc5
    for ch in norm_tr(text):
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def base_density_for(name: str, kind: str = "") -> int:
    """Yerin taban zombi yoğunluğu: türünden gelir, adından sabit sapma alır.

    Eşleme KÖKTEN yapılır — "sağlığı" da "sağlık" anahtarına, "hastanesi" de
    "hastane"ye düşsün diye. Düz `in` araması Türkçe eklerde tutmuyordu
    ("aile sağlığı merkezi" varsayılan yoğunluğa düşüyordu). En UZUN eşleşen
    anahtar kazanır: "metro istasyonu" metroya gider, istasyona değil."""
    from scenario import DEFAULT_DENSITY, PLACE_DENSITY

    kelimeler = norm_tr(f"{kind} {name}").split()
    taban, en_uzun = DEFAULT_DENSITY, 0
    for anahtar, deger in PLACE_DENSITY.items():
        kok = norm_tr(anahtar)
        # Ekli hâlleri yakalamak için anahtarın son bir-iki harfi düşürülür.
        kok = kok[: max(4, len(kok) - 2)]
        if any(kelime.startswith(kok) for kelime in kelimeler) and len(anahtar) > en_uzun:
            taban, en_uzun = deger, len(anahtar)
    # Aynı yer her oyunda aynı sapmayı alır (kararlı), ±9 puan.
    sapma = (_hash(name) % 19) - 9
    return clamp(taban + sapma)


def noise_from_text(text: str) -> int:
    """Oyuncunun hamlesinden gürültü tahmini — en yüksek eşleşme kazanır."""
    metin = norm_tr(text or "")
    if not metin:
        return 0
    en_yuksek = 0
    for kelimeler, puan in NOISE_KEYWORDS:
        if any(norm_tr(k) in metin for k in kelimeler):
            en_yuksek = max(en_yuksek, puan)
    return en_yuksek


def looks_like_travel(text: str) -> bool:
    metin = norm_tr(text or "")
    return any(norm_tr(k) in metin for k in TRAVEL_KEYWORDS)


@dataclass
class Encounter:
    """Bir turun karşılaşma sonucu."""

    var: bool = False
    severity: str = "iz"
    count: int = 0
    distance: int = 0
    types: list = field(default_factory=list)      # [{"ad", "adet", "kunye"}]
    approach: str = ""
    noticed_first: bool = True                    # grup mu önce fark etti
    chance: int = 0
    roll: int = 0
    travelling: bool = False
    sign: str = ""                                # temas yoksa ortamdaki iz

    def to_dict(self) -> dict:
        return {"var": self.var, "severity": self.severity, "count": self.count,
                "distance": self.distance, "types": self.types,
                "approach": self.approach, "noticed_first": self.noticed_first,
                "chance": self.chance, "roll": self.roll,
                "travelling": self.travelling, "sign": self.sign}


# `DictModel` tabanı kullanılmıyor: tehdit kaydı tamamen sunucunun ürettiği bir
# alandır, anlatıcının serbest yazdığı bir yapı değil. Sade bir dataclass hem
# yeterli hem de okuması kolay.
@dataclass
class ThreatState:
    """`world_state.threat` — tehdit motorunun kalıcı durumu."""

    noise: int = 0
    heat: int = 12
    quiet_turns: int = 0
    travelling: bool = False
    # Bir önceki turda geçen oyun-içi dakika: gürültü/dikkat sönümü GERÇEK
    # süreye göre yapılsın diye taşınır (sabit 20 dk varsaymak, uzun bir
    # yolculuk turundan sonra gürültüyü olduğu gibi bırakıyordu).
    last_minutes: int = 0
    # Grubun bir önceki turdaki konumu: değiştiyse bu tur YOLCULUK sayılır.
    last_location: str = ""
    density: dict = field(default_factory=dict)     # {yer adı: 0-100}
    last: dict = field(default_factory=dict)        # son karşılaşma özeti
    history: list = field(default_factory=list)     # son 12 karşılaşma
    encounters: int = 0
    contacts: int = 0                               # gerçek temas sayısı

    # ------------------------------------------------------------ dönüşüm
    @classmethod
    def from_dict(cls, data) -> "ThreatState":
        data = data if isinstance(data, dict) else {}
        state = cls()
        state.noise = clamp(data.get("noise", 0))
        state.heat = clamp(data.get("heat", 12))
        state.quiet_turns = max(0, int(data.get("quiet_turns") or 0))
        state.travelling = bool(data.get("travelling"))
        state.last_minutes = max(0, int(data.get("last_minutes") or 0))
        state.last_location = str(data.get("last_location") or "")
        raw = data.get("density")
        if isinstance(raw, dict):
            state.density = {str(k): clamp(v) for k, v in raw.items()}
        if isinstance(data.get("last"), dict):
            state.last = data["last"]
        if isinstance(data.get("history"), list):
            state.history = [h for h in data["history"] if isinstance(h, dict)][-12:]
        state.encounters = max(0, int(data.get("encounters") or 0))
        state.contacts = max(0, int(data.get("contacts") or 0))
        return state

    def to_dict(self) -> dict:
        return {"noise": self.noise, "heat": self.heat,
                "quiet_turns": self.quiet_turns, "travelling": self.travelling,
                "last_minutes": self.last_minutes,
                "last_location": self.last_location,
                "density": self.density, "last": self.last,
                "history": self.history, "encounters": self.encounters,
                "contacts": self.contacts}

    # -------------------------------------------------------------- yoğunluk
    def density_of(self, place: str, kind: str = "") -> int:
        """Yerin güncel yoğunluğu; kayıtta yoksa türünden türetilip yazılır."""
        if not place:
            return clamp(base_density_for("bilinmeyen"))
        if place not in self.density:
            self.density[place] = base_density_for(place, kind)
        return self.density[place]

    def bump_density(self, place: str, delta: int) -> None:
        if not place:
            return
        self.density[place] = clamp(self.density.get(place, base_density_for(place)) + delta)

    # ---------------------------------------------------------------- sönüm
    def decay(self, hours: float) -> None:
        """Sessiz geçen zaman gürültüyü ve bölgenin dikkatini düşürür."""
        if hours <= 0:
            return
        self.noise = clamp(self.noise - NOISE_DECAY_PER_HOUR * hours)
        self.heat = clamp(self.heat - HEAT_DECAY_PER_HOUR * hours)

    def add_noise(self, amount: int) -> None:
        self.noise = clamp(self.noise + int(amount or 0))

    # ------------------------------------------------------------- ihtimal
    def chance(self, density: int, *, travelling: bool, night: bool,
               weather: str = "", tension: str = "") -> int:
        """Bu turda karşılaşma ihtimali (yüzde). Şeffaf ve ayarlanabilir."""
        if travelling:
            puan = BASE_TRAVEL + density * W_DENSITY_TRAVEL
        else:
            puan = BASE_SETTLED + density * W_DENSITY_SETTLED
        puan += self.noise * W_NOISE
        puan += self.heat * W_HEAT
        if night:
            puan += NIGHT_BONUS
        hava = norm_tr(weather)
        if any(k in hava for k in ("sis", "pus", "firtina", "fırtına", "tipi")):
            puan += FOG_BONUS
        elif any(k in hava for k in ("yagmur", "yağmur", "sagabak", "sağanak")):
            puan += RAIN_MALUS
        puan += TENSION_BONUS.get(norm_tr(tension), 0) if tension else 0
        if self.quiet_turns >= 3:
            puan += min(QUIET_STREAK_CAP, (self.quiet_turns - 2) * QUIET_STREAK_BONUS)
        return clamp(puan, CHANCE_MIN, CHANCE_MAX)

    # ------------------------------------------------------------ karşılaşma
    def roll(self, *, density: int, travelling: bool, night: bool, day: int = 0,
             weather: str = "", tension: str = "") -> Encounter:
        """Karşılaşma zarını atar ve karşılaşmayı KURAR (tür, sayı, mesafe)."""
        sans = self.chance(density, travelling=travelling, night=night,
                           weather=weather, tension=tension)
        zar = secrets.randbelow(100) + 1
        sonuc = Encounter(chance=sans, roll=zar, travelling=travelling)

        if zar > sans:
            sonuc.sign = self._sign(density, night)
            return sonuc

        sonuc.var = True
        sonuc.severity = self._severity(density, travelling, zar, sans)
        if sonuc.severity == "iz":
            sonuc.var = False
            sonuc.sign = self._sign(density, night)
            return sonuc

        alt, ust = dict((ad, aralik) for ad, aralik, _ in SEVERITIES)[sonuc.severity]
        olcek = 0.6 + density / 100.0            # yoğun bölgede sürü büyür
        sonuc.count = max(1, int(round(secrets.randbelow(ust - alt + 1) + alt) * olcek))
        m_alt, m_ust = dict((ad, mesafe) for ad, _, mesafe in SEVERITIES)[sonuc.severity]
        sonuc.distance = secrets.randbelow(max(1, m_ust - m_alt + 1)) + m_alt
        sonuc.types = self._types(sonuc.count, density, night, day)
        sonuc.approach = APPROACHES[secrets.randbelow(len(APPROACHES))]
        # Gürültülü grup önce fark EDİLİR; sessiz grup genelde önce fark eder.
        sonuc.noticed_first = (secrets.randbelow(100) + 1) > (25 + self.noise * 0.5)
        return sonuc

    @staticmethod
    def _severity(density: int, travelling: bool, zar: int, sans: int) -> str:
        """Zarın payına göre şiddet: zar ne kadar düşükse karşılaşma o kadar büyük."""
        pay = zar / max(1, sans)
        yogun = density >= 66
        # Sürü NADİR olmalı: her turda "kaçın!" diyen bir oyun kısa sürede
        # köreliyor. Zarın en alt %10'u + yoğun bölge/yol şartı arıyoruz.
        if pay <= 0.10:
            return "sürü" if (yogun or travelling) else "kalabalık"
        if pay <= 0.32:
            return "kalabalık" if (yogun or travelling) else "küme"
        if pay <= 0.66:
            return "küme"
        if pay <= 0.88:
            return "tekil"
        return "iz"

    @staticmethod
    def _types(count: int, density: int, night: bool, day: int) -> list:
        """Sürünün tür karışımı — katalogdan ağırlıklı çekiliş."""
        from scenario import ZOMBIE_TYPES

        bant = density_band(density)
        havuz = [t for t in ZOMBIE_TYPES
                 if bant in t["yogunluk"] and day >= int(t.get("min_gun") or 0)]
        if not havuz:
            havuz = [t for t in ZOMBIE_TYPES if int(t.get("min_gun") or 0) == 0]

        agirliklar = [max(1, int(t["agirlik"] * (t.get("gece", 1.0) if night else 1.0)))
                      for t in havuz]
        toplam = sum(agirliklar)

        def cek():
            hedef = secrets.randbelow(toplam) + 1
            birikim = 0
            for tur, agirlik in zip(havuz, agirliklar):
                birikim += agirlik
                if hedef <= birikim:
                    return tur
            return havuz[-1]

        # Kalabalık sürülerde 2-3 tür karışır; küçük karşılaşmada 1-2.
        tur_sayisi = 1 if count <= 3 else (2 if count <= 12 else 3)
        secilen, kalan = [], count
        for i in range(tur_sayisi):
            tur = cek()
            if any(s["ad"] == tur["ad"] for s in secilen):
                continue
            son = i == tur_sayisi - 1
            adet = kalan if son else max(1, int(kalan * (0.55 if i == 0 else 0.5)))
            adet = min(adet, kalan)
            secilen.append({"ad": tur["ad"], "adet": adet, "kunye": tur["kunye"]})
            kalan -= adet
            if kalan <= 0:
                break
        if kalan > 0 and secilen:
            secilen[0]["adet"] += kalan
        return secilen

    @staticmethod
    def _sign(density: int, night: bool) -> str:
        """Temas yok — ama dünya boş değil: ortamda bir iz kalsın."""
        izler = [
            "taze ayak izleri ve sürüklenme çizgileri",
            "yakında bir yerde kırılan cam sesi",
            "duvarda kurumamış kan ve tırnak izleri",
            "leş kokusunun rüzgârla gelip gitmesi",
            "uzaktan gelen boğuk bir uğultu",
            "yerde yeni bırakılmış, hâlâ ıslak bir ceset",
            "bir kapının kendi kendine tıkırdaması",
        ]
        if night:
            izler += ["karanlıkta bir yerde kesilen bir çığlık",
                      "el fenerinin ucunda parlayan iki göz"]
        if density >= 66:
            izler += ["sokağın karşısında ağır ağır sallanan onlarca gölge",
                      "üst kattan gelen ayak sürtme sesleri"]
        return izler[secrets.randbelow(len(izler))]

    # --------------------------------------------------------------- kayıt
    def record(self, encounter: Encounter, day=None, clock=None, place=None) -> None:
        """Karşılaşmayı deftere işler; dikkat/sessizlik sayaçlarını günceller."""
        ozet = {
            "gun": day, "saat": clock, "yer": place,
            "severity": encounter.severity, "count": encounter.count,
            "types": [t["ad"] for t in encounter.types],
            "distance": encounter.distance, "chance": encounter.chance,
            "roll": encounter.roll, "travelling": encounter.travelling,
            "var": encounter.var,
        }
        if encounter.var:
            self.encounters += 1
            self.contacts += 1
            self.quiet_turns = 0
            # Karşılaşma bölgenin dikkatini artırır: sürü büyüdükçe daha çok.
            # Artış ölçülü: doyuma ulaşırsa gece/gürültü gibi asıl değişkenler
            # anlamsızlaşıyor, her tur aynı sıcaklıkta geçiyordu.
            self.heat = clamp(self.heat + 4 + min(12, encounter.count // 3))
            self.last = ozet
            self.history.append(ozet)
            del self.history[:-12]
            if place:
                self.bump_density(place, 2)
        else:
            self.quiet_turns += 1
