"""Metin normalleştirme ve saat aritmetiği — tüm modellerin ortak tabanı."""

import re
import unicodedata

# 'HH:MM' ya da 'HH.MM' — anlatıcı ikisini de yazabiliyor.
CLOCK_RE = re.compile(r"^\s*(\d{1,2})\s*[:.]\s*(\d{2})")

# Anlatıcı saati hiç ilerletmediyse bir turun taban süresi (dakika).
DEFAULT_TURN_MINUTES = 20


def norm_tr(text) -> str:
    """Türkçe'ye güvenli normalleştirme. Düz `casefold()` burada sessizce
    yanlış çalışıyor: "İyi".casefold() -> "i̇yi" (nokta ayrı bir birleşen
    olarak kalır, "iyi" ile eşleşmez), "I".casefold() -> "i" ama "ı" olduğu
    gibi kalır. Dört i varyantını da tek bir "i"ye indirger."""
    if not isinstance(text, str):
        return ""
    for src in ("ı", "I", "İ"):
        text = text.replace(src, "i")
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip()


def canonical_name(target, name):
    """Model aynı kişiyi farklı büyük/küçük harfle yazabiliyor ("celil" vs
    "Celil") — mevcut kayda karşılık gelen gerçek anahtarı döner, eşleşme
    yoksa None. Bu olmadan aynı kişi iki ayrı kayıt olarak birikiyor."""
    if not isinstance(name, str):
        return None
    if name in target:
        return name
    lowered = norm_tr(name)
    for key in target:
        if norm_tr(key) == lowered:
            return key
    return None


def clock_minutes(clock):
    """'HH:MM' -> gün içindeki dakika. Okunamazsa None."""
    if not isinstance(clock, str):
        return None
    m = CLOCK_RE.match(clock)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour * 60 + minute


# server.py'deki eski ad — servis katmanı geçişi kolay olsun diye duruyor.
_clock_minutes = clock_minutes


def elapsed_minutes(before: dict, after: dict) -> int:
    """İki tur arasında geçen oyun-içi dakika. Anlatıcı saati ilerletmediyse
    turun kendi ağırlığı kadar (varsayılan) bir süre sayılır.

    `before` / `after` {"day": .., "clock": ..} okuyabilen herhangi bir sözlük
    olabilir (WorldState.clock_snapshot() bunu üretir)."""
    day_delta = (after.get("day") or 0) - (before.get("day") or 0)
    start, end = clock_minutes(before.get("clock")), clock_minutes(after.get("clock"))
    if start is None or end is None:
        # saat okunamıyorsa: gün değiştiyse tam gün, yoksa turun taban süresi
        return max(0, day_delta) * 24 * 60 or DEFAULT_TURN_MINUTES
    minutes = day_delta * 24 * 60 + (end - start)
    if minutes < 0:
        # gün alanı güncellenmemiş ama saat gece yarısını dönmüş
        minutes += 24 * 60
    if minutes == 0:
        minutes = DEFAULT_TURN_MINUTES
    # tek turda 24 saatten fazla geçmesi anlatı hatasıdır; makul tut
    return min(minutes, 24 * 60)


def as_str_list(value) -> list:
    """Model tek eşyayı string, birden fazlasını liste olarak yazabiliyor —
    ikisini de listeye normalize eder."""
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [v.strip() for v in value if isinstance(v, str) and v.strip()]
    return []


def as_int(value):
    """Sayıya çevrilebiliyorsa int, çevrilemiyorsa None (bool sayılmaz)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None
