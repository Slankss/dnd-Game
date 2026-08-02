"""Sahne katılımı.

Her karakterin her turda sahnede olması gerekmez: biri uyuyor, biri erzak
aramaya gitmiş, biri esir düşmüş olabilir. Sahnede olmayan karakter için
anlatıcı replik/aksiyon UYDURMAZ, o karaktere zar yorumu yazmaz. Sahneye
dönüş koşulu (`until`) beat tetikleyicileriyle aynı motoru kullanır —
bkz. conditions.matches.
"""

from dataclasses import dataclass, field

from .base import DictModel
from .conditions import matches
from .text import norm_tr

PRESENCE_STATES = ("sahnede", "uyuyor", "uzakta", "baygın", "esir")

PRESENCE_LABELS = {
    "sahnede": "sahnede",
    "uyuyor": "uyuyor",
    "uzakta": "sahne dışında",
    "baygın": "baygın",
    "esir": "esir",
}

# Modelin aynı hal için kullanabileceği başka kelimeler (normalleştirilmiş).
PRESENCE_ALIASES = {
    "aktif": "sahnede", "uyanik": "sahnede", "burada": "sahnede", "sahnede": "sahnede",
    "uykuda": "uyuyor", "uyuyor": "uyuyor",
    "yok": "uzakta", "ayri": "uzakta", "uzak": "uzakta", "disarida": "uzakta",
    "sahne disi": "uzakta", "sahne disinda": "uzakta", "gitti": "uzakta",
    "bayilmis": "baygın", "bayildi": "baygın", "bilincsiz": "baygın",
    "tutsak": "esir", "kacirildi": "esir", "esir": "esir",
}


def canon_presence(value):
    """Modelin yazdığı hali bilinen bir hale indirger; tanımadıysa None."""
    key = norm_tr(value)
    if not key:
        return None
    for state in PRESENCE_STATES:
        if norm_tr(state) == key:
            return state
    return PRESENCE_ALIASES.get(key)


@dataclass
class Presence(DictModel):
    """`characters.<isim>.presence`."""

    KNOWN = ("state", "note", "until", "since_day", "since_clock")

    state: object = None
    note: object = None
    until: object = None
    since_day: object = None
    since_clock: object = None
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Presence":
        data = data or {}
        presence = cls()
        presence.extra, presence.key_order = cls._split(data)
        for name in cls.KNOWN:
            setattr(presence, name, data.get(name))
        return presence

    @classmethod
    def default(cls) -> "Presence":
        """`ensure_presence`'ın açtığı varsayılan kayıt (aynı anahtar sırası)."""
        presence = cls(state="sahnede", note="", until=None,
                       since_day=None, since_clock=None)
        presence.key_order = list(cls.KNOWN)
        return presence

    def to_dict(self) -> dict:
        return self._emit({name: getattr(self, name) for name in self.KNOWN})

    # ------------------------------------------------------------ davranış
    def normalize(self) -> "Presence":
        """`ensure_presence` karşılığı: tanınmayan hal `sahnede`'ye düşer."""
        if self.state not in PRESENCE_STATES:
            self._set("state", canon_presence(self.state) or "sahnede")
        if not isinstance(self.until, dict):
            self._set("until", None)
        if not isinstance(self.note, str):
            self._set("note", "")
        return self

    def set_present(self, day=None, clock=None) -> None:
        """Karakteri sahneye döndürür (`_set_present`)."""
        self._set("state", "sahnede")
        self._set("until", None)
        self._set("note", "")
        self._set("since_day", day)
        self._set("since_clock", clock)

    def merge_patch(self, raw: dict, day=None, clock=None) -> None:
        """Anlatıcının yazdığı `presence` alanını uygular."""
        state = canon_presence(raw.get("state") or raw.get("durum"))
        if state and state != self.state:
            self._set("state", state)
            self._set("since_day", day)
            self._set("since_clock", clock)
            # yeni hal, eski randevu düşer
            self._set("until", None)
            if state == "sahnede":
                self._set("note", "")
        if "until" in raw:
            self._set("until", raw["until"] if isinstance(raw["until"], dict) else None)
        if isinstance(raw.get("note"), str) and self.state != "sahnede":
            self._set("note", raw["note"].strip())

    def label(self) -> str:
        return PRESENCE_LABELS.get(self.state, self.state)

    def due(self, ctx: dict) -> bool:
        """Sahneye dönüş randevusu doldu mu?"""
        return bool(self.until) and matches(self.until, ctx)


# ------------------------------------------------- kadro (Person üzerinde)
# Aşağıdaki yardımcılar `dict[isim] -> Person` üzerinde çalışır; Person'ı
# import ETMEZLER (döngüsel import olurdu), sadece arayüzünü kullanırlar.

def present_players(characters: dict) -> list:
    """Bu turda sahnede olan, yaşayan oyuncu karakterleri."""
    return [name for name, person in (characters or {}).items()
            if person.is_alive and person.presence_state == "sahnede"]


def absent_players(characters: dict) -> list:
    """[(isim, Presence)] — yaşayan ama sahnede olmayan karakterler."""
    out = []
    for name, person in (characters or {}).items():
        if not person.is_alive:
            continue
        if person.presence_state != "sahnede":
            out.append((name, person.ensure_presence()))
    return out


def resolve_presence(characters: dict, ctx: dict, day=None, clock=None) -> list:
    """Vadesi dolan sahne dışılıkları kapatır (uyandı / geri döndü).
    Dönen liste prompt'a ve anlatıcı loguna gider."""
    returned = []
    for name, person in (characters or {}).items():
        if not person.is_alive:
            continue
        presence = person.ensure_presence()
        if presence.state == "sahnede":
            continue
        if presence.due(ctx):
            returned.append((name, presence.state))
            presence.set_present(day, clock)
    return returned


def bring_to_scene(characters: dict, name: str, day=None, clock=None):
    """Oyuncu sahne dışındaki karakteriyle mesaj gönderdiyse, bu mesajın
    kendisi 'uyandım / geri döndüm' demektir. Önceki hali döner (yoksa None)."""
    person = (characters or {}).get(name)
    if person is None or not person.is_alive:
        return None
    presence = person.ensure_presence()
    if presence.state == "sahnede":
        return None
    was = presence.state
    presence.set_present(day, clock)
    return was
