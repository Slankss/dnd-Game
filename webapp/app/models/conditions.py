"""Koşul motoru (eski `director.py`).

Şema iki ayrı yerde aynen kullanılıyor:

  * SAHNE KATILIMI — bir karakterin sahneye dönme/uyanma koşulu
    (`characters.<isim>.presence.until`)
  * OLAY ÖRGÜSÜ — planlanmış bir olayın (beat) ateşleme koşulu
    (`plot.beats[].when`)

İkisi de `matches(when, ctx)` ile çözülür; `ctx` bir turun anlık görüntüsüdür
(`build_context`). Böylece "şafakta uyanır" ile "gün 101'den sonra kampta
mühür görünür" aynı makineyi kullanır.
"""

from .text import as_int, clock_minutes, norm_tr

# Anahtarlar normalleştirilmiş biçimde: norm_tr("düşük") -> "dusuk".
TENSION_ORDER = {"dusuk": 0, "orta": 1, "yuksek": 2}


def tension_rank(value):
    return TENSION_ORDER.get(norm_tr(value))


# ------------------------------------------------------------------ bağlam

def build_context(world_state, world_entry: dict = None) -> dict:
    """Koşulların üzerinde çalıştığı turun anlık görüntüsü. `world_state` ham
    sözlük ya da WorldState olabilir (ikisi de `.get`/alan üzerinden okunur)."""
    read = world_state.get if isinstance(world_state, dict) else (
        lambda key, default=None: getattr(world_state, key, default))
    day = as_int(read("day")) or 0
    minutes = clock_minutes(read("clock"))
    flags = read("flags") or {}
    return {
        "day": day,
        "clock_minutes": minutes,
        # Gün + saat tek eksene indirgenir: "gün 99 saat 06:00" gibi randevular
        # gün dönümünü doğru geçsin diye.
        "abs_minutes": day * 1440 + (minutes if minutes is not None else 0),
        "location": read("location"),
        "tension": read("tension"),
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

    day_gte = as_int(when.get("day_gte"))
    day_lte = as_int(when.get("day_lte"))
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

    want_tension = tension_rank(when.get("tension_gte"))
    if want_tension is not None:
        have = tension_rank(ctx.get("tension"))
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
    roll_lte = as_int(when.get("world_roll_lte"))
    roll_gte = as_int(when.get("world_roll_gte"))
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
