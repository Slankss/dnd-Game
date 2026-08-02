"""Bir oyuncu turunun tam akışı.

Zincir: dünya zarı → sahne katılımı → prompt → model → state-update → kayıt.
Bu katman Flask bilmez: düz sözlük döndürür, hata için `app.errors`
istisnalarını atar. Modele giden uzun metinler `turn_prompts`'ta durur;
buradaki iş sadece sıralamak.
"""

import re
import time

from scenario import GROUP_DISPLAY_NAME, GROUP_LABEL

from app.errors import ValidationError
from app.models.dice import band_for, roll_d100, roll_world_dice
from app.models.text import canonical_name, elapsed_minutes
from app.repositories import log_repo
from app.repositories.scenario_repo import ScenarioRepository
from app.repositories.state_repo import LOCK, StateRepository
from app.serializers import public_world_state
from app.services import prompt_builder, state_update, turn_prompts
from app.services.director_service import DirectorService
from app.services.narrator_client import NarratorClient

CHAR_LINE_RE = re.compile(r"^\s*([^\n:：]+?)\s*[:：]\s*(.+)$")


def detect_multi_character(text: str, valid_players: list):
    """'İsim: aksiyon' satırlarından oluşan, 2+ FARKLI bilinen karaktere ait
    çoklu karakter mesajını ayrıştırır. Her satır bu formata uymuyorsa ya da
    tek karakter içeriyorsa None döner (normal tek-oyunculu akışa düşer)."""
    lower_map = {p.lower(): p for p in valid_players}
    matches = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = CHAR_LINE_RE.match(line)
        if not m:
            return None
        name_raw, action = m.group(1).strip(), m.group(2).strip()
        canon = lower_map.get(name_raw.lower())
        if not canon or not action:
            return None
        matches.append((canon, action))
    if len({c for c, _ in matches}) < 2:
        return None
    return matches


class TurnService:
    """`/api/message` ve `/api/takeover` akışları."""

    def __init__(self, state_repo=None, scenario_repo=None, narrator=None,
                 game_log=None, gm_log=None, director=None):
        self.scenario_repo = scenario_repo or ScenarioRepository()
        self.state_repo = state_repo or StateRepository(scenario_repo=self.scenario_repo)
        self.narrator = narrator or NarratorClient()
        self.game_log = game_log or log_repo.game_log()
        self.gm_log = gm_log or log_repo.gm_log()
        self.director = director or DirectorService()

    # ------------------------------------------------------------ /api/message
    def play(self, player, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            raise ValidationError("text is required")

        with LOCK:
            state = self.state_repo.load()
            if not state["started"]:
                raise ValidationError("Önce oyunu başlatın.")
            world = StateRepository.world_of(state)
            # ölen karakterler adına mesaj gönderilemez — oyuncusu devralma
            # ekranından yeni bir karakter seçmeli
            valid_players = world.alive_players()
            in_chargen = not world.chargen_complete()
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            # Tur başına TEK dünya zarı (karakter başına değil) — oyunculara
            # gösterilmez, sadece modele ve /secrets ekranına gider.
            world_entry = None if in_chargen else roll_world_dice(world)
            wants_inventory = bool(prompt_builder.INVENTORY_INTENT_RE.search(text)) and not in_chargen
            inventory_block = ("\n\n" + prompt_builder.INVENTORY_REPORT_INSTRUCTION) if wants_inventory else ""

            multi = detect_multi_character(text, valid_players)

            # Sahne katılımı: vadesi dolan uyku/uzaklık halleri bu turda kapanır.
            # Oyuncusu adına hamle yazılan karakter de tanım gereği sahneye dönmüş
            # demektir (uyuyan biri mesaj yazdıysa uyanmıştır).
            returned = [] if in_chargen else world.resolve_presence(world_entry)
            rejoined = []
            if not in_chargen:
                actors = ([n for n, _ in multi] if multi
                          else ([] if player == GROUP_LABEL else [player]))
                for name in actors:
                    if name and world.bring_to_scene(name):
                        rejoined.append(name)
            # Prompt blokları ve JSON dökümü AYNI anlık görüntüden okunur —
            # eski kodda hepsi mutasyonlardan sonraki `state["world_state"]`'ti.
            # Senarist planı (data/plot.json): koşulu SAĞLANAN bekleyen
            # beat'lerden yalnız biri bu tura girer. Kararı kod verir, model
            # değil. Chargen turunda plan işlemez — henüz hikaye yok.
            beat, plot, plan_olaylari = (None, None, [])
            if not in_chargen:
                beat, plot, plan_olaylari = self.director.take_due(world, world_entry)
            directive = prompt_builder.directive_note(beat.to_dict()) if beat else None

            ws = world.to_dict()
            scene_note = prompt_builder.presence_note(ws, returned, rejoined)
            log = self.game_log.read()

            if multi:
                user_entries = []
                line_descs = []
                for name, action in multi:
                    if in_chargen:
                        roll, band = None, None
                    else:
                        roll = roll_d100()
                        band = band_for(roll)
                    user_entries.append(
                        {
                            "id": self.state_repo.next_id(state),
                            "role": "user",
                            "player": name,
                            "is_group": False,
                            "roll": roll,
                            "band": band,
                            "text": action,
                            "ts": ts,
                        }
                    )
                    roll_desc = f" (ZAR: {roll} - {band})" if roll is not None else ""
                    line_descs.append(f"{name}{roll_desc}: {action}")
                combined = "\n".join(line_descs)
                prompt = f"[ÇOKLU KARAKTER TURU]\n{combined}"
                extra_system = turn_prompts.multi_extra_system(
                    ws, log, combined, in_chargen, world_entry, inventory_block,
                    scene_note, directive)
            else:
                is_group = player == GROUP_LABEL
                if not is_group and player not in valid_players:
                    if player in world.characters:
                        raise ValidationError(
                            f"{player} öldü — bu karakterle oynanamaz. "
                            "Devam etmek için hikayedeki bir karakteri devralın."
                        )
                    raise ValidationError(f"player must be one of {valid_players + [GROUP_LABEL]}")
                # Ortak karar artık karakter oluşturma sırasında da kullanılabilir
                # (eskiden burada 400 dönüyordu ve biri karakterini kurmayınca
                # buton hiç açılmıyordu). Chargen sürerken zar atılmaz, model
                # bunu grup aksiyonu olarak işler.

                if in_chargen:
                    roll, band = None, None
                    extra_system = turn_prompts.chargen_extra_system(ws, log, player, is_group)
                else:
                    roll = roll_d100()
                    band = band_for(roll)
                    extra_system = turn_prompts.turn_extra_system(
                        ws, log, is_group, roll, band, world_entry, inventory_block,
                        scene_note, directive)

                user_entries = [
                    {
                        "id": self.state_repo.next_id(state),
                        "role": "user",
                        "player": GROUP_DISPLAY_NAME if is_group else player,
                        "is_group": is_group,
                        "roll": roll,
                        "band": band,
                        "text": text,
                        "ts": ts,
                    }
                ]
                prompt = f"[GRUP - ORTAK KARAR]\n{text}" if is_group else f"[OYUNCU: {player}]\n{text}"

            result = self.narrator.ask(prompt, extra_system, state["session_id"],
                                       self.scenario_repo.load()["scenario_text"])

            state["session_id"] = result.get("session_id") or state["session_id"]
            for entry in user_entries:
                self.game_log.append(entry)

            raw_text = result.get("result", "")
            gm_text, patches = state_update.extract(raw_text)
            # Göstergeler zar gibi sunucunun sorumluluğunda: anlatıcının elle
            # yazdığı değerler (uyudu/yedi/içti) korunur, geri kalanı bu turda
            # geçen oyun-içi süreye göre kendiliğinden yükselir.
            clock_before = world.clock_snapshot()
            vitals_touched = {}
            for patch in patches:
                world.merge_patch(patch, vitals_touched)
            turn_minutes = elapsed_minutes(clock_before, world.clock_snapshot())
            world.apply_vitals_drift(turn_minutes, vitals_touched)
            world.advance_infections(turn_minutes)
            world.normalize_wound_status()

            gm_entry = {
                "id": self.state_repo.next_id(state),
                "role": "assistant",
                "text": gm_text,
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "tension": world.tension,
            }
            self.game_log.append(gm_entry)

            # Plan muhasebesi turun SONUNDA: model yanıt vermeden beat
            # ateşlenmiş sayılmaz (çağrı hata verirse beat kuyrukta kalır).
            if beat is not None:
                plan_olaylari.append(self.director.mark_fired(beat, plot, world))
            for olay in plan_olaylari:
                # Plan hareketleri yalnız anlatıcı ekranında görünür.
                self.gm_log.append({
                    "id": None,
                    "role": "plot",
                    "text": olay,
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                })

            StateRepository.store_world(state, world)
            self.state_repo.save(state)

        return {
            "user_entries": user_entries,
            "gm_entry": gm_entry,
            "world_state": public_world_state(state["world_state"]),
            # arayüz Grup Kaynakları panelini bu bayrakla açar
            "inventory_report": wants_inventory,
            "version": int(state.get("version", 0)),
        }

    # ----------------------------------------------------------- /api/takeover
    def takeover(self, dead_player, new_character) -> dict:
        """Ölen bir oyuncu karakterinin oyuncusu, hikayede zaten var olan bir
        NPC'yi devralıp oyuna onunla devam eder. NPC `npcs`'ten `characters`'a
        taşınır (geçmişi/envanteri/ilişkileri korunarak), ölen karakter listede
        ölü olarak kalır."""
        dead_name = (dead_player or "").strip()
        new_name = (new_character or "").strip()

        with LOCK:
            state = self.state_repo.load()
            if not state["started"]:
                raise ValidationError("Oyun henüz başlamadı.")

            world = StateRepository.world_of(state)
            # eski koddaki `ws.setdefault("characters"/"npcs", {})` karşılığı:
            # alanlar boş kalsalar bile kayıtta durmaya devam etsin
            world._touch("characters")
            world._touch("npcs")
            characters = world.characters
            npcs = world.npcs

            dead_key = canonical_name(characters, dead_name)
            if not dead_key:
                raise ValidationError("Ölen karakter bulunamadı.")
            if characters[dead_key].is_alive:
                raise ValidationError(f"{dead_key} hâlâ hayatta — devralma yapılamaz.")
            # `replaced_by` modelin tanımadığı bir alan: `extra`'da durur ve
            # kayda olduğu gibi geri yazılır.
            if characters[dead_key].extra.get("replaced_by"):
                raise ValidationError(
                    f"{dead_key} için zaten bir karakter devralındı "
                    f"({characters[dead_key].extra['replaced_by']})."
                )

            new_key = canonical_name(npcs, new_name)
            if not new_key:
                raise ValidationError("Devralınacak karakter hikayedeki NPC'ler arasında yok.")
            if not npcs[new_key].is_alive:
                raise ValidationError(f"{new_key} hayatta değil, devralınamaz.")

            entry = npcs.pop(new_key)
            entry._set("alive", True)
            characters[new_key] = entry
            characters[dead_key].extra["replaced_by"] = new_key
            ws = world.to_dict()

            prompt = (
                f"[KARAKTER DEVRALMA]\n{dead_key} öldü. O oyuncu bundan sonra hikayede "
                f"zaten var olan {new_key} karakterini oynayacak."
            )
            extra_system = turn_prompts.takeover_extra_system(
                ws, self.game_log.read(), dead_key, new_key)

            result = self.narrator.ask(prompt, extra_system, state["session_id"],
                                       self.scenario_repo.load()["scenario_text"])

            state["session_id"] = result.get("session_id") or state["session_id"]

            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            system_entry = {
                "id": self.state_repo.next_id(state),
                "role": "system",
                "text": f"💀 {dead_key} öldü. Oyuncusu artık {new_key} karakteriyle devam ediyor.",
                "ts": ts,
            }
            self.game_log.append(system_entry)

            raw_text = result.get("result", "")
            gm_text, patches = state_update.extract(raw_text)
            for patch in patches:
                world.merge_patch(patch)

            gm_entry = {
                "id": self.state_repo.next_id(state),
                "role": "assistant",
                "kind": "takeover",
                "text": gm_text,
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "tension": world.tension,
            }
            self.game_log.append(gm_entry)
            StateRepository.store_world(state, world)
            self.state_repo.save(state)

        return {"system_entry": system_entry, "gm_entry": gm_entry,
                "world_state": public_world_state(state["world_state"])}
