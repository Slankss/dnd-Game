"""Senarist katmanı: koşul motoru + olay örgüsü planı.

Koşul motoru iki ayrı yerde kullanılıyor, şeması ikisinde de aynı:

  * SAHNE KATILIMI — bir karakterin sahneye dönme/uyanma koşulu
    (`characters.<isim>.presence.until`)
  * OLAY ÖRGÜSÜ — planlanmış bir olayın (beat) ateşleme koşulu
    (`plot.beats[].when`)

İkisi de `matches(when, ctx)` ile çözülür; `ctx` bir turun anlık görüntüsüdür
(`build_context`). Böylece "şafakta uyanır" ile "gün 101'den sonra kampta
mühür görünür" aynı makineyi kullanır.

Bu modül `server`'ı import ETMEZ (döngüsel import olurdu) — bu yüzden metin
normalleştirme burada kendi kopyasıyla duruyor, bkz. `norm_tr`.
"""

import json
import re
import unicodedata
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PLOT_FILE = BASE_DIR / "data" / "plot.json"

# --------------------------------------------------------------- yardımcılar

_CLOCK_RE = re.compile(r"^\s*(\d{1,2})\s*[:.]\s*(\d{2})")


def norm_tr(text) -> str:
    """Türkçe'ye güvenli normalleştirme (server._norm_tr ile aynı davranış —
    modüller birbirini import etmesin diye kopya). Düz `casefold()` burada
    yanlış çalışır: "İyi".casefold() -> "i̇yi", "ı" olduğu gibi kalır."""
    if not isinstance(text, str):
        return ""
    for src in ("ı", "I", "İ"):
        text = text.replace(src, "i")
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip()


def clock_minutes(clock):
    """'HH:MM' -> gün içindeki dakika. Okunamazsa None."""
    if not isinstance(clock, str):
        return None
    m = _CLOCK_RE.match(clock)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour * 60 + minute


def _as_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


# Anahtarlar normalleştirilmiş biçimde: norm_tr("düşük") -> "dusuk".
TENSION_ORDER = {"dusuk": 0, "orta": 1, "yuksek": 2}


def _tension_rank(value):
    return TENSION_ORDER.get(norm_tr(value))


# ------------------------------------------------------------------ bağlam

def build_context(world_state: dict, world_entry: dict = None) -> dict:
    """Koşulların üzerinde çalıştığı turun anlık görüntüsü."""
    day = _as_int(world_state.get("day")) or 0
    minutes = clock_minutes(world_state.get("clock"))
    flags = world_state.get("flags") or {}
    return {
        "day": day,
        "clock_minutes": minutes,
        # Gün + saat tek eksene indirgenir: "gün 99 saat 06:00" gibi randevular
        # gün dönümünü doğru geçsin diye.
        "abs_minutes": day * 1440 + (minutes if minutes is not None else 0),
        "location": world_state.get("location"),
        "tension": world_state.get("tension"),
        "flags": {k: v for k, v in flags.items() if isinstance(k, str)},
        "world_roll": (world_entry or {}).get("roll"),
    }


# ------------------------------------------------------------------ koşullar
# Desteklenen alanlar (hepsi VE ile bağlanır, bilinmeyen alan YOK SAYILIR):
#   day_gte / day_lte          : int
#   clock_gte / clock_lte      : "HH:MM" (day_gte ile birlikte = randevu anı)
#   location_in                : [str]   (kısmi eşleşme, Türkçe duyarsız)
#   tension_gte                : "düşük" | "orta" | "yüksek"
#   flags_set / flags_unset    : [str]
#   world_roll_lte / _gte      : int

def matches(when, ctx: dict) -> bool:
    """Koşul sağlandı mı? Boş/None koşul HER ZAMAN sağlanır (hemen ateşler)."""
    if not when:
        return True
    if not isinstance(when, dict):
        return False

    day_gte = _as_int(when.get("day_gte"))
    day_lte = _as_int(when.get("day_lte"))
    clock_gte = clock_minutes(when.get("clock_gte"))
    clock_lte = clock_minutes(when.get("clock_lte"))

    # day_gte + clock_gte birlikte verildiyse tek bir randevu anıdır: "gün 99,
    # saat 06:00'dan sonra". Ayrı ayrı karşılaştırmak, gün 100 saat 02:00'de
    # koşulu sonsuza kadar sağlanmaz hale getirirdi (uyuyan karakter hiç
    # uyanmazdı).
    if day_gte is not None and clock_gte is not None:
        if ctx["abs_minutes"] < day_gte * 1440 + clock_gte:
            return False
    else:
        if day_gte is not None and ctx["day"] < day_gte:
            return False
        if clock_gte is not None:
            if ctx["clock_minutes"] is None or ctx["clock_minutes"] < clock_gte:
                return False

    if day_lte is not None and ctx["day"] > day_lte:
        return False
    if clock_lte is not None:
        if ctx["clock_minutes"] is None or ctx["clock_minutes"] > clock_lte:
            return False

    places = when.get("location_in")
    if isinstance(places, str):
        places = [places]
    if isinstance(places, list) and places:
        here = norm_tr(ctx.get("location"))
        if not here:
            return False
        if not any(norm_tr(p) and (norm_tr(p) in here or here in norm_tr(p)) for p in places):
            return False

    want_tension = _tension_rank(when.get("tension_gte"))
    if want_tension is not None:
        have = _tension_rank(ctx.get("tension"))
        if have is None or have < want_tension:
            return False

    flags = ctx.get("flags") or {}
    need_set = when.get("flags_set")
    if isinstance(need_set, str):
        need_set = [need_set]
    for flag in need_set or []:
        if not flags.get(flag):
            return False

    need_unset = when.get("flags_unset")
    if isinstance(need_unset, str):
        need_unset = [need_unset]
    for flag in need_unset or []:
        if flags.get(flag):
            return False

    roll = ctx.get("world_roll")
    roll_lte = _as_int(when.get("world_roll_lte"))
    roll_gte = _as_int(when.get("world_roll_gte"))
    if roll_lte is not None or roll_gte is not None:
        if roll is None:
            return False
        if roll_lte is not None and roll > roll_lte:
            return False
        if roll_gte is not None and roll < roll_gte:
            return False

    return True


def describe_when(when) -> str:
    """Koşulun insan okunur özeti — anlatıcı ekranı ve loglar için."""
    if not isinstance(when, dict) or not when:
        return "koşulsuz"
    parts = []
    if when.get("day_gte") is not None:
        parts.append(f"gün ≥ {when['day_gte']}")
    if when.get("day_lte") is not None:
        parts.append(f"gün ≤ {when['day_lte']}")
    if when.get("clock_gte"):
        parts.append(f"saat ≥ {when['clock_gte']}")
    if when.get("clock_lte"):
        parts.append(f"saat ≤ {when['clock_lte']}")
    places = when.get("location_in")
    if places:
        parts.append("konum: " + ", ".join(places if isinstance(places, list) else [places]))
    if when.get("tension_gte"):
        parts.append(f"gerilim ≥ {when['tension_gte']}")
    if when.get("flags_set"):
        parts.append("bayrak: " + ", ".join(when["flags_set"]))
    if when.get("flags_unset"):
        parts.append("bayrak yok: " + ", ".join(when["flags_unset"]))
    if when.get("world_roll_lte") is not None:
        parts.append(f"dünya zarı ≤ {when['world_roll_lte']}")
    if when.get("world_roll_gte") is not None:
        parts.append(f"dünya zarı ≥ {when['world_roll_gte']}")
    return " ve ".join(parts) if parts else "koşulsuz"


# --------------------------------------------------------- olay örgüsü planı
# (Faz 2'de kullanılacak; şimdilik sadece dosya iskeleti kuruluyor.)

DEFAULT_PLOT = {"version": 1, "updated_day": None, "threads": {}, "beats": [], "seeds": []}


def load_plot() -> dict:
    if not PLOT_FILE.exists():
        return json.loads(json.dumps(DEFAULT_PLOT))
    try:
        data = json.loads(PLOT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(DEFAULT_PLOT))
    if not isinstance(data, dict):
        return json.loads(json.dumps(DEFAULT_PLOT))
    for key, value in DEFAULT_PLOT.items():
        data.setdefault(key, json.loads(json.dumps(value)))
    if not isinstance(data.get("beats"), list):
        data["beats"] = []
    return data


def save_plot(plot: dict) -> None:
    PLOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PLOT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(plot, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PLOT_FILE)
