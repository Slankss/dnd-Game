"""Hayatta kalma göstergeleri.

Hepsinde 0 = gayet iyi, 100 = dayanılmaz. Zar gibi bunlar da sunucunun
sorumluluğunda: model unutsa bile akan zamana göre kendiliğinden artarlar.
"""

from dataclasses import dataclass, field

from .base import DictModel

VITALS_NUMERIC = ("fatigue", "hunger", "thirst", "stress")

# Uyanık geçen her SAAT için artış. fatigue ~25 saatte, thirst ~20 saatte,
# hunger ~28 saatte tavan yapar — kıyamet temposu için gerçekçi aralıklar.
VITALS_PER_HOUR = {"fatigue": 4.0, "hunger": 3.5, "thirst": 5.0, "stress": 0.8}

# Uyuyan karakter için (presence.state == "uyuyor"): yorgunluk ve stres düşer,
# açlık/susuzluk uykuda da birikmeye devam eder. ~8 saatlik uyku yorgunluğu
# tavandan tabana indirir.
VITALS_SLEEP_PER_HOUR = {"fatigue": -9.0, "hunger": 3.0, "thirst": 4.0, "stress": -3.0}

DEFAULT_VITALS = {
    "fatigue": 15, "hunger": 20, "thirst": 20, "stress": 10,
    "awake_hours": 3, "condition": "Dinç",
}

VITAL_NAMES = {"fatigue": "yorgunluk", "hunger": "açlık",
               "thirst": "susuzluk", "stress": "stres"}


def clamp_vital(value, default=0):
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def vital_label(vitals: dict) -> str:
    """En kötü göstergeye göre tek kelimelik özet (`_vital_label`)."""
    worst_key, worst = None, -1
    for key in VITALS_NUMERIC:
        if vitals.get(key, 0) > worst:
            worst_key, worst = key, vitals.get(key, 0)
    if worst >= 85:
        return f"kritik {VITAL_NAMES[worst_key]}"
    if worst >= 65:
        return f"ağır {VITAL_NAMES[worst_key]}"
    if worst >= 40:
        return f"belirgin {VITAL_NAMES[worst_key]}"
    return "formda"


@dataclass
class Vitals(DictModel):
    """`characters.<isim>.vitals` / `npcs.<isim>.vitals`."""

    KNOWN = ("fatigue", "hunger", "thirst", "stress", "awake_hours", "condition")

    fatigue: object = None
    hunger: object = None
    thirst: object = None
    stress: object = None
    awake_hours: object = None
    condition: object = None
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    # ------------------------------------------------------------ dönüşüm
    @classmethod
    def from_dict(cls, data: dict) -> "Vitals":
        """Değerlere DOKUNMAZ — sıkıştırma yalnızca `normalize()` ile olur,
        yoksa sadece yükleyip kaydetmek bile kayıttaki değerleri oynatırdı."""
        data = data or {}
        vitals = cls()
        vitals.extra, vitals.key_order = cls._split(data)
        for name in cls.KNOWN:
            setattr(vitals, name, data.get(name))
        return vitals

    @classmethod
    def default(cls) -> "Vitals":
        """`ensure_vitals`'ın açtığı varsayılan kayıt (aynı anahtar sırası)."""
        vitals = cls(**DEFAULT_VITALS)
        vitals.key_order = list(DEFAULT_VITALS)
        return vitals

    def to_dict(self) -> dict:
        return self._emit({name: getattr(self, name) for name in self.KNOWN})

    # ------------------------------------------------------------ davranış
    def normalize(self) -> "Vitals":
        """`ensure_vitals` karşılığı: dört sayısal alanı 0-100'e sıkıştırır."""
        for key in VITALS_NUMERIC:
            self._set(key, clamp_vital(getattr(self, key), DEFAULT_VITALS[key]))
        return self

    def label(self) -> str:
        return vital_label({key: getattr(self, key) for key in VITALS_NUMERIC})

    def drift(self, hours: float, asleep: bool = False, touched=()) -> None:
        """Geçen süre kadar yıpranma/dinlenme. Anlatıcının bu turda AÇIKÇA
        yazdığı alanlara (`touched`) dokunulmaz."""
        rates = VITALS_SLEEP_PER_HOUR if asleep else VITALS_PER_HOUR
        for key, rate in rates.items():
            if key in touched:
                continue
            self._set(key, clamp_vital(getattr(self, key) + rate * hours))
        if "awake_hours" not in touched:
            try:
                awake = float(self.awake_hours or 0)
            except (TypeError, ValueError):
                awake = 0.0
            self._set("awake_hours", 0 if asleep else round(awake + hours, 1))

    def merge_patch(self, fields: dict) -> set:
        """Anlatıcının yazdığı gösterge değerleri sunucunun otomatik artışını
        EZER (uyudu / yedi / içti). Dokunulan alanlar çağırana döner."""
        touched = set()
        for key, value in (fields or {}).items():
            if key in VITALS_NUMERIC:
                self._set(key, clamp_vital(value, getattr(self, key)))
                touched.add(key)
            elif key == "awake_hours":
                try:
                    self._set("awake_hours", max(0.0, round(float(value), 1)))
                    touched.add("awake_hours")
                except (TypeError, ValueError):
                    pass
            elif key == "condition" and isinstance(value, str):
                self._set("condition", value.strip())
        return touched
