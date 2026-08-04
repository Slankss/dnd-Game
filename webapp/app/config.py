"""Yollar, ortam değişkenleri ve süreç geneli sabitler.

Tek kaynak burası: hiçbir modül kendi başına `os.environ` okumaz, yol
kurmaz. Böylece bir dosyanın yerini değiştirmek tek satırlık iş olur.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# webapp/ kökü (app/ paketinin bir üstü)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
# Vite build çıktısı. Depoya commit edilir — oyun npm kurulumu olmadan da
# çalışmalı (run.bat sadece Python çalıştırıyor).
DIST_DIR = STATIC_DIR / "dist"

STATE_FILE = DATA_DIR / "state.json"
LOG_FILE = DATA_DIR / "game_log.jsonl"
GM_LOG_FILE = DATA_DIR / "gm_log.jsonl"
SCENARIO_OVERRIDE_FILE = DATA_DIR / "scenario_override.json"
PLOT_FILE = DATA_DIR / "plot.json"
# Öğrenme katmanı: oyun kendi oynanışından ders çıkarır (bkz. learning_service).
LEARNING_FILE = DATA_DIR / "learning.json"
LEARNING_EVENTS_FILE = DATA_DIR / "learning_events.jsonl"
# Seçenek havuzu: sunulan ve seçilen her seçenek zar sonucuyla buraya düşer.
OPTIONS_POOL_FILE = DATA_DIR / "options_pool.jsonl"

# Öğrenilenlerin yazıldığı Claude yeteneği (skill). Depo kökündeki
# `.claude/skills/` altında durur: bir sonraki Claude Code oturumu onu
# kendiliğinden yükler, yani oyun oynandıkça yetenek de büyür.
SKILL_DIR = BASE_DIR.parent / ".claude" / "skills" / "kizil-cokus-anlatici"
SKILL_LEARNED_FILE = SKILL_DIR / "ogrenilenler.md"

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

PORT = int(os.environ.get("PORT", "5050"))

# --------------------------------------------------------------- oyun ayarları
# Bunlar sadece VARSAYILANDIR; oyun içinde arayüzden değiştirilebilir ve
# `state["settings"]` altında saklanır (bkz. StateRepository.default_state).
# Bir turda oyunculara verilen süre (saniye). 0 = süre yok.
TURN_SECONDS = int(os.environ.get("TURN_SECONDS", "180"))
# Küfür/argo dozu: "kapalı" | "hafif" | "sert"
PROFANITY = os.environ.get("PROFANITY", "hafif")
# Karakter başına sunulacak seçenek sayısı (senaryo kuralı: en az 3, en çok 8,
# sabit değil). Gerçek kaynak app/models/options.py'deki OPTION_MIN/MAX'tır.
OPTIONS_MIN = 3
OPTIONS_MAX = 8
