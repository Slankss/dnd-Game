"""Açık yaralar.

`vitals.condition` her tur üzerine yazıldığı için kalıcı değildi; yaralar
burada, iyileşene kadar kayıtlı kalır. Enfeksiyon riski de göstergeler gibi
sunucunun işi — anlatıcı unutsa bile yara ilerler.
"""

from dataclasses import dataclass, field

from .base import DictModel
from .text import norm_tr
from .vitals import clamp_vital

WOUND_SEVERITIES = ("hafif", "orta", "ağır", "kritik")

# Tedavi edilmemiş yaranın saat başına enfeksiyon riski artışı. Tedavi
# edilmiş yara yavaşça temizlenir (negatif).
INFECTION_PER_HOUR = {"hafif": 0.6, "orta": 1.2, "ağır": 2.0, "kritik": 3.0}
INFECTION_TREATED_PER_HOUR = -1.0

# Yarası varken bu durumlarda kalmış kayıtlar düzeltilir.
HEALTHY_STATUSES = {norm_tr(w) for w in ("iyi", "sağlıklı", "normal", "formda", "")}


def wound_key(desc) -> str:
    return norm_tr(desc)


def status_for(wounds) -> str:
    """Kolunda kanayan yara varken `status: "İyi"` kalmasın — anlatıcı bunu
    sık sık atlıyor ve oyuncu kenar çubuğunda sağlıklı görünüyordu."""
    worst = max(WOUND_SEVERITIES.index(w.severity)
                if w.severity in WOUND_SEVERITIES else 1
                for w in wounds)
    infected = any((w.infection_risk or 0) >= 60 for w in wounds)
    if infected:
        return "Enfekte olabilir"
    if worst >= WOUND_SEVERITIES.index("ağır"):
        return "Ağır yaralı"
    return "Yaralı"


@dataclass
class Wound(DictModel):
    """`characters.<isim>.wounds[]` kaydı."""

    KNOWN = ("desc", "severity", "infection_risk", "treated", "notes",
             "since_day", "since_clock")

    desc: object = None
    severity: object = None
    infection_risk: object = None
    treated: object = None
    notes: object = None
    since_day: object = None
    since_clock: object = None
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Wound":
        """Kayıttaki yarayı olduğu gibi okur (normalleştirme YAPMAZ)."""
        data = data or {}
        wound = cls()
        wound.extra, wound.key_order = cls._split(data)
        for name in cls.KNOWN:
            setattr(wound, name, data.get(name))
        return wound

    @classmethod
    def normalize(cls, raw, day=None, clock=None):
        """Model yarayı düz string ya da sözlük olarak yazabiliyor; ikisini de
        aynı yapıya çevirir (`_normalize_wound`). Tanınmayan alan atılır."""
        if isinstance(raw, str):
            raw = {"desc": raw}
        if not isinstance(raw, dict):
            return None
        desc = str(raw.get("desc") or raw.get("description") or "").strip()
        if not desc:
            return None
        severity = str(raw.get("severity") or "orta").strip().casefold()
        if severity not in WOUND_SEVERITIES:
            severity = "orta"
        wound = cls(
            desc=desc,
            severity=severity,
            infection_risk=clamp_vital(raw.get("infection_risk"), 15),
            treated=bool(raw.get("treated")),
            notes=str(raw.get("notes") or "").strip(),
            since_day=raw.get("since_day", day),
            since_clock=raw.get("since_clock", clock),
        )
        wound.key_order = list(cls.KNOWN)
        return wound

    def to_dict(self) -> dict:
        return self._emit({name: getattr(self, name) for name in self.KNOWN})

    # ------------------------------------------------------------ davranış
    def apply_changes(self, changes: dict) -> None:
        """`wounds_update` altındaki kısmi düzenleme."""
        if "severity" in changes:
            sev = str(changes["severity"]).strip().casefold()
            if sev in WOUND_SEVERITIES:
                self._set("severity", sev)
        if "infection_risk" in changes:
            self._set("infection_risk",
                      clamp_vital(changes["infection_risk"], self.infection_risk))
        if "treated" in changes:
            self._set("treated", bool(changes["treated"]))
        if isinstance(changes.get("notes"), str):
            self._set("notes", changes["notes"].strip())
        if isinstance(changes.get("desc"), str) and changes["desc"].strip():
            self._set("desc", changes["desc"].strip())

    def advance_infection(self, hours: float) -> None:
        rate = (INFECTION_TREATED_PER_HOUR if self.treated
                else INFECTION_PER_HOUR.get(self.severity, 1.2))
        self._set("infection_risk", clamp_vital((self.infection_risk or 0) + rate * hours))


class WoundList:
    """Bir kişinin yara listesi. Tanınmayan (sözlük olmayan) kayıtlar da
    listede olduğu gibi taşınır — kayıp veri olmasın."""

    def __init__(self, items=None):
        self.items = list(items or [])

    @classmethod
    def from_list(cls, raw) -> "WoundList":
        return cls([Wound.from_dict(w) if isinstance(w, dict) else w
                    for w in (raw or [])])

    def to_list(self) -> list:
        return [w.to_dict() if isinstance(w, Wound) else w for w in self.items]

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def wounds(self) -> list:
        """Sadece gerçek yara kayıtları."""
        return [w for w in self.items if isinstance(w, Wound)]

    def find(self, fragment):
        """Parça isimle en yakın yarayı bulur (Türkçe duyarsız, kısmi)."""
        key = wound_key(fragment)
        if not key:
            return None
        for w in self.wounds():
            wk = wound_key(w.desc)
            if key == wk or key in wk or wk in key:
                return w
        return None

    def merge_patch(self, fields: dict, day=None, clock=None) -> None:
        raw_add = fields.get("wounds_add")
        if isinstance(raw_add, (str, dict)):
            raw_add = [raw_add]
        for raw in raw_add or []:
            wound = Wound.normalize(raw, day, clock)
            if wound and not self.find(wound.desc):
                self.items.append(wound)

        updates = fields.get("wounds_update")
        if isinstance(updates, dict):
            for fragment, changes in updates.items():
                wound = self.find(fragment)
                if wound is None or not isinstance(changes, dict):
                    continue
                wound.apply_changes(changes)

        healed = fields.get("wounds_heal")
        if isinstance(healed, str):
            healed = [healed]
        for fragment in healed or []:
            wound = self.find(fragment)
            if wound is not None:
                self.items.remove(wound)

    def advance_infection(self, hours: float) -> None:
        for wound in self.wounds():
            wound.advance_infection(hours)
