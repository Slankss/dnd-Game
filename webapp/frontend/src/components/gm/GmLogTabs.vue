<script setup>
/**
 * Kayıtlar — oyun günlüğü ile anlatıcı defteri sekmeli.
 *
 * İKİSİ DE EN YENİ EN ÜSTTE (docs §4). Otomatik kaydırma yok: anlatıcı
 * okurken liste ayağının altından kaymasın.
 */
import { ref, computed, useId } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import GmLogList from './GmLogList.vue'

const props = defineProps({
  /** Oyun günlüğü — en yeni en üstte */
  log: { type: Array, default: () => [] },
  /** Anlatıcı notları — en yeni en üstte */
  gmLog: { type: Array, default: () => [] },
})

const kimlik = useId()
const aktif = ref('oyun')

const SEKMELER = computed(() => [
  { ad: 'oyun', baslik: 'Oyun günlüğü', ikon: 'forum', sayi: props.log.length },
  { ad: 'not', baslik: 'Anlatıcı defteri', ikon: 'visibility_off', sayi: props.gmLog.length },
])

const girdiler = computed(() => (aktif.value === 'oyun' ? props.log : props.gmLog))
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex flex-wrap items-center gap-2">
      <div role="tablist" aria-label="Kayıt türü" class="flex gap-1">
        <button
          v-for="s in SEKMELER"
          :id="`${kimlik}-${s.ad}-tab`"
          :key="s.ad"
          type="button"
          role="tab"
          :aria-selected="aktif === s.ad"
          :aria-controls="`${kimlik}-${s.ad}-panel`"
          class="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-meta transition-colors duration-[var(--duration-base)] ease-[var(--ease-standard)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gm"
          :class="
            aktif === s.ad
              ? 'border-gm bg-gm-soft text-text'
              : 'border-border bg-surface-2 text-muted hover:bg-surface-3 hover:text-text'
          "
          @click="aktif = s.ad"
        >
          <Icon :name="s.ikon" :size="15" />
          {{ s.baslik }}
          <Badge size="sm" tone="muted">{{ s.sayi }}</Badge>
        </button>
      </div>
      <span class="ml-auto flex items-center gap-1 text-label text-faint">
        <Icon name="arrow_upward" :size="13" />
        en yeni en üstte
      </span>
    </div>

    <p v-if="aktif === 'oyun'" class="text-label text-faint">
      Oyuncuların canlı turları — sunucu son 40 girdiyi gönderir.
    </p>
    <p v-else class="text-label text-faint">
      Gönderdiğin notlar ve anlatıcının yanıtları. Yayınlanan sahneler ayrıca oyun
      günlüğünde de görünür.
    </p>

    <div
      :id="`${kimlik}-${aktif}-panel`"
      role="tabpanel"
      :aria-labelledby="`${kimlik}-${aktif}-tab`"
      tabindex="0"
      class="max-h-[32rem] overflow-y-auto overscroll-contain focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gm"
    >
      <GmLogList :entries="girdiler" :tur="aktif" />
    </div>
  </div>
</template>
