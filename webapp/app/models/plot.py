"""Olay örgüsü planı — senarist katmanının verisi (`data/plot.json`).

Plan oyuncuya ASLA gösterilmez. Bir beat'in `when` koşulu, sahne katılımıyla
aynı motoru kullanır (bkz. conditions.matches): "gün 101'den sonra kampta
mühür görünsün" ile "Okan 06:00'da uyanır" tek makinedir.
"""

from dataclasses import dataclass, field

from .base import DictModel
from .conditions import describe_when, matches

DEFAULT_PLOT = {"version": 1, "updated_day": None, "threads": {},
                "beats": [], "seeds": []}

# pending = bekliyor · fired = ateşlendi · expired = vadesi doldu · vetoed = GM iptal etti
BEAT_STATES = ("pending", "fired", "expired", "vetoed")

# `expires_day` yazılmamış bir beat'e verilen ömür (gün). Vadesiz beat kuyrukta
# sonsuza kadar bekler ve çok sonra alakasız bir sahnede patlar.
DEFAULT_TTL_DAYS = 8


@dataclass
class Beat(DictModel):
    """`plot.beats[]` — planlanmış tek bir müdahale."""

    KNOWN = ("id", "thread", "when", "directive", "on_fire",
             "expires_day", "state", "fired_day")

    id: object = None
    thread: object = None
    when: object = None
    directive: object = None
    on_fire: object = None
    expires_day: object = None
    state: object = None
    fired_day: object = None
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Beat":
        data = data or {}
        beat = cls()
        beat.extra, beat.key_order = cls._split(data)
        for name in cls.KNOWN:
            setattr(beat, name, data.get(name))
        return beat

    def to_dict(self) -> dict:
        return self._emit({name: getattr(self, name) for name in self.KNOWN})

    @property
    def is_pending(self) -> bool:
        return (self.state or "pending") == "pending"

    def ready(self, ctx: dict) -> bool:
        """Bekleyen bir beat'in koşulu bu turda sağlandı mı?"""
        return self.is_pending and matches(self.when, ctx)

    def describe(self) -> str:
        return describe_when(self.when)


@dataclass
class Plot(DictModel):
    """`data/plot.json` kökü."""

    KNOWN = ("version", "updated_day", "threads", "beats", "seeds")

    version: object = None
    updated_day: object = None
    threads: dict = field(default_factory=dict)
    beats: list = field(default_factory=list)
    seeds: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    @classmethod
    def default(cls) -> "Plot":
        plot = cls(version=1, updated_day=None, threads={}, beats=[], seeds=[])
        plot.key_order = list(DEFAULT_PLOT)
        return plot

    @classmethod
    def from_dict(cls, data) -> "Plot":
        """Eksik alanlar varsayılanla doldurulur; `beats` liste değilse
        boşaltılır (bozuk plan dosyası oyunu düşürmesin)."""
        if not isinstance(data, dict):
            return cls.default()
        plot = cls()
        plot.extra, plot.key_order = cls._split(data)
        for name in cls.KNOWN:
            setattr(plot, name, data.get(name))
        for name, value in DEFAULT_PLOT.items():
            if name not in data:  # eksik alan varsayılanla doldurulur
                plot._set(name, type(value)() if isinstance(value, (dict, list)) else value)
        if not isinstance(plot.beats, list):
            plot._set("beats", [])
        plot.beats = [Beat.from_dict(b) if isinstance(b, dict) else b
                      for b in plot.beats]
        return plot

    def to_dict(self) -> dict:
        values = {name: getattr(self, name) for name in self.KNOWN}
        values["beats"] = [b.to_dict() if isinstance(b, Beat) else b
                           for b in (self.beats or [])]
        return self._emit(values)

    # ------------------------------------------------------------ sorgular
    def pending_beats(self) -> list:
        return [b for b in self.beats if isinstance(b, Beat) and b.is_pending]

    def due_beats(self, ctx: dict) -> list:
        """Koşulu sağlanan beat'ler — en yakın vadeli önce (tur başına bir
        tanesi ateşlenir; üç direktif aynı sahneye girerse okunmaz olur)."""
        ready = [b for b in self.pending_beats() if b.ready(ctx)]
        return sorted(ready, key=lambda b: (b.expires_day is None, b.expires_day))

    # ------------------------------------------------------------- vade/ateş
    def ensure_expiry(self, day) -> list:
        """Vadesiz beat'e varsayılan vade yazar. Vadesiz bir beat sonsuza
        kadar kuyrukta bekler ve 20 tur sonra alakasız bir sahnede patlar —
        planın en sinsi hatası bu."""
        if not isinstance(day, int):
            return []
        yazilan = []
        for beat in self.pending_beats():
            if beat.expires_day is None:
                beat._set("expires_day", day + DEFAULT_TTL_DAYS)
                yazilan.append(beat.id)
        return yazilan

    def expire(self, day) -> list:
        """Vadesi geçmiş bekleyen beat'leri çürütür. Çürüyenlerin id'si döner
        (anlatıcı günlüğüne yazılır ki plan sessizce erimesin)."""
        if not isinstance(day, int):
            return []
        curuyen = []
        for beat in self.pending_beats():
            if isinstance(beat.expires_day, int) and day > beat.expires_day:
                beat._set("state", "expired")
                curuyen.append(beat.id)
        return curuyen

    def fire(self, beat: "Beat", day) -> None:
        """Beat ateşlendi: bir daha seçilmesin."""
        beat._set("state", "fired")
        beat._set("fired_day", day)
        if isinstance(day, int):
            self._set("updated_day", day)
