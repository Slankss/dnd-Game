"""Aktif zorluklar — oyunun omurgası.

Anlatıcı her turda `clock` ve `progress` alanlarını günceller. Oyunculara da
gösterilir; sadece `gm_notes` anlatıcı ekranına özeldir.
"""

from dataclasses import dataclass, field

from .base import DictModel

CHALLENGE_FIELDS = ("description", "severity", "clock", "progress",
                    "status", "consequence", "gm_notes")

# Oyunculara gitmeyen alan (bkz. serializers).
CHALLENGE_GM_FIELD = "gm_notes"


@dataclass
class Challenge(DictModel):
    """`world_state.challenges.<ad>`."""

    KNOWN = CHALLENGE_FIELDS

    description: object = None
    severity: object = None
    clock: object = None
    progress: object = None
    status: object = None
    consequence: object = None
    gm_notes: object = None
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Challenge":
        data = data or {}
        challenge = cls()
        challenge.extra, challenge.key_order = cls._split(data)
        for name in cls.KNOWN:
            setattr(challenge, name, data.get(name))
        return challenge

    @classmethod
    def new(cls) -> "Challenge":
        """Yeni zorluğun varsayılan gövdesi (aynı anahtar sırası)."""
        challenge = cls(description="", severity="orta", clock="", progress="",
                        status="açık", consequence="", gm_notes="")
        challenge.key_order = list(CHALLENGE_FIELDS)
        return challenge

    def to_dict(self) -> dict:
        return self._emit({name: getattr(self, name) for name in self.KNOWN})

    def merge_patch(self, fields: dict) -> None:
        """Sadece metin/sayı alanları yazılır — model buraya sözlük ya da
        bool yazarsa yok sayılır."""
        for name in CHALLENGE_FIELDS:
            value = fields.get(name)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                self._set(name, value)
