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

import secrets

from app.models.items import depletion_factor
from app.models.text import norm_tr
from app.repositories.items_repo import ItemsRepository

#: Arama izi — bu kelimeler geçen hamle "arama" sayılır.
SEARCH_WORDS = (
    "ara ", "arar", "araştır", "yağmala", "yağma", "karıştır", "tara ",
    "dolapları", "çekmece", "raflar", "raflara", "kasayı", "depoyu",
    "içeriyi kontrol", "eşyaları topla", "erzak topla", "malzeme topla",
    "toplamaya", "bakınmaya", "kurcala", "üstünü ara", "cebini",
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

#: Yeme/içme izi — hamle bir yiyeceği tüketiyor mu.
EAT_WORDS = ("ye ", "yer ", "yemek ye", "yiyor", "atıştır", "kahvaltı",
             "karnını doyur", "iç ", "içer", "su iç", "yudumla", "kana kana")


def _icerir(text: str, kelimeler) -> bool:
    """Anahtar kelime taraması. Sondaki boşluklu kalıplar ("ara ") metnin
    sonunda da tutsun diye metne bir boşluk eklenir — `norm_tr` sonu kırpıyor."""
    metin = norm_tr(text or "")
    if not metin:
        return False
    metin += " "
    return any(norm_tr(k) + (" " if k.endswith(" ") else "") in metin
               for k in kelimeler)


def looks_like_searching(text: str) -> bool:
    return _icerir(text, SEARCH_WORDS)


def looks_like_eating(text: str) -> bool:
    return _icerir(text, EAT_WORDS)


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

    def search(self, world, player: str, band: str = "") -> dict:
        """Bir aramayı çözer: ne bulundu, envantere yazıldı mı.

        Dönen: {"player", "place", "archetype", "found": [{ad, adet, kategori}],
                "empty_reason"}. Kilit ÇAĞIRANDA.
        """
        yer = self.place_of(world, player)
        tur = self.archetype(world, yer)
        katalog = self.catalog
        havuz = katalog.candidates(tur)
        sonuc = {"player": player, "place": yer, "archetype": tur,
                 "label": katalog.place_label(tur), "found": [], "empty_reason": ""}
        if not havuz:
            sonuc["empty_reason"] = "burada aranacak bir şey kalmamış"
            return sonuc

        # Aynı yeri tekrar aramak verimi düşürür: burası bir kaynak madeni değil.
        arananlar = world.ensure_searched()
        kez = int(arananlar.get(yer) or 0)
        carpan = depletion_factor(kez)
        arananlar[yer] = kez + 1

        alt, ust = BAND_LOOT.get(str(band or ""), DEFAULT_LOOT)
        adet = self.rng.randint(alt, ust) if ust >= alt else 0
        # Tükenmişlik her kalem yuvasına ayrı ayrı uygulanır: çok aranan bir yer
        # gerçekten kurur, yalnızca "bir eksik" vermez.
        if adet and carpan < 1.0:
            adet = sum(1 for _ in range(adet) if self.rng.random() < carpan)
        if not adet:
            sonuc["empty_reason"] = (
                "bu sefer işe yarar bir şey çıkmadı" if kez == 0
                else f"burası daha önce {kez} kez arandı, geriye pek bir şey kalmamış")
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
            else:
                satirlar.append(
                    f"- {kayit['player']} · {yer} → BOŞ: {kayit['empty_reason']}.")
        satirlar.append(
            "- Bulunanlar envantere ZATEN yazıldı; state-update'te tekrar ekleme. "
            "Listede olmayan bir şey BULDURMA (özellikle silah/mühimmat): neyin "
            "nerede bulunacağını yerin türü belirler. Boş çıkan aramayı da "
            "sahnede anlat — aranan yer boşsa bunun kendisi bir bilgidir."
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
