"""Dünya üretimi — her oyun farklı başlasın diye.

İki şey üretilir ve ikisi de öğrenme defterine NOT EDİLİR (bir sonraki oyun
aynılarını seçmesin):

  * **başlangıç noktası** — `scenario.START_LOCATIONS` havuzundan, daha önce
    kullanılmamışlar arasından. Sabit "eski metro istasyonu" yok.
  * **harita** — oyun başında BÜTÜN dünya kurulur: şehirler, kategorili
    mekanlar, aralarındaki yollar ve mesafeler (bkz. `models/mapgen.py`).
    Büyüklüğü `settings.map_size` belirler. Üretilen yerler `bilinmiyor`
    düzeyinde başlar: dünya baştan tutarlıdır ama oyuncu keşfederek öğrenir.
  * **fraksiyonlar** — `FACTION_NAMES` (kısa, İngilizce, vurucu adlar) ve
    `FACTION_ARCHETYPES` (gizli yüz + söylenti + olası tavırlar) havuzları
    çaprazlanarak 4-6 tanesi. Aynı ad iki oyunda üst üste çıkmaz; arketip
    eşleşmesi de her oyunda değiştiği için "Rust" bir oyunda çete, başka bir
    oyunda telsizci ağı olabilir.

Rastgelelik `secrets` ile: dünya zarıyla aynı kaynak.
"""

import math
import secrets

from app.models.learning import Learning
from app.models.mapgen import MapGenerator
from app.models.worldmap import Road
from app.repositories.places_repo import PlacesRepository

# Bir oyunda üretilecek fraksiyon sayısı aralığı.
FACTION_MIN = 4
FACTION_MAX = 6


def _pools():
    """`scenario.py` bir içerik dosyasıdır — gecikmeli okunur."""
    from scenario import FACTION_ARCHETYPES, FACTION_NAMES, START_LOCATIONS
    return START_LOCATIONS, FACTION_NAMES, FACTION_ARCHETYPES


def _pick_fresh(pool: list, used, key=lambda x: x):
    """Havuzdan daha önce kullanılmamış bir öğe seçer. Hepsi kullanıldıysa
    havuz baştan açılır (oyun durmasın)."""
    fresh = [item for item in pool if not used(key(item))]
    return secrets.choice(fresh or pool)


class WorldGenService:
    def __init__(self, learning=None, places_repo=None):
        # Geç bağlama: LearningService bu modülü import etmiyor, döngü yok.
        self._learning = learning
        self.places_repo = places_repo or PlacesRepository()

    @property
    def learning(self):
        if self._learning is None:
            from app.services.learning_service import LearningService
            self._learning = LearningService()
        return self._learning

    # ------------------------------------------------------------- üretim
    def generate(self, store: Learning = None, seed_factions: dict = None) -> dict:
        """{start, factions} — dünyaya yazılmaya hazır.

        `seed_factions` yürürlükteki senaryonun kendi fraksiyonlarıdır (özel
        bir senaryo içe aktarılmışsa onunkiler): isim havuzuna katılırlar,
        böylece senaryonun kendi rengi kaybolmaz ama liste yine her oyunda
        değişir."""
        store = store or self.learning.load()
        starts, names, archetypes = _pools()

        start = _pick_fresh(starts, lambda v: store.used(store.used_starts, v),
                            key=lambda item: item.get("name", ""))
        factions = self._factions(store, names, archetypes, seed_factions or {})
        return {"start": start, "factions": factions}

    @staticmethod
    def _factions(store: Learning, names: list, archetypes: list,
                  seed: dict) -> dict:
        count = FACTION_MIN + secrets.randbelow(FACTION_MAX - FACTION_MIN + 1)
        havuz = list(names) + [n for n in seed if n not in names]
        secilen_adlar, secilen_arketipler = [], []
        factions = {}
        for _ in range(count):
            aday = [n for n in havuz if n not in secilen_adlar]
            if not aday:
                break
            ad = _pick_fresh(aday, lambda v: store.used(store.used_factions, v))
            secilen_adlar.append(ad)
            # Senaryonun kendi tanımladığı bir fraksiyon seçildiyse onun gizli
            # yüzü korunur; havuzdan gelen ada bir arketip eşlenir.
            tanim = seed.get(ad)
            if isinstance(tanim, dict) and tanim.get("notes"):
                factions[ad] = {
                    "disposition": tanim.get("disposition") or "temkinli",
                    "known": "bilinmiyor",
                    "notes": tanim.get("notes"),
                    "public_notes": tanim.get("public_notes") or "",
                }
                continue
            # Arketipler oyun içinde tekrarlanmasın; havuz biterse serbest.
            kalan = [a for a in archetypes if a["kod"] not in secilen_arketipler]
            arketip = secrets.choice(kalan or archetypes)
            secilen_arketipler.append(arketip["kod"])
            tavir = arketip["tavir"][secrets.randbelow(len(arketip["tavir"]))]
            factions[ad] = {
                "disposition": tavir,
                "known": "bilinmiyor",
                "notes": arketip["gizli"],
                "public_notes": arketip["public"],
            }
        return factions

    # ------------------------------------------------------------- uygulama
    # -------------------------------------------------------------- harita
    def build_map(self, world, size: str, start_name: str = "") -> dict:
        """Oyun başında BÜTÜN haritayı üretir ve dünyaya yazar.

        Üretilen her mekan `bilinmiyor` düzeyinde başlar: dünya baştan tutarlı
        ve ölçülüdür ama oyuncu haritanın tamamını görmez (bkz. `public_place`).
        Grubun sığınağı haritaya EKLENİR ve keşfedilmiş sayılır; sığınağın yol
        komşuları da `duyuldu` olur, böylece ilk turda gidilecek bir yer vardır.

        Dönen: üretim özeti (anlatıcı günlüğü ve prompt için).
        """
        icerik = self.places_repo.load()
        uretim = MapGenerator(icerik, secrets.SystemRandom()).generate(size)

        world_map = world.ensure_map()
        # Harita BAŞTAN kuruluyor: senaryonun varsayılan konumundan kalan
        # kayıtlar temizlenir. Yoksa koordinatsız, şehirsiz bir hayalet mekan
        # (eski "metro istasyonu") haritada asılı kalıyordu.
        world_map.places = {}
        world_map.roads = []
        world_map._set("size", uretim["size"])
        world_map._set("cities", uretim["cities"])
        world_map._touch("places")
        gun = world.day if isinstance(world.day, int) else None
        for ad, bilgi in uretim["places"].items():
            place = world_map.ensure_place(ad, gun)
            place.merge_patch(bilgi)
            place.hide()
        world_map._touch("roads")
        world_map.roads = [Road.from_dict(r) for r in uretim["roads"]]

        # Sığınak haritanın parçası olsun: en yakın mekana bir kır yoluyla
        # bağlanır, yoksa grup adada başlardı.
        if start_name:
            self._siginagi_bagla(world_map, start_name, uretim)
            world_map._set("current", start_name)
            # Sığınağın yol komşuları DUYULMUŞ olur: ilk turda gidilecek bir
            # yer bulunsun, harita boş bir nokta olarak başlamasın.
            world_map.reveal_neighbours(start_name)
            for ad in list(world_map.party):
                world_map.party[ad] = start_name

        return {
            "size": uretim["size"],
            "cities": uretim["cities"],
            "places": len(uretim["places"]),
            "roads": len(uretim["roads"]),
        }

    @staticmethod
    def _siginagi_bagla(world_map, start_name: str, uretim: dict) -> None:
        """Grubun sığınağını üretilen haritaya yerleştirir ve bağlar."""
        sehirler = uretim.get("cities") or {}
        mekanlar = uretim.get("places") or {}
        if not mekanlar:
            return
        # Sığınak bir şehrin kenarına konur: içeride değil, ulaşılabilir uzakta.
        sehir = secrets.choice(list(sehirler)) if sehirler else ""
        merkez = sehirler.get(sehir) or {"x": 0.0, "y": 0.0}
        aci = secrets.SystemRandom().uniform(0, 6.28318)
        uzaklik = secrets.SystemRandom().uniform(2.2, 3.6)
        x = round(merkez["x"] + math.cos(aci) * uzaklik, 2)
        y = round(merkez["y"] + math.sin(aci) * uzaklik, 2)

        place = world_map.ensure_place(start_name)
        place.merge_patch({"city": f"{sehir} kırsalı" if sehir else "",
                           "category": "siginak", "x": x, "y": y})
        place.raise_knowledge("keşfedildi")

        # En yakın üç mekana yol: biri anayol, diğerleri kır yolu/patika.
        uzakliklar = sorted(
            ((math.hypot(x - m["x"], y - m["y"]), ad) for ad, m in mekanlar.items()),
            key=lambda p: p[0])[:3]
        for i, (d, ad) in enumerate(uzakliklar):
            kind = "kır yolu" if i else "anayol"
            sapma = 1.3 if i else 1.15
            world_map.add_road(start_name, ad, kind, round(d * sapma, 2),
                               status="açık", risk=2 if i else 3)

    @staticmethod
    def map_note(world, ozet: dict) -> str:
        """Açılış mesajına giren harita künyesi (anlatıcı için)."""
        sehirler = ozet.get("cities") or {}
        satirlar = [
            f"BU OYUNUN HARİTASI (sunucu üretti, {ozet.get('size')} boyut — "
            f"{ozet.get('places')} mekan, {ozet.get('roads')} yol):",
        ]
        for ad, bilgi in sehirler.items():
            uyeler = [a for a, p in (world.map.places or {}).items()
                      if p.city == ad]
            satirlar.append(
                f"- {ad} ({bilgi.get('tur')}): {len(uyeler)} mekan. "
                f"{bilgi.get('not') or ''}".strip())
        satirlar.append(
            "Harita SABİTTİR ve bütünüyle hazırdır: yeni yer UYDURMA, mevcut "
            "yerlerin adını değiştirme. Grup nereye giderse orası açılır; "
            "mesafeleri ve yolları sunucu hesaplar ve sana her turda bildirir."
        )
        return "\n".join(satirlar)

    def apply(self, world, generated: dict) -> dict:
        """Üretilen dünyayı `WorldState` üzerine yazar ve defterine not eder."""
        start = generated.get("start") or {}
        factions = generated.get("factions") or {}

        name = start.get("name")
        if name:
            world._set("location", name)
            world.ensure_map().go(name, world.day if isinstance(world.day, int) else None)
            place = world.ensure_map().ensure_place(name)
            place.merge_patch({
                "kind": start.get("kind") or "sığınak",
                "status": "grubun sığınağı",
                "danger": "temkinli",
                "notes": start.get("summary") or "",
            })
            # Kurulumda kadro sabitlendiyse herkes başlangıç noktasındadır.
            # Karakterlerin `location` alanı kurulum sırasında (başlangıç
            # üretilmeden önce) senaryonun eski konumuyla dolmuş olabilir —
            # burada yeni sığınakla eşitlenir, yoksa harita ilk turdan itibaren
            # olmayan bir yeri gösterir.
            for karakter, kisi in (world.characters or {}).items():
                kisi._set("location", name)
                world.ensure_map().place_person(karakter, name)

        if factions:
            # Üretilen liste senaryodaki başlangıç listesinin YERİNE geçer —
            # yoksa her oyun bir öncekinin fraksiyonlarını da taşıyıp
            # kalabalıklaşırdı.
            world._touch("factions")
            from app.models.factions import Faction
            world.factions = {}
            for ad, fields in factions.items():
                faction = Faction.new()
                faction.merge_patch(fields)
                world.factions[ad] = faction

        self.learning.record_game(name, list(factions.keys()))
        return {"start": start, "factions": factions}

    # -------------------------------------------------------------- prompt
    @staticmethod
    def start_note(start: dict, factions: dict) -> str:
        """OYUN BAŞLANGICI mesajına giren blok — anlatıcı bu oyunun mekânını
        ve fraksiyonlarını buradan öğrenir."""
        satirlar = []
        if start:
            satirlar += [
                "BAŞLANGIÇ NOKTASI (bu oyuna özel, sunucu seçti — başka bir "
                "sığınak UYDURMA):",
                f"- Yer: {start.get('name')}",
                f"- Tür: {start.get('kind')}",
                f"- Tarif: {start.get('summary')}",
                f"- YAPISAL ZAAF (ilk zorluğu tercihen buradan türet): {start.get('edge')}",
            ]
        if factions:
            satirlar.append("")
            satirlar.append(
                "BU OYUNUN FRAKSİYONLARI (tam liste — başka fraksiyon adı "
                "kullanma; `notes` gizli gerçektir, oyunculara açıklanmaz):"
            )
            for ad, bilgi in factions.items():
                satirlar.append(
                    f"- {ad} — söylenti: {bilgi.get('public_notes')} | "
                    f"GERÇEK: {bilgi.get('notes')} | gerçek tavrı: {bilgi.get('disposition')}"
                )
        return "\n".join(satirlar)
