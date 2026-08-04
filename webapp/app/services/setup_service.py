"""Oyun kurulumu ve durum anlık görüntüsü.

Karakter künyelerinin sabitlenmesi, oyunun açılış sahnesi, karakter
oluşturmanın elle bitirilmesi ve sıfırlama. Flask bilinmez: düz sözlük
döner, hata için `app.errors` istisnaları atılır.
"""

import json
import secrets
import time

from scenario import CHARACTER_TEMPLATE, GROUP_DISPLAY_NAME, GROUP_LABEL

from app import config
from app.errors import ValidationError
from app.models.learning import Learning
from app.models.mapgen import MAP_SIZES
from app.models.person import SHEET_FIELDS, Person, build_background, build_traits
from app.models.text import strip_option_block
from app.repositories import log_repo
from app.repositories.scenario_repo import ScenarioRepository
from app.repositories.state_repo import LOCK, StateRepository
from app.serializers import public_round, public_world_state
from app.services import prompt_builder, state_update
from app.services.learning_service import LearningService
from app.services.narrator_client import NarratorClient
from app.services.options_service import OptionsService
from app.services.worldgen_service import WorldGenService

# Kurulum ekranından gelebilecek künye alanları (isim + eşya + künye).
PICK_FIELDS = ("name", "item") + SHEET_FIELDS


class GameService:
    """`/api/state`, `/api/setup-characters`, `/api/start`,
    `/api/finish-chargen`, `/api/reset`."""

    def __init__(self, state_repo=None, scenario_repo=None, narrator=None,
                 game_log=None, gm_log=None, learning=None, options=None,
                 worldgen=None, rounds=None):
        self.scenario_repo = scenario_repo or ScenarioRepository()
        self.state_repo = state_repo or StateRepository(scenario_repo=self.scenario_repo)
        self.narrator = narrator or NarratorClient()
        self.game_log = game_log or log_repo.game_log()
        self.gm_log = gm_log or log_repo.gm_log()
        self.learning = learning or LearningService()
        self.options = options or OptionsService()
        self.worldgen = worldgen or WorldGenService(learning=self.learning)
        self._rounds = rounds

    @property
    def rounds(self):
        """Tur servisi geç bağlanır — RoundService bu modülü import etmiyor."""
        if self._rounds is None:
            from app.services.round_service import RoundService
            self._rounds = RoundService(
                state_repo=self.state_repo, scenario_repo=self.scenario_repo,
                narrator=self.narrator, game_log=self.game_log,
                gm_log=self.gm_log, learning=self.learning, options=self.options)
        return self._rounds

    # -------------------------------------------------------------- /api/state
    def snapshot(self, since=None) -> dict:
        with LOCK:
            state = self.state_repo.load()
            version = int(state.get("version", 0))
            # Hızlı yoklama: durum değişmediyse ağır gövdeyi hiç kurma.
            if since is not None and since.isdigit() and int(since) == version:
                return {"version": version, "changed": False}
            log = self.game_log.read()
            world = StateRepository.world_of(state)
            # Tur kapalıysa (ör. sunucu yeniden başladı) burada açılır: oyuncu
            # ekranı hiçbir zaman "tur yok" halinde kilitli kalmasın.
            onceki = json.dumps(state.get("round"), sort_keys=True)
            self.rounds.ensure_open(state, world)
            if json.dumps(state.get("round"), sort_keys=True) != onceki:
                version = self.state_repo.save(state)
            round_body = public_round(state.get("round"), self.rounds.actors(world))
        scenario = self.scenario_repo.load()
        return {
            "version": version,
            "changed": True,
            "world_state": public_world_state(state["world_state"]),
            "log": log,
            "started": state["started"],
            "characters_confirmed": state["characters_confirmed"],
            "chargen_done": world.chargen_complete(),
            "default_players": scenario["default_players"],
            "start_item_suggestions": scenario["start_item_suggestions"],
            "custom_scenario": self.scenario_repo.has_override,
            "group_label": GROUP_LABEL,
            "group_display_name": GROUP_DISPLAY_NAME,
            "settings": StateRepository.settings_of(state),
            "round": round_body,
        }

    # -------------------------------------------------- /api/setup-characters
    def setup_characters(self, players) -> dict:
        # `players` iki biçimde gelebilir: düz isim listesi (eski istemciler) ya da
        # karakter künyesi sözlükleri (isim + meslek/yaş/güçlü/zayıf/sır/eşya).
        picks = []
        for raw in players or []:
            if isinstance(raw, str):
                picks.append({"name": raw.strip()})
            elif isinstance(raw, dict):
                sheet = {key: str(raw.get(key) or "").strip() for key in PICK_FIELDS}
                picks.append(sheet)
        picks = [p for p in picks if p.get("name")]
        # tekrarları kaldır, sırayı koru
        seen = set()
        picks = [p for p in picks if not (p["name"] in seen or seen.add(p["name"]))]

        if not (1 <= len(picks) <= 8):
            raise ValidationError("1 ile 8 arasında karakter ismi girin.")

        with LOCK:
            state = self.state_repo.load()
            if state["started"]:
                raise ValidationError("Oyun zaten başladı, karakterler değiştirilemez.")
            if state["characters_confirmed"]:
                raise ValidationError("Karakterler zaten onaylandı. Değiştirmek için önce sıfırlayın.")

            world = StateRepository.world_of(state)
            start_location = world.location
            characters = {}
            for sheet in picks:
                char = json.loads(json.dumps(CHARACTER_TEMPLATE))
                char["location"] = start_location
                for key in SHEET_FIELDS:
                    char[key] = sheet.get(key) or None
                char["background"] = build_background(char)
                char["traits"] = build_traits(char)
                if char["background"]:
                    char["notes"] = ""
                # oyuncunun kurulum ekranında seçtiği tek başlangıç eşyası
                item = sheet.get("item")
                char["inventory"] = [item] if item else []
                characters[sheet["name"]] = Person.from_dict(char)
            world._touch("characters")
            world.characters = characters
            state["characters_confirmed"] = True
            # Künyeler ekrandan dolduysa oyun içi karakter oluşturma turuna gerek
            # yok — anlatıcı doğrudan hikayeye girer, zar ilk turdan itibaren atılır.
            world.ensure_flags()["chargen_done"] = all(
                c.background for c in characters.values()
            )
            StateRepository.store_world(state, world)
            self.state_repo.save(state)

        return {
            "world_state": public_world_state(state["world_state"]),
            "characters_confirmed": True,
        }

    # -------------------------------------------------------------- /api/start
    def start(self) -> dict:
        with LOCK:
            state = self.state_repo.load()
            if state["started"]:
                raise ValidationError("Oyun zaten başladı.")
            if not state["characters_confirmed"]:
                raise ValidationError("Önce karakterleri belirleyin.")

            scenario = self.scenario_repo.load()
            world = StateRepository.world_of(state)
            # Her oyun FARKLI bir yerde ve farklı fraksiyonlarla başlar; ikisi
            # de öğrenme defterine not edilir ki bir sonraki oyun tekrar etmesin.
            uretilen = self.worldgen.apply(world, self.worldgen.generate(
                seed_factions=(scenario["initial_world_state"] or {}).get("factions")))
            # HARİTA OYUN BAŞINDA BÜTÜNÜYLE ÜRETİLİR: şehirler, kategorili
            # mekanlar, yollar ve mesafeler. Oyuncu hepsini görmez — üretilen
            # yerler `bilinmiyor` başlar, keşfedildikçe açılır.
            harita_ozeti = self.worldgen.build_map(
                world,
                StateRepository.settings_of(state).get("map_size"),
                start_name=(uretilen["start"] or {}).get("name") or "",
            )
            world_note = self.worldgen.start_note(uretilen["start"], uretilen["factions"])
            world_note += "\n\n" + self.worldgen.map_note(world, harita_ozeti)
            ws = world.to_dict()
            players = list(world.characters.keys())
            hook = secrets.choice(scenario["opening_hooks"])
            sheets_done = world.sheets_complete()
            if sheets_done:
                chargen_note = (
                    "KÜNYELER TAMAMLANDI — oyuncular karakter oluşturma ekranını "
                    "doldurdu. Karakter oluşturma sorusu SORMA, seçenek sunma. "
                    "Açılış sahnesinde herkesi künyesine uygun biçimde tanıt ve "
                    "doğrudan asıl hikayeye geç: açılış olayını somut bir ZORLUĞA "
                    "dönüştürüp `challenges` altına kaydet ve tek satırlık DURUM "
                    "özetiyle bitir. Metne SEÇENEK LİSTESİ YAZMA (A/B/C, "
                    "'SEÇENEKLER:'); kararlar yalnız `options` alanına gider. "
                    "Durum güncelleme bloğunda `flags.chargen_done` "
                    "alanını true yap ve her karaktere mesleğine uyan 1-2 mütevazı "
                    "eşyayı `inventory_add` ile ekle. Bu turda zar mekaniği YOK."
                )
            else:
                chargen_note = (
                    "Yukarıdaki SCENARIO talimatlarındaki 'OYUN BAŞLANGICI VE "
                    "KARAKTER OLUŞTURMA' bölümüne göre davran: bu olayı sahne "
                    "olarak anlat, ardından yukarıdaki karakter listesindeki "
                    "HERKES için karakter oluşturma seçeneklerini sun. Bu turda "
                    "zar mekaniği YOK."
                )
            settings = StateRepository.settings_of(state)
            extra_system = (
                "OYUN BAŞLANGICI.\n"
                f"Bu oyundaki karakterler (SABİT, TAM LİSTE — başka oyuncu karakteri "
                f"YOK, isim uydurma): {', '.join(players)}.\n"
                f"Rastgele açılış olayı (sunucu tarafından seçildi): {hook}\n\n"
                + world_note
                + "\n\n"
                + prompt_builder.reflex_note(ws, settings.get("profanity") or "hafif")
                + "\n\n"
                + self.options.instruction(players)
                + "\n"
                + chargen_note
                + "\n\nKARAKTER KÜNYELERİ (kurulum ekranından geldi; meslek/yaş/"
                "güçlü-zayıf yan BAĞLAYICIDIR, eşyalar zaten envanterde — tekrar "
                "ekleme. SIRLAR sadece sana aittir, hiçbir koşulda metinde "
                "açıklama, sadece hikayenin gizli motoru olarak kullan):\n"
                + prompt_builder.character_sheets_note(ws)
                + "\n\nORTAK STOK YOK: `resources` bilerek BOŞ başlar. Ortada bir "
                "klan, topluluk ya da depo yok — grubun sahip olduğu tek şey "
                "yukarıdaki kişisel envanterlerdir. Açılış sahnesinde bir depodan, "
                "stoktan, 'elimizdeki erzaktan' söz ETME ve `resources` altına "
                "hiçbir başlangıç kalemi YAZMA. Stok ancak grup ilerideki turlarda "
                "bir topluluk kurar/katılır ya da oyuncular açıkça sayım isterse "
                "doğar (bkz. SCENARIO → 'GRUP KAYNAKLARI').\n\n"
                "GÜNCEL DÜNYA DURUMU (JSON):\n"
                + json.dumps(ws, ensure_ascii=False)
            )
            prompt = "(Oyun başlıyor. Sahneyi aç.)"

            # Açılış sahnesi dünyayı kuruyor: bütün oyunun üzerine bindiği tur
            # burası, effort'tan kısılacak yer değil (bkz. models/effort).
            result = self.narrator.ask(prompt, extra_system, None,
                                       scenario["scenario_text"],
                                       effort=config.EFFORT_KEY)

            state["session_id"] = result.get("session_id")
            state["started"] = True

            raw_text = result.get("result", "")
            gm_text, patches = state_update.extract(raw_text)
            # Künyeler hazırsa açılış sahnesi doğrudan oyuna girer: karar
            # seçenekleri metinde değil, seçenek havuzunda gösterilir.
            if sheets_done:
                gm_text = strip_option_block(gm_text)
            gun = world.day if isinstance(world.day, int) else None
            for patch in patches:
                world.merge_patch(patch)
                self.learning.absorb_patch(patch, day=gun)
            world.sync_map()
            # Açılış sahnesinden sonra herkes seçeneklerle karşılansın.
            self.options.refresh(world, world.present_players(),
                                 learning=self.learning, turn=0)

            gm_entry = {
                "id": self.state_repo.next_id(state),
                "role": "assistant",
                "kind": "opening",
                "text": gm_text,
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self.game_log.append(gm_entry)
            # Üretilen dünya anlatıcı günlüğüne de not edilir: hangi başlangıç,
            # hangi fraksiyonlar — GM sonradan görebilsin.
            self.gm_log.append({
                "id": None,
                "role": "worldgen",
                "text": "🌍 Bu oyunun dünyası üretildi:\n" + world_note,
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            StateRepository.store_world(state, world)
            self.rounds.ensure_open(state, world)
            self.state_repo.save(state)

        return {"gm_entry": gm_entry,
                "world_state": public_world_state(state["world_state"]),
                "round": state.get("round"),
                "started": True}

    # ----------------------------------------------------- /api/finish-chargen
    def finish_chargen(self) -> dict:
        """Karakter oluşturmayı elle bitirir. Biri hiç cevap vermezse oyun sonsuza
        kadar chargen'de takılı kalıp zar mekaniği ve ortak karar açılmıyordu."""
        with LOCK:
            state = self.state_repo.load()
            if not state["started"]:
                raise ValidationError("Oyun henüz başlamadı.")
            world = StateRepository.world_of(state)
            world.ensure_flags()["chargen_done"] = True
            StateRepository.store_world(state, world)
            self.state_repo.save(state)
        return {"ok": True, "world_state": public_world_state(state["world_state"])}

    # ----------------------------------------------------------- /api/settings
    def update_settings(self, patch) -> dict:
        """Oyun içi ayarlar: tur süresi, küfür dozu, tur bazlı akış.

        Öğrenme defteri ve seçenek havuzu SİLİNMEZ — ayar değişikliği oyunun
        hafızasını sıfırlamaz."""
        if not isinstance(patch, dict) or not patch:
            raise ValidationError("Boş ayar gönderildi.")
        with LOCK:
            state = self.state_repo.load()
            settings = StateRepository.settings_of(state)

            if "turn_seconds" in patch:
                saniye = patch.get("turn_seconds")
                if isinstance(saniye, str) and saniye.strip().isdigit():
                    saniye = int(saniye.strip())
                if not isinstance(saniye, int) or isinstance(saniye, bool) or saniye < 0:
                    raise ValidationError("Tur süresi 0 ya da pozitif bir sayı olmalı.")
                # 0 = süre yok. Çok kısa süre turu oynanamaz hale getiriyor.
                if saniye and saniye < 20:
                    raise ValidationError("Tur süresi en az 20 saniye olmalı (0 = süresiz).")
                settings["turn_seconds"] = min(saniye, 3600)

            if "profanity" in patch:
                doz = str(patch.get("profanity") or "").strip().lower()
                if doz not in ("kapalı", "hafif", "sert"):
                    raise ValidationError("Küfür ayarı: kapalı, hafif ya da sert.")
                settings["profanity"] = doz

            if "map_size" in patch:
                boyut = str(patch.get("map_size") or "").strip().lower()
                if boyut not in MAP_SIZES:
                    raise ValidationError(
                        "Harita büyüklüğü: küçük, orta ya da büyük.")
                if state.get("started"):
                    # Harita oyun başında bir kez üretilir ve sabittir; sonradan
                    # büyütmek mevcut mesafeleri ve keşifleri anlamsız kılardı.
                    raise ValidationError(
                        "Harita zaten üretildi — büyüklük ancak yeni oyunda "
                        "değişir (önce sıfırla).")
                settings["map_size"] = boyut

            if "round_mode" in patch and not patch.get("round_mode"):
                # Tur bazlı akış artık kapatılamaz: senaryo yalnız sunulan
                # tercihlerle ilerler, serbest yazışma kipi kaldırıldı.
                raise ValidationError(
                    "Serbest yazışma kipi kapalı — oyun yalnız sunulan "
                    "seçeneklerle ilerler."
                )

            state["settings"] = settings
            world = StateRepository.world_of(state)
            self.rounds.ensure_open(state, world)
            version = self.state_repo.save(state)
        return {"ok": True, "settings": settings, "version": version,
                "round": state.get("round")}

    # -------------------------------------------------------------- /api/reset
    def reset(self, keep_learning: bool = True) -> dict:
        """Oyunu sıfırlar. Öğrenme defteri VARSAYILAN OLARAK KORUNUR: oyun
        yeniden kurulduğunda öğrendiklerini unutmasın (istenirse
        `keep_learning=false` ile defter de silinir)."""
        with LOCK:
            state = self.state_repo.default_state()
            self.state_repo.save(state)
            self.game_log.clear()
            self.gm_log.clear()
            self.options.clear()
            if not keep_learning:
                self.learning.repo.save(Learning())
                self.learning.export_skill()
        return {"ok": True, "learning_kept": bool(keep_learning)}
