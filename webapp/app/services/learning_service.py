"""Öğrenme katmanı — oyun oynandıkça kendini geliştiren yetenek.

Sözleşme basit: **her interaction defterle biter.** Her tur, her seçim, her
anlatıcı yanıtı, her GM müdahalesi buradan geçer; defter sayaçları büyür,
sayaçlardan ders çıkar ve o dersler bir sonraki turun promptuna girer. Yani
oyun kendi kendini eğitir ve bunu ek bir model çağrısı ödemeden yapar.

Üç çıkış noktası vardır:

  1. `note()`      — her turda anlatıcının promptuna giren "ÖĞRENİLENLER" bloğu.
  2. `summary()`   — anlatıcı ekranındaki (/secrets) öğrenme paneli.
  3. `export_skill()` — `.claude/skills/kizil-cokus-anlatici/ogrenilenler.md`.
     Böylece öğrenilenler bu sunucunun dışında da yaşar: bir sonraki Claude
     Code oturumu yeteneği yükler ve oyun oradan da aynı bilgiyle devam eder.

Ders üretimi bilinçli olarak KOD tarafındadır (`_derive`): ucuz, tekrar
edilebilir ve denetlenebilir. Anlatıcının kendi gözlemi de kabul edilir —
state-update içindeki `learning.lessons_add` alanı buraya düşer.
"""

import time

from app import config
from app.models.learning import MIN_SAMPLE, Learning
from app.models.options import CATEGORIES
from app.repositories.learning_repo import LearningRepository
from app.repositories.options_repo import OptionsPoolRepository


class LearningService:
    def __init__(self, learning_repo=None, pool_repo=None, skill_dir=None):
        self.repo = learning_repo or LearningRepository()
        self.pool = pool_repo or OptionsPoolRepository()
        self.skill_dir = skill_dir or config.SKILL_DIR

    # --------------------------------------------------------------- okuma
    def load(self) -> Learning:
        return self.repo.load()

    def summary(self) -> dict:
        summary = self.load().summary()
        summary["pool"] = self.pool.stats()
        return summary

    # ------------------------------------------------------------ prompt
    def note(self, store: Learning = None) -> str:
        """Her turda modele giden blok. Defter boşken hiçbir şey yazmaz —
        ilk oyunda uydurma bir "öğrenilen" listesi göstermek yanıltıcı olurdu."""
        store = store or self.load()
        lessons = store.top_lessons()
        if not lessons and store.turns < 3:
            return ""
        lines = [
            "ÖĞRENİLENLER (bu masayla oynanan {} turdan çıkarıldı — kural değil, "
            "AYAR: sahneyi bunlara göre kalibre et, oyunculara bu bloktan ya da "
            "'öğrenme'den ASLA söz etme):".format(store.turns)
        ]
        favori = store.favourite_category()
        if favori and favori[2] >= MIN_SAMPLE:
            lines.append(
                f"- Masanın eğilimi: '{favori[0]}' seçenekler (%{round(favori[1] * 100)}, "
                f"{favori[2]} seçim). Bu eğilimi hem besle hem sına: aynı refleksin "
                "her turda aynı sonucu vermediğini göster."
            )
        for lesson in lessons:
            kaynak = {"gm": "GM", "anlatıcı": "anlatıcı"}.get(lesson.get("source"), "")
            etiket = f" [{kaynak}]" if kaynak else ""
            lines.append(f"- {lesson['text']}{etiket}")
        return "\n".join(lines)

    # -------------------------------------------------------------- yazma
    def record_game(self, start: str = None, factions=None) -> Learning:
        """Yeni oyun açıldı — kullanılan başlangıç/fraksiyonlar not edilir."""
        store = self.load()
        store.record_game(start, factions)
        if start:
            store.add_lesson(
                f"'{start}' başlangıcı kullanıldı; bir sonraki oyun başka bir "
                "başlangıç noktasıyla açılsın.",
                source="otomatik", key=f"baslangic:{start}", in_prompt=False,
            )
        self._finish(store)
        self.repo.append_event({
            "tip": "oyun_basladi", "start": start,
            "factions": list(factions or []),
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        return store

    def observe_turn(self, world, picks=None, scene_text: str = "",
                     events: dict = None, seconds=None, kind: str = "tur") -> Learning:
        """Bir tur tamamlandı. `picks` liste halinde seçim sözlükleridir
        (round_service'ten gelir; serbest metin turunda tek elemanlı olur)."""
        store = self.load()
        gun = world.day if world is not None and isinstance(world.day, int) else None
        tur = store.turns + 1

        havuz_kayitlari = []
        for pick in picks or []:
            store.record_pick(pick)
            havuz_kayitlari.append({
                "tip": "secildi", "tur": tur, "gun": gun,
                "player": pick.get("player"), "category": pick.get("category"),
                "text": (pick.get("text") or "")[:400], "roll": pick.get("roll"),
                "band": pick.get("band"), "custom": bool(pick.get("custom")),
                "timeout": bool(pick.get("timeout")),
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
        self.pool.append_many(havuz_kayitlari)

        store.record_turn(seconds, events)
        self.repo.append_event({
            "tip": kind, "tur": tur, "gun": gun,
            "tension": getattr(world, "tension", None),
            "picks": [
                {k: v for k, v in pick.items() if k in
                 ("player", "category", "roll", "band", "custom", "timeout")}
                for pick in picks or []
            ],
            "events": dict(events or {}),
            "scene_len": len(scene_text or ""),
            "seconds": seconds,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        self._derive(store, gun)
        self._finish(store)
        return store

    def record_offered(self, board, day=None, turn=None) -> None:
        """Anlatıcının bu turda sunduğu seçenekler havuza yazılır."""
        kayitlar = []
        for player, options in (board.by_player if board else {}).items():
            for option in options:
                kayitlar.append({
                    "tip": "sunuldu", "tur": turn, "gun": day, "player": player,
                    "category": option.category, "text": option.text[:400],
                    "cost": option.cost[:200],
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
        self.pool.append_many(kayitlar)

    def add_lesson(self, text: str, source: str = "gm", day=None) -> Learning:
        store = self.load()
        store.add_lesson(text, source=source, day=day)
        self._finish(store)
        return store

    def absorb_patch(self, patch: dict, day=None) -> None:
        """state-update içindeki `learning` alanı: anlatıcının kendi gözlemi.

        {"learning": {"lessons_add": ["..."], "note": "..."}}
        """
        if not isinstance(patch, dict):
            return
        raw = patch.get("learning")
        if not isinstance(raw, dict):
            return
        dersler = raw.get("lessons_add") or raw.get("lessons") or []
        if isinstance(dersler, str):
            dersler = [dersler]
        note = raw.get("note")
        if isinstance(note, str) and note.strip():
            dersler = list(dersler) + [note]
        if not dersler:
            return
        store = self.load()
        for text in dersler:
            if isinstance(text, str) and text.strip():
                store.add_lesson(text.strip(), source="anlatıcı", day=day)
        self._finish(store)

    # ------------------------------------------------------------- içerik
    @staticmethod
    def _derive(store: Learning, day=None) -> None:
        """Sayaçlardan ders çıkarır. Her ders bir EŞİĞE bağlıdır — az veriden
        büyük sonuç çıkarmak defteri gürültüyle doldururdu."""
        pace = store.pace
        havuzdan = int(pace.get("havuzdan") or 0)
        serbest = int(pace.get("serbest") or 0)
        toplam_secim = havuzdan + serbest

        favori = store.favourite_category()
        if favori and favori[2] >= MIN_SAMPLE and favori[1] >= 0.4:
            ad, oran, _adet = favori
            store.add_lesson(
                f"Bu masa ağırlıkla '{ad}' oynuyor (%{round(oran * 100)}). Bu "
                f"kategorinin bedelini her turda AYNI kalıba bağlama; ara sıra "
                f"'{ad}' hamlenin işe yaramadığı, başka bir kategorinin açıkça "
                "üstün olduğu bir sahne kur.",
                source="otomatik", key=f"egilim:{ad}", day=day,
            )

        for ad, stats in store.categories.items():
            secim = int(stats.get("secim") or 0)
            if secim < MIN_SAMPLE or ad not in CATEGORIES:
                continue
            felaket = int(stats.get("felaket") or 0)
            basari = int(stats.get("basari") or 0) + int(stats.get("kritik") or 0)
            if felaket / secim >= 0.25:
                store.add_lesson(
                    f"'{ad}' seçimler bu masada sık felaketle bitiyor "
                    f"({felaket}/{secim}). Bedeli artık ÖNCEDEN sezdir: seçeneğin "
                    "`cost` alanında somut riski yaz, sürpriz ceza verme.",
                    source="otomatik", key=f"felaket:{ad}", day=day,
                )
            if basari / secim >= 0.7:
                store.add_lesson(
                    f"'{ad}' seçimler bu masada neredeyse hep başarıya çıkıyor "
                    f"({basari}/{secim}) — kolay kazanç hikayeyi düzleştirir. Bu "
                    "kategoriye gerçek bir takas ekle (zaman, gürültü, ilişki).",
                    source="otomatik", key=f"kolay:{ad}", day=day,
                )

        # Serbest hamle kaldırıldı: her seçim havuzdan geliyor. Bu yüzden
        # ölçülen şey "havuzu kullanıyorlar mı" değil, havuzun ne kadar ZORLAYICI
        # olduğu — bekleme (pas) oranı bunun göstergesi.
        bekleme = int(store.categories.get("güvenli", {}).get("secim") or 0)
        if toplam_secim >= 12 and bekleme / max(1, toplam_secim) >= 0.5:
            store.add_lesson(
                "Seçimlerin yarısından fazlası düşük riskli/bekleme seçenekleri — "
                "sunduğun seçenekler ya yeterince cazip değil ya da hepsi fazla "
                "pahalı. Her listeye gerçekten çekici, kazanç vaat eden bir "
                "seçenek koy.",
                source="otomatik", key="havuz:pasif", day=day,
            )

        zaman_asimi = int(pace.get("zaman_asimi") or 0)
        if zaman_asimi >= 3:
            store.add_lesson(
                f"Süre {zaman_asimi} kez doldu ve oyuncular karar veremeden tur "
                "kapandı. Seçenekleri KISALT (ilk üçü tek satır olsun) ve "
                "sahnenin sonundaki soruyu tek cümlede sor.",
                source="otomatik", key="tempo:zamanasimi", day=day,
            )

        uzun = int(pace.get("uzun_secim") or 0)
        kisa = int(pace.get("kisa_secim") or 0)
        if uzun + kisa >= 15:
            if uzun / (uzun + kisa) >= 0.6:
                store.add_lesson(
                    "Bu masa uzun/planlı seçenekleri seçiyor — her turda en az "
                    "iki tane çok adımlı, plan tadında seçenek sun.",
                    source="otomatik", key="uzunluk:uzun", day=day,
                )
            elif kisa / (uzun + kisa) >= 0.75:
                store.add_lesson(
                    "Bu masa kısa ve doğrudan seçenekleri seçiyor — seçenekleri "
                    "tek satırda, fiil ile başlat; uzun planları en fazla ikiyle sınırla.",
                    source="otomatik", key="uzunluk:kisa", day=day,
                )

        events = store.events
        cozulen = int(events.get("cozulen_zorluk") or 0)
        if store.turns >= 12 and cozulen == 0:
            store.add_lesson(
                "12+ turdur hiçbir zorluk KAPANMADI. Zorlukları kapanabilir "
                "tut: her zorluğun 2-5 turluk net bir çözüm yolu ve ölçülebilir "
                "bir ilerleme parametresi olsun.",
                source="otomatik", key="tempo:zorlukkapanmiyor", day=day,
            )
        olum = int(events.get("olum") or 0)
        if store.turns >= 20 and olum == 0 and int(events.get("yara") or 0) < 3:
            store.add_lesson(
                "20+ turdur ne ölüm ne kayda değer yara var — tehdit inandırıcılığını "
                "yitiriyor. Bir sonraki kritik başarısızlıkta bedeli GERÇEKTEN uygula.",
                source="otomatik", key="tehdit:yumusak", day=day,
            )

        ortalama = pace.get("ortalama_saniye")
        if isinstance(ortalama, (int, float)) and int(pace.get("sure_adet") or 0) >= 10:
            if ortalama <= 25:
                store.add_lesson(
                    "Oyuncular çok hızlı karar veriyor (ortalama "
                    f"{int(ortalama)} sn) — seçenekleri daha zor takaslara "
                    "dönüştür; 'doğru cevabı' bariz olan seçenek sunma.",
                    source="otomatik", key="tempo:hizli", day=day,
                )

    def _finish(self, store: Learning) -> None:
        store.touch()
        self.repo.save(store)
        try:
            self.export_skill(store)
        except OSError:
            # Skill dosyası yazılamazsa oyun durmaz — defter yine de kaydedildi.
            pass

    # ------------------------------------------------------------- skill
    def export_skill(self, store: Learning = None) -> None:
        """Öğrenilenleri Claude yeteneğinin içine yazar.

        `SKILL.md` elle yazılmış zanaat bilgisidir ve buraya dokunulmaz;
        değişen tek dosya `ogrenilenler.md` — yeteneğin oyun oynadıkça büyüyen
        yarısı."""
        store = store or self.load()
        summary = store.summary()
        satirlar = [
            "# Öğrenilenler (otomatik üretilir — elle düzenlemeyin)",
            "",
            "Bu dosyayı `webapp` sunucusu her turun sonunda yeniden yazar "
            "(`app/services/learning_service.py`). Kızıl Çöküş anlatıcısı bu "
            "masayla oynadıkça biriken ayarlardır; `SKILL.md`'deki zanaat "
            "bilgisinin üstüne, o masaya özel kalibrasyon olarak okunur.",
            "",
            f"- Son güncelleme: {store.updated or '-'}",
            f"- Oynanan oyun: {store.games} · tur: {store.turns} · seçim: {store.picks}",
            "",
            "## Dersler",
            "",
        ]
        dersler = store.top_lessons(limit=len(store.lessons) or 1, prompt_only=False)
        if not dersler:
            satirlar.append("_Henüz ders çıkmadı — birkaç tur oynanması gerekiyor._")
        for lesson in dersler:
            kaynak = lesson.get("source") or "otomatik"
            agirlik = int(lesson.get("weight") or 1)
            satirlar.append(f"- **[{kaynak} ×{agirlik}]** {lesson['text']}")

        satirlar += ["", "## Masanın seçim profili", ""]
        if summary["categories"]:
            satirlar.append("| Kategori | Seçim | Pay | Ortalama zar | Felaket | Kritik |")
            satirlar.append("|---|---:|---:|---:|---:|---:|")
            for ad, stats in summary["categories"].items():
                satirlar.append(
                    f"| {ad} | {stats['secim']} | %{stats['oran']} | "
                    f"{stats['ortalama_zar'] if stats['ortalama_zar'] is not None else '-'} | "
                    f"{stats['felaket']} | {stats['kritik']} |"
                )
        else:
            satirlar.append("_Henüz seçim kaydı yok._")

        satirlar += ["", "## Tempo", ""]
        pace = summary["pace"]
        satirlar.append(
            f"- Havuzdan seçim: {int(pace.get('havuzdan') or 0)} · "
            f"kendi yazdığı: {int(pace.get('serbest') or 0)} · "
            f"süre aşımı: {int(pace.get('zaman_asimi') or 0)}"
        )
        if pace.get("ortalama_saniye"):
            satirlar.append(f"- Ortalama karar süresi: {pace['ortalama_saniye']} sn")
        events = summary["events"]
        if events:
            satirlar.append(
                "- Olaylar: " + ", ".join(f"{k}={v}" for k, v in sorted(events.items()))
            )

        satirlar += ["", "## Tekrar ETMEyecekler", ""]
        satirlar.append(
            "Başlangıç noktaları: "
            + (", ".join(store.used_starts) if store.used_starts else "(yok)")
        )
        satirlar.append(
            "Fraksiyon adları: "
            + (", ".join(store.used_factions) if store.used_factions else "(yok)")
        )
        satirlar.append("")

        self.skill_dir.mkdir(parents=True, exist_ok=True)
        (self.skill_dir / "ogrenilenler.md").write_text(
            "\n".join(satirlar), encoding="utf-8")
