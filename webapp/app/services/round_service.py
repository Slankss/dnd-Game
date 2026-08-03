"""Tur bazlı akış: seçim topla → hepsi gelince tek seferde gönder.

Akış:

  `ensure_open`  Anlatıcı sahneyi yazdıktan sonra tur açılır; süre sayacı
                 (settings.turn_seconds) o anda başlar.
  `pick`         Bir oyuncu SUNULAN SEÇENEKLERDEN birini seçer. Sunucu O ANDA
                 gerçek bir d100 atar ve sonucu döndürür — arayüz zarı
                 animasyonla gösterir, sonuç havuza not edilir. Seçim hafızada
                 birikir, modele GİTMEZ.
                 Serbest metin YOKTUR: hikaye yalnız sunulan tercihlerle
                 ilerler (bkz. `pick`'teki doğrulama).
  `commit`       Herkes seçince (ya da süre dolunca / elle gönderilince) tüm
                 seçimler TEK mesajda anlatıcıya gider. Seçim yapmayanlar için
                 "ani sahne" istenir: dünya kararsızı beklemez.

Kilit: `state_repo.LOCK` — tur akışı seri kalsın diye model çağrısı da kilidin
içindedir (mevcut TurnService davranışıyla aynı).
"""

import time

from app.errors import ValidationError
from app.models.dice import band_for, roll_d100, roll_world_dice
from app.models.options import CATEGORIES, FREE_CATEGORY
from app.models.round import DONE, OPEN, SENDING, Pick, Round
from app.models.text import DEFAULT_TURN_MINUTES
from app.repositories import log_repo
from app.repositories.scenario_repo import ScenarioRepository
from app.repositories.state_repo import LOCK, StateRepository
from app.serializers import public_round, public_world_state
from app.services import prompt_builder, turn_prompts
from app.services.director_service import DirectorService
from app.services.learning_service import LearningService
from app.services.narrator_client import NarratorClient
from app.services.options_service import OptionsService
from app.services.threat_service import ThreatService
from app.services.turn_service import TurnService

# Oyuncu serbest metin YAZAMAZ: hikaye yalnız sunulan seçeneklerle ilerler.
# `pick` yalnızca `option_id` kabul eder; gövdede metin gelirse reddedilir.
SERBEST_METIN_HATASI = (
    "Bu oyunda serbest hamle yok — sunulan seçeneklerden birini seç. "
    "Hiçbiri uymuyorsa 'Bu turda bekle'yi kullanabilirsin."
)


class RoundService:
    """`/api/round/pick`, `/api/round/commit`, `/api/round/skip`."""

    def __init__(self, state_repo=None, scenario_repo=None, narrator=None,
                 game_log=None, gm_log=None, director=None, learning=None,
                 options=None, turn=None, threat=None):
        self.scenario_repo = scenario_repo or ScenarioRepository()
        self.state_repo = state_repo or StateRepository(scenario_repo=self.scenario_repo)
        self.narrator = narrator or NarratorClient()
        self.game_log = game_log or log_repo.game_log()
        self.gm_log = gm_log or log_repo.gm_log()
        self.director = director or DirectorService()
        self.learning = learning or LearningService()
        self.options = options or OptionsService()
        self.threat = threat or ThreatService()
        self.turn = turn or TurnService(
            state_repo=self.state_repo, scenario_repo=self.scenario_repo,
            narrator=self.narrator, game_log=self.game_log, gm_log=self.gm_log,
            director=self.director, learning=self.learning, options=self.options,
            threat=self.threat,
        )

    # ------------------------------------------------------------ yardımcı
    @staticmethod
    def actors(world) -> list:
        """Bu turda seçim yapması beklenen karakterler: hayatta VE sahnede."""
        return [name for name in world.present_players()]

    @staticmethod
    def _round_mode(state) -> bool:
        return bool(StateRepository.settings_of(state).get("round_mode", True))

    def ensure_open(self, state, world, force: bool = False) -> Round:
        """Tur kapalıysa ve oyun seçim bekleyecek durumdaysa yeni tur açar.
        Kaydı DEĞİŞTİRİRSE çağıranın state'i kaydetmesi gerekir."""
        round_ = StateRepository.round_of(state)
        if round_.status == OPEN and not force:
            return round_
        if round_.status == SENDING and not force:
            return round_
        if not state.get("started") or not world.chargen_complete():
            return round_
        if not self._round_mode(state):
            return round_
        seconds = int(StateRepository.settings_of(state).get("turn_seconds") or 0)
        round_.open(round_.no + 1, seconds)
        StateRepository.store_round(state, round_)
        return round_

    # ------------------------------------------------------------ seçim
    def pick(self, player, option_id=None, text=None) -> dict:
        """Bir oyuncunun seçimi + o anda atılan zar.

        `text` KABUL EDİLMEZ: senaryo yalnız sunulan tercihlerle ilerler.
        Eski istemciler serbest metin gönderirse açık bir hatayla döner."""
        player = (player or "").strip()
        if not player:
            raise ValidationError("Karakter seçilmedi.")

        with LOCK:
            state = self.state_repo.load()
            if not state["started"]:
                raise ValidationError("Önce oyunu başlatın.")
            world = StateRepository.world_of(state)
            if not world.chargen_complete():
                raise ValidationError(
                    "Karakter oluşturma sürüyor — tur bazlı seçim henüz açılmadı."
                )

            round_ = self.ensure_open(state, world)
            if round_.status == SENDING:
                raise ValidationError("Tur gönderiliyor, biraz bekleyin.")
            if not round_.is_open:
                raise ValidationError("Şu anda açık bir tur yok.")

            oyuncular = self.actors(world)
            if player not in oyuncular:
                if player in (world.characters or {}) and not world.characters[player].is_alive:
                    raise ValidationError(f"{player} öldü — bu karakterle oynanamaz.")
                raise ValidationError(f"{player} bu turda sahnede değil.")
            if player in round_.picks:
                raise ValidationError(
                    f"{player} bu turda zaten seçim yaptı — zar atıldı, "
                    "seçim değiştirilemez."
                )

            if (text or "").strip():
                raise ValidationError(SERBEST_METIN_HATASI)
            if not option_id:
                raise ValidationError(SERBEST_METIN_HATASI)
            secenek = world.ensure_options().find(player, str(option_id))
            if secenek is None:
                raise ValidationError("Seçenek bulunamadı — sahne yenilenmiş olabilir.")
            metin = secenek.text

            # Zar SEÇİM ANINDA atılır: arayüz animasyonu gerçek sonucu gösterir.
            roll = roll_d100()
            pick = Pick(
                player=player,
                option_id=secenek.id,
                text=metin,
                category=secenek.category,
                roll=roll,
                band=band_for(roll),
                custom=False,          # serbest metin yok: her seçim havuzdan
                ts=time.time(),
            )
            round_.add(pick)
            StateRepository.store_round(state, round_)
            self.state_repo.save(state)
            hazir = round_.all_picked(oyuncular)

        return {
            "ok": True,
            "pick": pick.to_dict(),
            "roll": roll,
            "band": pick.band,
            "round": public_round(state.get("round"), oyuncular),
            "all_picked": hazir,
            "version": int(state.get("version", 0)),
        }

    def cancel(self, player) -> dict:
        """Seçimi geri alma YOKTUR (zar atıldı) — ama seçim yapmadan turdan
        çekilmek mümkün: karakter bu turda bekler."""
        player = (player or "").strip()
        with LOCK:
            state = self.state_repo.load()
            world = StateRepository.world_of(state)
            round_ = StateRepository.round_of(state)
            if not round_.is_open:
                raise ValidationError("Açık tur yok.")
            if player in round_.picks:
                raise ValidationError("Zar atıldı — bu seçim geri alınamaz.")
            roll = roll_d100()
            round_.add(Pick(player=player, text="(bekliyor, hamle yapmıyor)",
                            category="güvenli", roll=roll, band=band_for(roll),
                            custom=False, ts=time.time()))
            StateRepository.store_round(state, round_)
            self.state_repo.save(state)
            oyuncular = self.actors(world)
        return {"ok": True, "round": public_round(state.get("round"), oyuncular),
                "version": int(state.get("version", 0))}

    # ------------------------------------------------------------ gönderim
    def commit(self, reason: str = "elle", round_no=None) -> dict:
        """Turu kapatır ve tüm seçimleri TEK mesajda anlatıcıya gönderir."""
        with LOCK:
            state = self.state_repo.load()
            if not state["started"]:
                raise ValidationError("Oyun henüz başlamadı.")
            world = StateRepository.world_of(state)
            round_ = StateRepository.round_of(state)

            # Aynı turu iki istemci birden göndermeye çalışabilir (süre dolduğunda
            # herkesin sayacı aynı anda biter). Kilit sıraya dizer; ikinci istek
            # turun çoktan kapandığını görür ve sessizce döner.
            if round_no is not None and int(round_no) != round_.no:
                return {"ok": True, "skipped": True,
                        "round": public_round(state.get("round"), self.actors(world)),
                        "version": int(state.get("version", 0))}
            if not round_.is_open:
                return {"ok": True, "skipped": True,
                        "round": public_round(state.get("round"), self.actors(world)),
                        "version": int(state.get("version", 0))}

            oyuncular = self.actors(world)
            bekleyenler = round_.waiting_for(oyuncular)
            if not round_.picks:
                raise ValidationError("Bu turda hiç seçim yapılmadı.")
            if reason == "sure" and not round_.expired():
                raise ValidationError("Sürenin dolmasına daha var.")

            round_.status = SENDING
            StateRepository.store_round(state, round_)

            baslangic = time.time()
            ts = time.strftime("%Y-%m-%d %H:%M:%S")

            # Dünya zarı ve sahne katılımı — serbest turdaki sırayla aynı.
            world_entry = roll_world_dice(world)
            returned = world.resolve_presence(world_entry)
            rejoined = []
            for pick in round_.ordered_picks(oyuncular):
                if world.bring_to_scene(pick.player):
                    rejoined.append(pick.player)

            beat, plot, plan_olaylari = self.director.take_due(world, world_entry)
            directive = prompt_builder.directive_note(beat.to_dict()) if beat else None

            ws = world.to_dict()
            scene_note = prompt_builder.presence_note(ws, returned, rejoined)
            log = self.game_log.read()

            # Oyuncu akışına her seçim ayrı bir satır olarak düşer.
            user_entries = []
            satirlar = []
            for pick in round_.ordered_picks(oyuncular):
                kategori = pick.category if pick.category in CATEGORIES else FREE_CATEGORY
                user_entries.append({
                    "id": self.state_repo.next_id(state),
                    "role": "user",
                    "player": pick.player,
                    "is_group": False,
                    "roll": pick.roll,
                    "band": pick.band,
                    "category": kategori,
                    "text": pick.text,
                    "ts": ts,
                })
                satirlar.append(
                    f"{pick.player} (ZAR: {pick.roll} - {pick.band}) "
                    f"[{kategori}]: {pick.text}"
                )
            for name in bekleyenler:
                satirlar.append(f"{name} — SEÇİM YAPMADI (süre doldu)")

            # Zombi tehdidi: seçimlerin TAMAMINDAN gürültü/yolculuk okunur —
            # biri ateş ediyorsa ya da grup yola çıktıysa bu turda karşılaşma
            # ihtimali yükselir.
            threat_prep = self.threat.prepare(
                world, action_text=" \n".join(p.text for p in round_.picks.values()),
                minutes=DEFAULT_TURN_MINUTES)

            combined = "\n".join(satirlar)
            prompt = f"[TUR {round_.no} — TOPLU GÖNDERİM]\n{combined}"
            extra_system = turn_prompts.round_extra_system(
                ws, log, combined, world_entry, scene_note, directive,
                bekleyenler, StateRepository.settings_of(state), oyuncular,
                self.options, round_.no, self.learning.note(),
                threat_prep["note"],
            )

            try:
                result = self.narrator.ask(
                    prompt, extra_system, state["session_id"],
                    self.scenario_repo.load()["scenario_text"])
            except Exception:
                # Model çağrısı düştü: tur AÇIK kalsın, seçimler kaybolmasın.
                round_.status = OPEN
                StateRepository.store_round(state, round_)
                self.state_repo.save(state)
                raise

            state["session_id"] = result.get("session_id") or state["session_id"]
            for entry in user_entries:
                self.game_log.append(entry)
            if bekleyenler:
                self.game_log.append({
                    "id": self.state_repo.next_id(state),
                    "role": "system",
                    "text": "⏳ Süre doldu — " + ", ".join(bekleyenler)
                            + " seçim yapmadı, dünya beklemedi.",
                    "ts": ts,
                })

            picks = [dict(pick.to_dict(), uzun=len(pick.text) > 120)
                     for pick in round_.ordered_picks(oyuncular)]
            picks += [{"player": name, "category": FREE_CATEGORY, "text": "",
                       "roll": None, "band": None, "custom": False,
                       "timeout": True, "uzun": False} for name in bekleyenler]

            sonuc = self.turn.finish_turn(
                state, world, result.get("result", ""),
                beat=beat, plot=plot, plan_olaylari=plan_olaylari,
                picks=picks, kind="tur", seconds=round(time.time() - baslangic, 1),
                threat_prep=threat_prep,
            )

            # Yeni tur: seçenekler tazelendi, süre sayacı sıfırlanır.
            round_.status = DONE
            StateRepository.store_round(state, round_)
            StateRepository.store_world(state, world)
            self.ensure_open(state, world)
            self.state_repo.save(state)
            acik_tur = public_round(state.get("round"), self.actors(world))

        return {
            "ok": True,
            "user_entries": user_entries,
            "gm_entry": sonuc["gm_entry"],
            "world_state": public_world_state(state["world_state"]),
            "round": acik_tur,
            "timeouts": bekleyenler,
            "version": int(state.get("version", 0)),
        }

    # ------------------------------------------------------------- durum
    def snapshot_round(self, state, world) -> dict:
        """`/api/state` gövdesine giren tur bilgisi (kilit ÇAĞIRANDA)."""
        return public_round(state.get("round"), self.actors(world))
