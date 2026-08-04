"""Harcama muhasebesi — envanteri anlatıcı değil SUNUCU tutar.

Sorun şuydu: silah sıkılıyor ama mermi azalmıyordu. Çünkü tüketim, anlatıcının
yanıtından okunmaya çalışılıyordu ("bu turda ateş etti mi?") ve bu, serbest
metinden çıkarılması zor bir bilgi.

Çözüm: metni ayrıştırmıyoruz. Oyuncu ne yapacağını zaten SEÇİYOR ve seçim,
sahne yazılmadan önce belli. Bu yüzden bedel seçeneğin kendisinde beyan edilir
(`Option.spend`), sunucu turun çözümünde keser, sonra anlatıcıya ne kesildiğini
ZORUNLU bir blok olarak bildirir. Anlatıcı muhasebe tutmaz, sadece anlatır.

Üç katman:

  1. **Beyan** (`Option.spend`) — asıl yol. `{"9mm fişek": 2}`.
  2. **Otomatik tespit** — anlatıcı `spend` yazmayı unutursa seçeneğin metninde
     silah/ateş izi aranır (`threat.NOISE_KEYWORDS` ile aynı sözlük mantığı) ve
     zar bandına göre 1-3 fişek düşülür. Beceriksiz zar daha çok mermi yakar.
  3. **Süzgeç** (`options_service`) — karşılanamayan seçenek zaten sunulmaz;
     yine de bir yolla seçilirse "tetik boşa düştü" olarak çözülür ve anlatıcıya
     öyle bildirilir.

Kilit ÇAĞIRANDA (round_service).
"""

from app.models.inventory import cephane_mi
from app.models.text import norm_tr

#: Seçenek metninde ateş etme izi — otomatik tüketim bunları arar.
FIRE_WORDS = (
    "ateş et", "ateş aç", "ateşle", "tetiğe", "tetik", "vur ", "vurur",
    "sık ", "sıkar", "namlu", "nişan al", "silahla", "tabancayla",
    "tüfekle", "pompalıyla", "mermi harca", "kurşun",
)

#: Zar bandına göre harcanan mermi: beceriksiz atış daha çok fişek yakar.
BAND_AMMO = {
    "Felaket": 3,
    "Başarısız": 2,
    "Kısmi Başarı": 2,
    "Başarı": 1,
    "Güçlü Başarı": 1,
    "Kritik": 1,
}
DEFAULT_AMMO = 2


def looks_like_firing(text: str) -> bool:
    """Bu hamle ateş etmeyi içeriyor mu (kaba ama tutarlı bir tarama).

    Sondaki boşluklu kalıplar ("vur ") metnin sonunda da tutsun diye metne bir
    boşluk eklenir — `norm_tr` sonu kırpıyor."""
    metin = norm_tr(text or "")
    if not metin:
        return False
    metin += " "
    return any(norm_tr(k) + (" " if k.endswith(" ") else "") in metin
               for k in FIRE_WORDS)


class InventoryService:
    """Turun harcama ayağı."""

    # ------------------------------------------------------------ karşılama
    @staticmethod
    def can_afford(person, spend: dict) -> bool:
        """Karakter bu bedeli ÖDEYEBİLİR mi (seçenek süzgeci için).

        Sayacı hiç olmayan kalem engel değildir: "yarım saat", "kol gücü" gibi
        soyut bedeller ya da henüz sayılmamış eşyalar seçeneği kilitlemesin —
        yalnızca SAYILAN bir kalem yetersizse seçenek elenir."""
        if not spend or person is None:
            return True
        counted = person.counts()
        for ad, adet in spend.items():
            if counted.find(ad) is None:
                continue  # bu kalem sayaçla takip edilmiyor
            if counted.count(ad) < int(adet or 0):
                return False
        return True

    @staticmethod
    def missing(person, spend: dict) -> dict:
        """Eksik kalan kalemler {ad: eksik adet} — sıfırsa her şey karşılanıyor."""
        eksik = {}
        if not spend or person is None:
            return eksik
        counted = person.counts()
        for ad, adet in spend.items():
            if counted.find(ad) is None:
                continue
            fark = int(adet or 0) - counted.count(ad)
            if fark > 0:
                eksik[ad] = fark
        return eksik

    # -------------------------------------------------------------- harcama
    def apply(self, world, picks) -> list:
        """Turun seçimlerinin bedelini keser (kilit ÇAĞIRANDA).

        `picks`: `Round.ordered_picks()` çıktısı. Dönen liste, prompt bloğu ve
        anlatıcı günlüğü için kayıtlardır:

            [{"player":.., "spent":{ad:adet}, "left":{ad:kalan},
              "missing":{ad:eksik}, "auto":bool, "dry":bool}, ...]

        `dry=True` → tetik boşa düştü: hamle ateş etmeyi içeriyordu ama
        harcanacak mermi yoktu.
        """
        kayitlar = []
        for pick in picks or []:
            person = (world.characters or {}).get(pick.player)
            if person is None:
                continue
            kayit = self._apply_one(person, pick)
            if kayit:
                kayitlar.append(kayit)
        return kayitlar

    def _apply_one(self, person, pick):
        istenen = dict(getattr(pick, "spend", None) or {})
        otomatik = False

        # Beyan yoksa ateş izi ara: anlatıcı `spend` yazmayı unutsa bile
        # envanter akmalı (güvenlik ağı).
        if not istenen and looks_like_firing(pick.text):
            cephane = person.counts().ammo_keys()
            adet = BAND_AMMO.get(str(pick.band or ""), DEFAULT_AMMO)
            if cephane:
                istenen = {cephane[0]: adet}
                otomatik = True
            else:
                return {"player": pick.player, "spent": {}, "left": {},
                        "missing": {}, "auto": True, "dry": True}

        if not istenen:
            return None

        eksik = self.missing(person, istenen)
        harcanan, kalan = {}, {}
        for ad, adet in istenen.items():
            counted = person.counts()
            if counted.find(ad) is None:
                continue  # sayaçsız kalem: soyut bedel, kesilecek bir şey yok
            gercek = person.spend_item(ad, int(adet or 0))
            if gercek:
                harcanan[counted.find(ad) or ad] = gercek
            kalan[counted.find(ad) or ad] = person.count_of(ad)

        if not harcanan and not eksik:
            return None
        kuru = bool(eksik) and not harcanan
        return {"player": pick.player, "spent": harcanan, "left": kalan,
                "missing": eksik, "auto": otomatik, "dry": kuru}

    # --------------------------------------------------------------- prompt
    @staticmethod
    def note(kayitlar) -> str:
        """Anlatıcıya giden ZORUNLU harcama bloğu."""
        if not kayitlar:
            return ""
        satirlar = [
            "HARCAMA (sunucu kesti — bu blok ZORUNLUDUR, sahnede buna UY):",
        ]
        for kayit in kayitlar:
            parcalar = []
            if kayit["spent"]:
                parcalar.append("harcandı: " + ", ".join(
                    f"{adet}× {ad}" for ad, adet in kayit["spent"].items()))
            if kayit["left"]:
                parcalar.append("kalan: " + ", ".join(
                    f"{ad} {adet}" for ad, adet in kayit["left"].items()))
            if kayit["missing"]:
                parcalar.append("YETMEDİ: " + ", ".join(
                    f"{ad} (−{adet})" for ad, adet in kayit["missing"].items()))
            if not parcalar:
                parcalar.append("harcayacak mermisi yok")
            satirlar.append(f"- {kayit['player']}: " + " · ".join(parcalar))
            if kayit["dry"]:
                satirlar.append(
                    f"  → {kayit['player']} ATEŞ EDEMEDİ: harcayacak mermisi yok. "
                    "Tetik boşa düştü (klik). Bunu sahnede FİİLEN göster; "
                    "hamlenin sonucunu buna göre çöz, mermi varmış gibi anlatma."
                )
        satirlar.append(
            "- Bu sayılar KESİN: envanteri sunucu tutuyor. Metinde farklı bir "
            "miktar söyleme, harcanmayan bir şeyi harcanmış gibi anlatma ve "
            "state-update'te bu kalemleri TEKRAR düşürme (çift kesim olur)."
        )
        return "\n".join(satirlar)

    @staticmethod
    def stock_note(world, players) -> str:
        """Seçenek üretimi için: kimde sayılabilir ne kadar var.

        Anlatıcı bunu görmeden gerçekçi `spend` yazamaz — "3 fişek harca"
        diyen bir seçenek, 1 fişeği kalmış karaktere sunulmamalı."""
        satirlar = []
        for ad in players or []:
            person = (world.characters or {}).get(ad)
            if person is None:
                continue
            sayaclar = person.counts().to_dict()
            if sayaclar:
                satirlar.append(f"- {ad}: " + ", ".join(
                    f"{kalem} ×{adet}" for kalem, adet in sayaclar.items()))
            else:
                satirlar.append(f"- {ad}: sayılabilir eşyası yok")
        if not satirlar:
            return ""
        return (
            "SAYILABİLİR STOK (sunucunun tuttuğu KESİN miktarlar; seçeneklerin "
            "`spend` alanını buna göre yaz, olmayan şeyi harcatma):\n"
            + "\n".join(satirlar)
        )

    @staticmethod
    def has_ammo(person) -> bool:
        """Karakterin ateş edecek mermisi var mı (seçenek süzgeci için)."""
        if person is None:
            return False
        return any(cephane_mi(ad) and adet > 0
                   for ad, adet in person.counts().to_dict().items())
