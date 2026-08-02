<script setup>
/**
 * Tanışılan NPC'ler. Kadro kartıyla aynı bileşeni kullanır, rengi nötrdür —
 * kalabalık bir sahnede kimin oyuncu kimin NPC olduğu karışmasın.
 */
import { computed } from 'vue'
import EmptyState from '../ui/EmptyState.vue'
import CharacterCard from './CharacterCard.vue'

const props = defineProps({
  npcler: { type: Object, default: () => ({}) },
  yukleniyor: { type: Boolean, default: false },
})

defineEmits(['ac'])

const liste = computed(() => Object.entries(props.npcler || {}))
</script>

<template>
  <div v-if="yukleniyor" class="flex flex-col gap-1.5 py-1">
    <span v-for="i in 2" :key="i" class="h-16 rounded-card bg-surface-2 motion-safe:animate-pulse" />
    <span class="sr-only">NPC'ler yükleniyor…</span>
  </div>

  <EmptyState
    v-else-if="!liste.length"
    compact
    icon="person"
    title="Henüz kimseyle tanışılmadı"
    text="Grup birine rastladığında o kişi burada listelenir; ölen bir karakterin oyuncusu buradan devralabilir."
  />

  <div v-else class="flex flex-col gap-2">
    <CharacterCard
      v-for="[ad, bilgi] in liste"
      :key="ad"
      :ad="ad"
      :bilgi="bilgi"
      npc
      @ac="$emit('ac', ad)"
    />
  </div>
</template>
