"""Bekleyen yayın kuyruğu — bir turda tetiklenen hiçbir şey O TURDA devreye girmez.

Kural:

  Bir turda üretilen her şey — anlatıcının yazdığı sahne, sunucunun attığı
  karşılaşma zarı, anlatıcının bildirdiği patlama/alarm, senarist planının
  vadesi gelen beat'i — **bir sonraki turun başında** devreye girer.

Neden: oyuncu kararını verdiği anda, o karara sebep olmayan bir sürprizle
aynı turun içinde cezalandırılmasın. Karar verilen tur ile sonucun yayınlandığı
tur ayrıdır; böylece "ne olduğunu" her zaman turun BAŞINDA öğrenirsin ve
kararını ona göre verirsin.

Kuyruk `state["pending"]` altında, düz JSON olarak durur: sunucu tur ortasında
ölse bile bekleyen sahne bir sonraki turun başında yayınlanır.

Türler:
  `sahne`     Anlatıcının yazdığı ham yanıt. Yayınlanması (kayda düşmesi,
              dünya yamasının uygulanması, yeni seçenek havuzu) turun başına
              ertelenir.
  `tehdit`    Bu turda çıkan gürültü / yolculuk niyeti / anlatıcının bildirdiği
              olaylar. Karşılaşma zarına BİR SONRAKİ tur girer.
  `direktif`  Vadesi gelen senarist beat'i. Bir sonraki turun sahnesini
              şekillendirir.

Aynı tura birden fazla `tehdit` kaydı düşebilir (biri turun seçimlerinden,
biri sahnenin state-update'inden): `birlestir` hepsini tek bir devir sözlüğüne
toplar — gürültünün en yükseği, yolculuk niyetlerinin herhangi biri, olayların
tamamı geçerlidir.
"""

import time
from dataclasses import dataclass, field

# Kuyruk türleri.
SAHNE = "sahne"
TEHDIT = "tehdit"
DIREKTIF = "direktif"


@dataclass
class PendingItem:
    """Kuyrukta bekleyen tek bir kayıt."""

    kind: str = ""
    due_round: int = 0          # hangi turun BAŞINDA devreye girecek
    data: dict = field(default_factory=dict)
    ts: float = 0.0

    @classmethod
    def from_dict(cls, data) -> "PendingItem":
        data = data if isinstance(data, dict) else {}
        icerik = data.get("data")
        return cls(
            kind=str(data.get("kind") or ""),
            due_round=int(data.get("due_round") or 0),
            data=icerik if isinstance(icerik, dict) else {},
            ts=float(data.get("ts") or 0.0),
        )

    def to_dict(self) -> dict:
        return {"kind": self.kind, "due_round": self.due_round,
                "data": self.data, "ts": self.ts}


@dataclass
class PendingQueue:
    """`state["pending"]` — vadesi gelen kayıtları turun başında verir."""

    items: list = field(default_factory=list)

    # ------------------------------------------------------------ dönüşüm
    @classmethod
    def from_dict(cls, data) -> "PendingQueue":
        ham = data.get("items") if isinstance(data, dict) else data
        if not isinstance(ham, list):
            ham = []
        return cls(items=[PendingItem.from_dict(x) for x in ham
                          if isinstance(x, dict)])

    def to_dict(self) -> dict:
        return {"items": [item.to_dict() for item in self.items]}

    # --------------------------------------------------------------- yazma
    def add(self, kind: str, due_round: int, data: dict = None) -> PendingItem:
        """Kaydı `due_round` turunun başına yazar."""
        item = PendingItem(kind=str(kind), due_round=int(due_round or 0),
                           data=data if isinstance(data, dict) else {},
                           ts=time.time())
        self.items.append(item)
        return item

    # -------------------------------------------------------------- okuma
    def due(self, round_no: int, kind: str = None) -> list:
        """Vadesi GELMİŞ kayıtlar (kuyruktan silmez).

        `due_round <= round_no`: bir tur atlanırsa (sunucu yeniden başlarsa)
        kayıt kuyrukta unutulmasın, ilk fırsatta devreye girsin."""
        return [i for i in self.items
                if (kind is None or i.kind == kind) and i.due_round <= int(round_no or 0)]

    def take(self, round_no: int, kind: str = None) -> list:
        """Vadesi gelmiş kayıtları kuyruktan ALIR ve döndürür."""
        alinan = self.due(round_no, kind)
        if alinan:
            kalan = [i for i in self.items if i not in alinan]
            self.items = kalan
        return alinan

    def take_one(self, round_no: int, kind: str):
        """Vadesi gelmiş TEK kayıt (en eskisi). Yoksa None."""
        alinan = self.take(round_no, kind)
        return alinan[0] if alinan else None

    def waiting(self, kind: str = None) -> list:
        return [i for i in self.items if kind is None or i.kind == kind]


def birlestir(items) -> dict:
    """Birden fazla `tehdit` kaydını tek devir sözlüğüne toplar.

    Gürültü: en yükseği (iki ayrı ses üst üste binmez, en gürültülüsü sayar).
    Yolculuk: herhangi biri yolculuksa yolculuktur.
    Olaylar: hepsi sırayla uygulanır.
    """
    gurultu, yolculuk, olaylar = 0, False, []
    for item in items or []:
        veri = item.data if isinstance(item, PendingItem) else (item or {})
        try:
            gurultu = max(gurultu, int(veri.get("noise") or 0))
        except (TypeError, ValueError):
            pass
        yolculuk = yolculuk or bool(veri.get("travel"))
        ham = veri.get("events")
        if isinstance(ham, dict):
            ham = [ham]
        if isinstance(ham, list):
            olaylar += [o for o in ham if isinstance(o, dict)]
    return {"noise": gurultu, "travel": yolculuk, "events": olaylar}
