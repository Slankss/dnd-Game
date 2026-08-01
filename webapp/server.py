import json
import os
import re
import secrets
import subprocess
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

from scenario import (
    SCENARIO_TEXT,
    INITIAL_WORLD_STATE,
    OPENING_HOOKS,
    DEFAULT_PLAYERS,
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
        }
    return {
        "scenario_text": SCENARIO_TEXT,
        "initial_world_state": INITIAL_WORLD_STATE,
        "default_players": DEFAULT_PLAYERS,
        "opening_hooks": OPENING_HOOKS,
    }


# ---------------------------------------------------------------- state.json

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
        return json.load(f)


def save_state(state):
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

def _merge_person_like(target: dict, name: str, fields: dict) -> None:
    """`characters` ve `npcs` için ortak birleştirme mantığı (background/
    traits/status/location/notes üzerine yazar; inventory ekler/çıkarır;
    relationships iç içe günceller)."""
    entry = target.setdefault(
        name,
        {"background": None, "traits": None, "status": "İyi", "location": None,
         "inventory": [], "relationships": {}, "notes": ""},
    )
    for scalar_key in ("background", "traits", "status", "location", "notes"):
        if scalar_key in fields:
            entry[scalar_key] = fields[scalar_key]

    if isinstance(fields.get("relationships"), dict):
        entry.setdefault("relationships", {}).update(fields["relationships"])

    inv = entry.setdefault("inventory", [])
    for item in fields.get("inventory_add") or []:
        if item not in inv:
            inv.append(item)
    for item in fields.get("inventory_remove") or []:
        if item in inv:
            inv.remove(item)


TENSION_LEVELS = ("düşük", "orta", "yüksek")


def deep_merge_world_state(world_state: dict, patch: dict) -> None:
    if "day" in patch and isinstance(patch["day"], int):
        world_state["day"] = patch["day"]

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

    for section in ("characters", "npcs"):
        if section in patch and isinstance(patch[section], dict):
            target = world_state.setdefault(section, {})
            for name, fields in patch[section].items():
                if not isinstance(fields, dict):
                    continue
                _merge_person_like(target, name, fields)

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


def chargen_complete(world_state: dict) -> bool:
    characters = world_state.get("characters", {})
    if not characters:
        return False
    return all(info.get("background") for info in characters.values())


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


STATE_BLOCK_RE = re.compile(r"```state-update\s*(\{.*?\})\s*```", re.DOTALL)


def extract_state_update(text: str):
    """Metindeki TÜM ```state-update``` bloklarını (model bazen birden fazla
    ayrı blok yazabiliyor) ayrıştırıp listeler, hepsini metinden temizler."""
    patches = []

    def _collect(match):
        try:
            patches.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            pass
        return ""

    cleaned = STATE_BLOCK_RE.sub(_collect, text).strip()
    return cleaned, patches


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
    with lock:
        state = load_state()
        log = read_log()
    return jsonify(
        {
            "world_state": state["world_state"],
            "log": log,
            "started": state["started"],
            "characters_confirmed": state["characters_confirmed"],
            "default_players": load_scenario()["default_players"],
            "custom_scenario": SCENARIO_OVERRIDE_FILE.exists(),
            "group_label": GROUP_LABEL,
            "group_display_name": GROUP_DISPLAY_NAME,
        }
    )


@app.route("/api/setup-characters", methods=["POST"])
def setup_characters():
    body = request.get_json(force=True) or {}
    names = body.get("players") or []
    names = [n.strip() for n in names if isinstance(n, str) and n.strip()]
    # tekrarları kaldır, sırayı koru
    seen = set()
    names = [n for n in names if not (n in seen or seen.add(n))]

    if not (1 <= len(names) <= 8):
        return jsonify({"error": "1 ile 8 arasında karakter ismi girin."}), 400

    with lock:
        state = load_state()
        if state["started"]:
            return jsonify({"error": "Oyun zaten başladı, karakterler değiştirilemez."}), 400
        if state["characters_confirmed"]:
            return jsonify({"error": "Karakterler zaten onaylandı. Değiştirmek için önce sıfırlayın."}), 400

        start_location = state["world_state"].get("location")
        characters = {}
        for name in names:
            char = json.loads(json.dumps(CHARACTER_TEMPLATE))
            char["location"] = start_location
            characters[name] = char
        state["world_state"]["characters"] = characters
        state["characters_confirmed"] = True
        save_state(state)

    return jsonify(
        {
            "world_state": state["world_state"],
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
        extra_system = (
            "OYUN BAŞLANGICI.\n"
            f"Bu oyundaki karakterler: {', '.join(players)}.\n"
            f"Rastgele açılış olayı (sunucu tarafından seçildi): {hook}\n\n"
            "Yukarıdaki SCENARIO talimatlarındaki 'OYUN BAŞLANGICI VE KARAKTER "
            "OLUŞTURMA' bölümüne göre davran: bu olayı sahne olarak anlat, "
            "ardından yukarıdaki karakter listesindeki HERKES için karakter "
            "oluşturma seçeneklerini sun. Bu turda zar mekaniği YOK."
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

    return jsonify({"gm_entry": gm_entry, "world_state": state["world_state"], "started": True})


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
        valid_players = list(state["world_state"]["characters"].keys())
        in_chargen = not chargen_complete(state["world_state"])
        ts = time.strftime("%Y-%m-%d %H:%M:%S")

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
                    "state-update bloğuna characters.<isim> altına background/traits "
                    "eklemeyi UNUTMA — hepsi TEK bir state-update bloğunda birleşsin.\n\n"
                    + combined
                    + "\n\nGÜNCEL DÜNYA DURUMU (JSON):\n"
                    + json.dumps(state["world_state"], ensure_ascii=False)
                )
            else:
                extra_system = (
                    "ÇOKLU KARAKTER TURU — SCENARIO'daki 'ÇOKLU KARAKTER TURU' bölümüne "
                    "göre davran: aşağıdaki her satır farklı bir karakterin AYNI ANDA "
                    "aldığı farklı bir aksiyon, her biri KENDİ zarına göre ayrı ayrı "
                    "sonuçlanır ama sahneyi birleşik/akıcı anlat.\n"
                    "HATIRLATMA: yanıtının sonuna TEK bir state-update bloğu ekle, içine "
                    "en azından tension VE narrator.plot_summary (2-4 cümlelik güncel "
                    "özet) yaz — ikisi de her turda zorunlu.\n\n"
                    + combined
                    + "\n\nGÜNCEL DÜNYA DURUMU (JSON):\n"
                    + json.dumps(state["world_state"], ensure_ascii=False)
                )
        else:
            is_group = player == GROUP_LABEL
            if not is_group and player not in valid_players:
                return jsonify({"error": f"player must be one of {valid_players + [GROUP_LABEL]}"}), 400
            if is_group and in_chargen:
                return jsonify({"error": "Ortak karar, karakter oluşturma bitmeden kullanılamaz."}), 400

            if in_chargen:
                roll, band = None, None
                extra_system = (
                    "KARAKTER OLUŞTURMA AŞAMASI — bu turda zar mekaniği uygulanmaz.\n"
                    f"Bu mesajı yazan: {player}. Eğer bu mesajda {player} karakterini "
                    "kuruyorsa (bir seçenek seçtiyse ya da kendi tarifini yazdıysa), "
                    "yanıtının sonuna MUTLAKA ```state-update``` bloğu ekleyip "
                    f'characters.{player} altına background/traits alanlarını yaz — '
                    "bunu unutma, atlarsan karakter bilgisi kalıcı olarak kaybolur.\n\n"
                    "GÜNCEL DÜNYA DURUMU (JSON, sadece senin referansın, oyunculara okuma):\n"
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
                    f"ZAR: {roll} ({band})\n\n"
                    + group_note
                    + "HATIRLATMA (teknik, MUTLAKA uygula): yanıtının SONUNA bir "
                    "```state-update``` bloğu ekle ve içine EN AZINDAN şunları yaz — "
                    "bu iki alan her turda zorunlu, başka hiçbir şey değişmese bile "
                    'atlama: (1) bu sahnenin "tension" seviyesi (\"düşük\"/\"orta\"/'
                    '\"yüksek\"); (2) `narrator.plot_summary` — hikayenin şu anki '
                    "durumunun 2-4 cümlelik güncel özeti (bu SADECE anlatıcı ekranında "
                    "görünür, oyunculara asla gösterilmez). "
                    "Ayrıca gerçekten değişen başka alanlar varsa (karakter durumu/"
                    "envanteri/ilişkisi, fraksiyon tavrı, gün, konum, yeni NPC, "
                    "narrator.puzzles/upcoming_events vb.) aynı bloğa ekle.\n\n"
                    "GÜNCEL DÜNYA DURUMU (JSON, sadece senin referansın, oyunculara okuma):\n"
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
        for patch in patches:
            deep_merge_world_state(state["world_state"], patch)

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
            "world_state": state["world_state"],
        }
    )


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
    with lock:
        state = load_state()
        gm_log = read_gm_log()
    return jsonify({"world_state": state["world_state"], "gm_log": gm_log, "started": state["started"]})


@app.route("/api/gm/note", methods=["POST"])
def gm_note():
    body = request.get_json(force=True) or {}
    if body.get("pin") != GM_PIN:
        return jsonify({"error": "Yanlış PIN."}), 403
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Not metni boş olamaz."}), 400

    with lock:
        state = load_state()
        if not state["started"]:
            return jsonify({"error": "Oyun henüz başlamadı — önce ana ekrandan başlatın."}), 400

        prompt = f"[ANLATICI NOTU - GİZLİ]\n{text}"
        extra_system = (
            "Bu mesaj oyunculardan DEĞİL, oyunu yöneten gerçek kişiden (GM) "
            "geliyor ve oyunculara ASLA gösterilmeyecek. SCENARIO talimatlarındaki "
            "'Anlatıcıdan (GM) gizli yönetmen notu gelirse' bölümüne göre davran: "
            "notu otoriter kabul et, gerekiyorsa narrator alanlarını (plot_summary/"
            "puzzles/upcoming_events) state-update ile güncelle, ve SADECE bu "
            "anlatıcıya hitap eden kısa bir onay/yanıt yaz — bu yanıt oyunculara "
            "gösterilmeyecek, endişelenme.\n\n"
            "GÜNCEL DÜNYA DURUMU (JSON):\n" + json.dumps(state["world_state"], ensure_ascii=False)
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
            deep_merge_world_state(state["world_state"], patch)

        note_entry = {"id": None, "role": "gm_note", "text": text, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
        reply_entry = {"id": None, "role": "gm_reply", "text": reply_text, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
        append_gm_log(note_entry)
        append_gm_log(reply_entry)

        save_state(state)

    return jsonify({"note_entry": note_entry, "reply_entry": reply_entry, "world_state": state["world_state"]})


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
            "world_state": base["world_state"],
            "started": base["started"],
            "characters_confirmed": base["characters_confirmed"],
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    # threaded=True: bir claude çağrısı (15-90sn) sürerken /api/state yoklaması
    # (polling) donmasın diye — aksi halde tüm arayüz o süre boyunca kilitlenir.
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
