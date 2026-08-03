"""Harita — grubun nerede olduğu ve bugüne kadar keşfettiği yerler.

Oyun "neredeyiz?" sorusunu eskiden tek bir metin alanıyla (`location`)
cevaplıyordu; grup ikiye ayrıldığında ya da bir yer keşfedildiğinde bunun
kaydı hiçbir yerde durmuyordu. Harita üç şeyi birlikte tutar:

  * `current`  — grubun ana konumu (tek metin, `world_state.location` ile eşlenir)
  * `places`   — bilinen yerler: türü, durumu, tehlike seviyesi, komşuları
  * `party`    — kim nerede (grup dağıldığında karakter başına konum)

Anlatıcı bunu state-update'in `map` alanıyla günceller; sunucu ayrıca her
turda `location` ve `characters.<isim>.location` değerlerinden haritayı
kendiliğinden senkronlar — model unutsa bile harita akmaya devam eder.
"""

from dataclasses import dataclass, field

from .base import DictModel
from .text import canonical_name, norm_tr

PLACE_FIELDS = ("kind", "status", "danger", "notes", "links",
                "discovered_day", "visited")

# Tehlike seviyeleri (arayüzdeki rozet rengi buna bakar).
DANGER_LEVELS = ("güvenli", "temkinli", "tehlikeli", "ölümcül", "bilinmiyor")

DANGER_ALIASES = {
    "guvenli": "güvenli", "sakin": "güvenli", "temiz": "güvenli",
    "temkinli": "temkinli", "orta": "temkinli", "şüpheli": "temkinli",
    "supheli": "temkinli",
    "tehlikeli": "tehlikeli", "riskli": "tehlikeli", "yüksek": "tehlikeli",
    "yuksek": "tehlikeli",
    "ölümcül": "ölümcül", "olumcul": "ölümcül", "kritik": "ölümcül",
}


def canon_danger(value) -> str:
    if not isinstance(value, str) or not value.strip():
        return "bilinmiyor"
    raw = value.strip().lower()
    if raw in DANGER_LEVELS:
        return raw
    key = norm_tr(raw)
    for alias, canon in DANGER_ALIASES.items():
        if norm_tr(alias) == key:
            return canon
    return "bilinmiyor"


@dataclass
class Place(DictModel):
    """`world_state.map.places.<ad>`."""

    KNOWN = PLACE_FIELDS

    kind: object = None            # sığınak / kamp / harabe / yol / tesis …
    status: object = None          # kısa durum: "barikatlı", "yanmış", "terk"
    danger: object = None
    notes: object = None
    links: list = field(default_factory=list)   # komşu yerler (yürüme mesafesi)
    discovered_day: object = None
    visited: object = None
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Place":
        data = data or {}
        place = cls()
        place.extra, place.key_order = cls._split(data)
        for name in ("kind", "status", "danger", "notes", "discovered_day", "visited"):
            setattr(place, name, data.get(name))
        if isinstance(data.get("links"), list):
            place.links = [str(x) for x in data["links"] if isinstance(x, str)]
        elif "links" in data:
            place.extra["links"] = data["links"]
        return place

    @classmethod
    def new(cls, day=None) -> "Place":
        place = cls(kind="", status="", danger="bilinmiyor", notes="", links=[],
                    discovered_day=day, visited=False)
        place.key_order = list(PLACE_FIELDS)
        return place

    def to_dict(self) -> dict:
        values = {name: getattr(self, name) for name in
                  ("kind", "status", "danger", "notes")}
        values["links"] = self.links
        values["discovered_day"] = self.discovered_day
        values["visited"] = self.visited
        return self._emit(values)

    def merge_patch(self, fields: dict) -> None:
        for name in ("kind", "status", "notes"):
            value = fields.get(name)
            if isinstance(value, str):
                self._set(name, value)
        if "danger" in fields:
            self._set("danger", canon_danger(fields.get("danger")))
        if isinstance(fields.get("discovered_day"), (int, float)):
            self._set("discovered_day", int(fields["discovered_day"]))
        if isinstance(fields.get("visited"), bool):
            self._set("visited", fields["visited"])
        links = fields.get("links")
        if isinstance(links, str):
            links = [links]
        if isinstance(links, list):
            self._touch("links")
            for name in links:
                if isinstance(name, str) and name.strip() and name not in self.links:
                    self.links.append(name.strip())


@dataclass
class WorldMap(DictModel):
    """`world_state.map`."""

    KNOWN = ("current", "places", "party")

    current: object = None
    places: dict = field(default_factory=dict)
    party: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "WorldMap":
        data = data or {}
        world_map = cls()
        world_map.extra, world_map.key_order = cls._split(data)
        world_map.current = data.get("current")
        raw = data.get("places")
        if isinstance(raw, dict):
            world_map.places = {name: Place.from_dict(value)
                                for name, value in raw.items()
                                if isinstance(value, dict)}
        raw = data.get("party")
        if isinstance(raw, dict):
            world_map.party = {str(k): str(v) for k, v in raw.items()
                               if isinstance(v, str)}
        return world_map

    @classmethod
    def new(cls) -> "WorldMap":
        world_map = cls(current=None, places={}, party={})
        world_map.key_order = ["current", "places", "party"]
        return world_map

    def to_dict(self) -> dict:
        return self._emit({
            "current": self.current,
            "places": {name: place.to_dict() for name, place in self.places.items()},
            "party": dict(self.party),
        })

    # ------------------------------------------------------------ yardımcılar
    def ensure_place(self, name: str, day=None) -> Place:
        """Yer kaydı yoksa açar; adı büyük/küçük harf farkıyla tekrarlamaz."""
        key = canonical_name(self.places, name) or name
        place = self.places.get(key)
        if not isinstance(place, Place):
            place = self.places[key] = Place.new(day)
        return place

    def go(self, name: str, day=None) -> None:
        """Ana konumu değiştirir ve o yeri 'ziyaret edildi' olarak işaretler."""
        if not isinstance(name, str) or not name.strip():
            return
        name = name.strip()
        previous = self.current
        self._set("current", name)
        place = self.ensure_place(name, day)
        place._set("visited", True)
        if place.discovered_day is None and day is not None:
            place._set("discovered_day", day)
        # Yürüyerek gelinen yer komşudur: rota kendiliğinden çizilsin.
        if isinstance(previous, str) and previous.strip() and previous != name:
            self.link(previous, name)
        self._touch("places")

    def link(self, a: str, b: str) -> None:
        for src, dst in ((a, b), (b, a)):
            place = self.ensure_place(src)
            if dst not in place.links:
                place._touch("links")
                place.links.append(dst)

    def place_person(self, name: str, where: str, day=None) -> None:
        """Karakteri haritaya yerleştirir (grup dağıldığında kim nerede)."""
        if not isinstance(name, str) or not isinstance(where, str) or not where.strip():
            return
        self._touch("party")
        self.party[name] = where.strip()
        self.ensure_place(where.strip(), day)

    def keep_only(self, names) -> None:
        allowed = set(names or [])
        if self.party:
            self.party = {k: v for k, v in self.party.items() if k in allowed}

    def merge_patch(self, patch: dict, day=None) -> None:
        """state-update'in `map` alanı.

        Kabul edilen yazımlar:
          {"current": "Kuzey deposu"}
          {"places": {"Kuzey deposu": {"kind": "depo", "danger": "tehlikeli"}}}
          {"places_add": {...}}  (places ile aynı — model iki türlü de yazıyor)
          {"party": {"Okan": "Kuzey deposu"}}
          {"link": ["Kuzey deposu", "Su kulesi"]}
        """
        if not isinstance(patch, dict):
            return
        for key in ("places", "places_add", "places_update"):
            raw = patch.get(key)
            if not isinstance(raw, dict):
                continue
            self._touch("places")
            for name, fields in raw.items():
                if not isinstance(name, str) or not name.strip():
                    continue
                if isinstance(fields, str):       # {"Su kulesi": "yanmış"}
                    fields = {"status": fields}
                if not isinstance(fields, dict):
                    continue
                place = self.ensure_place(name.strip(), day)
                if place.discovered_day is None and day is not None:
                    place._set("discovered_day", day)
                place.merge_patch(fields)

        party = patch.get("party")
        if isinstance(party, dict):
            for name, where in party.items():
                self.place_person(name, where, day)

        links = patch.get("link") or patch.get("links")
        if isinstance(links, list) and len(links) == 2 and all(
                isinstance(x, str) for x in links):
            self.link(links[0], links[1])

        current = patch.get("current") or patch.get("location")
        if isinstance(current, str) and current.strip():
            self.go(current, day)

    def sync_from_world(self, location, characters: dict, day=None) -> None:
        """Model haritayı yazmayı unutsa bile konum bilgisi akmaya devam etsin:
        `location` ana konumu besler, `party`'de kaydı OLMAYAN karakterler de
        kişisel `location`'larına (yoksa ana konuma) yerleştirilir.

        Mevcut `party` kayıtlarının ÜZERİNE YAZMAZ: bu turda anlatıcı birini
        açıkça başka bir yere koyduysa (`map.party`) o kayıt geçerlidir. Aksi
        halde karakterin eskimiş `location` alanı, yeni yazılmış parti
        kaydını her turda geri alıyordu."""
        if isinstance(location, str) and location.strip() and location != self.current:
            self.go(location, day)
        for name, person in (characters or {}).items():
            if name in self.party:
                continue
            where = getattr(person, "location", None)
            if not (isinstance(where, str) and where.strip()):
                where = self.current
            if isinstance(where, str) and where.strip():
                self.place_person(name, where, day)
        self.keep_only(list((characters or {}).keys()))
