<script setup>
/**
 * Akıştaki tek girdi — üç varyant (docs §6):
 *   - oyuncu turu   : isim + karakter rengi + zar sonucu/bandı
 *   - anlatıcı sahnesi : asıl okuma alanı (SceneText)
 *   - sistem/devralma : ince, nötr bilgi şeridi
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import SceneText from './SceneText.vue'
import { colorForEntry, bashHarf } from '@/utils/characterColors'
import { emojiTemizle, saatMetni, zarTonu } from './gameFormat'

const props = defineProps({
  /** Sunucudan gelen log girdisi */
  girdi: { type: Object, required: true },
  /** Akışın en üstündeki girdi mi (yeni sahne vurgusu için) */
  ilk: { type: Boolean, default: false },
})

const tur = computed(() => {
  if (props.girdi.role === 'user') return 'oyuncu'
  if (props.girdi.role === 'system') return 'sistem'
  return 'anlatici'
})

const renk = computed(() => colorForEntry(props.girdi))

const baslik = computed(() => {
  if (tur.value === 'oyuncu') return props.girdi.player || 'Oyuncu'
  if (tur.value === 'sistem') return 'Sistem'
  if (props.girdi.kind === 'opening') return 'Anlatıcı · açılış'
  if (props.girdi.kind === 'takeover') return 'Anlatıcı · devralma'
  return 'Anlatıcı'
})

const saat = computed(() => saatMetni(props.girdi.ts))

/** Sistem girdileri sunucuda emojiyle yazılıyor; arayüzde emoji yok (docs §5). */
const sistemMetni = computed(() => emojiTemizle(props.girdi.text))

const zarVar = computed(() => props.girdi.roll !== null && props.girdi.roll !== undefined)

const renkDegiskenleri = computed(() => ({
  '--kr': renk.value,
  '--kr-soft': `color-mix(in oklab, ${renk.value} 14%, transparent)`,
}))
</script>

<template>
  <!-- ---------------------------------------------------------- sistem -->
  <article
    v-if="tur === 'sistem'"
    class="flex items-start gap-2 rounded-panel border border-border/70 bg-surface/60 px-3 py-2.5"
  >
    <Icon name="info" :size="16" class="mt-0.5 shrink-0 text-faint" label="Sistem bildirimi" />
    <div class="min-w-0">
      <p class="measure-scene text-meta text-muted">{{ sistemMetni }}</p>
      <p v-if="saat" class="mt-0.5 text-label text-faint nums-tabular">{{ saat }}</p>
    </div>
  </article>

  <!-- ---------------------------------------------------------- oyuncu -->
  <article
    v-else-if="tur === 'oyuncu'"
    class="rounded-panel border border-border bg-surface-2/60 px-3 py-2.5"
    :style="renkDegiskenleri"
  >
    <header class="mb-1.5 flex flex-wrap items-center gap-2">
      <span
        class="inline-flex size-6 shrink-0 items-center justify-center rounded-chip border text-label font-semibold"
        :style="{
          color: renk,
          borderColor: `color-mix(in oklab, ${renk} 45%, transparent)`,
          backgroundColor: 'var(--kr-soft)',
        }"
        aria-hidden="true"
        >{{ bashHarf(girdi.player) }}</span
      >
      <span class="text-card" :style="{ color: renk }">{{ baslik }}</span>

      <Badge v-if="girdi.is_group" tone="muted" icon="groups" size="sm">ortak karar</Badge>

      <Badge v-if="zarVar" :tone="zarTonu(girdi.band)" icon="casino" size="sm">
        <span class="nums-tabular">{{ girdi.roll }}</span>
        <span aria-hidden="true">·</span>
        {{ girdi.band }}
      </Badge>
      <Badge v-else tone="muted" icon="badge" size="sm">künye turu — zar yok</Badge>

      <span v-if="saat" class="ml-auto text-label text-faint nums-tabular">{{ saat }}</span>
    </header>
    <p class="measure-scene whitespace-pre-line text-meta text-text">{{ girdi.text }}</p>
  </article>

  <!-- -------------------------------------------------------- anlatıcı -->
  <article
    v-else
    class="rounded-panel border bg-surface px-4 py-3.5 shadow-[var(--shadow-panel)]"
    :class="ilk ? 'border-accent/35' : 'border-border'"
  >
    <header class="mb-2 flex flex-wrap items-center gap-2">
      <Icon name="auto_stories" :size="16" class="text-accent" />
      <span class="text-card text-accent">{{ baslik }}</span>
      <Badge v-if="girdi.tension" :tone="girdi.tension === 'yüksek' ? 'danger' : 'muted'" size="sm">
        gerilim: {{ girdi.tension }}
      </Badge>
      <span v-if="saat" class="ml-auto text-label text-faint nums-tabular">{{ saat }}</span>
    </header>
    <SceneText :metin="girdi.text" />
  </article>
</template>
