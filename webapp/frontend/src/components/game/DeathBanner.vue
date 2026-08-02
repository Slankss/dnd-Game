<script setup>
/**
 * Ölüm bandı — ölmüş ve yerine HENÜZ kimse geçmemiş her oyuncu karakteri için
 * bir satır. Devralma akışını (TakeoverModal) buradan başlatır.
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import BaseButton from '../ui/BaseButton.vue'
import { colorFor } from '@/utils/characterColors'

const props = defineProps({
  /** Tüm oyuncu karakterleri (world_state.characters) */
  karakterler: { type: Object, default: () => ({}) },
  /** Devralma isteği uçuşta mı */
  mesgul: { type: Boolean, default: false },
})

defineEmits(['devral'])

const bekleyenler = computed(() =>
  Object.entries(props.karakterler || {})
    .filter(([, bilgi]) => bilgi?.alive === false && !bilgi?.replaced_by)
    .map(([ad]) => ad),
)
</script>

<template>
  <section
    v-if="bekleyenler.length"
    class="rounded-panel border border-danger/40 bg-danger-soft px-3 py-2.5"
    aria-label="Devralma bekleyen karakterler"
  >
    <div
      v-for="ad in bekleyenler"
      :key="ad"
      class="flex flex-wrap items-center gap-x-2 gap-y-1.5 py-0.5"
    >
      <Icon name="lucide:skull" :size="18" class="shrink-0 text-danger" label="Ölü karakter" />
      <p class="min-w-0 flex-1 text-meta text-text">
        <span class="font-semibold" :style="{ color: colorFor(ad) }">{{ ad }}</span>
        öldü. Oyuncusu hikayedeki başka bir karakteri devralarak devam edebilir.
      </p>
      <BaseButton
        size="sm"
        variant="danger"
        icon="swap_horiz"
        :disabled="mesgul"
        @click="$emit('devral', ad)"
      >
        Karakter devral
      </BaseButton>
    </div>
  </section>
</template>
