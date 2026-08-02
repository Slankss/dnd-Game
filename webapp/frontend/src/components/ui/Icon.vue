<script setup>
/**
 * Tek ikon bileşeni — Material Symbols Rounded (yerel variable font).
 *
 * Kullanım:
 *   <Icon name="casino" />                            → dekoratif (aria-hidden)
 *   <Icon name="favorite" filled :size="18" />         → dolu, 18px
 *   <Icon name="crisis_alert" :weight="600" class="text-danger" />
 *   <Icon name="lock" label="Kilitli" />               → anlamlı ikon, ekran okuyucuya görünür
 *   <Icon name="lucide:swords" />                      → Lucide yedeği
 *
 * Kural: ikon tek başına bilgi taşıyorsa `label` ver; bir metnin yanında
 * süsse hiçbir şey verme (varsayılan aria-hidden="true").
 */
import { computed } from 'vue'
import { lucideBul } from './lucideIcons'

const props = defineProps({
  /** Material Symbols ligatür adı ('casino') veya 'lucide:swords' */
  name: { type: String, required: true },
  /** Dolu varyant (FILL ekseni) */
  filled: { type: Boolean, default: false },
  /** 100-700 arası ağırlık (wght ekseni) */
  weight: { type: Number, default: 400 },
  /** -25..200 arası derece (GRAD ekseni) — koyu zeminde 0 iyi çalışır */
  grade: { type: Number, default: 0 },
  /** px cinsinden kutu boyutu; 'sm'|'md'|'lg' kısayolları da kabul edilir */
  size: { type: [Number, String], default: 20 },
  /** Verilirse ikon ekran okuyucuya `role="img"` + bu etiketle görünür */
  label: { type: String, default: '' },
})

const OLCU = { xs: 16, sm: 18, md: 20, lg: 24, xl: 32 }

const px = computed(() => {
  if (typeof props.size === 'number') return props.size
  return OLCU[props.size] ?? Number(props.size) ?? 20
})

const lucide = computed(() => (props.name.startsWith('lucide:') ? lucideBul(props.name) : null))

const anlamli = computed(() => props.label.length > 0)

const stil = computed(() => ({
  fontSize: `${px.value}px`,
  width: `${px.value}px`,
  height: `${px.value}px`,
  // Material Symbols değişken eksenleri
  fontVariationSettings: `'FILL' ${props.filled ? 1 : 0}, 'wght' ${props.weight}, 'GRAD' ${props.grade}, 'opsz' ${px.value}`,
}))

const erisimOznitelikleri = computed(() =>
  anlamli.value
    ? { role: 'img', 'aria-label': props.label }
    : { 'aria-hidden': 'true', focusable: 'false' },
)
</script>

<template>
  <component
    :is="lucide"
    v-if="lucide"
    :size="px"
    :stroke-width="weight >= 600 ? 2.4 : 1.9"
    class="inline-block shrink-0 align-[-0.15em]"
    v-bind="erisimOznitelikleri"
  />
  <span
    v-else
    class="ms-icon inline-flex shrink-0 items-center justify-center overflow-hidden align-[-0.15em]"
    :style="stil"
    v-bind="erisimOznitelikleri"
    >{{ name }}</span
  >
</template>
