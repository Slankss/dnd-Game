<script setup>
/**
 * Hayatta kalma göstergeleri — yorgunluk / açlık / susuzluk / stres.
 * 0 = gayet iyi, 100 = dayanılmaz; renk YALNIZCA durum bildirir (docs §3).
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import { VITAL_ALANLARI, olcuyeAl, vitalTonu } from './gameFormat'

const props = defineProps({
  vitals: { type: Object, default: null },
})

const TON_CUBUK = { ok: 'bg-ok', warn: 'bg-warn', danger: 'bg-danger' }
const TON_METIN = { ok: 'text-muted', warn: 'text-warn', danger: 'text-danger' }

const satirlar = computed(() =>
  VITAL_ALANLARI.map((alan) => {
    const deger = olcuyeAl(props.vitals?.[alan.anahtar])
    return { ...alan, deger, ton: vitalTonu(deger) }
  }),
)

const altSatir = computed(() => {
  if (!props.vitals) return ''
  const parcalar = []
  const uyanik = props.vitals.awake_hours
  if (uyanik !== null && uyanik !== undefined && uyanik !== '') {
    parcalar.push(`${uyanik} saattir uyanık`)
  }
  if (props.vitals.condition) parcalar.push(props.vitals.condition)
  return parcalar.join(' · ')
})
</script>

<template>
  <p v-if="!vitals" class="text-meta text-faint">Bu karakter için gösterge tutulmuyor.</p>
  <div v-else class="flex flex-col gap-1.5">
    <div v-for="satir in satirlar" :key="satir.anahtar" class="flex items-center gap-2">
      <Icon :name="satir.ikon" :size="14" class="shrink-0 text-faint" />
      <span class="w-20 shrink-0 text-label text-muted">{{ satir.etiket }}</span>
      <span
        class="h-1.5 min-w-0 flex-1 overflow-hidden rounded-chip bg-surface-3"
        role="meter"
        :aria-valuenow="satir.deger"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-label="`${satir.etiket}: ${satir.deger}`"
      >
        <span
          class="block h-full rounded-chip transition-[width] duration-[var(--duration-slow)] ease-[var(--ease-standard)]"
          :class="TON_CUBUK[satir.ton]"
          :style="{ width: `${satir.deger}%` }"
        />
      </span>
      <span class="w-7 shrink-0 text-right text-label nums-tabular" :class="TON_METIN[satir.ton]">
        {{ satir.deger }}
      </span>
    </div>
    <p v-if="altSatir" class="text-label text-faint">{{ altSatir }}</p>
  </div>
</template>
