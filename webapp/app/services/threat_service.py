"""Zombi tehdidi — turun tehdit ayağı.

Her turda sırayla:

  1. Gürültü ve bölge dikkati, geçen oyun-içi zamana göre söner.
  2. Oyuncuların hamlesinden gürültü ve YOLCULUK niyeti okunur.
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
    ThreatState,
    density_band,
    looks_like_travel,
    noise_from_text,
)

# Gecenin sayıldığı zaman dilimleri.
NIGHT_WORDS = ("gece", "gece yarısı", "şafak")


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
    def place_kind(world) -> str:
        """Bulunulan yerin türü — yoğunluk tahmini için (haritadan)."""
        world_map = world.map
        if world_map is None or not world.location:
            return ""
        place = (world_map.places or {}).get(world.location)
        return getattr(place, "kind", "") or ""

    # ---------------------------------------------------------------- tur
    def prepare(self, world, action_text: str = "", minutes: int = 0) -> dict:
        """Turun BAŞINDA çağrılır: söndür, oku, zar at.

        Dönen sözlük prompt bloğunu ve karşılaşmayı taşır; karşılaşma turun
        SONUNDA `commit` ile deftere işlenir (model yanıt vermezse tehdit
        kaydı bozulmasın)."""
        threat = self.state_of(world)

        # 1) sönüm — BİR ÖNCEKİ turda gerçekten geçen oyun-içi süre kadar
        gecen = threat.last_minutes or minutes or 0
        threat.decay(max(0.0, gecen / 60.0))

        # 2) hamleden gürültü + yolculuk niyeti
        gurultu = noise_from_text(action_text)
        if gurultu:
            threat.add_noise(gurultu)
        # Yolculuk bayrağı YAPIŞKAN DEĞİLDİR: ya bu turda yola çıkma niyeti
        # var, ya da grup geçen turda gerçekten yer değiştirmiştir. Aksi halde
        # bir kez yola çıkan grup, sığınağa varsa bile sonsuza dek "yolda"
        # sayılıyor ve her tur sürüyle karşılaşıyordu.
        simdiki_yer = world.location or ""
        yer_degisti = bool(threat.last_location and simdiki_yer
                           and threat.last_location != simdiki_yer)
        yolculuk = looks_like_travel(action_text) or yer_degisti

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
                "density": yogunluk, "noise_added": gurultu,
                "note": self.note(world, threat, karsilasma, yer, yogunluk)}

    @staticmethod
    def commit(world, hazirlik: dict, minutes: int = 0) -> None:
        """Turun SONUNDA: karşılaşmayı deftere işle, süre ve konumu sakla."""
        if not hazirlik:
            return
        threat = hazirlik["threat"]
        threat.record(hazirlik["encounter"], day=world.day, clock=world.clock,
                      place=hazirlik.get("place"))
        # Sonraki turun sönümü ve yolculuk tespiti için: bu turda ne kadar
        # zaman geçti ve grup nerede kaldı.
        threat.last_minutes = max(0, int(minutes or 0))
        threat.last_location = world.location or threat.last_location

    # -------------------------------------------------------------- prompt
    @staticmethod
    def note(world, threat: ThreatState, encounter, place: str, density: int) -> str:
        """Anlatıcıya giden ZORUNLU tehdit bloğu."""
        bant = density_band(density)
        satirlar = [
            "ZOMBİ TEHDİDİ (sunucu zarı — bu blok ZORUNLUDUR, sahnede FİİLEN oynat):",
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

        satirlar.append(
            "- GÜRÜLTÜ KURALI: silah sesi, araç, kırılan kapı, bağırma bölgenin "
            "dikkatini çeker ve bir sonraki turda karşılaşma ihtimalini yükseltir. "
            "Bu turda gürültü çıktıysa state-update'e `threat` altında "
            '`{"noise_add": <10-35>}` yaz; sessiz ilerlendiyse yazma. Bir bölge '
            "temizlendiyse ya da kalabalıklaştıysa "
            '`{"density": {"<yer>": <0-100>}}` ile güncelle.'
        )
        if threat.quiet_turns >= 3:
            satirlar.append(
                f"- {threat.quiet_turns} turdur temas yok: baskı artıyor, sıradaki "
                "sessizlik daha tekinsiz olsun."
            )
        return "\n".join(satirlar)
