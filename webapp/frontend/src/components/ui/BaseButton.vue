<script setup>
/**
 * Temel düğme.
 *
 *   <BaseButton variant="primary" icon="send" @click="gonder">Gönder</BaseButton>
 *   <BaseButton variant="ghost" icon="settings" aria-label="Ayarlar" icon-only />
 *   <BaseButton :loading="gonderiliyor" loading-text="Anlatıcı düşünüyor…">Gönder</BaseButton>
 *
 * `iconOnly` kullanıldığında `aria-label` ZORUNLUDUR (dev modda uyarır).
 */
import { computed, useAttrs } from 'vue'
import Icon from './Icon.vue'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  /** görsel ağırlık */
  variant: {
    type: String,
    default: 'ghost',
    validator: (v) => ['primary', 'ghost', 'subtle', 'danger', 'gm', 'quiet'].includes(v),
  },
  size: { type: String, default: 'md', validator: (v) => ['sm', 'md', 'lg'].includes(v) },
  /** sol taraftaki Material Symbols adı */
  icon: { type: String, default: '' },
  /** sağ taraftaki Material Symbols adı */
  iconEnd: { type: String, default: '' },
  iconFilled: { type: Boolean, default: false },
  /** yalnızca ikon — kare kutu, aria-label şart */
  iconOnly: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  loadingText: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  block: { type: Boolean, default: false },
  type: { type: String, default: 'button' },
  /** true → aktif/seçili görünüm (sekme, mod seçici) */
  active: { type: Boolean, default: false },
})

const attrs = useAttrs()

if (import.meta.env.DEV) {
  if (props.iconOnly && !attrs['aria-label']) {
    console.warn('[BaseButton] iconOnly düğmelerde aria-label zorunludur:', props.icon)
  }
}

const VARYANT = {
  primary:
    'bg-accent text-[#140a04] hover:bg-accent-strong border border-transparent font-semibold',
  gm: 'bg-gm text-[#0b0713] hover:brightness-110 border border-transparent font-semibold',
  danger: 'bg-danger/15 text-danger hover:bg-danger/25 border border-danger/40',
  ghost: 'bg-surface-2 text-text hover:bg-surface-3 border border-border',
  subtle: 'bg-transparent text-muted hover:text-text hover:bg-surface-2 border border-border',
  quiet: 'bg-transparent text-muted hover:text-text border border-transparent',
}

const OLCU = {
  sm: 'h-7 text-label gap-1.5 rounded-md',
  md: 'h-9 text-meta gap-2 rounded-md',
  lg: 'h-11 text-scene gap-2 rounded-lg',
}

const YATAY = { sm: 'px-2.5', md: 'px-3.5', lg: 'px-5' }
const KARE = { sm: 'w-7', md: 'w-9', lg: 'w-11' }
const IKON_PX = { sm: 16, md: 18, lg: 20 }

const etkisiz = computed(() => props.disabled || props.loading)

const siniflar = computed(() => [
  'inline-flex items-center justify-center select-none whitespace-nowrap',
  'transition-colors duration-[var(--duration-base)] ease-[var(--ease-standard)]',
  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent',
  'disabled:opacity-45 disabled:pointer-events-none',
  OLCU[props.size],
  props.iconOnly ? KARE[props.size] : YATAY[props.size],
  VARYANT[props.variant],
  props.active ? 'ring-1 ring-accent/60 bg-surface-3 text-text' : '',
  props.block ? 'w-full' : '',
])
</script>

<template>
  <button
    :type="type"
    :class="siniflar"
    :disabled="etkisiz"
    :aria-busy="loading ? 'true' : undefined"
    v-bind="attrs"
  >
    <Icon
      v-if="loading"
      name="progress_activity"
      :size="IKON_PX[size]"
      class="motion-safe:animate-spin"
    />
    <Icon
      v-else-if="icon"
      :name="icon"
      :filled="iconFilled"
      :size="IKON_PX[size]"
      :weight="variant === 'primary' || variant === 'gm' ? 600 : 400"
    />
    <span v-if="!iconOnly" class="truncate">
      <template v-if="loading && loadingText">{{ loadingText }}</template>
      <slot v-else />
    </span>
    <Icon v-if="iconEnd && !iconOnly && !loading" :name="iconEnd" :size="IKON_PX[size]" />
  </button>
</template>
