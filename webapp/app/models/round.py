"""Tur (round) — oyunun tur bazlı akışının kaydı.

Eskiden her mesaj anında modele gidiyordu: ilk yazan turu açıyor, diğerleri
onun sahnesine yetişmeye çalışıyordu. Artık bir tur şöyle işler:

  1. Anlatıcı sahneyi yazar ve her karaktere 3-8 seçenek bırakır (sabit değil).
  2. Tur AÇILIR (`acik`). Her oyuncu kendi seçeneğini seçer ya da kendi
     hamlesini yazar; seçim anında sunucu o oyuncunun zarını atar (gerçek
     d100) ve sonucu geri döndürür — arayüz zarı orada animasyonla gösterir.
  3. Seçimler **hafızada** (bu kayıtta) birikir, modele GİTMEZ.
  4. Herkes seçince — ya da süre dolunca — tur TEK seferde gönderilir
     (`round_service.commit`) ve anlatıcı hepsini aynı sahnede çözer.

Süre dolduğunda seçim yapmamış oyuncular için "ani sahne" istenir: dünya
onları beklemez, kararsızlığın kendisi bir olaya dönüşür.
"""

import time
from dataclasses import dataclass, field

# Tur halleri.
OPEN = "acik"          # seçim bekleniyor
SENDING = "gonderiliyor"  # model çağrısı sürüyor
DONE = "kapali"        # gönderildi, yeni tur açılmayı bekliyor


@dataclass
class Pick:
    """Bir oyuncunun bu turdaki seçimi — zarı zaten atılmış haldedir."""

    player: str = ""
    option_id: str = ""
    text: str = ""
    category: str = "serbest"
    roll: object = None
    band: object = None
    custom: bool = False        # havuzdan mı, kendi yazdığı mı
    timeout: bool = False       # süre dolduğu için sunucunun açtığı boş seçim
    ts: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> "Pick":
        data = data or {}
        return cls(
            player=str(data.get("player") or ""),
            option_id=str(data.get("option_id") or ""),
            text=str(data.get("text") or ""),
            category=str(data.get("category") or "serbest"),
            roll=data.get("roll"),
            band=data.get("band"),
            custom=bool(data.get("custom")),
            timeout=bool(data.get("timeout")),
            ts=float(data.get("ts") or 0.0),
        )

    def to_dict(self) -> dict:
        return {"player": self.player, "option_id": self.option_id,
                "text": self.text, "category": self.category, "roll": self.roll,
                "band": self.band, "custom": self.custom, "timeout": self.timeout,
                "ts": self.ts}


@dataclass
class Round:
    """`state["round"]`."""

    no: int = 0
    status: str = DONE
    seconds: int = 0            # 0 = süre yok
    opened_ts: float = 0.0
    picks: dict = field(default_factory=dict)   # {isim: Pick}

    # ------------------------------------------------------------ dönüşüm
    @classmethod
    def from_dict(cls, data) -> "Round":
        data = data if isinstance(data, dict) else {}
        picks = {}
        raw = data.get("picks")
        if isinstance(raw, dict):
            for name, value in raw.items():
                if isinstance(value, dict):
                    pick = Pick.from_dict(value)
                    pick.player = pick.player or str(name)
                    picks[str(name)] = pick
        return cls(
            no=int(data.get("no") or 0),
            status=str(data.get("status") or DONE),
            seconds=int(data.get("seconds") or 0),
            opened_ts=float(data.get("opened_ts") or 0.0),
            picks=picks,
        )

    def to_dict(self) -> dict:
        return {"no": self.no, "status": self.status, "seconds": self.seconds,
                "opened_ts": self.opened_ts,
                "deadline_ts": self.deadline_ts,
                "picks": {name: pick.to_dict() for name, pick in self.picks.items()}}

    # --------------------------------------------------------------- durum
    @property
    def deadline_ts(self):
        """Turun bitiş anı (epoch). Süre yoksa None."""
        if not self.seconds or not self.opened_ts:
            return None
        return self.opened_ts + self.seconds

    @property
    def is_open(self) -> bool:
        return self.status == OPEN

    def remaining(self, now=None):
        """Kalan saniye. Süre yoksa None, süre dolduysa 0."""
        deadline = self.deadline_ts
        if deadline is None:
            return None
        return max(0, int(deadline - (now or time.time())))

    def expired(self, now=None) -> bool:
        remaining = self.remaining(now)
        return remaining is not None and remaining <= 0

    def open(self, no: int, seconds: int) -> None:
        self.no = no
        self.status = OPEN
        self.seconds = max(0, int(seconds or 0))
        self.opened_ts = time.time()
        self.picks = {}

    def waiting_for(self, players) -> list:
        """Henüz seçim yapmamış (ve sahnede olan) oyuncular."""
        return [name for name in players or [] if name not in self.picks]

    def all_picked(self, players) -> bool:
        players = list(players or [])
        return bool(players) and not self.waiting_for(players)

    def add(self, pick: Pick) -> None:
        self.picks[pick.player] = pick

    def ordered_picks(self, players=None) -> list:
        """Seçimler, kadro sırasıyla (kadro verilmezse seçim sırasıyla)."""
        if not players:
            return list(self.picks.values())
        ordered = [self.picks[name] for name in players if name in self.picks]
        ordered += [p for name, p in self.picks.items() if name not in (players or [])]
        return ordered
