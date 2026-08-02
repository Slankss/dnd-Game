<script setup>
/**
 * Kip pencere (modal).
 *
 *   <Modal v-model="acik" title="Okan" icon="person" size="lg">
 *     …içerik…
 *     <template #footer><BaseButton …/></template>
 *   </Modal>
 *
 * ESC ile kapanır, arka plana tıklanınca kapanır (kapatilabilir=false ise
 * kapanmaz), açılırken odak içeri alınır, kapanınca tetikleyiciye döner.
 */
import { ref, watch, nextTick, onUnmounted, useId } from 'vue'
import Icon from './Icon.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  /** Material Symbols adı */
  icon: { type: String, default: '' },
  size: { type: String, default: 'md', validator: (v) => ['sm', 'md', 'lg', 'xl'].includes(v) },
  /** false → ESC ve arka plan tıklaması kapatmaz */
  kapatilabilir: { type: Boolean, default: true },
  /** 'default' | 'gm' — anlatıcı ekranında mor vurgu */
  tone: { type: String, default: 'default' },
})

const emit = defineEmits(['update:modelValue', 'close'])

const OLCU = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
}

const basligKimlik = useId()
const kutu = ref(null)
let oncekiOdak = null

function kapat() {
  if (!props.kapatilabilir) return
  emit('update:modelValue', false)
  emit('close')
}

/** Basit odak tuzağı: Tab döngüsü kutunun içinde kalır. */
function tabDongusu(e) {
  if (e.key !== 'Tab' || !kutu.value) return
  const odaklanabilir = kutu.value.querySelectorAll(
    'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
  )
  if (!odaklanabilir.length) return
  const ilk = odaklanabilir[0]
  const son = odaklanabilir[odaklanabilir.length - 1]
  if (e.shiftKey && document.activeElement === ilk) {
    e.preventDefault()
    son.focus()
  } else if (!e.shiftKey && document.activeElement === son) {
    e.preventDefault()
    ilk.focus()
  }
}

function tusla(e) {
  if (e.key === 'Escape') {
    e.stopPropagation()
    kapat()
    return
  }
  tabDongusu(e)
}

watch(
  () => props.modelValue,
  async (acik) => {
    if (typeof document === 'undefined') return
    if (acik) {
      oncekiOdak = document.activeElement
      document.body.style.overflow = 'hidden'
      await nextTick()
      kutu.value?.focus()
    } else {
      document.body.style.overflow = ''
      oncekiOdak?.focus?.()
      oncekiOdak = null
    }
  },
)

onUnmounted(() => {
  if (typeof document !== 'undefined') document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-[var(--duration-slow)] ease-[var(--ease-standard)]"
      leave-active-class="transition-opacity duration-[var(--duration-base)] ease-[var(--ease-standard)]"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="modelValue"
        class="fixed inset-0 z-100 flex items-start justify-center overflow-y-auto bg-black/70 p-4 py-[8vh] backdrop-blur-[2px]"
        @mousedown.self="kapat"
      >
        <div
          ref="kutu"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="title ? basligKimlik : undefined"
          tabindex="-1"
          class="w-full rounded-panel border bg-surface shadow-[var(--shadow-float)] outline-none"
          :class="[OLCU[size], tone === 'gm' ? 'border-gm/40' : 'border-border']"
          @keydown="tusla"
        >
          <header
            v-if="title || $slots.header"
            class="flex items-center gap-2 border-b border-border px-4 py-3"
          >
            <Icon v-if="icon" :name="icon" :size="18" :class="tone === 'gm' ? 'text-gm' : 'text-accent'" />
            <slot name="header">
              <h2 :id="basligKimlik" class="text-card">{{ title }}</h2>
            </slot>
            <button
              v-if="kapatilabilir"
              type="button"
              class="ml-auto inline-flex size-8 items-center justify-center rounded-md text-muted transition-colors duration-[var(--duration-fast)] hover:bg-surface-2 hover:text-text"
              aria-label="Kapat"
              @click="kapat"
            >
              <Icon name="close" :size="18" />
            </button>
          </header>

          <div class="px-4 py-4">
            <slot />
          </div>

          <footer
            v-if="$slots.footer"
            class="flex items-center justify-end gap-2 border-t border-border px-4 py-3"
          >
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
