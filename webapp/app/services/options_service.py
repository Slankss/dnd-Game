"""Seçenek havuzunun bakımı.

Anlatıcı her turun sonunda `options` yazar; bu servis onu OYNANABİLİR hale
getirir:

  * sahnede olmayan/ölmüş karakterlerin listeleri düşer,
  * eksik kalanlar (5'ten az) sahneye bağlı jenerik seçeneklerle tamamlanır —
    oyuncu ekranı asla boş kalmaz, model bir turda unutsa bile oyun döner,
  * her listede EN AZ BİR düşük riskli seçenek bulunur: senaryo yalnız sunulan
    tercihlerle ilerlediği için (serbest hamle yok) oyuncuyu yalnızca ölümcül
    seçenekler arasına sıkıştırmak kabul edilemez,
  * sunulan her seçenek havuz dosyasına (`data/options_pool.jsonl`) düşer,
  * anlatıcıya "son sunulanlar" özeti hazırlanır ki kendini tekrar etmesin.
"""

from app.models.options import (
    CATEGORIES,
    OPTION_MAX,
    OPTION_MIN,
    Option,
    normalize_list,
)
from app.repositories.options_repo import OptionsPoolRepository

# Eksik seçenekleri tamamlarken kullanılan kalıplar. Sahneye bağlanabilmesi
# için {tehdit} ve {yer} yer tutucularını alırlar.
FALLBACK_TEMPLATES = [
    ("güvenli", "Olduğun yerde kal, {tehdit} yönünü dinle ve acele etme.",
     "zaman kaybı — durum kendi başına ilerler"),
    ("hazırlık", "{yer} içinde elindekileri gözden geçir; çıkışı ve barikatı sağlamlaştır.",
     "en az yarım saat, o sırada başka bir şey yapamazsın"),
    ("gizemli", "{tehdit} ile ilgili tuhaf duran şeyi yakından incele; ne olduğunu anlamaya çalış.",
     "yaklaşmak gerekir, fark edilebilirsin"),
    ("riskli", "Doğrudan {tehdit} üstüne git — hızlı, gürültülü ve geri dönüşsüz.",
     "gürültü + yaralanma riski"),
    ("kurnaz", "Dikkati başka yöne çekecek bir ses/iz bırak, sen ters yönden ilerle.",
     "bir eşyanı feda edersin, işe yaramayabilir"),
    ("insani", "Yanındakinin durumunu kontrol et; kötüyse onu geri çek, kendi planını ertele.",
     "kendi hamlen bir tur gecikir"),
    ("körü körüne", "Düşünme, ilk aklına geleni yap ve sonucuna katlan.",
     "sonuç tamamen zara kalır"),
    ("acımasız", "Kendini kurtaracak hamleyi yap; kimin geride kalacağına sonra bakarsın.",
     "grup içi güven yara alır"),
]


class OptionsService:
    def __init__(self, pool_repo=None):
        self.pool = pool_repo or OptionsPoolRepository()

    # ------------------------------------------------------------- bakım
    def refresh(self, world, players, learning=None, turn=None):
        """Turun sonunda çağrılır: havuzu kadroya göre düzeltir, eksikleri
        tamamlar ve sunulanları havuza yazar. Dönen: OptionBoard."""
        board = world.ensure_options()
        board.keep_only(players)
        for player in players:
            options = board.for_player(player)
            if len(options) < OPTION_MIN:
                options = self._pad(world, player, options)
            options = self._ensure_safe_exit(world, player, options)
            board.set_player(player, options[:OPTION_MAX])
        if learning is not None:
            day = world.day if isinstance(world.day, int) else None
            learning.record_offered(board, day=day, turn=turn)
        return board

    def _pad(self, world, player: str, options: list) -> list:
        """Eksik seçenekleri sahneye bağlı jeneriklerle tamamlar."""
        tehdit = self._threat(world)
        yer = self._where(world, player)
        var_olan = {o.category for o in options}
        tamamlanan = list(options)
        for category, template, cost in FALLBACK_TEMPLATES:
            if len(tamamlanan) >= OPTION_MIN:
                break
            # Önce eksik kategorileri kapat: liste tek renk olmasın.
            if category in var_olan and len(var_olan) < len(CATEGORIES):
                continue
            tamamlanan.append(Option(
                id="", category=category,
                text=template.format(tehdit=tehdit, yer=yer), cost=cost,
            ))
            var_olan.add(category)
        # Kategori çeşitliliği yetmediyse kalanı sırayla doldur.
        i = 0
        while len(tamamlanan) < OPTION_MIN and i < len(FALLBACK_TEMPLATES):
            category, template, cost = FALLBACK_TEMPLATES[i]
            metin = template.format(tehdit=tehdit, yer=yer)
            if all(o.text != metin for o in tamamlanan):
                tamamlanan.append(Option(id="", category=category, text=metin, cost=cost))
            i += 1
        return normalize_list(player, [o.to_dict() for o in tamamlanan])

    def _ensure_safe_exit(self, world, player: str, options: list) -> list:
        """Her listede en az bir düşük riskli çıkış olsun.

        Serbest hamle kaldırıldığı için oyuncunun tek çıkışı bu listedir;
        hepsi 'riskli'/'körü körüne' olan bir liste, oyuncuyu kendi seçmediği
        bir felakete zorlar. Anlatıcı böyle bir liste yazdıysa sunucu sona
        güvenli bir seçenek ekler."""
        guvenli_kategoriler = {"güvenli", "hazırlık", "insani"}
        if any(o.category in guvenli_kategoriler for o in options):
            return options
        kategori, sablon, cost = FALLBACK_TEMPLATES[0]
        metin = sablon.format(tehdit=self._threat(world), yer=self._where(world, player))
        tamam = list(options[:OPTION_MAX - 1])
        tamam.append(Option(id="", category=kategori, text=metin, cost=cost))
        return normalize_list(player, [o.to_dict() for o in tamam])

    @staticmethod
    def _threat(world) -> str:
        """Aktif zorluğun adı — jenerik seçenekleri sahneye bağlar."""
        for name, challenge in (world.challenges or {}).items():
            status = (getattr(challenge, "status", "") or "").lower()
            if status not in ("çözüldü", "başarısız"):
                return name
        return "tehdit"

    @staticmethod
    def _where(world, player: str) -> str:
        person = (world.characters or {}).get(player)
        where = getattr(person, "location", None)
        if isinstance(where, str) and where.strip():
            return where
        return world.location or "sığınak"

    # ------------------------------------------------------------- prompt
    def recent_note(self, players, limit: int = 8) -> str:
        """Anlatıcıya 'bunları zaten sundun' özeti."""
        satirlar = []
        for player in players or []:
            gecmis = self.pool.recent_offered(player, limit=limit)
            if gecmis:
                satirlar.append(f"- {player}: " + " | ".join(t[:90] for t in gecmis[:4]))
        if not satirlar:
            return ""
        return (
            "SON SUNULAN SEÇENEKLER (kelimesi kelimesine TEKRAR ETME; sahne "
            "ilerlediyse seçenekler de ilerlesin):\n" + "\n".join(satirlar)
        )

    @staticmethod
    def instruction(players) -> str:
        """Her normal turda modele verilen seçenek üretme talimatı."""
        isimler = ", ".join(players or []) or "(kimse)"
        return (
            "SEÇENEK ÜRETİMİ (bu turda ZORUNLU): state-update bloğunun "
            f"`options` alanına şu karakterlerin HER BİRİ için ayrı liste yaz: {isimler}. "
            f"Her seçenekte `text` (somut hamle), `category` "
            "(güvenli/riskli/gizemli/körü körüne/kurnaz/insani/acımasız/hazırlık) "
            "ve `cost` (somut bedel) olsun.\n"
            f"1. **SAYI SABİT DEĞİL**: karakter başına EN AZ {OPTION_MIN}, EN ÇOK "
            f"{OPTION_MAX} seçenek — ama bu bir HEDEF değil bir ARALIKTIR. Sahne "
            "mantıken kaç farklı, gerçekten birbirinden ayrışan karara izin "
            f"veriyorsa o kadarını yaz: sadece {OPTION_MIN} tane akla yatkın "
            f"alternatif varsa {OPTION_MIN} seçenekle bırak, sayıyı doldurmak için "
            "anlamsız/tekrar eden bir seçenek UYDURMA. Gerçekten farklı 6-7-8 "
            "yaklaşım varsa hepsini yaz.\n"
            "2. **Kategori oyuncuya GÖRÜNMEZ**: `category` ve `cost` SADECE "
            "sistem içi alanlardır, arayüz bunları oyuncuya hiç göstermez. Bu "
            "yüzden `text` alanının İÇİNE 'Güvenli', 'Riskli', 'En iyi seçenek', "
            "'Önerilen' gibi bir etiket, puan ya da ipucu YAZMA — seçenek metni "
            "sade bir eylem tarifi olsun, kendi kendini etiketlemesin. Bir "
            "seçeneğin ne kadar riskli/güvenli olduğu oyuncuya SADECE sahnenin "
            "bağlamından (ne olduğu, kime/neye yönelik olduğu) sezdirilsin.\n"
            "3. Aynı listede en az ÜÇ farklı kategori bulunsun (liste tek renk "
            "olmasın: hepsi 'riskli' olan bir liste gerçek bir seçim sunmaz), "
            "seçenekler o karakterin künyesine/eşyasına/bulunduğu yere özel "
            "olsun ve karakterleri farklı yönlere dağıtabilsin — ama sahnenin "
            "coğrafyası ve mevcut zorlukla bağı kopmasın.\n"
            "4. Seçenekler birbirinin tekrarı OLMASIN; her biri gerçekten farklı "
            "bir eylem/strateji sunsun ve mevcut sahnede FİİLEN uygulanabilir "
            "olsun. OYUNCULARIN SERBEST HAMLE YAZMA HAKKI YOKTUR: hikaye yalnız "
            "bu listelerle ilerler, bu yüzden liste sahnenin gerçek karar "
            "uzayını kapsasın ve içinde EN AZ BİR düşük riskli seçenek "
            "(bekle/geri çekil/hazırlık) bulunsun."
        )

    # -------------------------------------------------------------- havuz
    def stats(self) -> dict:
        return self.pool.stats()

    def clear(self) -> None:
        self.pool.clear()
