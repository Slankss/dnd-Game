"""Tur bazlı akış: seçim topla → oyuncu turu geçince tek seferde gönder.

Akış:

  `ensure_open`  Turun BAŞI. Bir önceki turda tetiklenen ne varsa (bekleyen
                 sahne, tehdit devri, senarist direktifi) burada devreye girer;
                 sonra tur açılır ve süre sayacı (settings.turn_seconds) başlar.
  `pick`         Bir oyuncu SUNULAN SEÇENEKLERDEN birini seçer. Sunucu turun
                 zarını atar (oyuncu başına BİR KEZ) ve sonucu döndürür —
                 arayüz zarı animasyonla gösterir. Seçim hafızada birikir,
                 modele GİTMEZ ve TUR İLERLEMEZ: oyuncu "Turu Geç"e basana
                 kadar kararını istediği kadar değiştirebilir.
                 Serbest metin YOKTUR: hikaye yalnız sunulan tercihlerle
                 ilerler (bkz. `pick`'teki doğrulama).
  `commit`       "Turu Geç" (ya da süre dolduysa sayaç) turu kapatır: tüm
                 seçimler TEK mesajda anlatıcıya gider. Seçim yapmayanlar için
                 "ani sahne" istenir: dünya kararsızı beklemez.

TUR GEÇİŞİ KURALI (bkz. `models/pending.py`): bir turda üretilen hiçbir şey o
turda yayınlanmaz. Anlatıcının yazdığı sahne, o turda tetiklenen gürültü/olay
ve vadesi gelen senarist beat'i kuyruğa yazılır; hepsi BİR SONRAKİ turun
başında (`ensure_open` → `release`) devreye girer.

Kilit: `state_repo.LOCK` — tur akışı seri kalsın diye model çağrısı da kilidin
içindedir (mevcut TurnService davranışıyla aynı).
"""

import time

from app.errors import ValidationError
from app.models.dice import band_for, roll_d100, roll_world_dice
from app.models.options import CATEGORIES, FREE_CATEGORY
from app.models.pending import DIREKTIF, SAHNE, TEHDIT, birlestir
from app.models.round import DONE, OPEN, SENDING, Pick, Round
from app.models.threat import Encounter
from app.models.text import DEFAULT_TURN_MINUTES
from app.repositories import log_repo
from app.repositories.scenario_repo import ScenarioRepository
from app.repositories.state_repo import LOCK, StateRepository
from app.serializers import public_round, public_world_state
from app.services import prompt_builder, turn_prompts
from app.services.director_service import DirectorService
from app.services.inventory_service import InventoryService
from app.services.items_service import (
    ItemsService,
    looks_like_eating,
    looks_like_searching,
)
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
                 options=None, turn=None, threat=None, inventory=None,
                 items=None):
        self.scenario_repo = scenario_repo or ScenarioRepository()
        self.state_repo = state_repo or StateRepository(scenario_repo=self.scenario_repo)
        self.narrator = narrator or NarratorClient()
        self.game_log = game_log or log_repo.game_log()
        self.gm_log = gm_log or log_repo.gm_log()
        self.director = director or DirectorService()
        self.learning = learning or LearningService()
        self.options = options or OptionsService()
        self.threat = threat or ThreatService()
        self.inventory = inventory or InventoryService()
        self.items = items or ItemsService()
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
        """TURUN BAŞI: bekleyenleri devreye alır, sonra yeni turu açar.

        Tur kapalıysa ve oyun seçim bekleyecek durumdaysa çalışır. Kaydı
        DEĞİŞTİRİRSE çağıranın state'i kaydetmesi gerekir.

        Bir önceki turda yazılan sahne burada — turun başında — yayınlanır.
        `commit` bunu hemen ardından çağırdığı için oyuncu bekleme hissetmez;
        ama sunucu tur ortasında ölse bile sahne kaybolmaz, ilk yoklamada
        (`/api/state` → `snapshot`) yayınlanır.
        """
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
        yeni_no = round_.no + 1
        # Tur numarası önce yazılır (seçenek havuzu ve öğrenme defteri yeni
        # turun numarasıyla kayıt tutsun), sonra bekleyen sahne yayınlanır.
        # İkisi de aynı kilidin içinde: istemci arada bir hal göremez.
        round_.open(yeni_no, seconds)
        StateRepository.store_round(state, round_)
        self.release(state, world, yeni_no)
        return round_

    # -------------------------------------------------------- turun başı
    def release(self, state, world, round_no: int) -> list:
        """Vadesi gelen bekleyen sahneleri yayınlar (kilit ÇAĞIRANDA).

        Tehdit devri ve senarist direktifi burada TÜKETİLMEZ: onlar turun
        çözümünde (`commit`) anlatıcıya girdi olarak verilir, kuyrukta o ana
        kadar bekler.
        """
        kuyruk = StateRepository.pending_of(state)
        sahneler = kuyruk.take(round_no, SAHNE)
        if not sahneler:
            return []
        yayinlar = []
        for item in sahneler:
            try:
                yayinlar.append(self._publish_scene(state, world, kuyruk, item))
            except Exception as hata:  # noqa: BLE001 — oyun tıkanmasın
                # Bozuk bir kayıt tüm masayı kilitlemesin: sahne düşer ama
                # sessizce değil, akışta görünür bir not bırakır.
                self.game_log.append({
                    "id": self.state_repo.next_id(state),
                    "role": "system",
                    "text": "⚠️ Bir önceki turun sahnesi yayınlanamadı "
                            f"({type(hata).__name__}). Tur devam ediyor.",
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
        StateRepository.store_pending(state, kuyruk)
        StateRepository.store_world(state, world)
        return yayinlar

    def _publish_scene(self, state, world, kuyruk, item) -> dict:
        """Bekleyen bir sahneyi yayınlar: dünyaya uygula, kayda düş, havuzu tazele.

        Bu sahnede FİİLEN oynanan karşılaşma kuyrukta JSON olarak bekliyordu;
        tehdit defterine burada işlenir. Sahnenin state-update'inde bildirilen
        olaylar ise UYGULANMAZ — bir sonraki turun devrine yazılır.
        """
        veri = item.data or {}
        # Bu turda anlatıcının bildirdiği olaylar: uygulanmaz, devre yazılır.
        ertelenen = []
        beat, plot = self.director.find(veri.get("beat_id"))
        sonuc = self.turn.finish_turn(
            state, world, veri.get("raw_text") or "",
            beat=beat, plot=plot, plan_olaylari=veri.get("plan_events") or [],
            picks=veri.get("picks") or [], kind=veri.get("kind") or "tur",
            seconds=veri.get("seconds"),
            threat_prep=self._rehydrate_threat(world, veri.get("threat")),
            defer_events=ertelenen,
        )
        if ertelenen:
            # Olayın etkisi (bölgeye ölü göçü) bir sonraki turun başında.
            kuyruk.add(TEHDIT, item.due_round, {"events": ertelenen})
        return sonuc

    @staticmethod
    def _rehydrate_threat(world, data) -> dict:
        """Kuyrukta bekleyen karşılaşmayı canlı tehdit kaydına bağlar.

        `threat` ve `graph` dünyadan yeniden okunur (JSON'a yazılamazlar);
        zarın kendisi kuyrukta olduğu gibi durur."""
        if not isinstance(data, dict) or not data:
            return None
        world_map = world.map
        return {
            "encounter": Encounter.from_dict(data.get("encounter")),
            "threat": world.ensure_threat(),
            "place": data.get("place") or "",
            "density": data.get("density") or 0,
            "graph": world_map.adjacency() if world_map is not None else {},
            "note": data.get("note") or "",
        }

    # ------------------------------------------------------------ seçim
    def pick(self, player, option_id=None, text=None) -> dict:
        """Bir oyuncunun seçimi + turun zarı.

        Seçim TUR İLERLETMEZ ve KİLİTLEMEZ: oyuncu "Turu Geç"e basana kadar
        kararını istediği kadar değiştirebilir, turda son seçtiği karar
        işlenir.

        Zar tur başına ve oyuncu başına BİR KEZ atılır: kararını değiştirmek
        zar atmak değildir. Aksi halde beğenmediği zarı yeniden atmak için
        seçenek değiştirmek serbest kalırdı.

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

            if (text or "").strip():
                raise ValidationError(SERBEST_METIN_HATASI)
            if not option_id:
                raise ValidationError(SERBEST_METIN_HATASI)
            secenek = world.ensure_options().find(player, str(option_id))
            if secenek is None:
                raise ValidationError("Seçenek bulunamadı — sahne yenilenmiş olabilir.")
            metin = secenek.text

            # Zar TURUN zarıdır, seçeneğin değil: oyuncu bu turda ilk kez
            # seçim yapıyorsa atılır, kararını değiştiriyorsa aynısı kalır.
            roll = self._turn_roll(round_, player)
            pick = Pick(
                player=player,
                option_id=secenek.id,
                text=metin,
                category=secenek.category,
                roll=roll,
                band=band_for(roll),
                custom=False,          # serbest metin yok: her seçim havuzdan
                # Bedel seçimle birlikte taşınır: tur çözülürken envanterden
                # kesilecek olan budur (havuz o sırada tazelenmiş olabilir).
                spend=dict(secenek.spend or {}),
                ts=time.time(),
            )
            degisti = player in round_.picks
            round_.add(pick)
            StateRepository.store_round(state, round_)
            self.state_repo.save(state)
            hazir = round_.all_picked(oyuncular)

        return {
            "ok": True,
            "pick": pick.to_dict(),
            "roll": roll,
            "band": pick.band,
            # Karar değiştirildiyse arayüz zarı yeniden oynatmaz.
            "changed": degisti,
            "round": public_round(state.get("round"), oyuncular),
            "all_picked": hazir,
            "version": int(state.get("version", 0)),
        }

    @staticmethod
    def _turn_roll(round_: Round, player: str) -> int:
        """Oyuncunun bu turdaki zarı — bir kez atılır, karar değişse de kalır."""
        onceki = round_.picks.get(player)
        if onceki is not None and isinstance(onceki.roll, int):
            return onceki.roll
        return roll_d100()

    def cancel(self, player) -> dict:
        """Bu turda bekle: hamle yapmadan turda kalmak.

        Bu da bir seçimdir ve değiştirilebilir — oyuncu turu geçene kadar
        fikrini değiştirip havuzdan bir seçenek seçebilir."""
        player = (player or "").strip()
        with LOCK:
            state = self.state_repo.load()
            world = StateRepository.world_of(state)
            round_ = StateRepository.round_of(state)
            if not round_.is_open:
                raise ValidationError("Açık tur yok.")
            roll = self._turn_roll(round_, player)
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
        """"Turu Geç" — turu kapatır ve tüm seçimleri TEK mesajda gönderir.

        Turun çözümüne giren tehdit ve senarist direktifi BİR ÖNCEKİ turdan
        devredilir; bu turda tetiklenenler (gürültü, yolculuk, anlatıcının
        bildirdiği olaylar, vadesi gelen yeni beat) ve anlatıcının yazdığı
        sahne kuyruğa yazılıp bir sonraki turun başında devreye girer.
        """
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

            # Bu turun çözümüne giren SÜRPRİZLER geçen turda tetiklendi.
            kuyruk = StateRepository.pending_of(state)
            devir = birlestir(kuyruk.take(round_.no, TEHDIT))
            direktif_kaydi = kuyruk.take_one(round_.no, DIREKTIF)

            # Senarist beat'i: geçen turda vadesi gelmişti, sahneye ŞİMDİ girer.
            beat, plot = self.director.find(
                (direktif_kaydi.data or {}).get("beat_id") if direktif_kaydi else None)
            directive = prompt_builder.directive_note(beat.to_dict()) if beat else None

            # HARCAMA: seçeneklerin beyan ettiği bedel envanterden ŞİMDİ kesilir
            # — sahne yazılmadan önce. Anlatıcı muhasebe tutmaz, ne kesildiğini
            # zorunlu bir blok olarak öğrenir. `ws` bu yüzden kesimden SONRA
            # kurulur: modele giden JSON güncel miktarları göstersin.
            secimler = round_.ordered_picks(oyuncular)
            harcamalar = self.inventory.apply(world, secimler)
            harcama_notu = self.inventory.note(harcamalar)

            # TÜKETİM: harcanan kalem katalogda bir yiyecek/içecekse açlık ve
            # susuzluk göstergesi sunucuda düşer — "karnınız doydu" cümlesi
            # göstergeyi değiştirmez.
            tuketimler = {}
            for kayit in harcamalar:
                etki = self.items.consume(world, kayit["player"], kayit["spent"])
                if etki:
                    tuketimler[kayit["player"]] = etki
            # Güvenlik ağı: hamle yemek/içmek diyorsa ama anlatıcı `spend`
            # yazmayı unuttuysa envanterdeki en doyurucu kalem tüketilir —
            # "karnını doyurdu" deyip açlık göstergesinin sabit kalması, mermi
            # sorununun aynısıydı.
            beyan_edenler = {k["player"] for k in harcamalar if k["spent"]}
            for pick in secimler:
                if pick.player in beyan_edenler or not looks_like_eating(pick.text):
                    continue
                etki = self.items.auto_consume(world, pick.player)
                if etki:
                    tuketimler.setdefault(pick.player, []).extend(etki)

            # ARAMA: bir yeri arayan hamlede ne bulunacağını YER TÜRÜ ve
            # katalog belirler (karakolda silah, metroda pek değil).
            aramalar = []
            for pick in secimler:
                if looks_like_searching(pick.text):
                    aramalar.append(
                        self.items.search(world, pick.player, str(pick.band or "")))
            arama_notu = self.items.search_note(aramalar)
            for kayit in aramalar:
                self.gm_log.append({
                    "id": None, "role": "system", "ts": ts,
                    "text": "🔎 " + (
                        f"{kayit['player']} ({kayit['label']}) buldu: " + ", ".join(
                            f"{b['adet']}× {b['ad']}" for b in kayit["found"])
                        if kayit["found"] else
                        f"{kayit['player']} aradı, bir şey çıkmadı ({kayit['place']})"),
                })

            for kayit in harcamalar:
                if kayit["spent"] or kayit["dry"]:
                    self.gm_log.append({
                        "id": None, "role": "system", "ts": ts,
                        "text": "🎒 " + (
                            f"{kayit['player']} ateş edemedi (mermi yok)."
                            if kayit["dry"] else
                            f"{kayit['player']} harcadı: " + ", ".join(
                                f"{adet}× {ad}" for ad, adet in kayit["spent"].items())
                            + (" [otomatik]" if kayit["auto"] else "")),
                    })

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

            # Zombi tehdidi: bu turda oynanacak karşılaşma GEÇEN turun
            # gürültüsünden ve olaylarından doğar. Bu turda çıkan ses aşağıda
            # bir sonraki tura yazılır.
            hamle_metni = " \n".join(p.text for p in round_.picks.values())
            threat_prep = self.threat.prepare(
                world, carry=devir, minutes=DEFAULT_TURN_MINUTES)

            combined = "\n".join(satirlar)
            prompt = f"[TUR {round_.no} — TOPLU GÖNDERİM]\n{combined}"
            extra_system = turn_prompts.round_extra_system(
                ws, log, combined, world_entry, scene_note, directive,
                bekleyenler, StateRepository.settings_of(state), oyuncular,
                self.options, round_.no, self.learning.note(),
                threat_prep["note"],
                "\n\n".join(x for x in (
                    harcama_notu,
                    self.items.consume_note(tuketimler),
                    arama_notu,
                ) if x),
                "\n\n".join(x for x in (
                    self.inventory.stock_note(world, oyuncular),
                    self.items.catalog_note(world, oyuncular),
                    self.items.story_note(world),
                ) if x),
                prompt_builder.distance_note(world.map, world.location),
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

            # SAHNE BU TURDA YAYINLANMAZ. Anlatıcının yanıtı, bu turda oynanan
            # karşılaşmayla birlikte kuyruğa yazılır ve BİR SONRAKİ turun
            # başında (`ensure_open` → `release`) yayınlanır.
            sonraki = round_.no + 1
            kuyruk.add(SAHNE, sonraki, {
                "round_no": round_.no,
                "raw_text": result.get("result", ""),
                "picks": picks,
                "kind": "tur",
                "seconds": round(time.time() - baslangic, 1),
                "beat_id": beat.id if beat else "",
                # Plan muhasebesi (çürüyen beat notları) aşağıda doğrudan
                # anlatıcı günlüğüne yazılır; sahneyle birlikte taşınmaz.
                "plan_events": [],
                "threat": {
                    "encounter": threat_prep["encounter"].to_dict(),
                    "place": threat_prep.get("place") or "",
                    "density": threat_prep.get("density") or 0,
                    "note": threat_prep.get("note") or "",
                },
            })
            # Bu turda tetiklenenler de bir sonraki tura: çıkardığın ses ve
            # yola çıkma niyetin ŞİMDİ değil, SONRAKİ turda ölü çeker.
            kuyruk.add(TEHDIT, sonraki,
                       self.threat.read_inputs(hamle_metni))
            # Vadesi gelen yeni beat de bir sonraki turun sahnesini şekillendirir.
            yeni_beat, _plot, yeni_plan_olaylari = self.director.take_due(
                world, world_entry)
            if yeni_beat is not None:
                kuyruk.add(DIREKTIF, sonraki, {"beat_id": yeni_beat.id})
            for olay in yeni_plan_olaylari:
                self.gm_log.append({"id": None, "role": "plot", "text": olay,
                                    "ts": ts})

            round_.status = DONE
            StateRepository.store_round(state, round_)
            StateRepository.store_pending(state, kuyruk)
            StateRepository.store_world(state, world)
            # Turun başı: bekleyen sahne burada yayınlanır, sonra yeni tur açılır.
            self.ensure_open(state, world)
            self.state_repo.save(state)
            acik_tur = public_round(state.get("round"), self.actors(world))
            gm_entry = self._last_scene_entry()

        return {
            "ok": True,
            "user_entries": user_entries,
            "gm_entry": gm_entry,
            "world_state": public_world_state(state["world_state"]),
            "round": acik_tur,
            "timeouts": bekleyenler,
            "version": int(state.get("version", 0)),
        }

    def _last_scene_entry(self):
        """Yayınlanan son anlatıcı kaydı — istemci yoklamayı beklemesin."""
        for entry in reversed(self.game_log.read()):
            if entry.get("role") == "assistant":
                return entry
        return None

    # ------------------------------------------------------------- durum
    def snapshot_round(self, state, world) -> dict:
        """`/api/state` gövdesine giren tur bilgisi (kilit ÇAĞIRANDA)."""
        return public_round(state.get("round"), self.actors(world))
