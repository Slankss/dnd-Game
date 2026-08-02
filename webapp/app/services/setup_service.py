"""Oyun kurulumu ve durum anlık görüntüsü.

Karakter künyelerinin sabitlenmesi, oyunun açılış sahnesi, karakter
oluşturmanın elle bitirilmesi ve sıfırlama. Flask bilinmez: düz sözlük
döner, hata için `app.errors` istisnaları atılır.
"""

import json
import secrets
import time

from scenario import CHARACTER_TEMPLATE, GROUP_DISPLAY_NAME, GROUP_LABEL

from app.errors import ValidationError
from app.models.person import SHEET_FIELDS, Person, build_background, build_traits
from app.repositories import log_repo
from app.repositories.scenario_repo import ScenarioRepository
from app.repositories.state_repo import LOCK, StateRepository
from app.serializers import public_world_state
from app.services import prompt_builder, state_update
from app.services.narrator_client import NarratorClient

# Kurulum ekranından gelebilecek künye alanları (isim + eşya + künye).
PICK_FIELDS = ("name", "item") + SHEET_FIELDS


class GameService:
    """`/api/state`, `/api/setup-characters`, `/api/start`,
    `/api/finish-chargen`, `/api/reset`."""

    def __init__(self, state_repo=None, scenario_repo=None, narrator=None,
                 game_log=None, gm_log=None):
        self.scenario_repo = scenario_repo or ScenarioRepository()
        self.state_repo = state_repo or StateRepository(scenario_repo=self.scenario_repo)
        self.narrator = narrator or NarratorClient()
        self.game_log = game_log or log_repo.game_log()
        self.gm_log = gm_log or log_repo.gm_log()

    # -------------------------------------------------------------- /api/state
    def snapshot(self, since=None) -> dict:
        with LOCK:
            state = self.state_repo.load()
            version = int(state.get("version", 0))
            # Hızlı yoklama: durum değişmediyse ağır gövdeyi hiç kurma.
            if since is not None and since.isdigit() and int(since) == version:
                return {"version": version, "changed": False}
            log = self.game_log.read()
        scenario = self.scenario_repo.load()
        return {
            "version": version,
            "changed": True,
            "world_state": public_world_state(state["world_state"]),
            "log": log,
            "started": state["started"],
            "characters_confirmed": state["characters_confirmed"],
            "chargen_done": StateRepository.world_of(state).chargen_complete(),
            "default_players": scenario["default_players"],
            "start_item_suggestions": scenario["start_item_suggestions"],
            "custom_scenario": self.scenario_repo.has_override,
            "group_label": GROUP_LABEL,
            "group_display_name": GROUP_DISPLAY_NAME,
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
                    "dönüştürüp `challenges` altına kaydet ve DURUM/SEÇENEKLER "
                    "bloğuyla bitir. Durum güncelleme bloğunda `flags.chargen_done` "
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
            extra_system = (
                "OYUN BAŞLANGICI.\n"
                f"Bu oyundaki karakterler (SABİT, TAM LİSTE — başka oyuncu karakteri "
                f"YOK, isim uydurma): {', '.join(players)}.\n"
                f"Rastgele açılış olayı (sunucu tarafından seçildi): {hook}\n\n"
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

            result = self.narrator.ask(prompt, extra_system, None, scenario["scenario_text"])

            state["session_id"] = result.get("session_id")
            state["started"] = True

            raw_text = result.get("result", "")
            gm_text, patches = state_update.extract(raw_text)
            for patch in patches:
                world.merge_patch(patch)

            gm_entry = {
                "id": self.state_repo.next_id(state),
                "role": "assistant",
                "kind": "opening",
                "text": gm_text,
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self.game_log.append(gm_entry)
            StateRepository.store_world(state, world)
            self.state_repo.save(state)

        return {"gm_entry": gm_entry,
                "world_state": public_world_state(state["world_state"]),
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

    # -------------------------------------------------------------- /api/reset
    def reset(self) -> dict:
        with LOCK:
            state = self.state_repo.default_state()
            self.state_repo.save(state)
            self.game_log.clear()
            self.gm_log.clear()
        return {"ok": True}
