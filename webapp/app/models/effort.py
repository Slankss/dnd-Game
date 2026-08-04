"""Anlatıcı bu turda ne kadar düşünsün?

Effort SABİT DEĞİL, tura göre seçilir. Ölçüm şunu gösterdi: aynı tur
`high` ile 12 851, `medium` ile 6 932 çıktı jetonu harcıyor ve görünen
sahne yalnızca %3 uzuyor. Aradaki gerçek fark üslupta değil DEFTER
TUTMADA — `high` sunucunun verdiği mesafeye sadık kaldı ve üç karakterin
de yarasını takip etti, `medium` mesafeyi 80 m'den 50 m'ye kaydırdı.

Yani üst seviyenin karşılığı yalnız SÜREKLİLİĞİN pahalıya patladığı
turlarda var: bir karşılaşma fiilen oynanırken, senarist beat'i sahneye
girerken, gerilim tepedeyken, biri ölüme yakınken. Sıradan bir "kapıyı
tut" turunda aynı parayı ödemek boşuna.

Burası SAF: sözlük alır, seviye ve gerekçe döndürür. Sinyalleri toplamak
çağıranın işi (bkz. services/round_service.commit).
"""

from app.models.vitals import VITALS_NUMERIC, clamp_vital
from app.models.wounds import WOUND_SEVERITIES

# claude CLI'ın kabul ettiği seviyeler, ucuzdan pahalıya.
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

# Bir göstergenin "ölüme yakın" sayıldığı eşik (vitals.vital_label ile aynı
# eşik: 85 ve üstü "kritik" diye etiketleniyor).
CRITICAL_VITAL = 85


def canon_effort(value, default=None):
    """Tanınmayan seviye sessizce `default` olur — .env'de yazım hatası
    yüzünden CLI'ın çağrıyı reddetmesindense varsayılana düşmek iyidir."""
    level = str(value or "").strip().lower()
    return level if level in EFFORT_LEVELS else default


def rank(level) -> int:
    """Seviyenin ucuz→pahalı sıradaki yeri; bilinmeyen seviye en ucuz sayılır."""
    level = canon_effort(level)
    return EFFORT_LEVELS.index(level) if level else 0


def critical_players(world_state: dict) -> list:
    """Ölüme yakın karakterler: kritik/ağır yara, enfeksiyon ya da 85+ gösterge.

    `characters` sözlüğü üzerinde çalışır (WorldState.to_dict() çıktısı).
    """
    out = []
    for name, info in (world_state.get("characters") or {}).items():
        if not isinstance(info, dict) or not info.get("alive", True):
            continue
        for wound in info.get("wounds") or []:
            if not isinstance(wound, dict):
                continue
            severity = str(wound.get("severity") or "").strip().lower()
            agir = (severity in WOUND_SEVERITIES
                    and WOUND_SEVERITIES.index(severity)
                    >= WOUND_SEVERITIES.index("ağır"))
            try:
                enfeksiyon = float(wound.get("infection_risk") or 0) >= 60
            except (TypeError, ValueError):
                enfeksiyon = False
            if agir or enfeksiyon:
                out.append(name)
                break
        else:
            vitals = info.get("vitals")
            vitals = vitals if isinstance(vitals, dict) else {}
            if any(clamp_vital(vitals.get(k)) >= CRITICAL_VITAL
                   for k in VITALS_NUMERIC):
                out.append(name)
    return out


def decide(taban="medium", yuksek="high", *, opening=False, encounter=False,
           directive=False, tension=None, critical=(), waiting=False):
    """(seviye, gerekçe) döndürür. Gerekçe boşsa taban seviye kullanıldı.

    Üst seviyeye çıkma nedenleri — hepsi turun çözümünde sunucunun ZATEN
    bildiği şeyler, modele sormaya gerek yok:

    - `opening`   : açılış sahnesi / karakter devralma — dünyanın kurulduğu tur
    - `encounter` : bu turda fiilen bir karşılaşma oynanıyor
    - `directive` : senarist beat'i bu turda sahneye giriyor
    - `tension`   : gerilim "yüksek"
    - `critical`  : ölüme yakın karakter var (ağır/enfekte yara ya da 85+ gösterge)
    - `waiting`   : süre doldu, seçim yapmayanlar için ANİ SAHNE yazılacak

    Taban seviye üsttekine eşit ya da ondan pahalıysa karar zaten tabandır:
    `.env`'de ikisini de `high` yapan biri sürpriz yaşamasın.
    """
    taban = canon_effort(taban, "medium")
    yuksek = canon_effort(yuksek, "high")
    if rank(yuksek) <= rank(taban):
        return taban, ""

    gerekceler = []
    if opening:
        gerekceler.append("açılış/devralma sahnesi")
    if encounter:
        gerekceler.append("karşılaşma oynanıyor")
    if directive:
        gerekceler.append("senarist beat'i")
    if str(tension or "").strip().lower() in ("yüksek", "yuksek"):
        gerekceler.append("gerilim yüksek")
    if critical:
        gerekceler.append("ölüme yakın: " + ", ".join(critical))
    if waiting:
        gerekceler.append("ani sahne")

    if not gerekceler:
        return taban, ""
    return yuksek, " · ".join(gerekceler)
