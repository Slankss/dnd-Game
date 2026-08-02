<script setup>
/**
 * Panel — başlıklı içerik kutusu.
 *
 *   <Panel title="Kaynaklar" icon="inventory_2" collapsible>
 *     <template #actions><BaseButton size="sm" …/></template>
 *     …içerik…
 *   </Panel>
 *
 * Panel başlığı 12px/600/uppercase/tracking-wide (docs §2).
 */
import { ref, computed } from 'vue'
import Icon from './Icon.vue'
import Badge from './Badge.vue'

const props = defineProps({
  title: { type: String, default: '' },
  /** Material Symbols adı */
  icon: { type: String, default: '' },
  /** Başlığın sağında küçük sayaç/rozet metni */
  count: { type: [String, Number], default: null },
  collapsible: { type: Boolean, default: false },
  /** Açılır panelin başlangıç hali */
  defaultOpen: { type: Boolean, default: true },
  /** 'default' | 'gm' | 'danger' — kenar vurgusu */
  tone: { type: String, default: 'default' },
  /** İç boşluğu kaldır (liste/tablo doğrudan otursun) */
  flush: { type: Boolean, default: false },
})

const emit = defineEmits(['toggle'])

const acik = ref(props.defaultOpen)

function degistir() {
  if (!props.collapsible) return
  acik.value = !acik.value
  emit('toggle', acik.value)
}

const TON = {
  default: 'border-border',
  gm: 'border-gm/30',
  danger: 'border-danger/35',
}

const govdeSinifi = computed(() => (props.flush ? '' : 'px-3 pb-3 pt-0.5'))

defineExpose({ acik })
</script>

<template>
  <section
    class="rounded-panel border bg-surface shadow-[var(--shadow-panel)]"
    :class="TON[tone] || TON.default"
  >
    <component
      :is="collapsible ? 'button' : 'div'"
      v-if="title || $slots.header || $slots.actions"
      :type="collapsible ? 'button' : undefined"
      :aria-expanded="collapsible ? String(acik) : undefined"
      class="flex w-full items-center gap-2 px-3 py-2.5 text-left"
      :class="
        collapsible
          ? 'cursor-pointer rounded-t-panel transition-colors duration-[var(--duration-fast)] hover:bg-surface-2'
          : ''
      "
      @click="degistir"
    >
      <Icon v-if="icon" :name="icon" :size="16" class="text-muted" />
      <slot name="header">
        <h2 class="text-panel uppercase tracking-[0.06em] text-muted">{{ title }}</h2>
      </slot>
      <Badge v-if="count !== null" size="sm" tone="muted">{{ count }}</Badge>
      <span class="ml-auto flex items-center gap-1" @click.stop>
        <slot name="actions" />
      </span>
      <Icon
        v-if="collapsible"
        name="keyboard_arrow_down"
        :size="18"
        class="text-faint transition-transform duration-[var(--duration-base)] ease-[var(--ease-standard)]"
        :class="acik ? '' : '-rotate-90'"
      />
    </component>

    <div v-show="acik" :class="govdeSinifi">
      <slot />
    </div>

    <div v-if="$slots.footer && acik" class="border-t border-border px-3 py-2">
      <slot name="footer" />
    </div>
  </section>
</template>
