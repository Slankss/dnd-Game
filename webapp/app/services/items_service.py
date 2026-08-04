"""Eşya motoru — arama (loot) ve tüketim.

İki soruyu SUNUCU cevaplar, anlatıcı değil:

  **Ne bulundu?** Oyuncu bir yeri aradığında bulunanları katalog belirler
  (`data/items.json`). Bir yerin ne barındırdığı o yerin TÜRÜNE bağlıdır:
  9mm tabancanın karakolda ağırlığı 55, metro istasyonunda 2'dir. Anlatıcı
  "karakolda tabanca yok" ya da "metroda üç tüfek buldunuz" diyemez.

  **Ne kadar doydu?** Bir yiyecek yendiğinde açlığı katalogdaki `doyum`
  değeri kadar düşer. "Karnınız doydu" cümlesi göstergeyi değiştirmez;
  gösterge sunucudadır.

Hikaye eşyaları bu motorun DIŞINDADIR: anlatıcı onları üretir, katalogda
yokturlar ve hiçbir mekanik etkileri olmaz (bkz. `world_patch._merge_story_items`).

Kilit ÇAĞIRANDA (round_service).
"""

import re
import secrets

from app.errors import ValidationError
from app.models.items import RARITY_FACTOR
from app.models.text import norm_tr
from app.repositories.items_repo import ItemsRepository

#: Arama izi — yeterince ayırt edici, ALT DİZE olarak aranan kalıplar.
SEARCH_PHRASES = (
    "araştır", "yağmala", "yağma", "karıştır", "dolapları", "dolaplara",
    "çekmece", "raflar", "raflara", "kasayı", "depoyu", "içeriyi kontrol",
    "eşyaları topla", "erzak topla", "malzeme topla", "kurcala", "cebini",
    "üstünü ara", "baştan aşağı", "didik didik",
)

#: Arama fiilleri — TAM KELİME olarak aranır. Alt dize aramak "kararlı"
#: içinde "arar" bulup hamleyi arama sanıyordu; kısa fiillerde çekimli
#: biçimleri tek tek saymak, kelime sınırını tahmin etmekten güvenli.
SEARCH_VERBS = (
    "ara", "arayalım", "arasın", "aradı", "arıyor", "arayıp", "aramak",
    "tara", "tarar", "tarasın", "taradı", "tarayalım", "taramak", "tarayıp",
    "tarıyor", "bakın", "bakınmaya", "toplamaya",
)

#: Zar bandı → (en az, en çok) bulunan kalem sayısı.
BAND_LOOT = {
    "Felaket": (0, 0),
    "Başarısız": (0, 1),
    "Kısmi Başarı": (1, 1),
    "Başarı": (1, 2),
    "Güçlü Başarı": (2, 3),
    "Kritik": (2, 4),
}
DEFAULT_LOOT = (1, 2)

#: Yeme/içme izi — kalıplar ve tam kelime fiilleri.
EAT_PHRASES = ("yemek ye", "atıştır", "kahvaltı", "karnını doyur", "su iç",
               "yudumla", "kana kana", "konserveyi aç")
EAT_VERBS = ("ye", "yer", "yiyor", "yiyelim", "yemek", "iç", "içer", "içiyor",
             "içelim", "içmek")


def icerir(text: str, phrases=(), verbs=()) -> bool:
    """Anahtar kelime taraması.

    `phrases` ALT DİZE olarak aranır (yeterince uzun ve ayırt edici olmalı),
    `verbs` TAM KELİME olarak. İkisini ayırmanın sebebi somut bir hata: "arar"
    alt dize olarak "kararlı" içinde geçiyor ve kararlılıkla kapı tutan
    karakter "arama yapmış" sayılıyordu.
    """
    metin = norm_tr(text or "")
    if not metin:
        return False
    if any(norm_tr(k) in metin for k in phrases):
        return True
    kelimeler = {k.strip(".,;:!?()[]" + chr(34) + chr(39)) for k in metin.split()}
    return any(norm_tr(k) in kelimeler for k in verbs)


def looks_like_searching(text: str) -> bool:
    return icerir(text, SEARCH_PHRASES, SEARCH_VERBS)


def looks_like_eating(text: str) -> bool:
    return icerir(text, EAT_PHRASES, EAT_VERBS)


class ItemsService:
    """Arama zarı, tüketim etkileri ve anlatıcıya giden bloklar."""

    def __init__(self, items_repo=None, rng=None):
        self.repo = items_repo or ItemsRepository()
        # Zar gibi arama da kriptografik RNG kullanır — tahmin edilemesin.
        self.rng = rng or secrets.SystemRandom()

    @property
    def catalog(self):
        return self.repo.load()

    # -------------------------------------------------------------- arama
    def place_of(self, world, player: str = "") -> str:
        """Karakterin bulunduğu yer (dağıldılarsa kendi konumu)."""
        person = (world.characters or {}).get(player) if player else None
        yer = getattr(person, "location", None)
        if isinstance(yer, str) and yer.strip():
            return yer.strip()
        return world.location or ""

    def archetype(self, world, place: str) -> str:
        """Yerin katalog türü — haritadaki `kind` varsa o da hesaba katılır."""
        kind = ""
        world_map = world.map
        if world_map is not None and place:
            kayit = (world_map.places or {}).get(place)
            kind = getattr(kayit, "kind", "") or ""
        return self.catalog.archetype_of(place, kind)

    @staticmethod
    def searched_places(world) -> dict:
        return world.searched if isinstance(world.searched, dict) else {}

    def already_searched(self, world, place: str) -> bool:
        """Bu mekan TARANDI mı? Bir yer yalnızca BİR KEZ taranabilir."""
        if not place:
            return False
        return bool(self.searched_places(world).get(place))

    def mark_searched(self, world, place: str, bulunan: int = 0) -> None:
        """Mekanı 'tarandı' diye işaretler — bir daha taranamaz."""
        if not place:
            return
        world.ensure_searched()[place] = {"found": int(bulunan or 0)}

    def search(self, world, player: str, band: str = "") -> dict:
        """Bir aramayı çözer: ne bulundu, envantere yazıldı mı.

        BİR MEKAN BİR KEZ TARANIR. İkinci kez denenirse hiçbir şey çıkmaz ve
        sonuç `already: True` döner — seçenek havuzu zaten böyle bir seçenek
        sunmuyor, bu sunucu tarafındaki son kapı.

        Dönen: {"player", "place", "archetype", "found": [...], "empty_reason",
                "already"}. Kilit ÇAĞIRANDA.
        """
        yer = self.place_of(world, player)
        tur = self.archetype(world, yer)
        katalog = self.catalog
        havuz = katalog.candidates(tur)
        sonuc = {"player": player, "place": yer, "archetype": tur,
                 "label": katalog.place_label(tur), "found": [],
                 "empty_reason": "", "already": False}

        if self.already_searched(world, yer):
            sonuc["already"] = True
            sonuc["empty_reason"] = "burası daha önce tarandı, alınacak bir şey kalmadı"
            return sonuc
        if not havuz:
            self.mark_searched(world, yer, 0)
            sonuc["empty_reason"] = "burada aranacak bir şey yok"
            return sonuc

        alt, ust = BAND_LOOT.get(str(band or ""), DEFAULT_LOOT)
        adet = self.rng.randint(alt, ust) if ust >= alt else 0
        # Tarama tek seferlik: sonuç ne olursa olsun mekan işaretlenir.
        # Kötü zar "burayı bir daha ararız" demek değildir; fırsat harcandı.
        self.mark_searched(world, yer, adet)
        if not adet:
            sonuc["empty_reason"] = "aceleyle bakıldı, işe yarar bir şey çıkmadı"
            return sonuc

        person = (world.characters or {}).get(player)
        secilenler = self._draw(havuz, adet)
        for item in secilenler:
            kac = 1
            if item.sayilabilir:
                kac = self.rng.randint(item.adet[0], max(item.adet[0], item.adet[1]))
            if person is not None:
                if item.sayilabilir:
                    person.merge_inventory({"inventory_counts": {item.ad: f"+{kac}"}})
                else:
                    person.merge_inventory({"inventory_add": [item.ad]})
            sonuc["found"].append({"ad": item.ad, "adet": kac if item.sayilabilir else 1,
                                   "kategori": item.kategori,
                                   "sayilabilir": item.sayilabilir,
                                   "not": item.aciklama})
        return sonuc

    def _draw(self, havuz: list, adet: int) -> list:
        """Ağırlıklı, TEKRARSIZ çekiliş."""
        kalan = list(havuz)
        secilen = []
        for _ in range(min(adet, len(kalan))):
            toplam = sum(a for _, a in kalan)
            if toplam <= 0:
                break
            esik = self.rng.random() * toplam
            birikim = 0.0
            for i, (item, agirlik) in enumerate(kalan):
                birikim += agirlik
                if birikim >= esik:
                    secilen.append(item)
                    kalan.pop(i)
                    break
        return secilen

    # ------------------------------------------------------------ tüketim
    def consume(self, world, player: str, spent: dict) -> list:
        """Harcanan kalemlerin katalog etkilerini uygular (açlık/susuzluk).

        `spent`: InventoryService'in GERÇEKTEN kestiği {ad: adet}. Dönen liste
        prompt bloğu içindir: [{"ad", "adet", "aclik", "susuzluk"}].
        """
        person = (world.characters or {}).get(player)
        if person is None or not spent:
            return []
        etkiler = []
        for ad, adet in spent.items():
            item = self.catalog.find(ad)
            if item is None or not (item.yiyecek_mi or item.icecek_mi):
                continue  # hikaye eşyası ya da etkisiz kalem
            aclik = item.doyum * int(adet or 0)
            susuzluk = item.susuzluk * int(adet or 0)
            if not (aclik or susuzluk):
                continue
            self._relieve(person, aclik, susuzluk)
            etkiler.append({"ad": item.ad, "adet": adet,
                            "aclik": aclik, "susuzluk": susuzluk})
        return etkiler

    def auto_consume(self, world, player: str) -> list:
        """Beyansız yeme/içme — güvenlik ağı.

        Hamle "ye/iç" diyorsa ama seçenekte `spend` yoksa, envanterdeki EN
        DOYURUCU katalog kalemi bir adet tüketilir. Böylece "karnını doyurdu"
        cümlesi ile açlık göstergesi arasındaki uçurum kapanır — mermi
        sorununun aynısı. Uygun kalem yoksa hiçbir şey olmaz."""
        person = (world.characters or {}).get(player)
        if person is None:
            return []
        en_iyi, en_iyi_deger = None, 0
        for ad in list(person.inventory or []):
            item = self.catalog.find(ad)
            if item is None or not (item.yiyecek_mi or item.icecek_mi):
                continue
            deger = max(item.doyum, item.susuzluk)
            if deger > en_iyi_deger:
                en_iyi, en_iyi_deger = item, deger
        if en_iyi is None:
            return []
        # Sayılabilir kalemse envanterden bir adet düşülür; değilse tüketilip
        # elden çıkar (tek kullanımlık kabul edilir).
        if en_iyi.sayilabilir:
            if not person.spend_item(en_iyi.ad, 1):
                return []
        else:
            person.merge_inventory({"inventory_remove": [en_iyi.ad]})
        self._relieve(person, en_iyi.doyum, en_iyi.susuzluk)
        return [{"ad": en_iyi.ad, "adet": 1, "aclik": en_iyi.doyum,
                 "susuzluk": en_iyi.susuzluk, "auto": True}]

    @staticmethod
    def _relieve(person, aclik: int, susuzluk: int) -> None:
        """Göstergeleri düşürür (0 = gayet iyi, 100 = dayanılmaz)."""
        vitals = person.ensure_vitals()
        yama = {}
        if aclik:
            yama["hunger"] = max(0, int(vitals.hunger or 0) - int(aclik))
        if susuzluk:
            yama["thirst"] = max(0, int(vitals.thirst or 0) - int(susuzluk))
        if yama:
            vitals.merge_patch(yama)

    # ------------------------------------------------------- katalog yazma
    def add_item(self, ham: dict) -> dict:
        """Anlatıcı ekranından yeni bir eşya ekler — KALICI, tüm oyunlar için.

        Eklenen eşya `data/items.json`'a yazılır; oyunun içeriğine girer, tek
        bir oyunun durumuna değil. Yeni oyun kurulsa, state sıfırlansa bile
        durur.

        Doğrulama burada: katalog elle düzenlenebilen bir içerik dosyası ama
        arayüzden gelen kayıt bozuk olamaz — bozuk bir kayıt her oyunda her
        aramayı etkilerdi.
        """
        ham = ham if isinstance(ham, dict) else {}
        katalog = self.catalog

        ad = str(ham.get("ad") or "").strip()
        if not ad:
            raise ValidationError("Eşyanın adı gerekli.")
        if len(ad) > 60:
            raise ValidationError("Eşya adı en fazla 60 karakter olabilir.")
        if any(norm_tr(i.ad) == norm_tr(ad) for i in katalog.items):
            raise ValidationError(f"'{ad}' katalogda zaten var.")

        kategori = str(ham.get("kategori") or "").strip()
        if kategori not in katalog.kategoriler:
            gecerli = ", ".join(katalog.kategoriler)
            raise ValidationError(f"Kategori şunlardan biri olmalı: {gecerli}")

        nadirlik = str(ham.get("nadirlik") or "yaygın").strip()
        if nadirlik not in RARITY_FACTOR:
            raise ValidationError("Nadirlik: yaygın, nadir ya da çok nadir.")

        bulunur = {}
        for yer, agirlik in (ham.get("bulunur") or {}).items():
            if yer not in katalog.yer_turleri:
                raise ValidationError(f"Tanınmayan yer türü: {yer}")
            sayi = self._sayi(agirlik, 0, 100, f"{yer} ağırlığı")
            if sayi:
                bulunur[yer] = sayi
        taban = self._sayi(ham.get("taban"), 0, 100, "taban ağırlık")
        if not bulunur and not taban:
            raise ValidationError(
                "Eşya hiçbir yerde bulunamaz — en az bir yer türüne ağırlık "
                "ver ya da taban ağırlığı gir.")

        kayit = {
            "id": self._yeni_id(katalog, ad),
            "ad": ad,
            "kategori": kategori,
            "nadirlik": nadirlik,
            "taban": taban,
            "bulunur": dict(sorted(bulunur.items())),
        }
        mermi = str(ham.get("mermi") or "").strip()
        if mermi:
            kayit["mermi"] = mermi
        if ham.get("sayilabilir"):
            kayit["sayilabilir"] = True
            alt = self._sayi(ham.get("adet_min"), 1, 999, "en az adet") or 1
            ust = self._sayi(ham.get("adet_max"), 1, 999, "en çok adet") or alt
            kayit["adet"] = [alt, max(alt, ust)]
        doyum = self._sayi(ham.get("doyum"), 0, 100, "doyum")
        if doyum:
            kayit["doyum"] = doyum
        susuzluk = self._sayi(ham.get("susuzluk"), 0, 100, "susuzluk")
        if susuzluk:
            kayit["susuzluk"] = susuzluk
        aciklama = str(ham.get("not") or "").strip()
        if aciklama:
            kayit["not"] = aciklama[:240]

        self.repo.append_item(kayit)
        return kayit

    @staticmethod
    def _sayi(value, alt: int, ust: int, alan: str) -> int:
        if value in (None, ""):
            return 0
        try:
            sayi = int(float(str(value).replace(",", ".")))
        except (TypeError, ValueError):
            raise ValidationError(f"{alan} sayı olmalı.") from None
        if not (alt <= sayi <= ust):
            raise ValidationError(f"{alan} {alt}-{ust} arasında olmalı.")
        return sayi

    @staticmethod
    def _yeni_id(katalog, ad: str) -> str:
        """Addan türeyen, katalogda tekrar etmeyen kimlik."""
        temel = re.sub(r"[^a-z0-9]+", "-", norm_tr(ad)).strip("-") or "esya"
        mevcut = {i.id for i in katalog.items}
        if temel not in mevcut:
            return temel
        i = 2
        while f"{temel}-{i}" in mevcut:
            i += 1
        return f"{temel}-{i}"

    # --------------------------------------------------------------- katalog
    def public_catalog(self) -> dict:
        """`GET /api/items` — katalog, arayüzün okuyacağı biçimde.

        Her eşyanın en olası üç yeri de hesaplanır: oyuncu "bunu nerede
        bulurum" sorusunu tabloya bakarak cevaplayabilsin."""
        katalog = self.catalog
        esyalar = []
        for item in katalog.items:
            en_iyi = sorted(
                ((tur, item.weight_at(tur)) for tur in katalog.yer_turleri),
                key=lambda p: -p[1])[:3]
            kayit = item.to_dict()
            kayit["nerede"] = [
                {"tur": tur, "ad": katalog.place_label(tur), "agirlik": round(a, 1)}
                for tur, a in en_iyi if a > 0
            ]
            esyalar.append(kayit)
        return {
            "surum": katalog.surum,
            "kategoriler": katalog.kategoriler,
            "yer_turleri": {tur: (bilgi or {}).get("ad") or tur
                            for tur, bilgi in katalog.yer_turleri.items()},
            "esyalar": esyalar,
        }

    # -------------------------------------------------------------- prompt
    @staticmethod
    def search_note(sonuclar) -> str:
        """Anlatıcıya giden ZORUNLU arama bloğu."""
        if not sonuclar:
            return ""
        satirlar = [
            "ARAMA SONUCU (sunucu belirledi — bu blok ZORUNLUDUR, sahnede FİİLEN göster):",
        ]
        for kayit in sonuclar:
            yer = f"{kayit['place']} ({kayit['label']})" if kayit["label"] else kayit["place"]
            if kayit["found"]:
                bulunan = ", ".join(
                    f"{b['adet']}× {b['ad']}" if b["sayilabilir"] else b["ad"]
                    for b in kayit["found"])
                satirlar.append(f"- {kayit['player']} · {yer} → BULDU: {bulunan}")
                for b in kayit["found"]:
                    if b["not"]:
                        satirlar.append(f"  · {b['ad']}: {b['not']}")
            elif kayit.get("already"):
                satirlar.append(
                    f"- {kayit['player']} · {yer} → ZATEN TARANMIŞ: "
                    f"{kayit['empty_reason']}. Karakter boşuna vakit kaybetti; "
                    "sahnede bunu göster (tanıdık boş raflar, kendi bıraktıkları iz).")
            else:
                satirlar.append(
                    f"- {kayit['player']} · {yer} → BOŞ: {kayit['empty_reason']}.")
        satirlar.append(
            "- Bulunanlar envantere ZATEN yazıldı; state-update'te tekrar ekleme. "
            "Listede olmayan bir şey BULDURMA (özellikle silah/mühimmat): neyin "
            "nerede bulunacağını yerin türü belirler. Boş çıkan aramayı da "
            "sahnede anlat — aranan yer boşsa bunun kendisi bir bilgidir.\n"
            "- BİR MEKAN BİR KEZ TARANIR. Taranmış bir yer için bir daha arama "
            "seçeneği YAZMA; o yerde bulunacak şey bitmiştir."
        )
        return "\n".join(satirlar)

    @staticmethod
    def consume_note(etkiler_by_player) -> str:
        """Yeme/içme sonrası gösterge değişimi."""
        if not etkiler_by_player:
            return ""
        satirlar = ["TÜKETİM (sunucu uyguladı):"]
        for oyuncu, etkiler in etkiler_by_player.items():
            for e in etkiler:
                parcalar = []
                if e["aclik"]:
                    parcalar.append(f"açlık −{e['aclik']}")
                if e["susuzluk"]:
                    parcalar.append(f"susuzluk −{e['susuzluk']}")
                satirlar.append(
                    f"- {oyuncu}: {e['adet']}× {e['ad']} tüketti · " + ", ".join(parcalar))
        satirlar.append(
            "- Göstergeleri state-update'te ayrıca düşürme; sunucu uyguladı.")
        return "\n".join(satirlar)

    def story_note(self, world, limit: int = 12) -> str:
        """Hikaye eşyaları defteri — sürekliliği anlatıcı unutmasın."""
        defter = world.story_items if isinstance(world.story_items, dict) else {}
        if not defter:
            return ""
        satirlar = []
        for ad, bilgi in list(defter.items())[:limit]:
            bilgi = bilgi if isinstance(bilgi, dict) else {}
            parca = [ad]
            if bilgi.get("sahip"):
                parca.append(f"kimde: {bilgi['sahip']}")
            if bilgi.get("nerede"):
                parca.append(f"nerede: {bilgi['nerede']}")
            if bilgi.get("not"):
                parca.append(str(bilgi["not"])[:120])
            satirlar.append("- " + " · ".join(parca))
        return (
            "HİKAYE EŞYALARI (bu oyuna özel; MEKANİĞİ YOKTUR — açlık doldurmaz, "
            "zar değiştirmez, mermi olmaz. Yalnızca anlamı vardır, sürekliliğini "
            "koru):\n" + "\n".join(satirlar)
        )

    def catalog_note(self, world, players) -> str:
        """Seçenek üretimi için: buradaki yer türü ve neyin bulunabileceği."""
        katalog = self.catalog
        yerler = {}
        for ad in players or []:
            yer = self.place_of(world, ad)
            if yer:
                yerler.setdefault(yer, []).append(ad)
        if not yerler:
            return ""
        satirlar = []
        for yer, kimler in yerler.items():
            tur = self.archetype(world, yer)
            etiket = katalog.place_label(tur) if tur else "tanımsız (genel yağma)"
            ornekler = sorted(katalog.candidates(tur), key=lambda p: -p[1])[:6]
            ornek_metin = ", ".join(i.ad for i, _ in ornekler) or "kayda değer bir şey yok"
            satirlar.append(
                f"- {', '.join(kimler)} · {yer} → yer türü: {etiket}. "
                f"Buradan çıkması muhtemel: {ornek_metin}")
        return (
            "ARAMA İMKANI (sabit eşya kataloğu): bir yerde ne bulunacağını YER "
            "TÜRÜ belirler, sunucu çeker. Arama seçeneği yazabilirsin ('rafları "
            "karıştır', 'depoyu ara'); ne çıkacağını YAZMA, sunucu söyler.\n"
            + "\n".join(satirlar)
        )
