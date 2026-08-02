<script setup>
/**
 * Yükleniyor hali — iskelet satır(lar)ı.
 *
 *   <SkeletonLine :lines="3" />
 *   <SkeletonLine width="40%" height="1.5rem" />
 *
 * `prefers-reduced-motion` açıkken parıltı animasyonu durur (motion-safe).
 */
import { computed } from 'vue'

const props = defineProps({
  /** Kaç satır çizilsin */
  lines: { type: Number, default: 1 },
  /** Tek satır genişliği (CSS değeri). Çok satırda son satır kısaltılır. */
  width: { type: String, default: '100%' },
  height: { type: String, default: '0.875rem' },
  /** Yuvarlaklık */
  rounded: { type: String, default: '0.375rem' },
})

const satirlar = computed(() => Array.from({ length: Math.max(1, props.lines) }, (_, i) => i))
</script>

<template>
  <div class="flex flex-col gap-2" role="status" aria-label="Yükleniyor">
    <div
      v-for="i in satirlar"
      :key="i"
      class="bg-surface-2 motion-safe:animate-pulse"
      :style="{
        width: lines > 1 && i === lines - 1 ? '62%' : width,
        height,
        borderRadius: rounded,
      }"
    />
    <span class="sr-only">Yükleniyor…</span>
  </div>
</template>
