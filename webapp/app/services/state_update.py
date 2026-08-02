"""Modelin yanıtından durum güncellemesini söker.

Ekrana ASLA ham JSON düşmemeli — ne oyuncuya ne anlatıcıya. Bu yüzden üç
kademeli çalışır: (1) ``` içindeki JSON blokları, (2) fence'i unutulmuş ham
JSON nesneleri, (3) boşta kalan fence kalıntıları. Bozuk JSON parse
edilemese bile metinden SİLİNİR.
"""

import json
import re

# Bir bloğun "durum güncellemesi" olduğunu ele veren anahtarlar — fence'i
# unutulmuş ham JSON'ı normal metindeki süslü parantezlerden ayırmak için.
STATE_KEYS = {
    "day", "time_of_day", "clock", "season", "weather", "temperature",
    "location", "tension", "factions", "characters", "npcs",
    "resources", "challenges", "zombie_sightings_add", "flags", "narrator",
}

# Etiketi ne olursa olsun (state-update / json / etiketsiz), içinde bir JSON
# nesnesi olan HER ``` bloğu. Etiketin doğru yazılmasına güvenmiyoruz.
FENCED_STATE_RE = re.compile(
    r"```[ \t]*[A-Za-z_-]*[ \t]*\r?\n?(\{.*?\})[ \t]*\r?\n?```", re.DOTALL
)
LEFTOVER_FENCE_RE = re.compile(
    r"```[ \t]*(?:state-update|state_update|json)[ \t]*\r?\n?", re.IGNORECASE
)
EMPTY_FENCE_RE = re.compile(r"```\s*```", re.DOTALL)

# Model bloğu sık sık {"state-update": {...}} diye sarmalıyor. Sarmalanmış
# hali birleştirmede hiçbir bilinen alana denk gelmediği için sessizce
# yutuluyordu — bu yüzden birleştirmeden önce daima soyuyoruz.
PATCH_WRAPPER_KEYS = {"state-update", "state_update", "stateupdate", "world_state", "patch"}


def _normalize_patch(obj):
    """Sarmalayıcı anahtar varsa içindeki gerçek yamayı döndürür."""
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
    """Model ``` fence'ini unuttuğunda ham JSON metnin içinde kalıyordu. Bu
    tarayıcı, gerçekten JSON olarak parse edilen VE bilinen bir durum alanı
    içeren nesneleri söker; normal metindeki süslü parantezlere dokunmaz."""
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


def extract(text: str):
    """(temizlenmiş metin, yama listesi) döndürür."""
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
