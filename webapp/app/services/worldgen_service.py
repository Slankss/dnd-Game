"""Dünya üretimi — her oyun farklı başlasın diye.

İki şey üretilir ve ikisi de öğrenme defterine NOT EDİLİR (bir sonraki oyun
aynılarını seçmesin):

  * **başlangıç noktası** — `scenario.START_LOCATIONS` havuzundan, daha önce
    kullanılmamışlar arasından. Sabit "eski metro istasyonu" yok.
  * **fraksiyonlar** — `FACTION_NAMES` (kısa, İngilizce, vurucu adlar) ve
    `FACTION_ARCHETYPES` (gizli yüz + söylenti + olası tavırlar) havuzları
    çaprazlanarak 4-6 tanesi. Aynı ad iki oyunda üst üste çıkmaz; arketip
    eşleşmesi de her oyunda değiştiği için "Rust" bir oyunda çete, başka bir
    oyunda telsizci ağı olabilir.

Rastgelelik `secrets` ile: dünya zarıyla aynı kaynak.
"""

import secrets

from app.models.learning import Learning

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
    def __init__(self, learning=None):
        # Geç bağlama: LearningService bu modülü import etmiyor, döngü yok.
        self._learning = learning

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
