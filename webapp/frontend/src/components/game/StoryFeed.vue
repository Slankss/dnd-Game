<script setup>
/**
 * Oyun akışı — EN YENİ EN ÜSTTE (docs §4).
 *
 * Otomatik kaydırma YOK: kullanıcı okurken sayfa altından kaymaz. Yeni içerik
 * geldiğinde üstteki "yeni sahne" rozeti bunu haber verir (rozeti PlayerView
 * çizer, çünkü composer ile aynı sabit şeritte durur).
 *
 * Uzun oturumlarda akış binlerce girdiye çıkabiliyor; varsayılan olarak son
 * 40 girdi çizilir, gerisi "daha eskisini göster" ile açılır.
 *
 * `#en-yeni-altina` slotu, en yeni (ilk) girdinin HEMEN ALTINA içerik enjekte
 * etmek için var — PlayerView bunu "Karar Ver" butonu için kullanır: buton
 * sahnenin altında dursun, seçenek listesi ise akışın içine karışmasın diye
 * ayrı bir popup'ta açılır.
 */
import { ref, computed, watch } from 'vue'
import BaseButton from '../ui/BaseButton.vue'
import EmptyState from '../ui/EmptyState.vue'
import SkeletonLine from '../ui/SkeletonLine.vue'
import StoryEntry from './StoryEntry.vue'

const props = defineProps({
  /** En yeni en üstte sıralanmış log */
  girdiler: { type: Array, default: () => [] },
  /** İlk yükleme sürüyor mu */
  yukleniyor: { type: Boolean, default: false },
  /** Bir tur gönderildi, anlatıcı yazıyor */
  bekleniyor: { type: Boolean, default: false },
})

const ADIM = 40
const gosterilecek = ref(ADIM)

// Yeni tur geldiğinde pencereyi büyütme; kullanıcı nerede kaldıysa orada kalır.
watch(
  () => props.girdiler.length,
  (yeni, eski) => {
    if (yeni < eski) gosterilecek.value = ADIM
  },
)

const gorunen = computed(() => props.girdiler.slice(0, gosterilecek.value))
const kalan = computed(() => Math.max(0, props.girdiler.length - gosterilecek.value))
</script>

<template>
  <section class="flex flex-col gap-3" aria-label="Oyun akışı" aria-live="polite">
    <!-- anlatıcı yazarken en üstte yer tutucu: yeni sahne buraya gelecek -->
    <div
      v-if="bekleniyor"
      class="rounded-panel border border-accent/30 bg-surface px-4 py-3.5"
      role="status"
    >
      <p class="mb-2 flex items-center gap-1.5 text-panel uppercase tracking-[0.06em] text-accent">
        Anlatıcı sahneyi yazıyor
      </p>
      <SkeletonLine :lines="4" />
    </div>

    <!-- yükleniyor -->
    <div v-if="yukleniyor && !girdiler.length" class="flex flex-col gap-3">
      <div v-for="i in 2" :key="i" class="rounded-panel border border-border bg-surface px-4 py-3.5">
        <SkeletonLine :lines="3" />
      </div>
    </div>

    <!-- boş -->
    <EmptyState
      v-else-if="!girdiler.length && !bekleniyor"
      icon="auto_stories"
      title="Sahne henüz açılmadı"
      text="İlk anlatıcı metni geldiğinde burada görünecek. En yeni sahne her zaman en üstte durur."
    />

    <!-- akış: en yeni girdi + hemen altına enjekte edilen içerik (Karar Ver
         butonu gibi), sonra geri kalan geçmiş -->
    <template v-if="gorunen.length">
      <StoryEntry
        :key="gorunen[0].id ?? `${gorunen[0].ts}-0`"
        :girdi="gorunen[0]"
        :ilk="!bekleniyor"
      />
      <slot name="en-yeni-altina" />
      <StoryEntry
        v-for="(girdi, i) in gorunen.slice(1)"
        :key="girdi.id ?? `${girdi.ts}-${i + 1}`"
        :girdi="girdi"
        :ilk="false"
      />
    </template>

    <div v-if="kalan > 0" class="flex justify-center py-1">
      <BaseButton size="sm" variant="subtle" icon="history" @click="gosterilecek += ADIM">
        Daha eskisini göster ({{ kalan }})
      </BaseButton>
    </div>
  </section>
</template>
