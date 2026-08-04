"""Anlatıcı (GM) akışları — /secrets ekranının arkasındaki iş kuralı.

PIN kontrolü burada yapılır (API katmanı değil), böylece kural tek yerde
durur. Anlatıcıya dönen gövdeler dünya durumunun TAMAMINI taşır: bu ekran
zaten gizli katmanı görmek içindir, `public_world_state` süzgecinden
geçirilmez.
"""

import json
import time

from app import config
from app.errors import AuthError, ValidationError
from app.repositories import log_repo
from app.repositories.plot_repo import PlotRepository
from app.repositories.scenario_repo import ScenarioRepository
from app.repositories.state_repo import LOCK, StateRepository
from app.services import prompt_builder, state_update
from app.services.items_service import ItemsService
from app.services.learning_service import LearningService
from app.services.narrator_client import NarratorClient

# Anlatıcı ekranında oyuncu akışından gösterilen son tur sayısı.
GM_LOG_TAIL = 40

NOTE_MODES = ("gizli", "sahne", "surpriz")


class GmService:
    """`/api/gm/unlock`, `/api/gm/state`, `/api/gm/note`, `/api/gm/patch`."""

    def __init__(self, state_repo=None, scenario_repo=None, narrator=None,
                 game_log=None, gm_log=None, pin=None, plot_repo=None,
                 learning=None, items=None):
        self.scenario_repo = scenario_repo or ScenarioRepository()
        self.state_repo = state_repo or StateRepository(scenario_repo=self.scenario_repo)
        self.narrator = narrator or NarratorClient()
        self.plot_repo = plot_repo or PlotRepository()
        self.game_log = game_log or log_repo.game_log()
        self.gm_log = gm_log or log_repo.gm_log()
        self.learning = learning or LearningService()
        self.items = items or ItemsService()
        self.pin = pin if pin is not None else config.GM_PIN

    def _check(self, pin) -> None:
        if pin != self.pin:
            raise AuthError("Yanlış PIN.")

    # ---------------------------------------------------------- /api/gm/unlock
    def unlock(self, pin) -> dict:
        self._check(pin)
        return {"ok": True}

    # ----------------------------------------------------------- /api/gm/state
    def snapshot(self, pin, since=None) -> dict:
        self._check(pin)
        with LOCK:
            state = self.state_repo.load()
            version = int(state.get("version", 0))
            if since is not None and since.isdigit() and int(since) == version:
                return {"version": version, "changed": False}
            gm_log = self.gm_log.read()
            log = self.game_log.read()
            # Senarist planı SADECE bu ekrana gider — /api/state'te izi yok.
            plot = self.plot_repo.load_raw()
            round_body = state.get("round")
            settings = StateRepository.settings_of(state)
        return {
            "version": version,
            "changed": True,
            "world_state": state["world_state"],
            "gm_log": gm_log,
            # anlatıcı, oyuncuların turlarını da bu ekrandan canlı izleyebilsin
            "log": log[-GM_LOG_TAIL:],
            "started": state["started"],
            "plot": plot,
            "round": round_body,
            "settings": settings,
            # Öğrenme defteri: oyunun kendi kendine çıkardığı dersler + havuz.
            "learning": self.learning.summary(),
        }

    # ------------------------------------------------------- /api/gm/lesson
    def add_lesson(self, pin, text) -> dict:
        """Anlatıcı deftere elle ders yazar — bu dersler otomatik olanların
        ÖNÜNDE prompt'a girer ve yeteneğe de işlenir."""
        self._check(pin)
        text = (text or "").strip()
        if not text:
            raise ValidationError("Ders metni boş olamaz.")
        with LOCK:
            state = self.state_repo.load()
            world = StateRepository.world_of(state)
            gun = world.day if isinstance(world.day, int) else None
        store = self.learning.add_lesson(text, source="gm", day=gun)
        self.gm_log.append({
            "id": None,
            "role": "learning",
            "text": "🧠 deftere ders eklendi: " + text,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        return {"ok": True, "learning": store.summary()}

    # ------------------------------------------------------------ /api/gm/note
    def note(self, pin, text, mode=None) -> dict:
        self._check(pin)
        text = (text or "").strip()
        # gizli   = yönlendirme; yanıt SADECE anlatıcı ekranında kalır
        # sahne   = müdahale doğrudan oyuncu akışına sahne olarak yayınlanır
        # surpriz = anlatıcı sürpriz bir gelişme uydurur ve sahne olarak yayınlar
        mode = (mode or "gizli").strip().lower()
        if mode not in NOTE_MODES:
            mode = "gizli"
        if not text and mode != "surpriz":
            raise ValidationError("Not metni boş olamaz.")

        with LOCK:
            state = self.state_repo.load()
            if not state["started"]:
                raise ValidationError("Oyun henüz başlamadı — önce ana ekrandan başlatın.")

            world = StateRepository.world_of(state)
            ws = world.to_dict()
            common_tail = (
                prompt_builder.roster_note(ws)
                + "\n\n"
                + prompt_builder.presence_note(ws)
                + "\n\n"
                + prompt_builder.inventory_note(ws)
                + "\n\n"
                + prompt_builder.visible_timeline_note(self.game_log.read())
                + "\n\nGÜNCEL DÜNYA DURUMU (JSON):\n"
                + json.dumps(ws, ensure_ascii=False)
            )
            publish = mode in ("sahne", "surpriz")
            prompt, extra_system = self._compose(mode, text, common_tail)

            # Anlatıcının elle yazdırdığı sahne/sürpriz oyunculara GİDER —
            # senarist beat'iyle aynı ağırlıkta, üst seviyede yazılır. "Gizli"
            # not ise yalnız defter tutar, taban seviye yeter.
            result = self.narrator.ask(prompt, extra_system, state["session_id"],
                                       self.scenario_repo.load()["scenario_text"],
                                       effort=(config.EFFORT_KEY if publish
                                               else config.EFFORT))

            state["session_id"] = result.get("session_id") or state["session_id"]

            raw_text = result.get("result", "")
            reply_text, patches = state_update.extract(raw_text)
            # GİZLİ modda oyuncuya görünen HİÇBİR alan yazılmaz. Bu turda
            # oyunculara sahne gitmiyor; buna rağmen `challenges`/`npcs`/
            # `characters` güncellenirse oyuncu panelinde henüz yaşanmamış bir
            # olay belirir (açılmamış bir zorluk, "ısırıldı" yazan bir NPC) ve
            # oyuncular olmamış tehdide karşı önceden hazırlık yapar.
            # Anlatıcının defteri (`narrator.*`) zaten yalnız /secrets'ta
            # göründüğü için o kısım uygulanır; gerisi düşer. Değişiklik,
            # sahne gerçekten yaşandığı turda normal yoldan kaydedilir.
            dropped = []
            if mode == "gizli":
                patches, dropped = self._gm_only_patches(patches)
            for patch in patches:
                world.merge_patch(patch)

            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            note_entry = {
                "id": None,
                "role": "gm_note",
                "mode": mode,
                "text": text or "(sürpriz olay üret — konu serbest)",
                "ts": ts,
            }
            self.gm_log.append(note_entry)

            gm_entry = None
            if publish:
                # Sahne oyuncu akışına düşer; anlatıcı ekranında kaydı da kalır.
                gm_entry = {
                    "id": self.state_repo.next_id(state),
                    "role": "assistant",
                    "kind": "gm_scene",
                    "text": reply_text,
                    "ts": ts,
                    "tension": world.tension,
                }
                self.game_log.append(gm_entry)

            reply_entry = {
                "id": None,
                "role": "gm_reply",
                "mode": mode,
                "published": publish,
                # Gizli modda uygulanmayan alanlar — GM neyin kaydedilmediğini
                # görsün, gerekirse elle yamayla kendisi yazsın.
                "dropped": dropped,
                "text": ("✅ Sahne oyuncu akışına yayınlandı:\n\n" + reply_text) if publish else reply_text,
                "ts": ts,
            }
            self.gm_log.append(reply_entry)

            StateRepository.store_world(state, world)
            self.state_repo.save(state)

        return {
            "note_entry": note_entry,
            "reply_entry": reply_entry,
            "gm_entry": gm_entry,
            # gizli modda uygulanmayan üst düzey alanlar
            "dropped": dropped,
            "published": publish,
            "world_state": state["world_state"],
        }

    @staticmethod
    def _gm_only_patches(patches):
        """Gizli yönlendirmede uygulanacak yamaları süzer.

        Yalnız `narrator` (anlatıcı defteri: plot_summary / puzzles /
        upcoming_events) geçer — o alan zaten oyuncuya gönderilmiyor.
        Düşürülen üst düzey alan adları ikinci değer olarak döner; anlatıcı
        günlüğünde "uygulanmadı" diye yazılır ki GM neyin kaydedilmediğini
        bilsin ve gerekirse elle yamayla (/api/gm/patch) kendisi yazsın.
        """
        temiz, dusen = [], []
        for patch in patches:
            if not isinstance(patch, dict):
                continue
            tutulan = {k: v for k, v in patch.items() if k == "narrator"}
            dusen += [k for k in patch if k != "narrator"]
            if tutulan:
                temiz.append(tutulan)
        # sırayı koruyarak tekrarları at
        return temiz, list(dict.fromkeys(dusen))

    def _compose(self, mode: str, text: str, common_tail: str):
        """(prompt, extra_system) — üç müdahale kipinin metinleri."""
        if mode == "gizli":
            prompt = f"[ANLATICI NOTU - GİZLİ]\n{text}"
            extra_system = (
                "Bu mesaj oyunculardan DEĞİL, oyunu yöneten gerçek kişiden (GM) "
                "geliyor ve oyunculara ASLA gösterilmeyecek. SCENARIO talimatlarındaki "
                "'Anlatıcıdan (GM) gizli yönetmen notu gelirse' bölümüne göre davran: "
                "notu otoriter kabul et, gerekiyorsa narrator alanlarını (plot_summary/"
                "puzzles/upcoming_events) state-update ile güncelle, ve SADECE bu "
                "anlatıcıya hitap eden kısa bir onay/yanıt yaz. Bu turda oyunculara "
                "gidecek HİÇBİR sahne yazma — talimatı sonraki oyuncu turlarında "
                "hayata geçir.\n"
                "ÖNEMLİ: bu turda SADECE `narrator` alanları kaydedilir. "
                "`challenges`, `npcs`, `characters`, `resources`, `factions`, "
                "`day`/`clock` gibi oyuncuya görünen alanlara yazdıkların "
                "UYGULANMAZ ve düşer — çünkü oyuncular bu olayı henüz "
                "yaşamadı; panelde belirirse olmamış bir tehdide karşı "
                "önceden hazırlanırlar. O alanları, olay sahnede GERÇEKTEN "
                "yaşandığı turda yaz.\n\n"
                + common_tail
            )
        elif mode == "sahne":
            prompt = f"[ANLATICI MÜDAHALESİ - SAHNE OLARAK YAYINLA]\n{text}"
            extra_system = (
                "Bu talimat oyunu yöneten gerçek kişiden (GM) geliyor ve OTORİTERDİR. "
                "Bu turda yazdığın metin DOĞRUDAN oyuncuların ekranına, hikayenin bir "
                "parçası olarak düşecek.\n"
                "- Sadece sahneyi yaz: anlatıcı sesiyle, 1-3 paragraf, atmosferik.\n"
                "- GM'den, bu talimattan ya da perde arkasından ASLA söz etme; "
                "oyuncular böyle bir müdahalenin varlığını bilmemeli.\n"
                "- Bu bir oyuncu aksiyonunun sonucu değil, dünyanın kendi hamlesi: "
                "zar mekaniği UYGULAMA.\n"
                "- Sahnenin sonunda oyunculara net bir durum bırak ve ne yapacaklarını sor.\n"
                "- Sahne SOMUT BİR PROBLEM üretsin ya da mevcut bir zorluğu ilerletsin: "
                "ölçülebilir parametre (sayı/mesafe/süre), bedeli olan seçenekler. "
                "'SAHNE YAPISI' bölümündeki **DURUM** + **SEÇENEKLER** bloğuyla bitir.\n"
                "- Yanıtının sonuna TEK bir state-update bloğu ekle: tension, "
                "narrator.plot_summary ve `challenges` (yeni zorluk ya da güncellenen "
                "clock/progress).\n\n"
                + common_tail
            )
        else:  # surpriz
            steer = f"\nGM'in yönlendirmesi (bunu dikkate al): {text}" if text else ""
            prompt = "[ANLATICI MÜDAHALESİ - SÜRPRİZ OLAY]" + steer
            extra_system = (
                "Oyunu yöneten kişi hikayeye SÜRPRİZ bir gelişme sokmanı istiyor. "
                "Bu turda yazdığın metin DOĞRUDAN oyuncuların ekranına düşecek.\n"
                "- Olayı SEN icat et, ama rastgele olmasın: mevcut dünya durumundan "
                "beslen — narrator.upcoming_events'teki kendi planların, çözülmemiş "
                "bulmacalar, fraksiyonların tavrı, karakter/NPC ilişkileri ve notları, "
                "azalan kaynaklar, son sahnedeki gerilim.\n"
                "- Beklenmedik ama GERİYE DÖNÜK TUTARLI olsun: oyuncular 'bunun izleri "
                "zaten vardı' diyebilmeli. Ucuz deus ex machina yazma.\n"
                "- Oyuncuların elini bağlama: sürpriz onlara karar verecekleri yeni bir "
                "durum açsın, sonucu sen dayatma.\n"
                "- GM'den ya da bu talimattan ASLA söz etme. Zar mekaniği UYGULAMA. "
                "1-3 paragraf, sonunda oyunculara ne yapacaklarını sor.\n"
                "- Sürpriz SOMUT BİR ZORLUĞA dönüşsün (ya da mevcut bir bulmacayı "
                "ilerletsin): ölçülebilir parametre + bedeli olan seçenekler. "
                "'SAHNE YAPISI' bölümündeki **DURUM** + **SEÇENEKLER** bloğuyla bitir.\n"
                "- Yanıtının sonuna TEK bir state-update bloğu ekle: tension, "
                "narrator.plot_summary, `challenges` ve gerekiyorsa "
                "narrator.puzzles (progress/clues_found/next_step).\n\n"
                + common_tail
            )
        return prompt, extra_system

    # ----------------------------------------------------------- /api/gm/patch
    # ------------------------------------------------------ eşya kataloğu
    def items_catalog(self, pin) -> dict:
        """Anlatıcı ekranının okuduğu katalog (PIN'li)."""
        self._check(pin)
        return self.items.public_catalog()

    def add_item(self, pin, item) -> dict:
        """Kataloga KALICI eşya ekler.

        Eklenen eşya `data/items.json`'a yazılır: oyunun içeriğine girer, tek
        bir oyunun durumuna değil. Yeni oyun kurulsa, `/api/reset` çekilse bile
        durur ve o andan itibaren her oyunda aranırken çıkabilir."""
        self._check(pin)
        kayit = self.items.add_item(item)
        self.gm_log.append({
            "id": None,
            "role": "system",
            "text": f"🧰 Kataloga kalıcı eşya eklendi: {kayit['ad']} "
                    f"({kayit['kategori']}) — bu eşya bundan sonra TÜM oyunlarda var.",
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        return {"ok": True, "item": kayit, "catalog": self.items.public_catalog()}

    def patch(self, pin, patch) -> dict:
        """Anlatıcının doğrudan (model çağrısı olmadan) dünya durumunu düzenlemesi:
        fraksiyon tavrı, zorluk saati, bulmaca ilerlemesi vb. Anında uygulanır."""
        self._check(pin)
        if not isinstance(patch, dict) or not patch:
            raise ValidationError("Boş ya da geçersiz düzenleme.")
        with LOCK:
            state = self.state_repo.load()
            world = StateRepository.world_of(state)
            world.merge_patch(patch)
            StateRepository.store_world(state, world)
            self.state_repo.save(state)
            version = int(state.get("version", 0))
        return {"ok": True, "version": version, "world_state": state["world_state"]}
