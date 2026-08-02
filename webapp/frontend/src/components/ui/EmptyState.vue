<script setup>
/**
 * Boş hal — "üç halden biri" (yükleniyor / hata / boş, docs §7).
 *
 *   <EmptyState icon="groups" title="Kadro yok" text="Karakter kurulumu bekleniyor." />
 *   <EmptyState tone="danger" icon="wifi_off" title="Sunucuya bağlanılamadı">
 *     <template #action><BaseButton icon="refresh" @click="yenile">Tekrar dene</BaseButton></template>
 *   </EmptyState>
 */
import Icon from './Icon.vue'

defineProps({
  /** Material Symbols adı */
  icon: { type: String, default: 'inbox' },
  title: { type: String, default: '' },
  text: { type: String, default: '' },
  tone: {
    type: String,
    default: 'muted',
    validator: (v) => ['muted', 'danger', 'warn', 'accent'].includes(v),
  },
  /** Dar alanlarda (sidebar bölümleri) kullanılan sıkışık varyant */
  compact: { type: Boolean, default: false },
})

const TON = {
  muted: 'text-faint',
  danger: 'text-danger',
  warn: 'text-warn',
  accent: 'text-accent',
}
</script>

<template>
  <div
    class="flex flex-col items-center justify-center text-center"
    :class="compact ? 'gap-1 px-2 py-4' : 'gap-2 px-4 py-8'"
  >
    <Icon :name="icon" :size="compact ? 20 : 28" :class="TON[tone]" />
    <p v-if="title" class="text-card text-text">{{ title }}</p>
    <p v-if="text" class="text-meta text-muted">{{ text }}</p>
    <slot />
    <div v-if="$slots.action" class="mt-2">
      <slot name="action" />
    </div>
  </div>
</template>
