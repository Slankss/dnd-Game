"""İş akışı katmanı — modelleri ve repo'ları orkestre eder.

Flask burada bilinmez: servisler düz sözlük döndürür, hata için
`app.errors` istisnalarını atar. API katmanı bu modüldeki tekil örnekleri
çağırır (`services.turn.play(...)` gibi); testler kendi repo/istemci
örnekleriyle yeni bir servis kurabilir.

Altı servis, altı akış:
  * `game`     — kurulum, açılış, ayarlar, sıfırlama, durum anlık görüntüsü
  * `turn`     — serbest metin turu ve karakter devralma
  * `rounds`   — tur bazlı akış: seçim topla, süre dolunca/herkes seçince gönder
  * `gm`       — anlatıcı notu/müdahalesi ve elle yama
  * `scenario` — senaryo ve oyun dışa/içe aktarma
  * `learning` — öğrenme defteri (her turda beslenir, yeteneğe yazılır)
  * `grid`     — sahnenin kare haritası (2D ızgara, O(1) hareket)
"""

from app.services.gm_service import GmService
from app.services.grid_service import GridService
from app.services.learning_service import LearningService
from app.services.options_service import OptionsService
from app.services.round_service import RoundService
from app.services.scenario_service import ScenarioService
from app.services.setup_service import GameService
from app.services.turn_service import TurnService
from app.services.worldgen_service import WorldGenService

# Süreç geneli tekil örnekler. Hepsi aynı `state_repo.LOCK` kilidini kullanır,
# dolayısıyla tur akışı bugünkü gibi seri kalır. Öğrenme defteri ve seçenek
# havuzu da tek örnek üzerinden paylaşılır: her akış aynı deftere yazar.
learning = LearningService()
options = OptionsService()
turn = TurnService(learning=learning, options=options)
rounds = RoundService(learning=learning, options=options, turn=turn)
game = GameService(learning=learning, options=options, rounds=rounds)
gm = GmService()
grid = GridService()
scenario = ScenarioService()

__all__ = ["GameService", "TurnService", "RoundService", "GmService",
           "GridService", "ScenarioService", "LearningService", "OptionsService",
           "WorldGenService", "game", "turn", "rounds", "gm", "grid", "scenario",
           "learning", "options"]
