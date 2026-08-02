"""Zarlar: oyuncunun d100'ü ve dünyanın kendi zarı."""

import secrets
import time

DICE_BANDS = [
    (1, 5, "Felaket"),
    (6, 25, "Başarısız"),
    (26, 45, "Kısmi Başarı"),
    (46, 70, "Başarı"),
    (71, 95, "Güçlü Başarı"),
    (96, 100, "Kritik"),
]


def roll_d100() -> int:
    return secrets.randbelow(100) + 1


def band_for(roll: int) -> str:
    for lo, hi, label in DICE_BANDS:
        if lo <= roll <= hi:
            return label
    return "Bilinmiyor"


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

# Dünya zarı geçmişinde tutulan atış sayısı.
WORLD_ROLL_HISTORY_LIMIT = 12


def world_band_for(roll: int) -> str:
    for lo, hi, label in WORLD_DICE_BANDS:
        if lo <= roll <= hi:
            return label
    return "Durgun"


def new_world_roll() -> dict:
    """Yeni bir dünya zarı kaydı üretir (henüz dünyaya yazılmaz)."""
    roll = roll_d100()
    band = world_band_for(roll)
    return {"roll": roll, "band": band, "hint": WORLD_BAND_HINTS[band],
            "ts": time.strftime("%Y-%m-%d %H:%M:%S")}


def roll_world_dice(world_state) -> dict:
    """Dünya zarını atar ve kaydı dünyaya yazar. `world_state` ham sözlük ya
    da WorldState olabilir — geçiş sırasında ikisi de kullanılıyor."""
    entry = new_world_roll()
    if isinstance(world_state, dict):
        world_state["world_roll"] = entry
        history = world_state.setdefault("world_roll_history", [])
    else:
        world_state.set_world_roll(entry)
        history = world_state.world_roll_history
    history.append({"roll": entry["roll"], "band": entry["band"], "ts": entry["ts"]})
    del history[:-WORLD_ROLL_HISTORY_LIMIT]  # son 12 atış yeter
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


class Dice:
    """Oyuncu zarı — ince bir isim alanı (bkz. modül fonksiyonları)."""

    BANDS = DICE_BANDS

    @staticmethod
    def roll() -> int:
        return roll_d100()

    @staticmethod
    def band_for(roll: int) -> str:
        return band_for(roll)


class WorldDice:
    """Dünya zarı — oyunculara asla gösterilmez."""

    BANDS = WORLD_DICE_BANDS
    HINTS = WORLD_BAND_HINTS

    @staticmethod
    def roll(world_state=None) -> dict:
        """`world_state` verilirse kayıt dünyaya da yazılır."""
        if world_state is None:
            return new_world_roll()
        return roll_world_dice(world_state)

    @staticmethod
    def band_for(roll: int) -> str:
        return world_band_for(roll)

    @staticmethod
    def note(entry: dict) -> str:
        return world_dice_note(entry)
