<script setup>
/**
 * Hikaye eşyaları — bu oyuna özel, MEKANİĞİ OLMAYAN eşyalar.
 *
 * Katalog eşyalarından (mermi, konserve, sargı) ayrı bir panelde durur ve
 * ayrı durması bilerekdir: bunların açlık doldurma, mermi olma, zar değiştirme
 * gibi bir etkisi yoktur. Değeri hikayededir — bir mektup, mühürlü bir zarf,
 * üstünde isim yazan bir anahtar.
 *
 * Anlatıcı bunları `story_items` ile üretir; sunucu deftere yazar ve her turda
 * anlatıcıya geri verir, böylece on tur önce bulunan zarf unutulmaz.
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import EmptyState from '../ui/EmptyState.vue'
import { colorFor } from '@/utils/characterColors'

const props = defineProps({
  /** world_state.story_items → {ad: {sahip, not, nerede, gun}} */
  esyalar: { type: Object, default: () => ({}) },
  yukleniyor: { type: Boolean, default: false },
})

const liste = computed(() =>
  Object.entries(props.esyalar || {}).map(([ad, bilgi]) => ({
    ad,
    sahip: bilgi?.sahip || '',
    nerede: bilgi?.nerede || '',
    not: bilgi?.not || '',
    gun: bilgi?.gun ?? null,
  })),
)
</script>

<template>
  <div v-if="yukleniyor" class="flex flex-col gap-1.5">
    <span v-for="i in 2" :key="i" class="h-10 rounded-card bg-surface-2 motion-safe:animate-pulse" />
    <span class="sr-only">Hikaye eşyaları yükleniyor…</span>
  </div>

  <EmptyState
    v-else-if="!liste.length"
    compact
    icon="inventory"
    title="Henüz yok"
    text="Hikaye ilerledikçe bu oyuna özel eşyalar burada birikir."
  />

  <ul v-else class="flex flex-col gap-1.5">
    <li
      v-for="esya in liste"
      :key="esya.ad"
      class="rounded-card border border-border bg-surface-2 p-2"
    >
      <div class="flex items-center gap-1.5">
        <Icon name="local_offer" :size="13" class="shrink-0 text-accent" />
        <span class="min-w-0 flex-1 truncate text-meta text-text">{{ esya.ad }}</span>
        <Badge v-if="esya.gun !== null" tone="muted" size="sm">gün {{ esya.gun }}</Badge>
      </div>
      <p v-if="esya.sahip" class="mt-0.5 flex items-center gap-1 text-label">
        <span
          class="size-1.5 shrink-0 rounded-full"
          :style="{ backgroundColor: colorFor(esya.sahip) }"
          aria-hidden="true"
        />
        <span class="text-muted">{{ esya.sahip }}</span>
        <span v-if="esya.nerede" class="text-faint">· {{ esya.nerede }}</span>
      </p>
      <p v-else-if="esya.nerede" class="mt-0.5 text-label text-faint">{{ esya.nerede }}</p>
      <p v-if="esya.not" class="mt-0.5 text-label leading-relaxed text-muted">{{ esya.not }}</p>
    </li>
  </ul>
</template>
