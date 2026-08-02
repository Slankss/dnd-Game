"""Giriş noktası.

Uygulamanın kendisi `app/` paketinde kurulur:
  app/models/        alan modelleri (saf Python, I/O yok)
  app/repositories/  dosya kalıcılığı (state.json, *.jsonl, senaryo, plan)
  app/services/      iş akışı (tur, kurulum, anlatıcı, senaryo)
  app/api/           Flask blueprint'leri (ince kontrolcüler)
Ayrıntı: docs/mimari.md
"""

from app import create_app
from app.config import PORT

app = create_app()

if __name__ == "__main__":
    # threaded=True: bir claude çağrısı (15-90 sn) sürerken /api/state
    # yoklaması donmasın diye — aksi halde tüm arayüz o süre boyunca kilitlenir.
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
