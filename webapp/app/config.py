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
# Effort TURA GÖRE seçilir (bkz. models/effort). `EFFORT` sıradan turların
# taban seviyesi, `EFFORT_KEY` ise sahnenin sürekliliğinin pahalıya patladığı
# turlarda (karşılaşma, senarist beat'i, yüksek gerilim, ölüme yakın karakter,
# açılış) çıkılan seviyedir. İkisini eşitlerseniz effort yine sabitlenir.
EFFORT = os.environ.get("CLAUDE_EFFORT", "medium")
EFFORT_KEY = os.environ.get("CLAUDE_EFFORT_KEY", "high")
# Ölçüm: aynı tur `high` ile 186.9 saniye sürdü — eski 180 sn'lik tavan
# kritik turları zaman aşımına düşürüyordu.
CLAUDE_TIMEOUT = int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "300"))

# --------------------------------------------------------------------- kimlik
# Oyun dışarı açık bir sunucuda çalışabilir: hem oyuncu hem anlatıcı ekranı
# oturum tabanlı kimlikle korunur (bkz. services/auth_service).

# Anlatıcı ekranı (/secrets) girişi.
GM_PIN = os.environ.get("GM_PIN", "1453")
# Oyuncunun karakterini İLK KEZ sahiplenirken sorulan davet kodu. Anlatıcı
# bunu masaya söyler; sonraki girişlerde sorulmaz.
GAME_CODE = os.environ.get("GAME_CODE", "kizil")
# Oturum çerezini imzalayan anahtar. .env'de yoksa data/ altında üretilir ve
# saklanır — yeniden başlatma herkesi dışarı atmasın.
SECRET_KEY = os.environ.get("SECRET_KEY", "")
SECRET_KEY_FILE = DATA_DIR / "secret_key"
# Oyuncu hesapları (şifre ÖZETLERİ). Oyun sıfırlansa da silinmez.
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
# Sunucu HTTPS arkasındaysa çerez yalnız güvenli bağlantıda gönderilsin.
# Ters vekil (nginx/Caddy) kullanıyorsanız .env'de 1 yapın.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") not in ("0", "", "false", "False")
# Oturum kaç gün açık kalsın (oyun gecesi arası yeniden giriş istenmesin).
SESSION_DAYS = int(os.environ.get("SESSION_DAYS", "30"))
# TEK EKRAN KİPİ varsayılanı: herkes aynı masada tek cihazın başındaysa
# oyun koduyla açılan bir "masa" oturumu tüm karakterler adına oynar.
# Oyun içinden de açılıp kapanır (ayarlar → tek ekran).
SINGLE_SCREEN = os.environ.get("SINGLE_SCREEN", "0") not in ("0", "", "false", "False")

PORT = int(os.environ.get("PORT", "5050"))

# --------------------------------------------------------------- oyun ayarları
# Bunlar sadece VARSAYILANDIR; oyun içinde arayüzden değiştirilebilir ve
# `state["settings"]` altında saklanır (bkz. StateRepository.default_state).
# Bir turda oyunculara verilen süre (saniye). 0 = süre yok.
TURN_SECONDS = int(os.environ.get("TURN_SECONDS", "180"))

# Harita büyüklüğü: küçük | orta | büyük (bkz. models/mapgen.MAP_SIZES).
# Oyun başında üretilecek şehir ve mekan sayısını belirler.
MAP_SIZE = os.environ.get("MAP_SIZE", "orta")
# Küfür/argo dozu: "kapalı" | "hafif" | "sert"
PROFANITY = os.environ.get("PROFANITY", "hafif")
# Karakter başına sunulacak seçenek sayısı (senaryo kuralı: en az 3, en çok 8,
# sabit değil). Gerçek kaynak app/models/options.py'deki OPTION_MIN/MAX'tır.
OPTIONS_MIN = 3
OPTIONS_MAX = 8
