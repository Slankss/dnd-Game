"""Kişi kaydı — `characters` ve `npcs` için ortak gövde.

`_merge_person_like`'ın tamamı burada: künye alanları üzerine yazılır,
envanter birleştirilir (elden çıkan `lost_items`'a düşer), ilişkiler/vitals/
yaralar/sahne katılımı iç içe güncellenir.
"""

from dataclasses import dataclass, field

from .base import DictModel
from .presence import PRESENCE_STATES, Presence
from .text import as_str_list, norm_tr
from .vitals import Vitals
from .wounds import HEALTHY_STATUSES, WoundList, status_for

# Kurulum ekranındaki künye alanları. `secret` oyuncu arayüzüne ASLA gitmez.
# `reflex` = karakterin baskı altındaki ilk tepkisi (küfreder, donar, saldırır…);
# felaket/kritik zar bantlarında anlatıcı bu refleksi FİİLEN oynatır.
SHEET_FIELDS = ("profession", "age", "strength", "weakness", "reflex", "secret")
SECRET_FIELD = "secret"
REFLEX_FIELD = "reflex"

# Üzerine yazılan düz metin alanları (`_merge_person_like`'daki sıra).
SCALAR_FIELDS = ("background", "traits", "status", "location", "notes") + SHEET_FIELDS

# Tanınmadık bir isim için açılan boş kaydın anahtar sırası.
NEW_PERSON_ORDER = ("background", "traits", "status", "alive", "location",
                    "inventory", "relationships", "notes")


def build_background(char) -> str:
    """Künyeden okunabilir bir `background` cümlesi kurar — anlatıcı ve
    kenar çubuğu bu alanı kullanıyor."""
    age, profession = char.get("age"), char.get("profession")
    parts = []
    if age:
        parts.append(f"{age} yaşında")
    if profession:
        parts.append(profession)
    return ", ".join(parts)


def build_traits(char) -> str:
    parts = []
    if char.get("strength"):
        parts.append(f"Güçlü yanı: {char['strength']}")
    if char.get("weakness"):
        parts.append(f"Zayıf yanı: {char['weakness']}")
    if char.get("reflex"):
        parts.append(f"Refleksi: {char['reflex']}")
    return " · ".join(parts)


@dataclass
class Person(DictModel):
    """`world_state.characters.<isim>` / `world_state.npcs.<isim>`."""

    KNOWN = SHEET_FIELDS + ("background", "traits", "status", "alive", "location",
                            "notes", "inventory", "lost_items", "relationships",
                            "wounds", "vitals", "presence")

    profession: object = None
    age: object = None
    strength: object = None
    weakness: object = None
    reflex: object = None
    secret: object = None
    background: object = None
    traits: object = None
    status: object = None
    alive: object = None
    location: object = None
    notes: object = None
    inventory: list = field(default_factory=list)
    lost_items: list = field(default_factory=list)
    relationships: dict = field(default_factory=dict)
    wounds: object = None      # None = kayıtta yok (eski NPC'lerde olabiliyor)
    vitals: object = None      # None = takip edilmiyor (NPC'ler için normal)
    presence: object = None
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    # ------------------------------------------------------------ dönüşüm
    @classmethod
    def from_dict(cls, data: dict) -> "Person":
        data = data or {}
        person = cls()
        person.extra, person.key_order = cls._split(data)
        for name in SHEET_FIELDS + ("background", "traits", "status", "alive",
                                    "location", "notes"):
            setattr(person, name, data.get(name))
        # Beklenmedik tipteki alanlar `extra`'ya düşer: modelin yapısını
        # bozamayız ama kaydı da atamayız.
        for name, kind in (("inventory", list), ("lost_items", list),
                           ("relationships", dict)):
            raw = data.get(name)
            if isinstance(raw, kind):
                setattr(person, name, kind(raw))
            elif name in data:
                person.extra[name] = raw
        if isinstance(data.get("wounds"), list):
            person.wounds = WoundList.from_list(data["wounds"])
        elif "wounds" in data:
            person.extra["wounds"] = data["wounds"]
        if isinstance(data.get("vitals"), dict):
            person.vitals = Vitals.from_dict(data["vitals"])
        elif "vitals" in data:
            person.extra["vitals"] = data["vitals"]
        if isinstance(data.get("presence"), dict):
            person.presence = Presence.from_dict(data["presence"])
        elif "presence" in data:
            person.extra["presence"] = data["presence"]
        return person

    @classmethod
    def new(cls) -> "Person":
        """`_merge_person_like`'ın tanımadık isim için açtığı boş kayıt."""
        person = cls(background=None, traits=None, status="İyi", alive=True,
                     location=None, inventory=[], relationships={}, notes="")
        person.key_order = list(NEW_PERSON_ORDER)
        return person

    def to_dict(self) -> dict:
        values = {name: getattr(self, name) for name in
                  SHEET_FIELDS + ("background", "traits", "status", "alive",
                                  "location", "notes")}
        values["inventory"] = self.inventory
        values["lost_items"] = self.lost_items
        values["relationships"] = self.relationships
        if self.wounds is not None:
            values["wounds"] = self.wounds.to_list()
        if self.vitals is not None:
            values["vitals"] = self.vitals.to_dict()
        if self.presence is not None:
            values["presence"] = self.presence.to_dict()
        return self._emit(values)

    # ------------------------------------------------------------- durum
    @property
    def is_alive(self) -> bool:
        """`entry.get("alive", True)` karşılığı — alan hiç yoksa hayattadır."""
        return bool(self.alive) if "alive" in self.key_order else True

    @property
    def explicitly_dead(self) -> bool:
        """`entry.get("alive") is False` karşılığı (drift/enfeksiyon atlama)."""
        return self.alive is False

    @property
    def presence_state(self) -> str:
        if self.presence is None or self.presence.state not in PRESENCE_STATES:
            return "sahnede"
        return self.presence.state

    def ensure_vitals(self) -> Vitals:
        if self.vitals is None:
            self.vitals = Vitals.default()
        self._touch("vitals")
        return self.vitals.normalize()

    def ensure_presence(self) -> Presence:
        if self.presence is None:
            self.presence = Presence.default()
        self._touch("presence")
        return self.presence.normalize()

    def ensure_wounds(self) -> WoundList:
        if self.wounds is None:
            self.wounds = WoundList()
        self._touch("wounds")
        return self.wounds

    # ---------------------------------------------------------- birleştirme
    def merge_patch(self, fields: dict, day=None, clock=None) -> set:
        """Anlatıcının bu turda elle yazdığı `vitals` alanlarını döndürür —
        otomatik artıştan muaf tutulurlar."""
        for scalar_key in SCALAR_FIELDS:
            if scalar_key in fields:
                self._set(scalar_key, fields[scalar_key])

        if isinstance(fields.get("alive"), bool):
            self._set("alive", fields["alive"])

        if isinstance(fields.get("relationships"), dict):
            self._touch("relationships")
            self.relationships.update(fields["relationships"])

        self.merge_presence(fields, day, clock)
        self.ensure_wounds().merge_patch(fields, day, clock)
        self.merge_inventory(fields)

        touched = set()
        if isinstance(fields.get("vitals"), dict):
            touched = self.ensure_vitals().merge_patch(fields["vitals"])
        return touched

    def merge_presence(self, fields: dict, day=None, clock=None) -> None:
        """Düz string de kabul edilir ("presence": "uyuyor")."""
        raw = fields.get("presence")
        if isinstance(raw, str):
            raw = {"state": raw}
        if not isinstance(raw, dict):
            return
        self.ensure_presence().merge_patch(raw, day, clock)

    def merge_inventory(self, fields: dict) -> None:
        self._touch("inventory")
        inv = self.inventory
        # Elden çıkmış eşyaların kaydı. Model sonraki turlarda hafızasından TAM
        # listeyi tekrar yazınca (atılan madalyonu içeren eski liste gibi) eşya
        # sessizce cebe geri dönüyordu — hikaye tutarsızlaşıyordu. Bir eşya ancak
        # sahnede FİİLEN geri alınırsa (`inventory_add`) bu listeden çıkar.
        self._touch("lost_items")
        lost = self.lost_items
        lost_keys = {norm_tr(i) for i in lost}

        added = as_str_list(fields.get("inventory_add"))
        bulk = as_str_list(fields.get("inventory"))
        removed = as_str_list(fields.get("inventory_remove"))

        # açık geri alma: eşya tekrar sahiplenildi
        for item in added:
            key = norm_tr(item)
            if key in lost_keys:
                lost_keys.discard(key)
                lost[:] = [i for i in lost if norm_tr(i) != key]

        # Model bazen `inventory_add` yerine doğrudan tam listeyi (`inventory`)
        # ya da tek bir eşyayı düz string olarak yazıyor; üçü de kabul ediliyor.
        # `inventory` üzerine YAZMAZ, birleştirir (model listeyi eksik yazarsa
        # mevcut eşyalar kaybolmasın) — ama elden çıkmış eşyayı geri getiremez.
        added_keys = {norm_tr(i) for i in added}
        for item in bulk + added:
            if not item or item in inv:
                continue
            key = norm_tr(item)
            if key in lost_keys and key not in added_keys:
                continue
            inv.append(item)

        for item in removed:
            key = norm_tr(item)
            inv[:] = [i for i in inv if norm_tr(i) != key]
            if key not in lost_keys:
                lost.append(item)
                lost_keys.add(key)

    # ------------------------------------------------------ tur bakımı
    def apply_vitals_drift(self, hours: float, touched=()) -> None:
        self.ensure_vitals().drift(hours, self.presence_state == "uyuyor", touched)

    def advance_infections(self, hours: float) -> None:
        if self.wounds is not None:
            self.wounds.advance_infection(hours)

    def normalize_wound_status(self) -> None:
        wounds = self.wounds.wounds() if self.wounds is not None else []
        if not wounds:
            return
        if norm_tr(self.status) not in HEALTHY_STATUSES:
            return
        self._set("status", status_for(wounds))
