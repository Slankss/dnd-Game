"""Senarist katmanının çalışan yarısı: planı turun içine sokar.

Plan (`data/plot.json`) koşullu olaylardan (beat) oluşur. Bu servis her turda
üç şey yapar:

  1. vadesi geçmiş beat'leri çürütür,
  2. koşulu SAĞLANAN bekleyen beat'lerden **bir tanesini** seçer,
  3. tur bittikten sonra onu `fired` işaretler ve `on_fire` etkisini uygular.

Kararı kod verir, model değil: `when` koşulu `models.conditions.matches` ile
çözülür. Tur başına tek beat — üç direktif aynı sahneye girerse sahne okunmaz
hale gelir ve oyuncu ne yaparsa yapsın aynı yere çıkar.

Plan oyuncuya asla gösterilmez; yalnızca anlatıcı ekranı görür.
"""

from app.models.plot import Plot
from app.repositories.plot_repo import PlotRepository


class DirectorService:
    def __init__(self, plot_repo=None):
        self.plot_repo = plot_repo or PlotRepository()

    def load(self) -> Plot:
        return self.plot_repo.load()

    def take_due(self, world, world_entry=None):
        """Bu turda ateşlenecek beat'i seçer.

        Dönen: (beat, plot, olaylar). `beat` None olabilir. `olaylar`, anlatıcı
        günlüğüne düşecek kısa notlardır (çürüyen beat'ler sessizce kaybolmasın).
        Seçim diske YAZMAZ — ateşlemenin kesinleşmesi için `mark_fired`
        çağrılmalı; ama çürümeler burada kaydedilir, çünkü tur başarısız olsa
        bile vade geçmiştir.
        """
        plot = self.load()
        if not plot.beats:
            return None, plot, []

        day = world.day if isinstance(world.day, int) else None
        olaylar = []
        vade_yazilan = plot.ensure_expiry(day)
        curuyen = plot.expire(day)
        if vade_yazilan or curuyen:
            self.plot_repo.save(plot)
        for beat_id in curuyen:
            olaylar.append(f"plan: '{beat_id}' vadesi doldu, çürüdü")

        ctx = world.build_context(world_entry)
        due = plot.due_beats(ctx)
        if not due:
            return None, plot, olaylar
        return due[0], plot, olaylar

    def mark_fired(self, beat, plot, world) -> str:
        """Tur bittikten sonra: beat ateşlendi say, `on_fire` etkisini uygula.

        Şu an desteklenen tek etki `flags` — beat'in kendi tekrarını
        engellemesi (`flags_unset` ile) ve sonraki beat'lerin ona dayanması
        için yeterli.
        """
        day = world.day if isinstance(world.day, int) else None
        plot.fire(beat, day)

        etkiler = beat.on_fire if isinstance(beat.on_fire, dict) else {}
        bayraklar = etkiler.get("flags")
        if isinstance(bayraklar, dict):
            hedef = world.ensure_flags()
            for ad, deger in bayraklar.items():
                if isinstance(ad, str):
                    hedef[ad] = deger
        self.plot_repo.save(plot)
        return f"plan: '{beat.id}' ateşlendi (gün {day})"
