"""`data/state.json` — oyunun tek kalıcı durumu.

Buradaki kilit tüm sunucunun kilidi: tur akışı seri kalsın diye tek bir
`threading.Lock` var ve state.json'a yazan herkes ondan geçer.
"""

import json
import os
import threading
from pathlib import Path

from .. import config
from ..models.pending import PendingQueue
from ..models.round import Round
from ..models.world import TIME_FIELDS, WorldState
from .scenario_repo import ScenarioRepository

BASE_DIR = Path(__file__).resolve().parents[2]
STATE_FILE = BASE_DIR / "data" / "state.json"

# Sunucunun tek kilidi (bkz. mimari.md §2.6).
LOCK = threading.Lock()


class StateRepository:
    def __init__(self, state_file=None, scenario_repo=None):
        self.state_file = Path(state_file) if state_file else STATE_FILE
        self.scenario = scenario_repo or ScenarioRepository()
        self.lock = LOCK

    # --------------------------------------------------------- varsayılan
    @staticmethod
    def default_settings() -> dict:
        """Oyun içi ayarlar — arayüzden değiştirilebilir (bkz. /api/settings)."""
        return {
            # Bir turda oyunculara verilen süre (saniye). 0 = süre yok.
            "turn_seconds": config.TURN_SECONDS,
            # Küfür/argo dozu: kapalı | hafif | sert
            "profanity": config.PROFANITY,
            # Tur bazlı seçenek akışı. Kapatılamaz: senaryo yalnız sunulan
            # tercihlerle ilerler (serbest hamle kaldırıldı). Alan, eski
            # kayıtlarla uyum ve arayüzün okuması için duruyor.
            "round_mode": True,
            # Harita büyüklüğü: oyun BAŞLARKEN kaç şehir ve mekan üretileceği.
            # Oyun başladıktan sonra değiştirilemez — harita üretilmiştir.
            "map_size": config.MAP_SIZE,
            # TEK EKRAN KİPİ: herkes aynı masada, tek cihazın başında.
            # Açıkken oyun koduyla açılan bir "masa" oturumu TÜM karakterler
            # adına seçim yapabilir. Kapalıyken her oyuncu yalnız kendi
            # karakterini oynar (bkz. services/auth_service).
            "single_screen": config.SINGLE_SCREEN,
        }

    def default_state(self) -> dict:
        return {
            "world_state": self.scenario.initial_world_state(),
            "next_id": 1,
            "session_id": None,
            "characters_confirmed": False,
            "started": False,
            "settings": self.default_settings(),
            "round": Round().to_dict(),
            # Bir turda tetiklenip BİR SONRAKİ turun başında devreye girecek
            # kayıtlar (sahne yayını, tehdit devri, senarist direktifi).
            "pending": PendingQueue().to_dict(),
        }

    # ------------------------------------------------------------- okuma
    def load(self) -> dict:
        """Ham state sözlüğü (eski `load_state` ile birebir)."""
        if not self.state_file.exists():
            state = self.default_state()
            self.save(state)
            return state
        with open(self.state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        self.backfill(state)
        return state

    def backfill(self, state: dict) -> dict:
        """Devam eden bir oyun, `resources` alanı eklenmeden önce başlamış
        olabilir — eksikse senaryonun başlangıç stoğuyla doldur, oyun
        bozulmasın. Aynı şekilde zaman/hava alanları da sonradan eklendi:
        devam eden oyunda eksikse senaryonun başlangıç değeriyle doldur,
        yoksa arayüzde ve prompt'ta boş görünüp anlatıcı saati hiç
        ilerletmiyor."""
        ws = state.setdefault("world_state", {})
        if not ws.get("resources"):
            ws["resources"] = json.loads(json.dumps(
                self.scenario.load()["initial_world_state"].get("resources", {})))
        missing = [f for f in TIME_FIELDS if not ws.get(f)]
        if missing:
            initial = self.scenario.load()["initial_world_state"]
            for name in missing:
                if initial.get(name):
                    ws[name] = initial[name]
        # Harita da sonradan eklendi. Devam eden bir oyunda boşsa mevcut
        # konumdan tohumlanır — yoksa harita paneli, bir sonraki tur oynanana
        # kadar "boş" görünüyordu.
        if ws.get("location") and not (ws.get("map") or {}).get("current"):
            world = WorldState.from_dict(ws)
            world.sync_map()
            ws = state["world_state"] = world.to_dict()
        # Ayarlar ve tur kaydı sonradan eklendi: devam eden bir oyunda eksikse
        # varsayılanla doldur, yoksa tur akışı hiç açılmaz.
        settings = state.get("settings")
        if not isinstance(settings, dict):
            settings = state["settings"] = {}
        for name, value in self.default_settings().items():
            settings.setdefault(name, value)
        if not isinstance(state.get("round"), dict):
            state["round"] = Round().to_dict()
        # Bekleyen yayın kuyruğu da sonradan eklendi; devam eden oyunda boş
        # başlar (o oyunun ilk turu ertelenmiş bir sahne bulmaz).
        if not isinstance(state.get("pending"), dict):
            state["pending"] = PendingQueue().to_dict()
        return state

    # -------------------------------------------------------- tur kaydı
    @staticmethod
    def round_of(state: dict) -> Round:
        return Round.from_dict(state.get("round"))

    @staticmethod
    def store_round(state: dict, round_: Round) -> None:
        state["round"] = round_.to_dict()

    # ------------------------------------------------- bekleyen yayınlar
    @staticmethod
    def pending_of(state: dict) -> PendingQueue:
        return PendingQueue.from_dict(state.get("pending"))

    @staticmethod
    def store_pending(state: dict, queue: PendingQueue) -> None:
        state["pending"] = queue.to_dict()

    @staticmethod
    def settings_of(state: dict) -> dict:
        settings = state.get("settings")
        return settings if isinstance(settings, dict) else {}

    # ------------------------------------------------------------- yazma
    def save(self, state: dict) -> int:
        """Sürüm sayacı: istemciler /api/state?since=<v> ile yoklayıp
        değişmediyse gövdesiz cevap alır — böylece 1 saniyelik hızlı polling
        ucuz kalır. Yazma atomiktir: yarım kalan bir yazma kaydı bozmasın."""
        state["version"] = int(state.get("version", 0)) + 1
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.state_file)
        return int(state["version"])

    @staticmethod
    def version_of(state: dict) -> int:
        return int(state.get("version", 0))

    # ------------------------------------------------------- model köprüsü
    @staticmethod
    def world_of(state: dict) -> WorldState:
        """Ham state'ten alan modelini kurar."""
        return WorldState.from_dict(state.get("world_state") or {})

    @staticmethod
    def store_world(state: dict, world: WorldState) -> None:
        """Modeli ham state'e geri yazar (kaydetmeden önce çağrılır)."""
        state["world_state"] = world.to_dict()

    def load_world(self):
        """(state, WorldState) — servis katmanının olağan giriş noktası."""
        state = self.load()
        return state, self.world_of(state)

    def save_world(self, state: dict, world: WorldState) -> int:
        self.store_world(state, world)
        return self.save(state)

    # -------------------------------------------------------- yardımcılar
    @staticmethod
    def next_id(state: dict) -> int:
        val = state["next_id"]
        state["next_id"] += 1
        return val
