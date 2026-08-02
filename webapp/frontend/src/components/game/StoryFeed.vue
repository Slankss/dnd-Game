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

    <!-- akış -->
    <StoryEntry
      v-for="(girdi, i) in gorunen"
      :key="girdi.id ?? `${girdi.ts}-${i}`"
      :girdi="girdi"
      :ilk="i === 0 && !bekleniyor"
    />

    <div v-if="kalan > 0" class="flex justify-center py-1">
      <BaseButton size="sm" variant="subtle" icon="history" @click="gosterilecek += ADIM">
        Daha eskisini göster ({{ kalan }})
      </BaseButton>
    </div>
  </section>
</template>
