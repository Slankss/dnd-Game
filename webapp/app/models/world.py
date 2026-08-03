"""Kök nesne: `state.json` içindeki `world_state`.

Veri kabı, tur bakımı (göstergeler/yaralar/sahne katılımı) ve sorgular burada;
state-update yamasının uygulanması `world_patch.py`'de.
"""

from dataclasses import dataclass, field

from .base import DictModel
from .challenges import Challenge
from .conditions import build_context
from .factions import Faction
from .options import OptionBoard
from .person import Person
from .presence import absent_players, bring_to_scene, present_players, resolve_presence
from .resources import ResourcePool
from .worldmap import WorldMap
# TIME_FIELDS / TENSION_LEVELS burada da dışa açılır: `state_repo` ve servis
# katmanı bunları dünya modelinin parçası olarak import ediyor.
from .world_patch import TENSION_LEVELS, TIME_FIELDS, WorldPatchMixin  # noqa: F401

# Oyuncuların /api/state ile ASLA görmemesi gereken alanlar. `narrator`
# (plot_summary/puzzles/upcoming_events) buraya eklenene kadar dünya durumuyla
# birlikte her oyuncunun tarayıcısına gidiyordu — spoiler sızıntısıydı.
GM_ONLY_FIELDS = ("narrator", "world_roll", "world_roll_history")

DEFAULT_NARRATOR = {"plot_summary": "", "puzzles": {}, "upcoming_events": {}}

# Yapısı olan (alt modele çevrilen) alanlar.
NESTED_FIELDS = (("factions", Faction), ("characters", Person),
                 ("npcs", Person), ("challenges", Challenge))

# Düz okunan alanlar — sözlük/liste olsalar bile içeriğine karışılmaz.
FLAT_FIELDS = ("day",) + TIME_FIELDS + ("location", "tension", "flags",
                                        "zombie_sightings", "world_roll")

# Kanonik alan sırası (senaryodaki INITIAL_WORLD_STATE ile aynı).
WORLD_FIELDS = ("day",) + TIME_FIELDS + (
    "location", "map", "factions", "characters", "npcs", "resources", "challenges",
    "options", "zombie_sightings", "flags", "narrator", "tension",
    "world_roll", "world_roll_history")


@dataclass
class WorldState(WorldPatchMixin, DictModel):
    """`state["world_state"]`."""

    KNOWN = WORLD_FIELDS

    day: object = None
    time_of_day: object = None
    clock: object = None
    season: object = None
    weather: object = None
    temperature: object = None
    location: object = None
    tension: object = None
    factions: dict = field(default_factory=dict)
    characters: dict = field(default_factory=dict)
    npcs: dict = field(default_factory=dict)
    resources: object = None
    challenges: dict = field(default_factory=dict)
    map: object = None
    options: object = None
    zombie_sightings: object = None
    flags: object = None
    narrator: object = None
    world_roll: object = None
    world_roll_history: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    # ------------------------------------------------------------ dönüşüm
    @classmethod
    def from_dict(cls, data: dict) -> "WorldState":
        data = data or {}
        world = cls()
        world.extra, world.key_order = cls._split(data)
        for name in FLAT_FIELDS:
            setattr(world, name, data.get(name))
        # Beklenmedik tipteki alanlar `extra`'ya düşer: modelin yapısını
        # bozamayız ama kaydı da atamayız.
        for name, model in NESTED_FIELDS:
            raw = data.get(name)
            if isinstance(raw, dict):
                setattr(world, name, {key: (model.from_dict(value)
                                            if isinstance(value, dict) else value)
                                      for key, value in raw.items()})
            elif name in data:
                world.extra[name] = raw
        for name, kind, parse in (("resources", dict, ResourcePool.from_dict),
                                  ("map", dict, WorldMap.from_dict),
                                  ("options", dict, OptionBoard.from_dict),
                                  ("narrator", dict, dict),
                                  ("world_roll_history", list, list)):
            raw = data.get(name)
            if isinstance(raw, kind):
                setattr(world, name, parse(raw))
            elif name in data:
                world.extra[name] = raw
        return world

    def to_dict(self) -> dict:
        values = {name: getattr(self, name) for name in FLAT_FIELDS}
        for name, _model in NESTED_FIELDS:
            values[name] = {key: (value.to_dict() if hasattr(value, "to_dict") else value)
                            for key, value in (getattr(self, name) or {}).items()}
        if self.resources is not None:
            values["resources"] = self.resources.to_dict()
        if self.map is not None:
            values["map"] = self.map.to_dict()
        if self.options is not None:
            values["options"] = self.options.to_dict()
        values["narrator"] = self.narrator
        values["world_roll_history"] = self.world_roll_history
        return self._emit({name: values[name] for name in WORLD_FIELDS if name in values})

    def clock_snapshot(self) -> dict:
        """`elapsed_minutes` için turun başındaki/sonundaki zaman."""
        return {"day": self.day, "clock": self.clock}

    def sections(self):
        """[(bölüm adı, {isim: Person})] — characters ve npcs sırayla."""
        return (("characters", self.characters), ("npcs", self.npcs))

    # ------------------------------------------------- alan hazırlayıcılar
    def ensure_resources(self) -> ResourcePool:
        if not isinstance(self.resources, ResourcePool):
            self.resources = ResourcePool()
        self._touch("resources")
        return self.resources

    def ensure_map(self) -> WorldMap:
        if not isinstance(self.map, WorldMap):
            self.map = WorldMap.new()
        self._touch("map")
        return self.map

    def ensure_options(self) -> OptionBoard:
        if not isinstance(self.options, OptionBoard):
            self.options = OptionBoard()
        self._touch("options")
        return self.options

    def ensure_flags(self) -> dict:
        if not isinstance(self.flags, dict):
            self.flags = {}
        self._touch("flags")
        return self.flags

    def ensure_narrator(self) -> dict:
        if not isinstance(self.narrator, dict):
            self.narrator = dict(DEFAULT_NARRATOR)
        self._touch("narrator")
        return self.narrator

    def ensure_sightings(self) -> list:
        if not isinstance(self.zombie_sightings, list):
            self.zombie_sightings = []
        self._touch("zombie_sightings")
        return self.zombie_sightings

    def set_world_roll(self, entry: dict) -> None:
        self._set("world_roll", entry)
        self._touch("world_roll_history")

    # -------------------------------------------------------- tur bakımı
    def apply_vitals_drift(self, minutes: int, skip: dict = None) -> None:
        """Geçen süre kadar yorgunluk/açlık/susuzluk biriktirir. Anlatıcının bu
        turda AÇIKÇA yazdığı alanlara (uyudu/yedi/içti) dokunmaz — `skip`
        {isim: {alan, ...}} biçiminde o alanları taşır."""
        if minutes <= 0:
            return
        hours, skip = minutes / 60.0, (skip or {})
        for section, people in self.sections():
            for name, person in (people or {}).items():
                if person.explicitly_dead:
                    continue
                # NPC'lerde sadece anlatıcı bir kez vitals açtıysa takip edilir
                if section == "npcs" and person.vitals is None:
                    continue
                person.apply_vitals_drift(hours, skip.get(name) or set())

    def advance_infections(self, minutes: int) -> None:
        """Tedavi edilmemiş yaraların enfeksiyon riski zamanla yükselir; tedavi
        edilmişler yavaşça temizlenir. Göstergeler gibi bu da sunucunun işi —
        anlatıcı unutsa bile yara ilerler."""
        if minutes <= 0:
            return
        hours = minutes / 60.0
        for _section, people in self.sections():
            for person in (people or {}).values():
                if person.explicitly_dead:
                    continue
                person.advance_infections(hours)

    def normalize_wound_status(self) -> None:
        """Kolunda kanayan yara varken `status: "İyi"` kalmasın."""
        for _section, people in self.sections():
            for person in (people or {}).values():
                if person.explicitly_dead:
                    continue
                person.normalize_wound_status()

    def sync_map(self) -> None:
        """Haritayı dünyanın geri kalanıyla eşler: ana konum `location`'dan,
        parti dağılımı karakterlerin `location` alanından beslenir. Anlatıcı
        `map` yazmayı unutsa bile harita akmaya devam eder."""
        day = self.day if isinstance(self.day, int) else None
        self.ensure_map().sync_from_world(self.location, self.characters, day)

    # ----------------------------------------------------- sahne katılımı
    def build_context(self, world_entry: dict = None) -> dict:
        return build_context(self, world_entry)

    def resolve_presence(self, world_entry: dict = None) -> list:
        """Vadesi dolan uyku/uzaklık hallerini kapatır; dönenlerin listesi."""
        return resolve_presence(self.characters, self.build_context(world_entry),
                                self.day, self.clock)

    def bring_to_scene(self, name: str):
        return bring_to_scene(self.characters, name, self.day, self.clock)

    def present_players(self) -> list:
        return present_players(self.characters)

    def absent_players(self) -> list:
        return absent_players(self.characters)

    def alive_players(self) -> list:
        return [name for name, person in (self.characters or {}).items() if person.is_alive]

    # ------------------------------------------------------------ durum
    def sheets_complete(self) -> bool:
        return bool(self.characters) and all(c.background for c in self.characters.values())

    def chargen_complete(self) -> bool:
        # Oyuncular karakter oluşturmayı arayüzden elle bitirmiş olabilir —
        # biri hiç cevap vermezse oyun sonsuza kadar chargen'de takılı kalıp zar
        # mekaniği ve ortak karar hiç açılmıyordu.
        if (self.flags or {}).get("chargen_done"):
            return True
        if not self.characters:
            return False
        alive = [c for c in self.characters.values() if c.is_alive]
        if not alive:
            return False
        return all(c.background for c in alive)
