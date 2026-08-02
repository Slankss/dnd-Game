"""İş akışı katmanı — modelleri ve repo'ları orkestre eder.

Flask burada bilinmez: servisler düz sözlük döndürür, hata için
`app.errors` istisnalarını atar. API katmanı bu modüldeki tekil örnekleri
çağırır (`services.turn.play(...)` gibi); testler kendi repo/istemci
örnekleriyle yeni bir servis kurabilir.

Dört servis, dört akış:
  * `game`     — kurulum, açılış, sıfırlama, durum anlık görüntüsü
  * `turn`     — bir oyuncu turu ve karakter devralma
  * `gm`       — anlatıcı notu/müdahalesi ve elle yama
  * `scenario` — senaryo ve oyun dışa/içe aktarma
"""

from app.services.gm_service import GmService
from app.services.scenario_service import ScenarioService
from app.services.setup_service import GameService
from app.services.turn_service import TurnService

# Süreç geneli tekil örnekler. Hepsi aynı `state_repo.LOCK` kilidini kullanır,
# dolayısıyla tur akışı bugünkü gibi seri kalır.
game = GameService()
turn = TurnService()
gm = GmService()
scenario = ScenarioService()

__all__ = ["GameService", "TurnService", "GmService", "ScenarioService",
           "game", "turn", "gm", "scenario"]
