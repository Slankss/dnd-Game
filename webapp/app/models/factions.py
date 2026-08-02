"""Fraksiyonlar — iki katmanlı görünürlük.

  disposition / notes        -> GERÇEK tavır ve anlatıcı notu (sadece /secrets)
  known / public_notes       -> oyuncuların o ana kadar ÖĞRENDİĞİ (oyun ekranı)
"""

from dataclasses import dataclass, field

from .base import DictModel

FACTION_FIELDS = ("disposition", "known", "notes", "public_notes")


@dataclass
class Faction(DictModel):
    """`world_state.factions.<ad>`."""

    KNOWN = FACTION_FIELDS

    disposition: object = None
    known: object = None
    notes: object = None
    public_notes: object = None
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Faction":
        data = data or {}
        faction = cls()
        faction.extra, faction.key_order = cls._split(data)
        for name in cls.KNOWN:
            setattr(faction, name, data.get(name))
        return faction

    @classmethod
    def new(cls) -> "Faction":
        """Anlatıcının açtığı yeni fraksiyon — alanları yamayla dolar."""
        return cls()

    def to_dict(self) -> dict:
        return self._emit({name: getattr(self, name) for name in self.KNOWN})

    def merge_patch(self, fields: dict) -> None:
        """Düz `dict.update` davranışı: gelen ne varsa üzerine yazılır,
        tanınmayan alanlar da kaydedilir (anlatıcı serbest alan ekleyebiliyor)."""
        for name, value in (fields or {}).items():
            if name in FACTION_FIELDS:
                self._set(name, value)
            else:
                self.extra[name] = value
                self._touch(name)

    def to_public_dict(self) -> dict:
        """Oyuncu arayüzünün gördüğü hal: gerçek tavır değil, ÖĞRENİLEN tavır."""
        return {"disposition": self.known or "bilinmiyor",
                "notes": self.public_notes or ""}
