import json
import os
import re
import secrets
import subprocess
import threading
import time
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

from scenario import (
    SCENARIO_TEXT,
    INITIAL_WORLD_STATE,
    OPENING_HOOKS,
    DEFAULT_PLAYERS,
    START_ITEM_SUGGESTIONS,
    CHARACTER_TEMPLATE,
    GROUP_LABEL,
    GROUP_DISPLAY_NAME,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "data" / "state.json"
LOG_FILE = BASE_DIR / "data" / "game_log.jsonl"
GM_LOG_FILE = BASE_DIR / "data" / "gm_log.jsonl"
SCENARIO_OVERRIDE_FILE = BASE_DIR / "data" / "scenario_override.json"
STATIC_DIR = BASE_DIR / "static"

# claude CLI'ı zaten "claude auth login" ile bağlı olduğunuz claude.ai (Pro/Max)
# hesabınızın kimlik bilgileriyle çalıştırır — ayrı bir API anahtarı gerekmez.
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
MODEL = os.environ.get("CLAUDE_MODEL", "sonnet")
EFFORT = os.environ.get("CLAUDE_EFFORT", "medium")
CLAUDE_TIMEOUT = int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "180"))

# /secrets ekranına (anlatıcı ekranı) girişi kabaca kilitler — gerçek bir
# güvenlik önlemi değil, aynı ağdaki oyuncuların yanlışlıkla spoiler
# görmesini engelleyen hafif bir kapı. .env'de GM_PIN ile değiştirin.
GM_PIN = os.environ.get("GM_PIN", "1453")

app = Flask(__name__, static_folder=None)
lock = threading.Lock()

DICE_BANDS = [
    (1, 5, "Felaket"),
    (6, 25, "Başarısız"),
    (26, 45, "Kısmi Başarı"),
    (46, 70, "Başarı"),
    (71, 95, "Güçlü Başarı"),
    (96, 100, "Kritik"),
]


def band_for(roll: int) -> str:
    for lo, hi, label in DICE_BANDS:
        if lo <= roll <= hi:
            return label
    return "Bilinmiyor"


def roll_d100() -> int:
    return secrets.randbelow(100) + 1


# Dünya zarı — oyuncunun zarından ayrı, oyuncudan bağımsız olarak DÜNYANIN o
# turda ne yaptığını belirler. Oyunculara ASLA gösterilmez, sadece modele ve
# /secrets ekranına gider.
WORLD_DICE_BANDS = [
    (1, 10, "Lehte Kırılma"),
    (11, 35, "Durgun"),
    (36, 65, "Sızıntı"),
    (66, 88, "Baskı"),
    (89, 100, "Kriz"),
]

WORLD_BAND_HINTS = {
    "Lehte Kırılma": "dünya oyuncular lehine döner — beklenmedik kaynak, gecikme, dağılan bir tehdit",
    "Durgun": "aktif tehditler ilerlemez, nefes alma payı doğar",
    "Sızıntı": "aktif zorluklardan biri BİR ADIM ilerler; küçük ama somut yeni bir komplikasyon",
    "Baskı": "aktif zorluk belirgin ilerler (süre kısalır, sayı artar, mesafe kapanır) ya da yeni zorluk doğar",
    "Kriz": "yeni büyük tehdit patlar ya da mevcut zorluk en kötü aşamasına sıçrar",
}


def world_band_for(roll: int) -> str:
    for lo, hi, label in WORLD_DICE_BANDS:
        if lo <= roll <= hi:
            return label
    return "Durgun"


def roll_world_dice(world_state: dict) -> dict:
    roll = roll_d100()
    band = world_band_for(roll)
    entry = {"roll": roll, "band": band, "hint": WORLD_BAND_HINTS[band],
             "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    world_state["world_roll"] = entry
    history = world_state.setdefault("world_roll_history", [])
    history.append({"roll": roll, "band": band, "ts": entry["ts"]})
    del history[:-12]  # son 12 atış yeter
    return entry


def world_dice_note(entry: dict) -> str:
    return (
        f"DÜNYA ZARI (GİZLİ — oyunculara ASLA gösterme, metninde ondan söz etme): "
        f"{entry['roll']} ({entry['band']}) — {entry['hint']}.\n"
        "Bu zar oyuncunun hamlesinden BAĞIMSIZ olarak dünyanın bu turda ne "
        "yaptığını belirler: aktif `challenges` kayıtlarının clock/progress/"
        "severity değerlerini bu banda göre ilerlet ya da sabit tut ve "
        "state-update ile kaydet."
    )


# --------------------------------------------------------------- scenario.json
# scenario.py'deki değerler varsayılandır. data/scenario_override.json varsa
# (arayüzden "senaryo içe aktar" ile yüklenir) onun içeriği önceliklidir —
# server.py'yi yeniden başlatmadan senaryo değiştirilebilir.

def load_scenario():
    if SCENARIO_OVERRIDE_FILE.exists():
        with open(SCENARIO_OVERRIDE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "scenario_text": data.get("scenario_text") or SCENARIO_TEXT,
            "initial_world_state": data.get("initial_world_state") or INITIAL_WORLD_STATE,
            "default_players": data.get("default_players") or DEFAULT_PLAYERS,
            "opening_hooks": data.get("opening_hooks") or OPENING_HOOKS,
            "start_item_suggestions": data.get("start_item_suggestions") or START_ITEM_SUGGESTIONS,
        }
    return {
        "scenario_text": SCENARIO_TEXT,
        "initial_world_state": INITIAL_WORLD_STATE,
        "default_players": DEFAULT_PLAYERS,
        "opening_hooks": OPENING_HOOKS,
        "start_item_suggestions": START_ITEM_SUGGESTIONS,
    }


# ---------------------------------------------------------------- state.json

# Dünya saati/takvimi/havası — state-update ile güncellenen, hepsi metin alan.
TIME_FIELDS = ("time_of_day", "clock", "season", "weather", "temperature")


def default_state():
    scenario = load_scenario()
    return {
        "world_state": json.loads(json.dumps(scenario["initial_world_state"])),
        "next_id": 1,
        "session_id": None,
        "characters_confirmed": False,
        "started": False,
    }


def load_state():
    if not STATE_FILE.exists():
        state = default_state()
        save_state(state)
        return state
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)
    # Devam eden bir oyun, `resources` alanı eklenmeden önce başlamış olabilir —
    # eksikse senaryonun başlangıç stoğuyla doldur, oyun bozulmasın.
    ws = state.setdefault("world_state", {})
    if not ws.get("resources"):
        ws["resources"] = json.loads(json.dumps(load_scenario()["initial_world_state"].get("resources", {})))
    # Aynı şekilde zaman/hava alanları da sonradan eklendi — devam eden oyunda
    # eksikse senaryonun başlangıç değeriyle doldur, yoksa arayüzde ve
    # prompt'ta boş görünüp anlatıcı saati hiç ilerletmiyor.
    missing = [f for f in TIME_FIELDS if not ws.get(f)]
    if missing:
        initial = load_scenario()["initial_world_state"]
        for field in missing:
            if initial.get(field):
                ws[field] = initial[field]
    return state


def save_state(state):
    # Sürüm sayacı: istemciler /api/state?since=<v> ile yoklayıp değişmediyse
    # gövdesiz cevap alır — böylece 1 saniyelik hızlı polling ucuz kalır.
    state["version"] = int(state.get("version", 0)) + 1
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------- game_log.jsonl
# Kalıcı, ekleme-yapılan (append-only) oyun geçmişi dosyası. state.json sadece
# güncel dünya durumunu tutar; tüm oynanış geçmişi burada saklanır.

def append_log(entry: dict) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_log() -> list:
    if not LOG_FILE.exists():
        return []
    entries = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def clear_log() -> None:
    if LOG_FILE.exists():
        LOG_FILE.unlink()


# ---------------------------------------------------------------- gm_log.jsonl
# Anlatıcının /secrets ekranından gönderdiği gizli yönetmen notları + model
# yanıtları — oyunculara asla gösterilmeyen, tamamen ayrı bir günlük.

def append_gm_log(entry: dict) -> None:
    GM_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GM_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_gm_log() -> list:
    if not GM_LOG_FILE.exists():
        return []
    entries = []
    with open(GM_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def clear_gm_log() -> None:
    if GM_LOG_FILE.exists():
        GM_LOG_FILE.unlink()


# ------------------------------------------------------------------ world state

def _as_str_list(value) -> list:
    """Model tek eşyayı string, birden fazlasını liste olarak yazabiliyor —
    ikisini de listeye normalize eder."""
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [v.strip() for v in value if isinstance(v, str) and v.strip()]
    return []


# Kurulum ekranındaki künye alanları. `secret` oyuncu arayüzüne ASLA gitmez.
SHEET_FIELDS = ("profession", "age", "strength", "weakness", "secret")
SECRET_FIELD = "secret"


def build_background(char: dict) -> str:
    """Künyeden okunabilir bir `background` cümlesi kurar — anlatıcı ve
    kenar çubuğu bu alanı kullanıyor."""
    age, profession = char.get("age"), char.get("profession")
    parts = []
    if age:
        parts.append(f"{age} yaşında")
    if profession:
        parts.append(profession)
    return ", ".join(parts)


def build_traits(char: dict) -> str:
    parts = []
    if char.get("strength"):
        parts.append(f"Güçlü yanı: {char['strength']}")
    if char.get("weakness"):
        parts.append(f"Zayıf yanı: {char['weakness']}")
    return " · ".join(parts)


# --------------------------------------------- hayatta kalma göstergeleri
# Hepsinde 0 = gayet iyi, 100 = dayanılmaz. Zar gibi bunlar da sunucunun
# sorumluluğunda: model unutsa bile akan zamana göre kendiliğinden artarlar.
VITALS_NUMERIC = ("fatigue", "hunger", "thirst", "stress")

# Uyanık geçen her SAAT için artış. fatigue ~25 saatte, thirst ~20 saatte,
# hunger ~28 saatte tavan yapar — kıyamet temposu için gerçekçi aralıklar.
VITALS_PER_HOUR = {"fatigue": 4.0, "hunger": 3.5, "thirst": 5.0, "stress": 0.8}

DEFAULT_VITALS = {
    "fatigue": 15, "hunger": 20, "thirst": 20, "stress": 10,
    "awake_hours": 3, "condition": "Dinç",
}


def _clamp_vital(value, default=0):
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def ensure_vitals(entry: dict) -> dict:
    vitals = entry.get("vitals")
    if not isinstance(vitals, dict):
        vitals = dict(DEFAULT_VITALS)
        entry["vitals"] = vitals
    for key in VITALS_NUMERIC:
        vitals[key] = _clamp_vital(vitals.get(key), DEFAULT_VITALS[key])
    return vitals


CLOCK_RE = re.compile(r"^\s*(\d{1,2})\s*[:.]\s*(\d{2})")


def _clock_minutes(clock) -> int:
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


def elapsed_minutes(before: dict, after: dict) -> int:
    """İki tur arasında geçen oyun-içi dakika. Anlatıcı saati ilerletmediyse
    turun kendi ağırlığı kadar (varsayılan) bir süre sayılır."""
    day_delta = (after.get("day") or 0) - (before.get("day") or 0)
    start, end = _clock_minutes(before.get("clock")), _clock_minutes(after.get("clock"))
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


DEFAULT_TURN_MINUTES = 20


def apply_vitals_drift(world_state: dict, minutes: int, skip: dict) -> None:
    """Geçen süre kadar yorgunluk/açlık/susuzluk biriktirir. Anlatıcının bu
    turda AÇIKÇA yazdığı alanlara (uyudu/yedi/içti) dokunmaz — `skip`
    {isim: {alan, ...}} biçiminde o alanları taşır."""
    if minutes <= 0:
        return
    hours = minutes / 60.0
    for section in ("characters", "npcs"):
        for name, entry in (world_state.get(section) or {}).items():
            if not isinstance(entry, dict) or entry.get("alive") is False:
                continue
            # NPC'lerde sadece anlatıcı bir kez vitals açtıysa takip edilir
            if section == "npcs" and not isinstance(entry.get("vitals"), dict):
                continue
            vitals = ensure_vitals(entry)
            touched = skip.get(name) or set()
            for key, rate in VITALS_PER_HOUR.items():
                if key in touched:
                    continue
                vitals[key] = _clamp_vital(vitals[key] + rate * hours)
            if "awake_hours" not in touched:
                try:
                    awake = float(vitals.get("awake_hours") or 0)
                except (TypeError, ValueError):
                    awake = 0.0
                vitals["awake_hours"] = round(awake + hours, 1)


def _vital_label(vitals: dict) -> str:
    worst_key, worst = None, -1
    for key in VITALS_NUMERIC:
        if vitals.get(key, 0) > worst:
            worst_key, worst = key, vitals.get(key, 0)
    names = {"fatigue": "yorgunluk", "hunger": "açlık",
             "thirst": "susuzluk", "stress": "stres"}
    if worst >= 85:
        return f"kritik {names[worst_key]}"
    if worst >= 65:
        return f"ağır {names[worst_key]}"
    if worst >= 40:
        return f"belirgin {names[worst_key]}"
    return "formda"


def vitals_note(world_state: dict) -> str:
    """Her turda modele verilen güncel gösterge tablosu — zar yorumunu
    bunlara göre kaydırması için."""
    lines = []
    for section in ("characters", "npcs"):
        for name, entry in (world_state.get(section) or {}).items():
            if not isinstance(entry, dict) or entry.get("alive") is False:
                continue
            vitals = entry.get("vitals")
            if not isinstance(vitals, dict):
                continue
            awake = vitals.get("awake_hours")
            lines.append(
                f"- {name}: yorgunluk {vitals.get('fatigue', 0)}, "
                f"açlık {vitals.get('hunger', 0)}, susuzluk {vitals.get('thirst', 0)}, "
                f"stres {vitals.get('stress', 0)}"
                + (f", {awake} saattir uyanık" if awake not in (None, "") else "")
                + f" → {_vital_label(vitals)}"
            )
    if not lines:
        return ""
    return (
        "HAYATTA KALMA GÖSTERGELERİ (0 = iyi, 100 = dayanılmaz — sunucu akan "
        "zamana göre otomatik artırdı, GÜNCEL değerler bunlar):\n"
        + "\n".join(lines)
        + "\nBu değerleri bu turun anlatısında FİİLEN kullan: zar bandını "
        "yorgunluk/açlık/susuzluk seviyesine göre kaydır (40+ belirgin, 65+ "
        "bir kademe aşağı, 85+ neredeyse kesin bedelli), ve sonucu bir "
        "cümleyle değil yapılan işin SONUCUYLA göster. Bir karakter bu turda "
        "uyuduysa/yediyse/içtiyse `vitals` alanını state-update ile GÜNCELLE; "
        "aksi halde yazma, sunucu kendisi ilerletir."
    )


def _norm_tr(text) -> str:
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


# ------------------------------------------------------------------ yaralar
WOUND_SEVERITIES = ("hafif", "orta", "ağır", "kritik")

# Tedavi edilmemiş yaranın saat başına enfeksiyon riski artışı. Tedavi
# edilmiş yara yavaşça temizlenir (negatif).
INFECTION_PER_HOUR = {"hafif": 0.6, "orta": 1.2, "ağır": 2.0, "kritik": 3.0}
INFECTION_TREATED_PER_HOUR = -1.0


def _wound_key(desc: str) -> str:
    return _norm_tr(desc)


def _normalize_wound(raw, day=None, clock=None) -> dict:
    """Model yarayı düz string ya da sözlük olarak yazabiliyor; ikisini de
    aynı yapıya çevirir."""
    if isinstance(raw, str):
        raw = {"desc": raw}
    if not isinstance(raw, dict):
        return None
    desc = str(raw.get("desc") or raw.get("description") or "").strip()
    if not desc:
        return None
    severity = str(raw.get("severity") or "orta").strip().casefold()
    if severity not in WOUND_SEVERITIES:
        severity = "orta"
    return {
        "desc": desc,
        "severity": severity,
        "infection_risk": _clamp_vital(raw.get("infection_risk"), 15),
        "treated": bool(raw.get("treated")),
        "notes": str(raw.get("notes") or "").strip(),
        "since_day": raw.get("since_day", day),
        "since_clock": raw.get("since_clock", clock),
    }


def _merge_wounds(entry: dict, fields: dict, day=None, clock=None) -> None:
    wounds = entry.setdefault("wounds", [])
    if not isinstance(wounds, list):
        wounds = entry["wounds"] = []

    def _find(fragment):
        key = _wound_key(fragment)
        if not key:
            return None
        for w in wounds:
            wk = _wound_key(w.get("desc"))
            if key == wk or key in wk or wk in key:
                return w
        return None

    raw_add = fields.get("wounds_add")
    if isinstance(raw_add, (str, dict)):
        raw_add = [raw_add]
    for raw in raw_add or []:
        wound = _normalize_wound(raw, day, clock)
        if wound and not _find(wound["desc"]):
            wounds.append(wound)

    updates = fields.get("wounds_update")
    if isinstance(updates, dict):
        for fragment, changes in updates.items():
            wound = _find(fragment)
            if wound is None or not isinstance(changes, dict):
                continue
            if "severity" in changes:
                sev = str(changes["severity"]).strip().casefold()
                if sev in WOUND_SEVERITIES:
                    wound["severity"] = sev
            if "infection_risk" in changes:
                wound["infection_risk"] = _clamp_vital(
                    changes["infection_risk"], wound["infection_risk"])
            if "treated" in changes:
                wound["treated"] = bool(changes["treated"])
            if isinstance(changes.get("notes"), str):
                wound["notes"] = changes["notes"].strip()
            if isinstance(changes.get("desc"), str) and changes["desc"].strip():
                wound["desc"] = changes["desc"].strip()

    healed = fields.get("wounds_heal")
    if isinstance(healed, str):
        healed = [healed]
    for fragment in healed or []:
        wound = _find(fragment)
        if wound is not None:
            wounds.remove(wound)


def advance_infections(world_state: dict, minutes: int) -> None:
    """Tedavi edilmemiş yaraların enfeksiyon riski zamanla yükselir; tedavi
    edilmişler yavaşça temizlenir. Göstergeler gibi bu da sunucunun işi —
    anlatıcı unutsa bile yara ilerler."""
    if minutes <= 0:
        return
    hours = minutes / 60.0
    for section in ("characters", "npcs"):
        for entry in (world_state.get(section) or {}).values():
            if not isinstance(entry, dict) or entry.get("alive") is False:
                continue
            for wound in entry.get("wounds") or []:
                if not isinstance(wound, dict):
                    continue
                rate = (INFECTION_TREATED_PER_HOUR if wound.get("treated")
                        else INFECTION_PER_HOUR.get(wound.get("severity"), 1.2))
                wound["infection_risk"] = _clamp_vital(
                    (wound.get("infection_risk") or 0) + rate * hours)


def normalize_wound_status(world_state: dict) -> None:
    """Kolunda kanayan yara varken `status: "İyi"` kalmasın — anlatıcı bunu
    sık sık atlıyor ve oyuncu kenar çubuğunda sağlıklı görünüyordu."""
    healthy = {_norm_tr(w) for w in ("iyi", "sağlıklı", "normal", "formda", "")}
    for section in ("characters", "npcs"):
        for entry in (world_state.get(section) or {}).values():
            if not isinstance(entry, dict) or entry.get("alive") is False:
                continue
            wounds = [w for w in (entry.get("wounds") or []) if isinstance(w, dict)]
            if not wounds:
                continue
            if _norm_tr(entry.get("status")) not in healthy:
                continue
            worst = max(WOUND_SEVERITIES.index(w.get("severity", "orta"))
                        if w.get("severity") in WOUND_SEVERITIES else 1
                        for w in wounds)
            infected = any((w.get("infection_risk") or 0) >= 60 for w in wounds)
            if infected:
                entry["status"] = "Enfekte olabilir"
            elif worst >= WOUND_SEVERITIES.index("ağır"):
                entry["status"] = "Ağır yaralı"
            else:
                entry["status"] = "Yaralı"


def wounds_note(world_state: dict) -> str:
    lines = []
    for section in ("characters", "npcs"):
        for name, entry in (world_state.get(section) or {}).items():
            if not isinstance(entry, dict) or entry.get("alive") is False:
                continue
            for wound in entry.get("wounds") or []:
                if not isinstance(wound, dict):
                    continue
                risk = wound.get("infection_risk") or 0
                flag = ("  ⚠️ ENFEKSİYON BELİRTİLERİ BAŞLADI" if risk >= 85
                        else "  ⚠️ enfeksiyon kapıda" if risk >= 60 else "")
                lines.append(
                    f"- {name}: {wound.get('desc')} ({wound.get('severity')}, "
                    f"enfeksiyon riski {risk}, "
                    + ("tedavi edildi" if wound.get("treated") else "TEDAVİ EDİLMEDİ")
                    + (f", not: {wound['notes']}" if wound.get("notes") else "")
                    + ")"
                    + flag
                )
    if not lines:
        return ""
    return (
        "AÇIK YARALAR (iyileşene kadar kayıtlı kalır — bu turda da FİİLEN "
        "hissedilsinler: ağrı, kanama, o uzvu kullanamama):\n"
        + "\n".join(lines)
        + "\nEnfeksiyon riski tedavi edilmedikçe zamanla kendiliğinden "
        "yükselir. 60'ı geçince belirtiler (ateş, titreme, kızarma) başlasın, "
        "85'i geçince bunu ölümcül bir `challenges` kaydına dönüştür. Tedavi "
        "edildiyse `wounds_update` ile `treated: true` yaz ve harcanan "
        "malzemeyi envanterden/`resources`'tan DÜŞ."
    )


def _merge_person_like(target: dict, name: str, fields: dict,
                       day=None, clock=None) -> set:
    """`characters` ve `npcs` için ortak birleştirme mantığı (background/
    traits/status/location/notes üzerine yazar; inventory ekler/çıkarır;
    relationships ve vitals iç içe günceller). Anlatıcının bu turda elle
    yazdığı `vitals` alanlarını döndürür — otomatik artıştan muaf tutulurlar."""
    entry = target.setdefault(
        name,
        {"background": None, "traits": None, "status": "İyi", "alive": True,
         "location": None, "inventory": [], "relationships": {}, "notes": ""},
    )
    for scalar_key in ("background", "traits", "status", "location", "notes") + SHEET_FIELDS:
        if scalar_key in fields:
            entry[scalar_key] = fields[scalar_key]

    if isinstance(fields.get("alive"), bool):
        entry["alive"] = fields["alive"]

    if isinstance(fields.get("relationships"), dict):
        entry.setdefault("relationships", {}).update(fields["relationships"])

    _merge_wounds(entry, fields, day, clock)

    inv = entry.setdefault("inventory", [])
    # Elden çıkmış eşyaların kaydı. Model sonraki turlarda hafızasından TAM
    # listeyi tekrar yazınca (atılan madalyonu içeren eski liste gibi) eşya
    # sessizce cebe geri dönüyordu — hikaye tutarsızlaşıyordu. Bir eşya ancak
    # sahnede FİİLEN geri alınırsa (`inventory_add`) bu listeden çıkar.
    lost = entry.setdefault("lost_items", [])
    lost_keys = {_norm_tr(i) for i in lost}

    added = _as_str_list(fields.get("inventory_add"))
    bulk = _as_str_list(fields.get("inventory"))
    removed = _as_str_list(fields.get("inventory_remove"))

    # açık geri alma: eşya tekrar sahiplenildi
    for item in added:
        key = _norm_tr(item)
        if key in lost_keys:
            lost_keys.discard(key)
            lost[:] = [i for i in lost if _norm_tr(i) != key]

    # Model bazen `inventory_add` yerine doğrudan tam listeyi (`inventory`)
    # ya da tek bir eşyayı düz string olarak yazıyor; üçü de kabul ediliyor.
    # `inventory` üzerine YAZMAZ, birleştirir (model listeyi eksik yazarsa
    # mevcut eşyalar kaybolmasın) — ama elden çıkmış eşyayı geri getiremez.
    added_keys = {_norm_tr(i) for i in added}
    for item in bulk + added:
        if not item or item in inv:
            continue
        key = _norm_tr(item)
        if key in lost_keys and key not in added_keys:
            continue
        inv.append(item)

    for item in removed:
        key = _norm_tr(item)
        inv[:] = [i for i in inv if _norm_tr(i) != key]
        if key not in lost_keys:
            lost.append(item)
            lost_keys.add(key)

    # Anlatıcının yazdığı gösterge değerleri sunucunun otomatik artışını EZER
    # (uyudu / yedi / içti). Dokunulan alanlar çağırana döner.
    touched = set()
    if isinstance(fields.get("vitals"), dict):
        vitals = ensure_vitals(entry)
        for key, value in fields["vitals"].items():
            if key in VITALS_NUMERIC:
                vitals[key] = _clamp_vital(value, vitals.get(key, 0))
                touched.add(key)
            elif key == "awake_hours":
                try:
                    vitals["awake_hours"] = max(0.0, round(float(value), 1))
                    touched.add("awake_hours")
                except (TypeError, ValueError):
                    pass
            elif key == "condition" and isinstance(value, str):
                vitals["condition"] = value.strip()
    return touched


TENSION_LEVELS = ("düşük", "orta", "yüksek")

# "+3" / "-12" gibi göreli miktar değişimleri
RESOURCE_DELTA_RE = re.compile(r"^\s*([+-])\s*(\d+(?:[.,]\d+)?)\s*$")


def _as_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _tidy_qty(value):
    """3.0 -> 3, 2.5 -> 2.5, negatif -> 0 (stok eksiye düşemez)."""
    if value is None:
        return 0
    value = max(0, value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _merge_resources(target: dict, patch: dict) -> None:
    """Grup stoğunu (kategori > kalem > miktar) birleştirir. Kalem değeri
    üç şekilde gelebilir: kesin sayı (12), göreli değişim ("-2"/"+9") ya da
    detaylı sözlük ({"qty": .., "unit": .., "notes": ..})."""
    for category, items in patch.items():
        if not isinstance(items, dict):
            continue
        cat_key = canonical_name(target, category) or category
        cat = target.setdefault(cat_key, {})
        for raw_name, value in items.items():
            item_key = canonical_name(cat, raw_name) or raw_name
            entry = cat.setdefault(item_key, {"qty": 0, "unit": "adet", "notes": ""})
            current = _as_number(entry.get("qty")) or 0

            num = _as_number(value)
            if num is not None:
                entry["qty"] = _tidy_qty(num)
            elif isinstance(value, str):
                m = RESOURCE_DELTA_RE.match(value)
                if m:
                    delta = float(m.group(2).replace(",", "."))
                    entry["qty"] = _tidy_qty(current + (delta if m.group(1) == "+" else -delta))
                else:
                    entry["notes"] = value  # "birkaç kutu" gibi serbest metin
            elif isinstance(value, dict):
                qty = value.get("qty")
                qty_num = _as_number(qty)
                if qty_num is not None:
                    entry["qty"] = _tidy_qty(qty_num)
                elif isinstance(qty, str):
                    m = RESOURCE_DELTA_RE.match(qty)
                    if m:
                        delta = float(m.group(2).replace(",", "."))
                        entry["qty"] = _tidy_qty(current + (delta if m.group(1) == "+" else -delta))
                for field in ("unit", "notes"):
                    if isinstance(value.get(field), str):
                        entry[field] = value[field]


def canonical_name(target: dict, name: str):
    """Model aynı kişiyi farklı büyük/küçük harfle yazabiliyor ("celil" vs
    "Celil") — mevcut kayda karşılık gelen gerçek anahtarı döner, eşleşme
    yoksa None. Bu olmadan aynı kişi iki ayrı kayıt olarak birikiyor."""
    if not isinstance(name, str):
        return None
    if name in target:
        return name
    lowered = _norm_tr(name)
    for key in target:
        if _norm_tr(key) == lowered:
            return key
    return None


def alive_players(world_state: dict) -> list:
    return [
        name
        for name, info in (world_state.get("characters") or {}).items()
        if info.get("alive", True)
    ]


# Her normal turda modele verilen "defter tutma" hatırlatması. Envanter ve
# grup stoğu buraya eklenmeden önce model bunları çoğu turda atlıyordu —
# hikayede ortaya çıkan bir bıçak arayüzdeki envanterde hiç görünmüyordu.
UPKEEP_REMINDER = (
    "(3) ENVANTER KONTROLÜ (her tur, atlama): bu turun anlatısında bir "
    "karakterin elinde/üzerinde/cebinde bir eşya geçtiyse ve o eşya GÜNCEL "
    "DÜNYA DURUMU'nda o karakterin `inventory` listesinde YOKSA, aynı bloğa "
    "`inventory_add` ile ekle. Bir karakter bu turda bir eşyayı ATTIYSA, "
    "verdiyse, kaybettiyse, tükettiyse ya da kırdıysa AYNI TURDA "
    "`inventory_remove` ile çıkarmak ZORUNDASIN — yazmazsan eşya cebinde "
    "kalır ve hikaye tutarsızlaşır (atılan bir madalyon saatler sonra tekrar "
    "cepte çıkar). Anlatıda var olup envanterde görünmeyen ya da anlatıda "
    "elden çıkıp envanterde duran eşya kalmasın — oyuncular envanteri "
    "arayüzden canlı izliyor.\n"
    "(4) GRUP STOĞU: SADECE ortak bir depo/klan gerçekten varsa geçerlidir. "
    "Yoksa `resources`'a hiçbir şey yazma. Varsa ve bu turda bir şey "
    "harcandıysa/eklendiyse (mermi, yiyecek, su, ilaç, yakıt, hayvan, mahsul, "
    'takas malı...) güncelle — ör. {"Mühimmat": {"9mm mermi": "-3"}, '
    '"Yiyecek": {"Konserve": "+4"}}.\n'
    "(5) ZORLUKLAR: sahnedeki aktif `challenges` kayıtlarının `clock` ve "
    "`progress` alanlarını bu turda GÜNCELLE (oyuncu zarı ne kadar ilerletti, "
    "dünya zarı sorunu ne kadar büyüttü). Zorluk kapandıysa status'ü "
    "'çözüldü'/'başarısız' yap ve sonucunu gerçekten uygula. Sahnede aktif "
    "zorluk kalmadıysa yenisini aç.\n"
    "(6) BULMACALAR: oyuncular bu turda bir gizemle ilgili somut bir şey "
    "öğrendiyse `narrator.puzzles.<ad>` altında `progress` (0-100), "
    "`clues_found` ve `next_step` alanlarını güncelle — anlatıcı ekranı "
    "ilerlemeyi buradan izliyor.\n"
    "(7) ZAMAN VE HAVA (her tur, atlama): bu turdaki aksiyonların gerçekçi "
    "süresi kadar `clock`'u ilerlet, gerekirse `time_of_day`'i değiştir. "
    "Gece yarısı geçildiyse `day`'i 1 artır ve gün dönümü muhasebesini "
    "(tüketim, hayvan/tarım, iyileşme) `resources` ile birlikte işle. "
    "Hava değiştiyse `weather`/`temperature` alanlarını güncelle ve etkisini "
    "sahnede göster.\n"
    "Ayrıca gerçekten değişen başka alanlar varsa (karakter durumu/ilişkisi, "
    "fraksiyon tavrı, gün, konum, yeni NPC, narrator.upcoming_events vb.) "
    "aynı bloğa ekle.\n"
    "SON OLARAK: yanıtını 'SAHNE YAPISI' bölümündeki **DURUM** + **SEÇENEKLER** "
    "bloğuyla bitir. Bu blok state-update'in DIŞINDA, oyuncuya görünen metnin "
    "son parçası olsun."
)


def visible_timeline_note(log: list, limit: int = 6) -> str:
    """Oyunculara FİİLEN gösterilmiş son akış. İki kanal (oyuncu sohbeti +
    anlatıcı kanalı) aynı Claude oturumunu paylaşıyor; bu blok olmadan model
    bazen hikayeyi, oyuncuların hiç görmediği GM onay mesajından devam
    ettiriyor ve iki taraf birbirini tutmuyordu."""
    lines = ["OYUNCULARIN EKRANINDA GÖRÜNEN SON AKIŞ (hikaye buradan devam eder):"]
    for entry in (log or [])[-limit:]:
        role = entry.get("role")
        text = (entry.get("text") or "").strip().replace("\n", " ")
        if role == "user":
            roll = ""
            if entry.get("roll") is not None:
                roll = f" (ZAR {entry['roll']} - {entry.get('band')})"
            lines.append(f"[{entry.get('player', '?')}{roll}] {text[:300]}")
        elif role == "system":
            lines.append(f"[SİSTEM] {text[:300]}")
        else:
            lines.append(f"[ANLATICI] {text[:600]}")
    if len(lines) == 1:
        lines.append("(henüz gösterilmiş bir sahne yok)")
    lines.append(
        "ÖNEMLİ — İKİ KANAL TEK HİKAYE: konuşma geçmişinde `[ANLATICI NOTU - "
        "GİZLİ]` etiketli mesajlar ve onlara verdiğin kısa onaylar olabilir. "
        "Bunlar oyuncuların GÖRMEDİĞİ ayrı bir yönetim kanalıdır — hikayeyi o "
        "onaylardan değil, YUKARIDAKİ oyuncu akışından devam ettir ve "
        "oyunculara görmedikleri bir şeye atıfta bulunma. `[ANLATICI MÜDAHALESİ "
        "- ...]` etiketiyle yayınlanan sahneler ise oyuncuların gördüğü akışın "
        "parçasıdır, onlara normal şekilde atıfta bulunabilirsin."
    )
    return "\n".join(lines)


def inventory_note(world_state: dict) -> str:
    """Kimde ne var — her turda modele düz metin olarak verilir. JSON'un içine
    gömülü kalınca model bunu sık sık gözden kaçırıp olmayan eşya
    kullandırıyordu ("bıçağını çıkardı" — bıçağı yokken)."""
    lines = ["ENVANTER GERÇEĞİ (bu turda kimin üzerinde fiilen ne var):"]
    for name, info in (world_state.get("characters") or {}).items():
        if not info.get("alive", True):
            continue
        inv = info.get("inventory") or []
        lines.append(f"- {name}: {', '.join(inv) if inv else '(üzerinde hiçbir eşya yok)'}")
        lost = info.get("lost_items") or []
        if lost:
            lines.append(
                f"  · {name} ARTIK ŞUNLARA SAHİP DEĞİL (attı/verdi/kaybetti/"
                f"tüketti — hikayede fiilen geri almadıkça bir daha elinde "
                f"OLAMAZ): {', '.join(lost)}"
            )
    has_stock = any(
        isinstance(cat, dict) and cat
        for cat in (world_state.get("resources") or {}).values()
    )
    if not has_stock:
        lines.append(
            "ORTAK STOK: YOK. Grubun bir klanı, topluluğu ya da deposu henüz "
            "yok — elde SADECE yukarıdaki kişisel eşyalar var. Depodan, "
            "erzaktan, 'stoğumuzdan' söz ETME ve `resources` altına kendiliğinden "
            "kalem YAZMA. Stok ancak grup bir topluluk kurarsa/katılırsa ya da "
            "oyuncular açıkça sayım isterse doğar."
        )
    lines.append(
        "KURAL: bir karakter SADECE bu listedeki eşyaları, grubun `resources` "
        "stoğundan sahnede fiilen aldığı bir şeyi, ya da bulunduğu ortamda "
        "gerçekten var olan bir nesneyi kullanabilir. Listede olmayan bir eşyayı "
        "ASLA kullandırma — oyuncu mesajında 'bıçağımı çekiyorum' gibi yazsa "
        "bile bu sadece o oyuncunun iddiasıdır, gerçek değildir. Böyle bir "
        "durumda sahnede gerçekçi biçimde düzelt (eli boşa gider, cebinde "
        "olmadığını fark eder, eldeki başka bir şeyle idare etmek zorunda "
        "kalır) ve bunu kuru bir ret değil, küçük bir gerilim anına çevir."
    )
    lines.append(
        "SÜREKLİLİK: elden çıkmış bir eşya kendiliğinden geri GELMEZ. Bir "
        "karakter bir şeyi attıysa/verdiyse/kaybettiyse o şey artık bulunduğu "
        "yerdedir; ancak o yere geri dönüp FİİLEN alırlarsa envantere geri "
        "girer (o zaman `inventory_add` yaz). Aradan saatler geçmesi eşyayı "
        "cebe geri koymaz."
    )
    return "\n".join(lines)


# "envanter sayımı yapalım", "depoda ne kadar mermi var" gibi taleplerde
# arayüzdeki Grup Kaynakları paneli açılır ve anlatıcıdan kalem kalem döküm
# istenir. Panel bunun dışında kapalı durur — sürekli açık bir stok tablosu
# sahnenin içinde doğal durmuyordu.
INVENTORY_INTENT_RE = re.compile(
    r"(envanter|stok\b|sayım|sayim|depoyu\s*(?:say|kontrol)|"
    r"kaç\s+(?:tane\s+)?(?:mermi|fişek|tavuk|keçi|konserve|litre|kutu)|"
    r"ne\s+kadar\s+(?:yiyecek|su|mermi|fişek|ilaç|yakıt|erzak|mahsul)|"
    r"kaynak(?:lar)?\s*(?:durum|listesi|sayım|kontrol))",
    re.IGNORECASE,
)

INVENTORY_REPORT_INSTRUCTION = (
    "ENVANTER SAYIMI TALEBİ: bu turda oyuncular grubun stoğunu saymak/kontrol "
    "etmek istiyor. Sahneyi normal kur, ama içinde sayımı KALEM KALEM ve "
    "SAYIYLA aktar (kategori kategori: yiyecek, su, tarım, hayvan, silah, "
    "mühimmat, tıbbi, yakıt, takas). Sayım sırasında hikaye gereği bir "
    "tutarsızlık çıkarabilirsin (eksik çıkan bir şey, bozulmuş erzak) — "
    "çıkarırsan `resources` alanını buna göre güncelle."
)


def starting_items_note(world_state: dict) -> str:
    lines = []
    for name, info in (world_state.get("characters") or {}).items():
        inv = info.get("inventory") or []
        lines.append(f"- {name}: {', '.join(inv) if inv else '(eşya seçmedi)'}")
    return "\n".join(lines) if lines else "(karakter yok)"


def character_sheets_note(world_state: dict) -> str:
    """Kurulum ekranından gelen karakter künyeleri — sırlar dahil. Sadece
    modele gider, oyuncu arayüzüne asla."""
    lines = []
    for name, info in (world_state.get("characters") or {}).items():
        bits = []
        if info.get("age"):
            bits.append(f"yaş {info['age']}")
        if info.get("profession"):
            bits.append(f"meslek: {info['profession']}")
        if info.get("strength"):
            bits.append(f"güçlü yanı: {info['strength']}")
        if info.get("weakness"):
            bits.append(f"zayıf yanı: {info['weakness']}")
        inv = info.get("inventory") or []
        bits.append(f"başlangıç eşyası: {', '.join(inv) if inv else '(seçmedi)'}")
        lines.append(f"- {name} — " + "; ".join(bits))
        if info.get(SECRET_FIELD):
            lines.append(
                f"  · GİZLİ SIR (sadece sen bilirsin, asla açıklama): {info[SECRET_FIELD]}"
            )
    return "\n".join(lines) if lines else "(karakter yok)"


def sheets_complete(world_state: dict) -> bool:
    characters = world_state.get("characters") or {}
    return bool(characters) and all(c.get("background") for c in characters.values())


def roster_note(world_state: dict) -> str:
    """Her turda modele verilen sabit oyuncu kadrosu hatırlatması — model
    hikayenin ortasında isim uydurmasın/karıştırmasın diye."""
    characters = world_state.get("characters") or {}
    alive = alive_players(world_state)
    dead = [n for n in characters if n not in alive]
    lines = [
        "OYUNCU KARAKTERLERİ (SABİT LİSTE — bunların dışında oyuncu karakteri YOKTUR): "
        + (", ".join(alive) if alive else "(yok)")
    ]
    if dead:
        lines.append(
            "ÖLMÜŞ oyuncu karakterleri (kalıcı olarak öldü, canlı gibi sahneye sokma): "
            + ", ".join(dead)
        )
    lines.append(
        "Bu isimleri harfi harfine, aynı yazımla kullan. Yeni bir oyuncu karakteri "
        "UYDURMA, mevcut birini başka isimle anma. Hikayedeki diğer herkes NPC'dir "
        "ve state-update'te `npcs` altına yazılır."
    )
    if any((characters.get(n) or {}).get(SECRET_FIELD) for n in alive):
        lines.append(
            "KÜNYE HATIRLATMASI: her karakterin `profession`/`age`/`strength`/"
            "`weakness` alanları BAĞLAYICIDIR — sahnede ve zar yorumunda "
            "kullan. `secret` alanı SADECE SANA aittir: asla açıklama, "
            "listeleme ya da başka bir karaktere söyletme; sadece gerilim "
            "kaynağı olarak, ima ve baskı yoluyla kullan."
        )
    return "\n".join(lines)


def deep_merge_world_state(world_state: dict, patch: dict,
                           vitals_touched: dict = None) -> None:
    """`vitals_touched` verilirse, anlatıcının bu turda elle yazdığı
    gösterge alanları {isim: {alan}} olarak oraya biriktirilir."""
    # Model gün sayısını bazen "98" diye string yazıyor; eskiden bu sessizce
    # yok sayılıp başlıktaki gün sayacı hiç ilerlemiyordu.
    day = patch.get("day")
    if isinstance(day, bool):
        day = None
    if isinstance(day, str) and day.strip().isdigit():
        day = int(day.strip())
    if isinstance(day, (int, float)):
        world_state["day"] = int(day)

    # Zaman ve hava: anlatıcı her turda ilerletir (saat akar, gün döner, hava
    # değişir). Boş string gönderilirse mevcut değer korunur — model alanı
    # "unutup" boş bıraktığında dünya saati sıfırlanmasın.
    for field in TIME_FIELDS:
        value = patch.get(field)
        if isinstance(value, str) and value.strip():
            world_state[field] = value.strip()

    if "location" in patch and isinstance(patch["location"], str):
        world_state["location"] = patch["location"]

    if patch.get("tension") in TENSION_LEVELS:
        world_state["tension"] = patch["tension"]

    if "factions" in patch and isinstance(patch["factions"], dict):
        target = world_state.setdefault("factions", {})
        for key, fields in patch["factions"].items():
            if not isinstance(fields, dict):
                continue
            entry = target.setdefault(key, {})
            entry.update(fields)

    # Oyuncu kadrosu (`characters`) kurulumda sabitlenir ve model tarafından
    # GENİŞLETİLEMEZ. Model tanımadık bir ismi `characters` altına yazarsa
    # (hikayede geçen birini oyuncu sanması, ya da isim uydurması) o kayıt
    # sessizce `npcs`'e yönlendirilir — aksi halde uydurma isim rostere girip
    # sonraki turlarda dünya durumuyla birlikte modele geri besleniyor ve
    # kalıcılaşıyordu. Ters yön de düzeltilir: `npcs` altına yazılmış gerçek
    # bir oyuncu karakteri `characters`'a geri alınır.
    characters = world_state.setdefault("characters", {})
    npcs = world_state.setdefault("npcs", {})

    for section in ("characters", "npcs"):
        if not isinstance(patch.get(section), dict):
            continue
        for name, fields in patch[section].items():
            if not isinstance(fields, dict):
                continue
            day, clock = world_state.get("day"), world_state.get("clock")
            pc_key = canonical_name(characters, name)
            if pc_key:
                touched = _merge_person_like(characters, pc_key, fields, day, clock)
                key = pc_key
            else:
                key = canonical_name(npcs, name) or name
                touched = _merge_person_like(npcs, key, fields, day, clock)
            if touched and vitals_touched is not None:
                vitals_touched.setdefault(key, set()).update(touched)

    if isinstance(patch.get("resources"), dict):
        _merge_resources(world_state.setdefault("resources", {}), patch["resources"])

    if isinstance(patch.get("challenges"), dict):
        target = world_state.setdefault("challenges", {})
        for raw_name, fields in patch["challenges"].items():
            if not isinstance(fields, dict):
                continue
            key = canonical_name(target, raw_name) or raw_name
            entry = target.setdefault(
                key,
                {"description": "", "severity": "orta", "clock": "", "progress": "",
                 "status": "açık", "consequence": "", "gm_notes": ""},
            )
            for field in ("description", "severity", "clock", "progress",
                          "status", "consequence", "gm_notes"):
                if isinstance(fields.get(field), (str, int, float)) and not isinstance(fields.get(field), bool):
                    entry[field] = fields[field]

    if "zombie_sightings_add" in patch and isinstance(patch["zombie_sightings_add"], list):
        seen = world_state.setdefault("zombie_sightings", [])
        for item in patch["zombie_sightings_add"]:
            if item not in seen:
                seen.append(item)

    if "flags" in patch and isinstance(patch["flags"], dict):
        world_state.setdefault("flags", {}).update(patch["flags"])

    if "narrator" in patch and isinstance(patch["narrator"], dict):
        narrator = world_state.setdefault(
            "narrator", {"plot_summary": "", "puzzles": {}, "upcoming_events": {}}
        )
        npatch = patch["narrator"]
        if isinstance(npatch.get("plot_summary"), str):
            narrator["plot_summary"] = npatch["plot_summary"]
        if isinstance(npatch.get("puzzles"), dict):
            puzzles = narrator.setdefault("puzzles", {})
            for name, fields in npatch["puzzles"].items():
                if isinstance(fields, dict):
                    puzzles.setdefault(name, {}).update(fields)
        if isinstance(npatch.get("upcoming_events"), dict):
            narrator.setdefault("upcoming_events", {}).update(npatch["upcoming_events"])


# Oyuncuların /api/state ile ASLA görmemesi gereken alanlar. `narrator`
# (plot_summary/puzzles/upcoming_events) buraya eklenene kadar dünya durumuyla
# birlikte her oyuncunun tarayıcısına gidiyordu — spoiler sızıntısıydı.
GM_ONLY_FIELDS = ("narrator", "world_roll", "world_roll_history")


def public_world_state(world_state: dict) -> dict:
    """Oyuncu arayüzüne gidecek, gizli alanları ayıklanmış kopya."""
    public = {k: v for k, v in world_state.items() if k not in GM_ONLY_FIELDS}
    # Karakter künyesindeki `secret` sadece anlatıcıya aittir — diğer
    # oyuncular aynı ekranı paylaştığı için buradan tamamen çıkarılır.
    for section in ("characters", "npcs"):
        people = public.get(section)
        if isinstance(people, dict):
            public[section] = {
                name: {k: v for k, v in (info or {}).items() if k != SECRET_FIELD}
                for name, info in people.items()
            }
    challenges = public.get("challenges")
    if isinstance(challenges, dict):
        # zorluklar oyunculara görünür ama her zorluğun gm_notes'u görünmez
        public["challenges"] = {
            name: {k: v for k, v in (info or {}).items() if k != "gm_notes"}
            for name, info in challenges.items()
        }
    factions = public.get("factions")
    if isinstance(factions, dict):
        # Fraksiyonun GERÇEK tavrı (disposition/notes) anlatıcıya özeldir;
        # oyuncular sadece öğrendiklerini (known/public_notes) görür.
        public["factions"] = {
            name: {
                "disposition": (info or {}).get("known") or "bilinmiyor",
                "notes": (info or {}).get("public_notes") or "",
            }
            for name, info in factions.items()
        }
    return public


def chargen_complete(world_state: dict) -> bool:
    # Oyuncular karakter oluşturmayı arayüzden elle bitirmiş olabilir —
    # biri hiç cevap vermezse oyun sonsuza kadar chargen'de takılı kalıp zar
    # mekaniği ve ortak karar hiç açılmıyordu.
    if (world_state.get("flags") or {}).get("chargen_done"):
        return True
    characters = world_state.get("characters", {})
    if not characters:
        return False
    alive = [info for info in characters.values() if info.get("alive", True)]
    if not alive:
        return False
    return all(info.get("background") for info in alive)


CHAR_LINE_RE = re.compile(r"^\s*([^\n:：]+?)\s*[:：]\s*(.+)$")


def detect_multi_character(text: str, valid_players: list):
    """'İsim: aksiyon' satırlarından oluşan, 2+ FARKLI bilinen karaktere ait
    çoklu karakter mesajını ayrıştırır. Her satır bu formata uymuyorsa ya da
    tek karakter içeriyorsa None döner (normal tek-oyunculu akışa düşer)."""
    lower_map = {p.lower(): p for p in valid_players}
    matches = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = CHAR_LINE_RE.match(line)
        if not m:
            return None
        name_raw, action = m.group(1).strip(), m.group(2).strip()
        canon = lower_map.get(name_raw.lower())
        if not canon or not action:
            return None
        matches.append((canon, action))
    if len({c for c, _ in matches}) < 2:
        return None
    return matches


# Bir bloğun "durum güncellemesi" olduğunu ele veren anahtarlar — fence'i
# unutulmuş ham JSON'ı normal metindeki süslü parantezlerden ayırmak için.
STATE_KEYS = {
    "day", "time_of_day", "clock", "season", "weather", "temperature",
    "location", "tension", "factions", "characters", "npcs",
    "resources", "challenges", "zombie_sightings_add", "flags", "narrator",
}

# Etiketi ne olursa olsun (state-update / json / etiketsiz), içinde bir JSON
# nesnesi olan HER ``` bloğu. Ne oyuncuya ne anlatıcıya ham JSON gösterilmeli,
# o yüzden etiketin doğru yazılmış olmasına güvenmiyoruz.
FENCED_STATE_RE = re.compile(
    r"```[ \t]*[A-Za-z_-]*[ \t]*\r?\n?(\{.*?\})[ \t]*\r?\n?```", re.DOTALL
)
LEFTOVER_FENCE_RE = re.compile(
    r"```[ \t]*(?:state-update|state_update|json)[ \t]*\r?\n?", re.IGNORECASE
)
EMPTY_FENCE_RE = re.compile(r"```\s*```", re.DOTALL)

# Model bloğu sık sık {"state-update": {...}} diye sarmalıyor. Sarmalanmış
# hali deep_merge'de hiçbir bilinen alana denk gelmediği için sessizce
# yutuluyordu — bu yüzden birleştirmeden önce daima soyuyoruz.
PATCH_WRAPPER_KEYS = {"state-update", "state_update", "stateupdate", "world_state", "patch"}


def _normalize_patch(obj):
    """Sarmalayıcı anahtarı varsa içindeki gerçek yamayı döndürür."""
    while isinstance(obj, dict) and len(obj) == 1:
        key, inner = next(iter(obj.items()))
        if key.strip().lower().replace(" ", "") not in PATCH_WRAPPER_KEYS:
            break
        if not isinstance(inner, dict):
            break
        obj = inner
    return obj


def _looks_like_patch(obj) -> bool:
    return isinstance(obj, dict) and bool(set(_normalize_patch(obj)) & STATE_KEYS)


def _strip_bare_json_objects(text: str):
    """Model ``` fence'ini unuttuğunda ham JSON metnin içinde kalıyor ve
    hem oyuncu hem anlatıcı ekranında görünüyordu. Bu tarayıcı, gerçekten
    JSON olarak parse edilen VE bilinen bir durum alanı içeren nesneleri
    söker; normal metindeki süslü parantezlere dokunmaz."""
    patches = []
    out = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != "{":
            out.append(text[i])
            i += 1
            continue
        depth, in_str, esc, j = 0, False, False, i
        while j < n:
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        parsed = None
        if j < n:
            try:
                parsed = json.loads(text[i:j + 1])
            except json.JSONDecodeError:
                parsed = None
        if _looks_like_patch(parsed):
            patches.append(_normalize_patch(parsed))
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out), patches


def extract_state_update(text: str):
    """Modelin yanıtındaki TÜM durum verisini ayrıştırıp metinden temizler.
    Üç kademe: (1) ``` içindeki JSON blokları, (2) fence'i unutulmuş ham JSON
    nesneleri, (3) boşta kalan fence kalıntıları. Bozuk JSON parse edilemese
    bile metinden SİLİNİR — ekrana asla ham JSON düşmemeli."""
    patches = []

    def _collect(match):
        try:
            patches.append(_normalize_patch(json.loads(match.group(1))))
        except json.JSONDecodeError:
            pass  # parse edilemedi ama yine de gösterilmez
        return ""

    cleaned = FENCED_STATE_RE.sub(_collect, text)
    cleaned, bare = _strip_bare_json_objects(cleaned)
    patches.extend(bare)
    cleaned = LEFTOVER_FENCE_RE.sub("", cleaned)
    cleaned = EMPTY_FENCE_RE.sub("", cleaned)
    # sökülen blokların ardında kalan boş satır yığınlarını topla
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip(), patches


# ------------------------------------------------------------------ claude CLI

def call_claude(prompt: str, extra_system: str, session_id, scenario_text: str = None):
    """claude CLI'ı headless (-p) modda çalıştırır; claude.ai OAuth girişini kullanır.

    session_id None ise yeni bir oturum başlatılır (scenario_text sistem
    promptu olarak verilir); değilse mevcut oturum --resume ile sürdürülür.
    """
    cmd = [
        CLAUDE_BIN,
        "-p",
        prompt,
        "--tools",
        "",
        "--output-format",
        "json",
        "--model",
        MODEL,
        "--effort",
        EFFORT,
        "--append-system-prompt",
        extra_system,
    ]
    if session_id is None:
        cmd += ["--system-prompt", scenario_text or SCENARIO_TEXT]
    else:
        cmd += ["--resume", session_id]

    result = subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        timeout=CLAUDE_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI çıkışı {result.returncode}: {result.stderr.strip()[:500]}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"claude CLI çıktısı JSON değil: {result.stdout[:500]}") from e


def next_id(state) -> int:
    val = state["next_id"]
    state["next_id"] += 1
    return val


# ----------------------------------------------------------------------- routes

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    # audio/ambient.mp3 gibi kullanıcının kendi eklediği dosyaları servis eder
    return send_from_directory(STATIC_DIR, filename)


@app.route("/secrets")
def secrets_page():
    # Anlatıcı-only ekran — ana oyun arayüzünden hiçbir yere bağlanmaz.
    return send_from_directory(STATIC_DIR, "secrets.html")


@app.route("/api/state", methods=["GET"])
def get_state():
    since = request.args.get("since")
    with lock:
        state = load_state()
        version = int(state.get("version", 0))
        # Hızlı yoklama: durum değişmediyse ağır gövdeyi hiç kurma.
        if since is not None and since.isdigit() and int(since) == version:
            return jsonify({"version": version, "changed": False})
        log = read_log()
    return jsonify(
        {
            "version": version,
            "changed": True,
            "world_state": public_world_state(state["world_state"]),
            "log": log,
            "started": state["started"],
            "characters_confirmed": state["characters_confirmed"],
            "chargen_done": chargen_complete(state["world_state"]),
            "default_players": load_scenario()["default_players"],
            "start_item_suggestions": load_scenario()["start_item_suggestions"],
            "custom_scenario": SCENARIO_OVERRIDE_FILE.exists(),
            "group_label": GROUP_LABEL,
            "group_display_name": GROUP_DISPLAY_NAME,
        }
    )


@app.route("/api/setup-characters", methods=["POST"])
def setup_characters():
    body = request.get_json(force=True) or {}
    # `players` iki biçimde gelebilir: düz isim listesi (eski istemciler) ya da
    # karakter künyesi sözlükleri (isim + meslek/yaş/güçlü/zayıf/sır/eşya).
    picks = []
    for raw in body.get("players") or []:
        if isinstance(raw, str):
            picks.append({"name": raw.strip()})
        elif isinstance(raw, dict):
            sheet = {
                key: str(raw.get(key) or "").strip()
                for key in ("name", "item", "profession", "age",
                            "strength", "weakness", "secret")
            }
            picks.append(sheet)
    picks = [p for p in picks if p.get("name")]
    # tekrarları kaldır, sırayı koru
    seen = set()
    picks = [p for p in picks if not (p["name"] in seen or seen.add(p["name"]))]
    names = [p["name"] for p in picks]

    if not (1 <= len(picks) <= 8):
        return jsonify({"error": "1 ile 8 arasında karakter ismi girin."}), 400

    with lock:
        state = load_state()
        if state["started"]:
            return jsonify({"error": "Oyun zaten başladı, karakterler değiştirilemez."}), 400
        if state["characters_confirmed"]:
            return jsonify({"error": "Karakterler zaten onaylandı. Değiştirmek için önce sıfırlayın."}), 400

        start_location = state["world_state"].get("location")
        characters = {}
        for sheet in picks:
            name = sheet["name"]
            char = json.loads(json.dumps(CHARACTER_TEMPLATE))
            char["location"] = start_location
            for key in ("profession", "age", "strength", "weakness", "secret"):
                char[key] = sheet.get(key) or None
            char["background"] = build_background(char)
            char["traits"] = build_traits(char)
            if char["background"]:
                char["notes"] = ""
            # oyuncunun kurulum ekranında seçtiği tek başlangıç eşyası
            item = sheet.get("item")
            char["inventory"] = [item] if item else []
            characters[name] = char
        state["world_state"]["characters"] = characters
        state["characters_confirmed"] = True
        # Künyeler ekrandan dolduysa oyun içi karakter oluşturma turuna gerek
        # yok — anlatıcı doğrudan hikayeye girer, zar ilk turdan itibaren atılır.
        state["world_state"].setdefault("flags", {})["chargen_done"] = all(
            c.get("background") for c in characters.values()
        )
        save_state(state)

    return jsonify(
        {
            "world_state": public_world_state(state["world_state"]),
            "characters_confirmed": True,
        }
    )


@app.route("/api/start", methods=["POST"])
def start_game():
    with lock:
        state = load_state()
        if state["started"]:
            return jsonify({"error": "Oyun zaten başladı."}), 400
        if not state["characters_confirmed"]:
            return jsonify({"error": "Önce karakterleri belirleyin."}), 400

        scenario = load_scenario()
        players = list(state["world_state"]["characters"].keys())
        hook = secrets.choice(scenario["opening_hooks"])
        sheets_done = sheets_complete(state["world_state"])
        if sheets_done:
            chargen_note = (
                "KÜNYELER TAMAMLANDI — oyuncular karakter oluşturma ekranını "
                "doldurdu. Karakter oluşturma sorusu SORMA, seçenek sunma. "
                "Açılış sahnesinde herkesi künyesine uygun biçimde tanıt ve "
                "doğrudan asıl hikayeye geç: açılış olayını somut bir ZORLUĞA "
                "dönüştürüp `challenges` altına kaydet ve DURUM/SEÇENEKLER "
                "bloğuyla bitir. Durum güncelleme bloğunda `flags.chargen_done` "
                "alanını true yap ve her karaktere mesleğine uyan 1-2 mütevazı "
                "eşyayı `inventory_add` ile ekle. Bu turda zar mekaniği YOK."
            )
        else:
            chargen_note = (
                "Yukarıdaki SCENARIO talimatlarındaki 'OYUN BAŞLANGICI VE "
                "KARAKTER OLUŞTURMA' bölümüne göre davran: bu olayı sahne "
                "olarak anlat, ardından yukarıdaki karakter listesindeki "
                "HERKES için karakter oluşturma seçeneklerini sun. Bu turda "
                "zar mekaniği YOK."
            )
        extra_system = (
            "OYUN BAŞLANGICI.\n"
            f"Bu oyundaki karakterler (SABİT, TAM LİSTE — başka oyuncu karakteri "
            f"YOK, isim uydurma): {', '.join(players)}.\n"
            f"Rastgele açılış olayı (sunucu tarafından seçildi): {hook}\n\n"
            + chargen_note
            + "\n\nKARAKTER KÜNYELERİ (kurulum ekranından geldi; meslek/yaş/"
            "güçlü-zayıf yan BAĞLAYICIDIR, eşyalar zaten envanterde — tekrar "
            "ekleme. SIRLAR sadece sana aittir, hiçbir koşulda metinde "
            "açıklama, sadece hikayenin gizli motoru olarak kullan):\n"
            + character_sheets_note(state["world_state"])
            + "\n\nORTAK STOK YOK: `resources` bilerek BOŞ başlar. Ortada bir "
            "klan, topluluk ya da depo yok — grubun sahip olduğu tek şey "
            "yukarıdaki kişisel envanterlerdir. Açılış sahnesinde bir depodan, "
            "stoktan, 'elimizdeki erzaktan' söz ETME ve `resources` altına "
            "hiçbir başlangıç kalemi YAZMA. Stok ancak grup ilerideki turlarda "
            "bir topluluk kurar/katılır ya da oyuncular açıkça sayım isterse "
            "doğar (bkz. SCENARIO → 'GRUP KAYNAKLARI').\n\n"
            "GÜNCEL DÜNYA DURUMU (JSON):\n"
            + json.dumps(state["world_state"], ensure_ascii=False)
        )
        prompt = "(Oyun başlıyor. Sahneyi aç.)"

        try:
            result = call_claude(prompt, extra_system, None, scenario["scenario_text"])
        except subprocess.TimeoutExpired:
            return jsonify({"error": "claude CLI zaman aşımına uğradı."}), 504
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 502

        if result.get("is_error"):
            return jsonify({"error": f"claude hata döndürdü: {result.get('result')}"}), 502

        state["session_id"] = result.get("session_id")
        state["started"] = True

        raw_text = result.get("result", "")
        gm_text, patches = extract_state_update(raw_text)
        for patch in patches:
            deep_merge_world_state(state["world_state"], patch)

        gm_entry = {
            "id": next_id(state),
            "role": "assistant",
            "kind": "opening",
            "text": gm_text,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        append_log(gm_entry)
        save_state(state)

    return jsonify({"gm_entry": gm_entry, "world_state": public_world_state(state["world_state"]), "started": True})


@app.route("/api/message", methods=["POST"])
def post_message():
    body = request.get_json(force=True) or {}
    player = body.get("player")
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    with lock:
        state = load_state()
        if not state["started"]:
            return jsonify({"error": "Önce oyunu başlatın."}), 400
        # ölen karakterler adına mesaj gönderilemez — oyuncusu devralma
        # ekranından yeni bir karakter seçmeli
        valid_players = alive_players(state["world_state"])
        in_chargen = not chargen_complete(state["world_state"])
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        # Tur başına TEK dünya zarı (karakter başına değil) — oyunculara
        # gösterilmez, sadece modele ve /secrets ekranına gider.
        world_entry = None if in_chargen else roll_world_dice(state["world_state"])
        wants_inventory = bool(INVENTORY_INTENT_RE.search(text)) and not in_chargen
        inventory_block = ("\n\n" + INVENTORY_REPORT_INSTRUCTION) if wants_inventory else ""

        multi = detect_multi_character(text, valid_players)

        if multi:
            user_entries = []
            line_descs = []
            for name, action in multi:
                if in_chargen:
                    roll, band = None, None
                else:
                    roll = roll_d100()
                    band = band_for(roll)
                user_entries.append(
                    {
                        "id": next_id(state),
                        "role": "user",
                        "player": name,
                        "is_group": False,
                        "roll": roll,
                        "band": band,
                        "text": action,
                        "ts": ts,
                    }
                )
                roll_desc = f" (ZAR: {roll} - {band})" if roll is not None else ""
                line_descs.append(f"{name}{roll_desc}: {action}")
            combined = "\n".join(line_descs)
            prompt = f"[ÇOKLU KARAKTER TURU]\n{combined}"

            if in_chargen:
                extra_system = (
                    "ÇOKLU KARAKTER TURU — KARAKTER OLUŞTURMA AŞAMASI, zar mekaniği YOK.\n"
                    "Aşağıdaki her satır farklı bir oyuncunun AYNI ANDA gönderdiği karakter "
                    "oluşturma cevabıdır. Her biri için (gerçekten karakterini kuruyorsa) "
                    "state-update bloğuna characters.<isim> altına background, traits VE "
                    "inventory_add (mesleğine uyan 2-3 mütevazı başlangıç eşyası; kurulum "
                    "ekranında seçtikleri eşya zaten envanterlerinde, tekrar ekleme) "
                    "eklemeyi UNUTMA — hepsi TEK bir state-update bloğunda birleşsin.\n\n"
                    + combined
                    + "\n\n"
                    + roster_note(state["world_state"])
                    + "\n\n"
                    + inventory_note(state["world_state"])
                    + "\n\n"
                    + wounds_note(state["world_state"])
                    + "\n\n"
                    + vitals_note(state["world_state"])
                    + "\n\n"
                    + visible_timeline_note(read_log())
                    + "\n\nGÜNCEL DÜNYA DURUMU (JSON):\n"
                    + json.dumps(state["world_state"], ensure_ascii=False)
                )
            else:
                extra_system = (
                    "ÇOKLU KARAKTER TURU — SCENARIO'daki 'ÇOKLU KARAKTER TURU' bölümüne "
                    "göre davran: aşağıdaki her satır farklı bir karakterin AYNI ANDA "
                    "aldığı farklı bir aksiyon, her biri KENDİ zarına göre ayrı ayrı "
                    "sonuçlanır ama sahneyi birleşik/akıcı anlat.\n"
                    + world_dice_note(world_entry)
                    + inventory_block
                    + "\n\nHATIRLATMA: yanıtının sonuna TEK bir state-update bloğu ekle. "
                    "(1) tension ve (2) narrator.plot_summary (2-4 cümlelik güncel "
                    "özet) her turda zorunlu.\n"
                    + UPKEEP_REMINDER
                    + "\n\n"
                    + combined
                    + "\n\n"
                    + roster_note(state["world_state"])
                    + "\n\n"
                    + inventory_note(state["world_state"])
                    + "\n\n"
                    + wounds_note(state["world_state"])
                    + "\n\n"
                    + vitals_note(state["world_state"])
                    + "\n\n"
                    + visible_timeline_note(read_log())
                    + "\n\nGÜNCEL DÜNYA DURUMU (JSON):\n"
                    + json.dumps(state["world_state"], ensure_ascii=False)
                )
        else:
            is_group = player == GROUP_LABEL
            if not is_group and player not in valid_players:
                if player in (state["world_state"].get("characters") or {}):
                    return jsonify(
                        {"error": f"{player} öldü — bu karakterle oynanamaz. "
                                  "Devam etmek için hikayedeki bir karakteri devralın."}
                    ), 400
                return jsonify({"error": f"player must be one of {valid_players + [GROUP_LABEL]}"}), 400
            # Ortak karar artık karakter oluşturma sırasında da kullanılabilir
            # (eskiden burada 400 dönüyordu ve biri karakterini kurmayınca
            # buton hiç açılmıyordu). Chargen sürerken zar atılmaz, model
            # bunu grup aksiyonu olarak işler.

            if in_chargen:
                roll, band = None, None
                if is_group:
                    chargen_head = (
                        "KARAKTER OLUŞTURMA AŞAMASI — zar mekaniği uygulanmaz.\n"
                        "Bu mesaj [GRUP - ORTAK KARAR] etiketiyle geliyor: tek bir "
                        "karakterin değil, grubun ortak sözü/aksiyonu. Karakter "
                        "oluşturma henüz bitmemiş olabilir; grubu birlikte ele al, "
                        "hâlâ karakterini kurmamış olan varsa ona kısaca hatırlat.\n\n"
                    )
                else:
                    chargen_head = (
                        "KARAKTER OLUŞTURMA AŞAMASI — bu turda zar mekaniği uygulanmaz.\n"
                        f"Bu mesajı yazan: {player}. Eğer bu mesajda {player} karakterini "
                        "kuruyorsa (bir seçenek seçtiyse ya da kendi tarifini yazdıysa), "
                        "yanıtının sonuna MUTLAKA ```state-update``` bloğu ekleyip "
                        f"characters.{player} altına background, traits VE inventory_add "
                        "(mesleğine/geçmişine uyan 2-3 mütevazı başlangıç eşyası; kurulum "
                        "ekranında seçtiği eşya zaten envanterinde, onu tekrar ekleme) "
                        "alanlarını yaz — bunu unutma, atlarsan karakter bilgisi kalıcı "
                        "olarak kaybolur.\n\n"
                    )
                extra_system = (
                    chargen_head
                    + roster_note(state["world_state"])
                    + "\n\n"
                    + inventory_note(state["world_state"])
                    + "\n\n"
                    + wounds_note(state["world_state"])
                    + "\n\n"
                    + vitals_note(state["world_state"])
                    + "\n\n"
                    + visible_timeline_note(read_log())
                    + "\n\nGÜNCEL DÜNYA DURUMU (JSON, sadece senin referansın, oyunculara okuma):\n"
                    + json.dumps(state["world_state"], ensure_ascii=False)
                )
            else:
                roll = roll_d100()
                band = band_for(roll)
                group_note = (
                    "Bu mesaj [GRUP - ORTAK KARAR] etiketiyle geliyor — SCENARIO'daki "
                    "'ORTAK KARAR MESAJLARI' bölümüne göre davran, tek bir karaktere "
                    "değil TÜM gruba ait bir karar/aksiyon olarak ele al.\n\n"
                    if is_group else ""
                )
                extra_system = (
                    f"ZAR (oyuncunun hamlesi): {roll} ({band})\n"
                    + world_dice_note(world_entry)
                    + inventory_block
                    + "\n\n"
                    + group_note
                    + "HATIRLATMA (teknik, MUTLAKA uygula): yanıtının SONUNA bir "
                    "```state-update``` bloğu ekle ve içine EN AZINDAN şunları yaz — "
                    "bu iki alan her turda zorunlu, başka hiçbir şey değişmese bile "
                    'atlama: (1) bu sahnenin "tension" seviyesi (\"düşük\"/\"orta\"/'
                    '\"yüksek\"); (2) `narrator.plot_summary` — hikayenin şu anki '
                    "durumunun 2-4 cümlelik güncel özeti (bu SADECE anlatıcı ekranında "
                    "görünür, oyunculara asla gösterilmez).\n"
                    + UPKEEP_REMINDER
                    + "\n\n"
                    + roster_note(state["world_state"])
                    + "\n\n"
                    + inventory_note(state["world_state"])
                    + "\n\n"
                    + wounds_note(state["world_state"])
                    + "\n\n"
                    + vitals_note(state["world_state"])
                    + "\n\n"
                    + visible_timeline_note(read_log())
                    + "\n\nGÜNCEL DÜNYA DURUMU (JSON, sadece senin referansın, oyunculara okuma):\n"
                    + json.dumps(state["world_state"], ensure_ascii=False)
                )

            user_entries = [
                {
                    "id": next_id(state),
                    "role": "user",
                    "player": GROUP_DISPLAY_NAME if is_group else player,
                    "is_group": is_group,
                    "roll": roll,
                    "band": band,
                    "text": text,
                    "ts": ts,
                }
            ]
            prompt = f"[GRUP - ORTAK KARAR]\n{text}" if is_group else f"[OYUNCU: {player}]\n{text}"

        try:
            result = call_claude(prompt, extra_system, state["session_id"], load_scenario()["scenario_text"])
        except subprocess.TimeoutExpired:
            return jsonify({"error": "claude CLI zaman aşımına uğradı."}), 504
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 502

        if result.get("is_error"):
            return jsonify({"error": f"claude hata döndürdü: {result.get('result')}"}), 502

        state["session_id"] = result.get("session_id") or state["session_id"]
        for entry in user_entries:
            append_log(entry)

        raw_text = result.get("result", "")
        gm_text, patches = extract_state_update(raw_text)
        # Göstergeler zar gibi sunucunun sorumluluğunda: anlatıcının elle
        # yazdığı değerler (uyudu/yedi/içti) korunur, geri kalanı bu turda
        # geçen oyun-içi süreye göre kendiliğinden yükselir.
        clock_before = {"day": state["world_state"].get("day"),
                        "clock": state["world_state"].get("clock")}
        vitals_touched = {}
        for patch in patches:
            deep_merge_world_state(state["world_state"], patch, vitals_touched)
        turn_minutes = elapsed_minutes(clock_before, state["world_state"])
        apply_vitals_drift(state["world_state"], turn_minutes, vitals_touched)
        advance_infections(state["world_state"], turn_minutes)
        normalize_wound_status(state["world_state"])

        gm_entry = {
            "id": next_id(state),
            "role": "assistant",
            "text": gm_text,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tension": state["world_state"].get("tension"),
        }
        append_log(gm_entry)

        save_state(state)

    return jsonify(
        {
            "user_entries": user_entries,
            "gm_entry": gm_entry,
            "world_state": public_world_state(state["world_state"]),
            # arayüz Grup Kaynakları panelini bu bayrakla açar
            "inventory_report": wants_inventory,
            "version": int(state.get("version", 0)),
        }
    )


@app.route("/api/takeover", methods=["POST"])
def takeover_character():
    """Ölen bir oyuncu karakterinin oyuncusu, hikayede zaten var olan bir
    NPC'yi devralıp oyuna onunla devam eder. NPC `npcs`'ten `characters`'a
    taşınır (geçmişi/envanteri/ilişkileri korunarak), ölen karakter listede
    ölü olarak kalır."""
    body = request.get_json(force=True) or {}
    dead_name = (body.get("dead_player") or "").strip()
    new_name = (body.get("new_character") or "").strip()

    with lock:
        state = load_state()
        if not state["started"]:
            return jsonify({"error": "Oyun henüz başlamadı."}), 400

        ws = state["world_state"]
        characters = ws.setdefault("characters", {})
        npcs = ws.setdefault("npcs", {})

        dead_key = canonical_name(characters, dead_name)
        if not dead_key:
            return jsonify({"error": "Ölen karakter bulunamadı."}), 400
        if characters[dead_key].get("alive", True):
            return jsonify({"error": f"{dead_key} hâlâ hayatta — devralma yapılamaz."}), 400
        if characters[dead_key].get("replaced_by"):
            return jsonify(
                {"error": f"{dead_key} için zaten bir karakter devralındı "
                          f"({characters[dead_key]['replaced_by']})."}
            ), 400

        new_key = canonical_name(npcs, new_name)
        if not new_key:
            return jsonify({"error": "Devralınacak karakter hikayedeki NPC'ler arasında yok."}), 400
        if not npcs[new_key].get("alive", True):
            return jsonify({"error": f"{new_key} hayatta değil, devralınamaz."}), 400

        entry = npcs.pop(new_key)
        entry["alive"] = True
        characters[new_key] = entry
        characters[dead_key]["replaced_by"] = new_key

        prompt = (
            f"[KARAKTER DEVRALMA]\n{dead_key} öldü. O oyuncu bundan sonra hikayede "
            f"zaten var olan {new_key} karakterini oynayacak."
        )
        extra_system = (
            "KARAKTER DEVRALMA TURU — zar mekaniği YOK.\n"
            f"{dead_key} kalıcı olarak öldü ve ölü kalacak; onun oyuncusu artık "
            f"{new_key} karakterini oynuyor. {new_key} bu andan itibaren bir NPC "
            "DEĞİL, bir OYUNCU KARAKTERİDİR — state-update'te `characters` altında "
            "takip et ve doğrudan ona hitap et.\n"
            f"Kısa (1-2 paragraf) bir geçiş sahnesi yaz: {new_key} sahnenin/grubun "
            f"merkezine nasıl geçiyor, {dead_key}'in ölümü gruba nasıl yansıyor. "
            f"Sonra {new_key}'e ne yapacağını sor.\n"
            "Yanıtının sonuna TEK bir state-update bloğu ekle; içinde en azından "
            "tension ve narrator.plot_summary olsun.\n\n"
            + roster_note(ws)
            + "\n\n"
            + inventory_note(ws)
            + "\n\n"
            + visible_timeline_note(read_log())
            + "\n\nGÜNCEL DÜNYA DURUMU (JSON):\n"
            + json.dumps(ws, ensure_ascii=False)
        )

        try:
            result = call_claude(prompt, extra_system, state["session_id"], load_scenario()["scenario_text"])
        except subprocess.TimeoutExpired:
            return jsonify({"error": "claude CLI zaman aşımına uğradı."}), 504
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 502

        if result.get("is_error"):
            return jsonify({"error": f"claude hata döndürdü: {result.get('result')}"}), 502

        state["session_id"] = result.get("session_id") or state["session_id"]

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        system_entry = {
            "id": next_id(state),
            "role": "system",
            "text": f"💀 {dead_key} öldü. Oyuncusu artık {new_key} karakteriyle devam ediyor.",
            "ts": ts,
        }
        append_log(system_entry)

        raw_text = result.get("result", "")
        gm_text, patches = extract_state_update(raw_text)
        for patch in patches:
            deep_merge_world_state(ws, patch)

        gm_entry = {
            "id": next_id(state),
            "role": "assistant",
            "kind": "takeover",
            "text": gm_text,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tension": ws.get("tension"),
        }
        append_log(gm_entry)
        save_state(state)

    return jsonify({"system_entry": system_entry, "gm_entry": gm_entry, "world_state": public_world_state(ws)})


@app.route("/api/finish-chargen", methods=["POST"])
def finish_chargen():
    """Karakter oluşturmayı elle bitirir. Biri hiç cevap vermezse oyun sonsuza
    kadar chargen'de takılı kalıp zar mekaniği ve ortak karar açılmıyordu."""
    with lock:
        state = load_state()
        if not state["started"]:
            return jsonify({"error": "Oyun henüz başlamadı."}), 400
        ws = state["world_state"]
        ws.setdefault("flags", {})["chargen_done"] = True
        save_state(state)
    return jsonify({"ok": True, "world_state": public_world_state(ws)})


@app.route("/api/gm/patch", methods=["POST"])
def gm_patch():
    """Anlatıcının doğrudan (model çağrısı olmadan) dünya durumunu düzenlemesi:
    fraksiyon tavrı, zorluk saati, bulmaca ilerlemesi vb. Anında uygulanır."""
    body = request.get_json(force=True) or {}
    if body.get("pin") != GM_PIN:
        return jsonify({"error": "Yanlış PIN."}), 403
    patch = body.get("patch")
    if not isinstance(patch, dict) or not patch:
        return jsonify({"error": "Boş ya da geçersiz düzenleme."}), 400
    with lock:
        state = load_state()
        deep_merge_world_state(state["world_state"], patch)
        save_state(state)
        version = int(state.get("version", 0))
    return jsonify({"ok": True, "version": version, "world_state": state["world_state"]})


@app.route("/api/reset", methods=["POST"])
def reset_state():
    with lock:
        state = default_state()
        save_state(state)
        clear_log()
        clear_gm_log()
    return jsonify({"ok": True})


# ------------------------------------------------------------- /secrets (GM) API

@app.route("/api/gm/unlock", methods=["POST"])
def gm_unlock():
    body = request.get_json(force=True) or {}
    if body.get("pin") != GM_PIN:
        return jsonify({"error": "Yanlış PIN."}), 403
    return jsonify({"ok": True})


@app.route("/api/gm/state", methods=["GET"])
def gm_state():
    body = request.args
    if body.get("pin") != GM_PIN:
        return jsonify({"error": "Yanlış PIN."}), 403
    since = body.get("since")
    with lock:
        state = load_state()
        version = int(state.get("version", 0))
        if since is not None and since.isdigit() and int(since) == version:
            return jsonify({"version": version, "changed": False})
        gm_log = read_gm_log()
        log = read_log()
    return jsonify(
        {
            "version": version,
            "changed": True,
            "world_state": state["world_state"],
            "gm_log": gm_log,
            # anlatıcı, oyuncuların turlarını da bu ekrandan canlı izleyebilsin
            "log": log[-40:],
            "started": state["started"],
        }
    )


@app.route("/api/gm/note", methods=["POST"])
def gm_note():
    body = request.get_json(force=True) or {}
    if body.get("pin") != GM_PIN:
        return jsonify({"error": "Yanlış PIN."}), 403
    text = (body.get("text") or "").strip()
    # gizli   = yönlendirme; yanıt SADECE anlatıcı ekranında kalır
    # sahne   = müdahale doğrudan oyuncu akışına sahne olarak yayınlanır
    # surpriz = anlatıcı sürpriz bir gelişme uydurur ve sahne olarak yayınlar
    mode = (body.get("mode") or "gizli").strip().lower()
    if mode not in ("gizli", "sahne", "surpriz"):
        mode = "gizli"
    if not text and mode != "surpriz":
        return jsonify({"error": "Not metni boş olamaz."}), 400

    with lock:
        state = load_state()
        if not state["started"]:
            return jsonify({"error": "Oyun henüz başlamadı — önce ana ekrandan başlatın."}), 400

        ws = state["world_state"]
        common_tail = (
            roster_note(ws)
            + "\n\n"
            + inventory_note(ws)
            + "\n\n"
            + visible_timeline_note(read_log())
            + "\n\nGÜNCEL DÜNYA DURUMU (JSON):\n"
            + json.dumps(ws, ensure_ascii=False)
        )
        publish = mode in ("sahne", "surpriz")

        if mode == "gizli":
            prompt = f"[ANLATICI NOTU - GİZLİ]\n{text}"
            extra_system = (
                "Bu mesaj oyunculardan DEĞİL, oyunu yöneten gerçek kişiden (GM) "
                "geliyor ve oyunculara ASLA gösterilmeyecek. SCENARIO talimatlarındaki "
                "'Anlatıcıdan (GM) gizli yönetmen notu gelirse' bölümüne göre davran: "
                "notu otoriter kabul et, gerekiyorsa narrator alanlarını (plot_summary/"
                "puzzles/upcoming_events) state-update ile güncelle, ve SADECE bu "
                "anlatıcıya hitap eden kısa bir onay/yanıt yaz. Bu turda oyunculara "
                "gidecek HİÇBİR sahne yazma — talimatı sonraki oyuncu turlarında "
                "hayata geçir.\n\n"
                + common_tail
            )
        elif mode == "sahne":
            prompt = f"[ANLATICI MÜDAHALESİ - SAHNE OLARAK YAYINLA]\n{text}"
            extra_system = (
                "Bu talimat oyunu yöneten gerçek kişiden (GM) geliyor ve OTORİTERDİR. "
                "Bu turda yazdığın metin DOĞRUDAN oyuncuların ekranına, hikayenin bir "
                "parçası olarak düşecek.\n"
                "- Sadece sahneyi yaz: anlatıcı sesiyle, 1-3 paragraf, atmosferik.\n"
                "- GM'den, bu talimattan ya da perde arkasından ASLA söz etme; "
                "oyuncular böyle bir müdahalenin varlığını bilmemeli.\n"
                "- Bu bir oyuncu aksiyonunun sonucu değil, dünyanın kendi hamlesi: "
                "zar mekaniği UYGULAMA.\n"
                "- Sahnenin sonunda oyunculara net bir durum bırak ve ne yapacaklarını sor.\n"
                "- Sahne SOMUT BİR PROBLEM üretsin ya da mevcut bir zorluğu ilerletsin: "
                "ölçülebilir parametre (sayı/mesafe/süre), bedeli olan seçenekler. "
                "'SAHNE YAPISI' bölümündeki **DURUM** + **SEÇENEKLER** bloğuyla bitir.\n"
                "- Yanıtının sonuna TEK bir state-update bloğu ekle: tension, "
                "narrator.plot_summary ve `challenges` (yeni zorluk ya da güncellenen "
                "clock/progress).\n\n"
                + common_tail
            )
        else:  # surpriz
            steer = f"\nGM'in yönlendirmesi (bunu dikkate al): {text}" if text else ""
            prompt = "[ANLATICI MÜDAHALESİ - SÜRPRİZ OLAY]" + steer
            extra_system = (
                "Oyunu yöneten kişi hikayeye SÜRPRİZ bir gelişme sokmanı istiyor. "
                "Bu turda yazdığın metin DOĞRUDAN oyuncuların ekranına düşecek.\n"
                "- Olayı SEN icat et, ama rastgele olmasın: mevcut dünya durumundan "
                "beslen — narrator.upcoming_events'teki kendi planların, çözülmemiş "
                "bulmacalar, fraksiyonların tavrı, karakter/NPC ilişkileri ve notları, "
                "azalan kaynaklar, son sahnedeki gerilim.\n"
                "- Beklenmedik ama GERİYE DÖNÜK TUTARLI olsun: oyuncular 'bunun izleri "
                "zaten vardı' diyebilmeli. Ucuz deus ex machina yazma.\n"
                "- Oyuncuların elini bağlama: sürpriz onlara karar verecekleri yeni bir "
                "durum açsın, sonucu sen dayatma.\n"
                "- GM'den ya da bu talimattan ASLA söz etme. Zar mekaniği UYGULAMA. "
                "1-3 paragraf, sonunda oyunculara ne yapacaklarını sor.\n"
                "- Sürpriz SOMUT BİR ZORLUĞA dönüşsün (ya da mevcut bir bulmacayı "
                "ilerletsin): ölçülebilir parametre + bedeli olan seçenekler. "
                "'SAHNE YAPISI' bölümündeki **DURUM** + **SEÇENEKLER** bloğuyla bitir.\n"
                "- Yanıtının sonuna TEK bir state-update bloğu ekle: tension, "
                "narrator.plot_summary, `challenges` ve gerekiyorsa "
                "narrator.puzzles (progress/clues_found/next_step).\n\n"
                + common_tail
            )

        try:
            result = call_claude(prompt, extra_system, state["session_id"], load_scenario()["scenario_text"])
        except subprocess.TimeoutExpired:
            return jsonify({"error": "claude CLI zaman aşımına uğradı."}), 504
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 502

        if result.get("is_error"):
            return jsonify({"error": f"claude hata döndürdü: {result.get('result')}"}), 502

        state["session_id"] = result.get("session_id") or state["session_id"]

        raw_text = result.get("result", "")
        reply_text, patches = extract_state_update(raw_text)
        for patch in patches:
            deep_merge_world_state(ws, patch)

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        note_entry = {
            "id": None,
            "role": "gm_note",
            "mode": mode,
            "text": text or "(sürpriz olay üret — konu serbest)",
            "ts": ts,
        }
        append_gm_log(note_entry)

        gm_entry = None
        if publish:
            # Sahne oyuncu akışına düşer; anlatıcı ekranında kaydı da kalır.
            gm_entry = {
                "id": next_id(state),
                "role": "assistant",
                "kind": "gm_scene",
                "text": reply_text,
                "ts": ts,
                "tension": ws.get("tension"),
            }
            append_log(gm_entry)

        reply_entry = {
            "id": None,
            "role": "gm_reply",
            "mode": mode,
            "published": publish,
            "text": ("✅ Sahne oyuncu akışına yayınlandı:\n\n" + reply_text) if publish else reply_text,
            "ts": ts,
        }
        append_gm_log(reply_entry)

        save_state(state)

    return jsonify(
        {
            "note_entry": note_entry,
            "reply_entry": reply_entry,
            "gm_entry": gm_entry,
            "published": publish,
            "world_state": ws,
        }
    )


# ------------------------------------------------------------- senaryo dışa/içe

@app.route("/api/scenario/export", methods=["GET"])
def export_scenario():
    return jsonify(load_scenario())


@app.route("/api/scenario/import", methods=["POST"])
def import_scenario():
    body = request.get_json(force=True) or {}
    if not isinstance(body.get("scenario_text"), str) or not body["scenario_text"].strip():
        return jsonify({"error": "Geçersiz senaryo dosyası: 'scenario_text' eksik."}), 400
    if not isinstance(body.get("initial_world_state"), dict):
        return jsonify({"error": "Geçersiz senaryo dosyası: 'initial_world_state' eksik."}), 400

    payload = {
        "scenario_text": body["scenario_text"],
        "initial_world_state": body["initial_world_state"],
        "default_players": body.get("default_players") or DEFAULT_PLAYERS,
        "opening_hooks": body.get("opening_hooks") or OPENING_HOOKS,
        "start_item_suggestions": body.get("start_item_suggestions") or START_ITEM_SUGGESTIONS,
    }
    with lock:
        SCENARIO_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SCENARIO_OVERRIDE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        # yeni senaryo = oyun baştan başlar (eski dünya durumu artık geçerli değil)
        state = default_state()
        save_state(state)
        clear_log()
        clear_gm_log()
    return jsonify({"ok": True})


@app.route("/api/scenario/reset-default", methods=["POST"])
def reset_scenario_to_default():
    with lock:
        if SCENARIO_OVERRIDE_FILE.exists():
            SCENARIO_OVERRIDE_FILE.unlink()
        state = default_state()
        save_state(state)
        clear_log()
        clear_gm_log()
    return jsonify({"ok": True})


# ----------------------------------------------------------------- oyun dışa/içe

@app.route("/api/game/export", methods=["GET"])
def export_game():
    with lock:
        state = load_state()
        log = read_log()
        gm_log = read_gm_log()
    return jsonify({"state": state, "log": log, "gm_log": gm_log})


@app.route("/api/game/import", methods=["POST"])
def import_game():
    body = request.get_json(force=True) or {}
    imported_state = body.get("state")
    imported_log = body.get("log")
    if not isinstance(imported_state, dict) or "world_state" not in imported_state:
        return jsonify({"error": "Geçersiz oyun dosyası: 'state.world_state' eksik."}), 400
    if not isinstance(imported_log, list):
        return jsonify({"error": "Geçersiz oyun dosyası: 'log' bir liste olmalı."}), 400

    with lock:
        base = default_state()
        base.update(imported_state)
        # Oturum ID'si başka bir bilgisayarda/durumda geçerli olmayabilir —
        # her içe aktarma güvenle yeni bir Claude oturumuyla devam etsin diye
        # her zaman sıfırlanır. Dünya durumu/envanter/ilişkiler/geçmiş korunur.
        base["session_id"] = None
        max_id = max([e.get("id", 0) for e in imported_log if isinstance(e, dict)], default=0)
        base["next_id"] = max(base.get("next_id", 1), max_id + 1)
        save_state(base)

        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            for entry in imported_log:
                if isinstance(entry, dict):
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        imported_gm_log = body.get("gm_log")
        if isinstance(imported_gm_log, list):
            GM_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(GM_LOG_FILE, "w", encoding="utf-8") as f:
                for entry in imported_gm_log:
                    if isinstance(entry, dict):
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return jsonify(
        {
            "ok": True,
            "world_state": public_world_state(base["world_state"]),
            "started": base["started"],
            "characters_confirmed": base["characters_confirmed"],
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    # threaded=True: bir claude çağrısı (15-90sn) sürerken /api/state yoklaması
    # (polling) donmasın diye — aksi halde tüm arayüz o süre boyunca kilitlenir.
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
