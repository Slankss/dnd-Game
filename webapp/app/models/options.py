"""Seçenek havuzu — her karaktere sunulan, kategorili hamle seçenekleri.

Anlatıcı her turun sonunda her oyuncu karakteri için 5-10 seçenek üretir ve
bunları state-update bloğunun `options` alanına yazar. Seçenekler:

  * **karakter başınadır** — herkes kendi listesini görür, aynı turda farklı
    yönlere dağılabilirler,
  * **kategorilidir** — riskli / güvenli / gizemli / körü körüne … Kategori
    sadece etiket değil: oyuncunun neyi seçtiği havuza not edilir ve öğrenme
    katmanı bundan ders çıkarır (bkz. learning_service),
  * **uzunluğu serbesttir** — tek satırlık bir refleks de, üç cümlelik bir
    plan da olabilir; sahne neyi gerektiriyorsa.

Bu modül yalnız VERİYİ tanımlar: normalize eder, kategoriyi kanonlaştırır,
sayıyı 5-10 aralığına oturtur. Turun akışı `services/round_service.py`'de.
"""

from dataclasses import dataclass, field

from .text import norm_tr

# Karakter başına sunulan seçenek sayısı — senaryo kuralı.
OPTION_MIN = 5
OPTION_MAX = 10

# Kanonik kategoriler ve anlatıcıya verilen tanımları. Sıra, arayüzdeki
# gösterim sırasıdır.
CATEGORIES = {
    "güvenli": "riski düşük; yavaş, temkinli, geri dönüşü olan hamle",
    "riskli": "yüksek kazanç, yüksek bedel — ters giderse gerçekten acıtır",
    "gizemli": "bilinmeyene dokunur; bilgi/gizem peşinde, sonucu belirsiz",
    "körü körüne": "düşünmeden atılmak — sonuç neredeyse tamamen zara kalır",
    "kurnaz": "hile, aldatma, dolambaçlı yol; güç yerine akıl",
    "insani": "başkasını korur, bedeli kendi üstlenir",
    "acımasız": "kazancı başkasının bedeliyle alır",
    "hazırlık": "şimdi kaybettirir, sonraki turlarda kazandırır",
}

DEFAULT_CATEGORY = "güvenli"

# Modelin yazması muhtemel eş anlamlılar. Tanınmayan kategori DEFAULT'a düşer.
CATEGORY_ALIASES = {
    "guvenli": "güvenli", "temkinli": "güvenli", "savunmacı": "güvenli",
    "savunmaci": "güvenli", "sakin": "güvenli", "safe": "güvenli",
    "riskli": "riskli", "tehlikeli": "riskli", "cüretkar": "riskli",
    "cüretkâr": "riskli", "atak": "riskli", "saldırgan": "riskli",
    "saldirgan": "riskli", "risky": "riskli",
    "gizemli": "gizemli", "gizem": "gizemli", "meraklı": "gizemli",
    "merakli": "gizemli", "keşif": "gizemli", "kesif": "gizemli",
    "araştırma": "gizemli", "arastirma": "gizemli",
    "körü körüne": "körü körüne", "koru korune": "körü körüne",
    "körükörüne": "körü körüne", "delice": "körü körüne",
    "çılgın": "körü körüne", "cilgin": "körü körüne",
    "kurnaz": "kurnaz", "sinsi": "kurnaz", "hileli": "kurnaz",
    "gizlice": "kurnaz", "gizli": "kurnaz", "diplomatik": "kurnaz",
    "insani": "insani", "fedakâr": "insani", "fedakar": "insani",
    "koruyucu": "insani", "merhametli": "insani",
    "acımasız": "acımasız", "acimasiz": "acımasız", "bencil": "acımasız",
    "zalim": "acımasız", "soğukkanlı": "acımasız",
    "hazırlık": "hazırlık", "hazirlik": "hazırlık", "planlı": "hazırlık",
    "planli": "hazırlık", "uzun vadeli": "hazırlık", "yatırım": "hazırlık",
}

# Arayüzdeki rozet tonu (Badge bileşeninin tone değerleri).
CATEGORY_TONES = {
    "güvenli": "ok",
    "riskli": "danger",
    "gizemli": "accent",
    "körü körüne": "warn",
    "kurnaz": "gm",
    "insani": "ok",
    "acımasız": "danger",
    "hazırlık": "neutral",
}

# "Kendi planını yaz" — havuzun dışında kalan, her zaman açık kapı.
FREE_CATEGORY = "serbest"


def canon_category(value) -> str:
    """Modelin yazdığı kategori adını kanonik kategoriye çevirir."""
    if not isinstance(value, str) or not value.strip():
        return DEFAULT_CATEGORY
    raw = value.strip().lower()
    if raw in CATEGORIES:
        return raw
    key = norm_tr(raw)
    for alias, canon in CATEGORY_ALIASES.items():
        if norm_tr(alias) == key:
            return canon
    # "riskli (gürültülü)" gibi süslü yazımlar: ilk kelimeye bak
    first = key.split()[0] if key.split() else ""
    for alias, canon in CATEGORY_ALIASES.items():
        if norm_tr(alias) == first:
            return canon
    return DEFAULT_CATEGORY


@dataclass
class Option:
    """Tek bir seçenek. `id` sunucu tarafından verilir — oyuncu seçimini bu
    kimlikle bildirir, böylece metin uzun olsa bile ağdan geri taşınmaz."""

    id: str = ""
    text: str = ""
    category: str = DEFAULT_CATEGORY
    cost: str = ""

    @classmethod
    def from_dict(cls, data, fallback_id: str = "") -> "Option":
        """Modelden gelen ham seçeneği okur. Düz string de kabul edilir."""
        if isinstance(data, str):
            return cls(id=fallback_id, text=data.strip())
        if not isinstance(data, dict):
            return cls(id=fallback_id, text="")
        text = data.get("text") or data.get("secenek") or data.get("action") or ""
        cost = data.get("cost") or data.get("bedel") or data.get("risk") or ""
        return cls(
            id=str(data.get("id") or fallback_id),
            text=str(text).strip(),
            category=canon_category(data.get("category") or data.get("kategori")),
            cost=str(cost).strip(),
        )

    def to_dict(self) -> dict:
        return {"id": self.id, "text": self.text, "category": self.category,
                "cost": self.cost}

    @property
    def uzun(self) -> bool:
        """Uzun seçenek (çok cümleli plan) mı — havuz istatistiği için."""
        return len(self.text) > 120


@dataclass
class OptionBoard:
    """`world_state.options` — {karakter: [Option, ...]}."""

    by_player: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data) -> "OptionBoard":
        board = cls()
        if not isinstance(data, dict):
            return board
        for player, raw in data.items():
            if not isinstance(raw, list):
                continue
            board.by_player[str(player)] = normalize_list(player, raw)
        return board

    def to_dict(self) -> dict:
        return {player: [o.to_dict() for o in options]
                for player, options in self.by_player.items()}

    def for_player(self, player: str) -> list:
        return self.by_player.get(player) or []

    def find(self, player: str, option_id: str):
        for option in self.for_player(player):
            if option.id == option_id:
                return option
        return None

    def set_player(self, player: str, options: list) -> None:
        self.by_player[player] = options

    def keep_only(self, players) -> None:
        """Ölen/oyundan çıkan karakterlerin seçenekleri havuzda kalmasın."""
        allowed = set(players or [])
        self.by_player = {p: o for p, o in self.by_player.items() if p in allowed}


def normalize_list(player: str, raw: list) -> list:
    """Ham seçenek listesini kimliklendirir, boşları atar, 10 ile sınırlar."""
    options, seen = [], set()
    for i, item in enumerate(raw or []):
        option = Option.from_dict(item, fallback_id=f"{player}-{i + 1}")
        if not option.text:
            continue
        key = norm_tr(option.text)
        if key in seen:  # model aynı seçeneği iki kez yazabiliyor
            continue
        seen.add(key)
        option.id = f"{player}-{len(options) + 1}"
        options.append(option)
        if len(options) >= OPTION_MAX:
            break
    return options
