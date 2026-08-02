<script setup>
/**
 * Rozet / çip — 11px, 500 ağırlık (docs §2).
 *
 *   <Badge tone="danger" icon="crisis_alert">kritik</Badge>
 *   <Badge tone="ok" dot>hayatta</Badge>
 *   <Badge :color="colorFor(ad)">{{ ad }}</Badge>   ← karakter rengi
 *
 * Severity renkleri YALNIZCA durum bildirir: düşük=ok, orta=warn, yüksek=danger.
 */
import { computed } from 'vue'
import Icon from './Icon.vue'

const props = defineProps({
  tone: {
    type: String,
    default: 'neutral',
    validator: (v) => ['neutral', 'ok', 'warn', 'danger', 'accent', 'gm', 'muted'].includes(v),
  },
  /** Material Symbols adı */
  icon: { type: String, default: '' },
  iconFilled: { type: Boolean, default: false },
  /** Renk noktası göster */
  dot: { type: Boolean, default: false },
  /** Serbest renk (karakter rengi gibi) — tone'u geçersiz kılar */
  color: { type: String, default: '' },
  size: { type: String, default: 'md', validator: (v) => ['sm', 'md'].includes(v) },
  /** İçi dolu (opak) varyant */
  solid: { type: Boolean, default: false },
})

const TON = {
  neutral: 'bg-surface-2 text-text border-border',
  muted: 'bg-transparent text-muted border-border',
  ok: 'bg-ok-soft text-ok border-ok/35',
  warn: 'bg-warn-soft text-warn border-warn/35',
  danger: 'bg-danger-soft text-danger border-danger/35',
  accent: 'bg-accent-soft text-accent border-accent/35',
  gm: 'bg-gm-soft text-gm border-gm/35',
}

const TON_SOLID = {
  neutral: 'bg-surface-3 text-text border-transparent',
  muted: 'bg-surface-2 text-muted border-transparent',
  ok: 'bg-ok text-[#06140c] border-transparent',
  warn: 'bg-warn text-[#1a1204] border-transparent',
  danger: 'bg-danger text-[#180404] border-transparent',
  accent: 'bg-accent text-[#140a04] border-transparent',
  gm: 'bg-gm text-[#0b0713] border-transparent',
}

const ozelStil = computed(() =>
  props.color
    ? {
        color: props.color,
        borderColor: `color-mix(in oklab, ${props.color} 45%, transparent)`,
        backgroundColor: `color-mix(in oklab, ${props.color} 14%, transparent)`,
      }
    : undefined,
)

const siniflar = computed(() => [
  'inline-flex items-center gap-1 rounded-chip border font-medium leading-none',
  props.size === 'sm' ? 'h-5 px-1.5 text-[0.625rem]' : 'h-6 px-2 text-label',
  props.color ? '' : props.solid ? TON_SOLID[props.tone] : TON[props.tone],
])
</script>

<template>
  <span :class="siniflar" :style="ozelStil">
    <span
      v-if="dot"
      class="size-1.5 shrink-0 rounded-full bg-current"
      aria-hidden="true"
    />
    <Icon v-if="icon" :name="icon" :filled="iconFilled" :size="size === 'sm' ? 12 : 14" />
    <slot />
  </span>
</template>
