#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if ! command -v claude >/dev/null 2>&1; then
  echo "HATA: 'claude' komutu bulunamadı. Bu uygulama Claude Code CLI'ını kullanır."
  exit 1
fi

if ! claude auth status 2>/dev/null | grep -q '"loggedIn": true'; then
  echo "HATA: Claude Code'a giriş yapılmamış. Önce şunu çalıştırın: claude auth login"
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Sanal ortam oluşturuluyor..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

echo "Sunucu başlıyor: http://localhost:${PORT:-5050}"
python3 server.py
