"""Zombi tehdidi — turun tehdit ayağı.

Her turda sırayla:

  1. Gürültü ve bölge dikkati, geçen oyun-içi zamana göre söner.
  2. BİR ÖNCEKİ turdan devredilen gürültü, yolculuk niyeti ve olaylar
     (patlama/alarm) devreye girer. Bu turda çıkan ses bu turun zarını
     etkilemez — sonuçları bir sonraki tura yazılır (bkz. `models/pending.py`).
  3. Bulunulan yerin (ya da yolun) yoğunluğuyla karşılaşma zarı atılır.
  4. Sonuç anlatıcıya ZORUNLU bir blok olarak verilir: kaç zombi, hangi
     türler, ne mesafede, hangi yönden, kim önce fark etti.
  5. Tur bitince sonuç deftere işlenir (dikkat artar, sessizlik sayacı sıfırlanır).

Neden sunucu tarafında: "zombiler sık olsun" ricası her turda farklı
yorumlanıyordu ve yolculuk güvenli bir geçiş sahnesine dönüşüyordu. Sayıyı zar
belirleyince anlatıcının geçiştirmesi mümkün olmuyor.
"""

from app.models.text import norm_tr
from app.models.threat import (
    EVENT_PULL,
    ThreatState,
    density_band,
    looks_like_travel,
    noise_from_text,
)

# Gecenin sayıldığı zaman dilimleri.
NIGHT_WORDS = ("gece", "gece yarısı", "şafak")

# Gürültü bu eşiği aşarsa bölgeye ölü çekilir (göç tetiklenir).
MIGRATION_NOISE_MIN = 10
# Karşılaşmanın kendisi de bölgeye ölü toplar — küçük ama gerçek bir çekim.
ENCOUNTER_PULL = 0.35


class ThreatService:
    """Tehdit motorunun akış katmanı. Kilit ÇAĞIRANDA (turn/round servisi)."""

    # ------------------------------------------------------------- yardımcı
    @staticmethod
    def state_of(world) -> ThreatState:
        return world.ensure_threat()

    @staticmethod
    def is_night(world) -> bool:
        return norm_tr(world.time_of_day or "") in [norm_tr(w) for w in NIGHT_WORDS]

    @staticmethod
    def graph(world) -> dict:
        """Göç motorunun komşuluk grafiği — haritadaki `links` alanlarından."""
        world_map = world.map
        return world_map.adjacency() if world_map is not None else {}

    @staticmethod
    def place_kind(world) -> str:
        """Bulunulan yerin türü — yoğunluk tahmini için (haritadan)."""
        world_map = world.map
        if world_map is None or not world.location:
            return ""
        place = (world_map.places or {}).get(world.location)
        return getattr(place, "kind", "") or ""

    # ---------------------------------------------------------------- devir
    @staticmethod
    def read_inputs(action_text: str = "", events=None) -> dict:
        """Bu turda tetiklenen tehdit girdileri — BİR SONRAKİ tura yazılır.

        Gürültü ve yolculuk niyeti oyuncuların seçimlerinden, olaylar
        anlatıcının state-update'inden okunur. Hiçbiri bu turda uygulanmaz:
        ses çıkardığın tur değil, ONDAN SONRAKİ tur tehlikelidir
        (bkz. `models/pending.py`)."""
        ham = events if isinstance(events, list) else ([events] if isinstance(events, dict) else [])
        return {
            "noise": noise_from_text(action_text),
            "travel": looks_like_travel(action_text),
            "events": [o for o in ham if isinstance(o, dict)],
        }

    # ---------------------------------------------------------------- tur
    def prepare(self, world, action_text: str = "", minutes: int = 0,
                carry: dict = None) -> dict:
        """Turun BAŞINDA çağrılır: söndür, devri uygula, zar at.

        `carry` verilirse (tur bazlı akışın normal hali) gürültü/yolculuk/olay
        girdileri BİR ÖNCEKİ turdan gelir — bu turda çıkan ses bu turun zarını
        etkilemez. `carry` verilmezse girdiler `action_text`'ten okunur
        (karakter oluşturma turları ve eski çağrı yolları).

        Dönen sözlük prompt bloğunu ve karşılaşmayı taşır; karşılaşma turun
        SONUNDA `commit` ile deftere işlenir (model yanıt vermezse tehdit
        kaydı bozulmasın)."""
        threat = self.state_of(world)
        devir = carry if isinstance(carry, dict) else None

        # 1) sönüm — BİR ÖNCEKİ turda gerçekten geçen oyun-içi süre kadar
        gecen = threat.last_minutes or minutes or 0
        threat.decay(max(0.0, gecen / 60.0))

        # 1b) yayılma — boşalan bölgeler komşularından yavaşça dolar
        graf = self.graph(world)
        threat.diffuse(graf, max(0.0, gecen / 60.0))

        # 2) devreye giren gürültü + yolculuk niyeti (geçen turdan devredilen)
        gurultu = int(devir.get("noise") or 0) if devir else noise_from_text(action_text)
        goc = None
        if gurultu:
            threat.add_noise(gurultu)
            # SES ÖLÜLERİ ÇEKER: bu bölgeye gelenler komşu bölgelerden eksilir.
            if gurultu >= MIGRATION_NOISE_MIN and world.location:
                goc = threat.attract(
                    world.location, gurultu * EVENT_PULL["gürültü"], graf)

        # 2b) geçen turda bildirilen OLAYLAR (patlama/alarm/yangın) şimdi
        # devreye girer: ölüler o bölgeye komşularından çekilir.
        for olay in (devir.get("events") if devir else None) or []:
            kayit = self.apply_event(world, olay)
            if kayit:
                goc = kayit

        # Yolculuk bayrağı YAPIŞKAN DEĞİLDİR: ya geçen turda yola çıkma niyeti
        # vardı, ya da grup gerçekten yer değiştirmiştir. Aksi halde bir kez
        # yola çıkan grup, sığınağa varsa bile sonsuza dek "yolda" sayılıyor
        # ve her tur sürüyle karşılaşıyordu.
        simdiki_yer = world.location or ""
        yer_degisti = bool(threat.last_location and simdiki_yer
                           and threat.last_location != simdiki_yer)
        niyet = bool(devir.get("travel")) if devir else looks_like_travel(action_text)
        yolculuk = niyet or yer_degisti

        # 3) yoğunluk ve zar
        if yolculuk:
            from scenario import ROUTE_DENSITY
            yogunluk = ROUTE_DENSITY
            yer = "yol"
        else:
            yer = world.location or "sahne"
            yogunluk = threat.density_of(yer, self.place_kind(world))

        gun = world.day if isinstance(world.day, int) else 0
        karsilasma = threat.roll(
            density=yogunluk, travelling=yolculuk, night=self.is_night(world),
            day=gun, weather=world.weather or "", tension=world.tension or "",
        )
        threat.travelling = yolculuk

        return {"encounter": karsilasma, "threat": threat, "place": yer,
                "density": yogunluk, "noise_added": gurultu, "graph": graf,
                "migration": goc,
                "note": self.note(world, threat, karsilasma, yer, yogunluk, goc)}

    @staticmethod
    def commit(world, hazirlik: dict, minutes: int = 0) -> None:
        """Turun SONUNDA: karşılaşmayı deftere işle, süre ve konumu sakla."""
        if not hazirlik:
            return
        threat = hazirlik["threat"]
        karsilasma = hazirlik["encounter"]
        threat.record(karsilasma, day=world.day, clock=world.clock,
                      place=hazirlik.get("place"))
        # Karşılaşma bölgeye ölü TOPLAR: gelenler yine komşulardan eksilir,
        # nüfus yoktan var olmaz.
        if karsilasma.var and world.location and not karsilasma.travelling:
            threat.attract(world.location, karsilasma.count * ENCOUNTER_PULL,
                           hazirlik.get("graph") or {})
        # Sonraki turun sönümü ve yolculuk tespiti için: bu turda ne kadar
        # zaman geçti ve grup nerede kaldı.
        threat.last_minutes = max(0, int(minutes or 0))
        threat.last_location = world.location or threat.last_location

    def apply_event(self, world, event: dict) -> dict:
        """Anlatıcının bildirdiği bir OLAY: patlama, yangın, alarm…

        {"type": "patlama", "place": "Kuzey deposu", "strength": 40}

        Olay o bölgeye ölü çeker; gelenler komşu bölgelerden eksilir. Olay
        grubun bulunduğu yerde olmak zorunda değil — uzaktaki bir patlama da
        haritayı değiştirir (ve o yöne giden yolları boşaltır)."""
        if not isinstance(event, dict):
            return {}
        yer = str(event.get("place") or world.location or "").strip()
        if not yer:
            return {}
        tur = norm_tr(event.get("type") or "gürültü")
        carpan = next((v for k, v in EVENT_PULL.items() if norm_tr(k) == tur), 1.0)
        try:
            guc = float(event.get("strength") or 25)
        except (TypeError, ValueError):
            guc = 25.0
        guc = max(0.0, min(100.0, guc))
        threat = self.state_of(world)
        kayit = threat.attract(yer, guc * carpan, self.graph(world))
        if kayit:
            kayit["type"] = event.get("type") or "gürültü"
        return kayit

    # -------------------------------------------------------------- prompt
    @staticmethod
    def note(world, threat: ThreatState, encounter, place: str, density: int,
             migration: dict = None) -> str:
        """Anlatıcıya giden ZORUNLU tehdit bloğu."""
        bant = density_band(density)
        satirlar = [
            "ZOMBİ TEHDİDİ (sunucu zarı — bu blok ZORUNLUDUR, sahnede FİİLEN oynat).",
            "Bu blok GEÇEN turda olanların sonucudur: geçen turun gürültüsü, "
            "yola çıkma niyeti ve bildirilen olaylar şimdi devreye girdi.",
            f"- Bölge yoğunluğu: {place} · {density}/100 ({bant}) · "
            f"grup gürültüsü {threat.noise}/100 · bölgenin dikkati {threat.heat}/100",
        ]
        if encounter.travelling:
            satirlar.append(
                "- DURUM: GRUP YOLDA. Açık alanda saklanacak yer yoktur; yolculuk "
                "bu dünyanın en tehlikeli işidir. Yol boyunca ölülerin varlığını "
                "sürekli hissettir (uzaktan siluetler, tıkanmış geçitler, terk "
                "edilmiş araçların arasındaki hareket)."
            )

        if encounter.var:
            tur_metni = ", ".join(f"{t['adet']}× {t['ad']} ({t['kunye']})"
                                  for t in encounter.types)
            satirlar += [
                f"- KARŞILAŞMA VAR ({encounter.severity}): toplam ~{encounter.count} ölü, "
                f"{encounter.distance} metre mesafede, {encounter.approach}.",
                f"- Tür karışımı (AYNEN kullan, türlerin davranışını uygula): {tur_metni}",
                ("- Grup onları ÖNCE fark etti: tepki vermek için kısa bir pay var."
                 if encounter.noticed_first else
                 "- ONLAR ÖNCE fark etti: grup hazırlıksız yakalandı, ilk hamle onların."),
                "- Bu karşılaşmayı sahnede GERÇEKTEN yaşat: sayıyı azaltma, "
                "'uzaklaştılar' diye kapatma. Kaçmak, saklanmak ya da savaşmak bir "
                "BEDEL ister (mermi, yaralanma, gürültü, kaybedilen zaman, bırakılan "
                "eşya). Sonucu oyuncuların hamlesine ve zarına göre çöz.",
            ]
            if encounter.count >= 25:
                satirlar.append(
                    "- Bu bir SÜRÜ: karşı koymak intihardır. Sahne 'nasıl savaşırız' "
                    "değil, 'nereye kaçarız, neyi feda ederiz' sorusu olsun."
                )
        else:
            satirlar += [
                f"- Bu turda TEMAS YOK — ama bölge boş değil: {encounter.sign}.",
                "- Bunu sahnede kısa ve somut bir işaret olarak göster; tehdit hep "
                "yakında dursun. Oyunculara 'güvendesiniz' hissi VERME.",
            ]

        goc = migration or (threat.migrations[-1] if threat.migrations else None)
        if goc and goc.get("from"):
            kaynaklar = ", ".join(f"{k['place']} −{k['amount']}"
                                  for k in goc["from"][:4])
            satirlar.append(
                f"- GÖÇ: ses {goc['target']} bölgesine ölü çekti (+{goc['gain']} yoğunluk); "
                f"gelenler komşu bölgelerden eksildi → {kaynaklar}. Bunu sahnede "
                "göster: çekilen yöne akan gölgeler, boşalan bölgenin tuhaf "
                "sessizliği. Boşalan bölge bir süre daha SAKİN kalır."
            )

        satirlar.append(
            "- GÜRÜLTÜ KURALI: silah sesi, araç, kırılan kapı, bağırma bölgenin "
            "dikkatini çeker ve bir sonraki turda karşılaşma ihtimalini yükseltir. "
            "Bu turda gürültü çıktıysa state-update'e `threat` altında "
            '`{"noise_add": <10-35>}` yaz; sessiz ilerlendiyse yazma. Bir bölge '
            "temizlendiyse ya da kalabalıklaştıysa "
            '`{"density": {"<yer>": <0-100>}}` ile güncelle.'
        )
        satirlar.append(
            "- OLAY BİLDİRİMİ: bu turda bir yerde patlama/yangın/alarm gibi ölü "
            "çeken bir olay olduysa state-update'e "
            '`"threat": {"events": [{"type": "patlama", "place": "<yer>", "strength": 40}]}` '
            "yaz. Sunucu o bölgeye KOMŞU BÖLGELERDEN ölü göçü yapar ve kaynak "
            "bölgeleri boşaltır — olay grubun bulunduğu yerde olmak zorunda değil."
        )
        if threat.quiet_turns >= 3:
            satirlar.append(
                f"- {threat.quiet_turns} turdur temas yok: baskı artıyor, sıradaki "
                "sessizlik daha tekinsiz olsun."
            )
        return "\n".join(satirlar)
