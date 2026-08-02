<script setup>
/**
 * Basit ipucu balonu — hover ve klavye odağıyla açılır.
 *
 *   <Tooltip text="Kadro" placement="right">
 *     <BaseButton icon="groups" icon-only aria-label="Kadro" />
 *   </Tooltip>
 *
 * Not: kapalı sidebar'daki ikon şeridi bunu kullanır. Balon `aria-hidden`
 * değildir; tetikleyiciye `aria-describedby` ile bağlanır — ama ikon
 * düğmesinin kendi `aria-label`'ı yine de zorunludur.
 */
import { ref, computed, useId } from 'vue'

const props = defineProps({
  text: { type: String, required: true },
  placement: {
    type: String,
    default: 'right',
    validator: (v) => ['top', 'right', 'bottom', 'left'].includes(v),
  },
  /** ms — çok hızlı açılıp göz yormasın */
  delay: { type: Number, default: 220 },
  disabled: { type: Boolean, default: false },
})

const kimlik = useId()
const acik = ref(false)
let zamanlayici = null

function ac() {
  if (props.disabled) return
  clearTimeout(zamanlayici)
  zamanlayici = setTimeout(() => (acik.value = true), props.delay)
}

function kapat() {
  clearTimeout(zamanlayici)
  acik.value = false
}

const KONUM = {
  top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
  bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
  left: 'right-full top-1/2 -translate-y-1/2 mr-2',
  right: 'left-full top-1/2 -translate-y-1/2 ml-2',
}

const siniflar = computed(() => [
  'pointer-events-none absolute z-50 whitespace-nowrap rounded-md border border-border',
  'bg-surface-3 px-2 py-1 text-label text-text shadow-[var(--shadow-float)]',
  KONUM[props.placement],
])
</script>

<template>
  <span
    class="relative inline-flex"
    @mouseenter="ac"
    @mouseleave="kapat"
    @focusin="ac"
    @focusout="kapat"
    @keydown.escape="kapat"
  >
    <slot :describedby="kimlik" />
    <Transition
      enter-active-class="transition-opacity duration-[var(--duration-fast)] ease-[var(--ease-standard)]"
      leave-active-class="transition-opacity duration-[var(--duration-fast)] ease-[var(--ease-standard)]"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <span v-if="acik && !disabled" :id="kimlik" role="tooltip" :class="siniflar">
        {{ text }}
      </span>
    </Transition>
  </span>
</template>
