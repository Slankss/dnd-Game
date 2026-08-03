"""Öğrenme defteri — oyunun kendi oynanışından çıkardığı kalıcı bilgi.

Bu, oyunun "her interaction'da gelişen yetenek" tarafının VERİ katmanıdır.
Her turda şunlar biriktirilir:

  * hangi kategoriden seçenek seçildi, zarı ne geldi, sonucu ne oldu,
  * havuzdan mı seçildi yoksa oyuncu kendi hamlesini mi yazdı,
  * tur ne kadar sürdü, süre doldu mu,
  * o turda ölüm/yara/çözülen zorluk oldu mu,
  * hangi başlangıç noktası ve hangi fraksiyonlar kullanıldı (tekrar etmesin).

Bu ham sayılardan `dersler` üretilir: her turda anlatıcının promptuna giren,
insan okuyabilir kısa kurallar. Ders üretimi KOD tarafından yapılır (ek model
çağrısı yok, bu yüzden bedava ve her turda çalışır); anlatıcı da kendi
gözlemini `state-update` içindeki `learning.lessons_add` alanıyla ekleyebilir.

Defter ayrıca `.claude/skills/kizil-cokus-anlatici/ogrenilenler.md` dosyasına
yazılır — böylece öğrenilenler bu web uygulamasının dışında, Claude Code
oturumlarında da yüklenen gerçek bir yeteneğe dönüşür.
"""

import time
from dataclasses import dataclass, field

from .options import CATEGORIES
from .text import norm_tr

VERSION = 1

# Prompt'a giren ders sayısı ve defterde tutulan üst sınır.
LESSONS_IN_PROMPT = 8
LESSONS_MAX = 60

# Bir kategoriden ders çıkarmak için gereken en az seçim sayısı — üç turluk
# veriden "bu masa riskli oynuyor" sonucu çıkarmak gürültüdür.
MIN_SAMPLE = 8


def _bos_kategori() -> dict:
    return {"secim": 0, "zar_toplam": 0, "felaket": 0, "kritik": 0,
            "basari": 0, "basarisiz": 0}


@dataclass
class Learning:
    """`data/learning.json`."""

    version: int = VERSION
    updated: str = ""
    games: int = 0
    turns: int = 0
    picks: int = 0
    categories: dict = field(default_factory=dict)
    bands: dict = field(default_factory=dict)
    pace: dict = field(default_factory=dict)
    players: dict = field(default_factory=dict)
    events: dict = field(default_factory=dict)
    used_starts: list = field(default_factory=list)
    used_factions: list = field(default_factory=list)
    lessons: list = field(default_factory=list)

    # ------------------------------------------------------------ dönüşüm
    @classmethod
    def from_dict(cls, data) -> "Learning":
        data = data if isinstance(data, dict) else {}
        store = cls()
        store.version = int(data.get("version") or VERSION)
        store.updated = str(data.get("updated") or "")
        store.games = int(data.get("games") or 0)
        store.turns = int(data.get("turns") or 0)
        store.picks = int(data.get("picks") or 0)
        for name, target in (("categories", "categories"), ("bands", "bands"),
                             ("pace", "pace"), ("players", "players"),
                             ("events", "events")):
            raw = data.get(name)
            if isinstance(raw, dict):
                setattr(store, target, raw)
        for name in ("used_starts", "used_factions"):
            raw = data.get(name)
            if isinstance(raw, list):
                setattr(store, name, [str(x) for x in raw if isinstance(x, str)])
        raw = data.get("lessons")
        if isinstance(raw, list):
            store.lessons = [x for x in raw if isinstance(x, dict) and x.get("text")]
        return store

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "updated": self.updated,
            "games": self.games,
            "turns": self.turns,
            "picks": self.picks,
            "categories": self.categories,
            "bands": self.bands,
            "pace": self.pace,
            "players": self.players,
            "events": self.events,
            "used_starts": self.used_starts,
            "used_factions": self.used_factions,
            "lessons": self.lessons,
        }

    # ------------------------------------------------------------- yazma
    def touch(self) -> None:
        self.updated = time.strftime("%Y-%m-%d %H:%M:%S")

    def record_pick(self, pick: dict) -> None:
        """Bir oyuncunun bu turdaki seçimi (zarı atılmış halde)."""
        category = pick.get("category") or "serbest"
        stats = self.categories.setdefault(category, _bos_kategori())
        for key, value in _bos_kategori().items():   # eski kayıtları tamamla
            stats.setdefault(key, value)
        stats["secim"] += 1
        self.picks += 1

        roll, band = pick.get("roll"), pick.get("band")
        if isinstance(roll, int):
            stats["zar_toplam"] += roll
        if isinstance(band, str):
            self.bands[band] = int(self.bands.get(band) or 0) + 1
            if band == "Felaket":
                stats["felaket"] += 1
            elif band == "Kritik":
                stats["kritik"] += 1
            elif band in ("Başarı", "Güçlü Başarı"):
                stats["basari"] += 1
            elif band == "Başarısız":
                stats["basarisiz"] += 1

        self.pace["havuzdan"] = int(self.pace.get("havuzdan") or 0) + (0 if pick.get("custom") else 1)
        self.pace["serbest"] = int(self.pace.get("serbest") or 0) + (1 if pick.get("custom") else 0)
        if pick.get("timeout"):
            self.pace["zaman_asimi"] = int(self.pace.get("zaman_asimi") or 0) + 1
        if pick.get("uzun"):
            self.pace["uzun_secim"] = int(self.pace.get("uzun_secim") or 0) + 1
        else:
            self.pace["kisa_secim"] = int(self.pace.get("kisa_secim") or 0) + 1

        player = pick.get("player")
        if isinstance(player, str) and player:
            profile = self.players.setdefault(player, {"secim": 0, "kategoriler": {}})
            profile["secim"] = int(profile.get("secim") or 0) + 1
            cats = profile.setdefault("kategoriler", {})
            cats[category] = int(cats.get(category) or 0) + 1

    def record_turn(self, saniye=None, events=None) -> None:
        self.turns += 1
        if isinstance(saniye, (int, float)) and saniye > 0:
            toplam = float(self.pace.get("sure_toplam") or 0.0) + float(saniye)
            sayi = int(self.pace.get("sure_adet") or 0) + 1
            self.pace["sure_toplam"] = round(toplam, 1)
            self.pace["sure_adet"] = sayi
            self.pace["ortalama_saniye"] = round(toplam / sayi, 1)
        for name, count in (events or {}).items():
            if isinstance(count, int) and count:
                self.events[name] = int(self.events.get(name) or 0) + count

    def record_game(self, start: str = None, factions=None) -> None:
        """Yeni oyun açıldı: kullanılan başlangıç ve fraksiyonlar not edilir —
        bir sonraki oyun aynılarını üretmesin."""
        self.games += 1
        if isinstance(start, str) and start.strip():
            self.remember(self.used_starts, start.strip(), limit=40)
        for name in factions or []:
            if isinstance(name, str) and name.strip():
                self.remember(self.used_factions, name.strip(), limit=120)

    @staticmethod
    def remember(target: list, value: str, limit: int) -> None:
        keys = {norm_tr(x) for x in target}
        if norm_tr(value) in keys:
            return
        target.append(value)
        del target[:-limit]

    def used(self, target: list, value: str) -> bool:
        return norm_tr(value) in {norm_tr(x) for x in target}

    # ------------------------------------------------------------ dersler
    def add_lesson(self, text: str, source: str = "otomatik", key: str = None,
                   day=None, in_prompt: bool = True) -> bool:
        """Ders ekler/tazeler. Aynı `key`'li ders varsa metni güncellenir ve
        ağırlığı artar — defter aynı gözlemi 40 kez tekrarlamasın.

        `in_prompt=False` olan kayıtlar deftere ve yeteneğe yazılır ama
        anlatıcının promptuna GİRMEZ: "şu başlangıç kullanıldı" gibi muhasebe
        notları sahne yazımına yardım etmez, sadece yer kaplar."""
        text = (text or "").strip()
        if not text:
            return False
        key = key or norm_tr(text)[:60]
        for lesson in self.lessons:
            if lesson.get("key") == key:
                lesson["text"] = text
                lesson["weight"] = int(lesson.get("weight") or 1) + 1
                lesson["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
                lesson["day"] = day if day is not None else lesson.get("day")
                return False
        self.lessons.append({
            "key": key,
            "text": text,
            "source": source,
            "weight": 1,
            "day": day,
            "in_prompt": bool(in_prompt),
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        # Defter şişerse: en az ağırlıklı ve en eski dersler düşer.
        if len(self.lessons) > LESSONS_MAX:
            self.lessons.sort(key=lambda x: (int(x.get("weight") or 1), x.get("ts") or ""))
            del self.lessons[:len(self.lessons) - LESSONS_MAX]
        return True

    def top_lessons(self, limit: int = LESSONS_IN_PROMPT, prompt_only: bool = True) -> list:
        """Prompt'a girecek dersler: elle yazılanlar önce, sonra ağırlık.
        `prompt_only=False` muhasebe notlarını da verir (defter/yetenek görünümü)."""
        dersler = [x for x in self.lessons if x.get("in_prompt", True)] if prompt_only \
            else list(self.lessons)
        oncelik = {"gm": 0, "anlatıcı": 1, "otomatik": 2}
        return sorted(
            dersler,
            key=lambda x: (oncelik.get(x.get("source"), 3),
                           -int(x.get("weight") or 1),
                           x.get("ts") or ""),
        )[:limit]

    # -------------------------------------------------------- türetilmiş
    def category_share(self) -> dict:
        """{kategori: oran} — sadece gerçekten seçilmiş kategoriler."""
        toplam = sum(int(v.get("secim") or 0) for v in self.categories.values())
        if not toplam:
            return {}
        return {name: (int(stats.get("secim") or 0) / toplam)
                for name, stats in self.categories.items()}

    def favourite_category(self):
        """(kategori, oran, adet) — masanın en sık seçtiği kategori."""
        share = self.category_share()
        if not share:
            return None
        name = max(share, key=share.get)
        return name, share[name], int(self.categories[name].get("secim") or 0)

    def summary(self) -> dict:
        """Anlatıcı ekranı ve skill dosyası için okunabilir özet."""
        share = self.category_share()
        return {
            "games": self.games,
            "turns": self.turns,
            "picks": self.picks,
            "categories": {
                name: {
                    "secim": int(stats.get("secim") or 0),
                    "oran": round(share.get(name, 0.0) * 100),
                    "ortalama_zar": (round(int(stats.get("zar_toplam") or 0)
                                           / int(stats.get("secim") or 1)))
                    if int(stats.get("secim") or 0) else None,
                    "felaket": int(stats.get("felaket") or 0),
                    "kritik": int(stats.get("kritik") or 0),
                }
                for name, stats in sorted(
                    self.categories.items(),
                    key=lambda kv: -int(kv[1].get("secim") or 0))
                if name in CATEGORIES or name == "serbest"
            },
            "pace": dict(self.pace),
            "events": dict(self.events),
            "lessons": self.top_lessons(LESSONS_MAX, prompt_only=False),
            "used_starts": list(self.used_starts),
            "used_factions": list(self.used_factions),
            "updated": self.updated,
        }


DEFAULT_LEARNING = Learning().to_dict()
