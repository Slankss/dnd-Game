<script setup>
/**
 * Sidebar bölümü — sidebar açıkken başlık + içerik, kapalıyken yalnızca
 * ikon (tooltip'li). Kapalı şeritte ikona tıklanınca sidebar açılır ve
 * bölüm görünür olur.
 *
 *   <SidebarSection title="Kadro" icon="groups" :count="4">
 *     <CharacterCard v-for="…" />
 *   </SidebarSection>
 */
import { ref, computed } from 'vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import Tooltip from '../ui/Tooltip.vue'
import { useSidebar } from '@/composables/useSidebar'

const props = defineProps({
  title: { type: String, required: true },
  /** Material Symbols adı — kapalı şeritte bölümü bu temsil eder */
  icon: { type: String, required: true },
  /** Başlık yanında küçük sayaç */
  count: { type: [String, Number], default: null },
  collapsible: { type: Boolean, default: true },
  defaultOpen: { type: Boolean, default: true },
  /** Dikkat çekmesi gereken bölüm (örn. yeni zorluk) */
  vurgu: { type: Boolean, default: false },
})

const { daraltilmis, ac } = useSidebar()

// Açık/kapalı hali dışarıdan da sürülebilir: `v-model:acik`. Bağlanmazsa
// bileşen kendi yerel durumunu tutar (envanter raporu gelince paneli dışarıdan
// açabilmek için gerekiyordu — bunun için bileşeni `:key` ile yeniden kurmak
// zorunda kalınıyordu).
const acik = defineModel('acik', { type: Boolean, default: undefined })
if (acik.value === undefined) acik.value = props.defaultOpen

const gosterilecekIcerik = computed(() => !daraltilmis.value && acik.value)

function basligaTikla() {
  if (daraltilmis.value) {
    ac() // kapalı şeritte ikona tıklamak sidebar'ı açar
    acik.value = true
    return
  }
  if (props.collapsible) acik.value = !acik.value
}
</script>

<template>
  <section class="border-b border-border/70 last:border-b-0">
    <!-- Kapalı şerit: sadece ikon + tooltip -->
    <Tooltip v-if="daraltilmis" :text="title" placement="right" class="w-full">
      <button
        type="button"
        class="relative flex h-12 w-12 items-center justify-center text-muted transition-colors duration-[var(--duration-fast)] hover:bg-surface-2 hover:text-text"
        :aria-label="title"
        @click="basligaTikla"
      >
        <Icon :name="icon" :size="20" />
        <span
          v-if="vurgu"
          class="absolute right-2.5 top-2.5 size-1.5 rounded-full bg-accent"
          aria-hidden="true"
        />
      </button>
    </Tooltip>

    <!-- Açık sidebar: başlık + içerik -->
    <template v-else>
      <component
        :is="collapsible ? 'button' : 'div'"
        :type="collapsible ? 'button' : undefined"
        :aria-expanded="collapsible ? String(acik) : undefined"
        class="flex w-full items-center gap-2 px-3 py-2.5 text-left transition-colors duration-[var(--duration-fast)]"
        :class="collapsible ? 'hover:bg-surface-2' : ''"
        @click="basligaTikla"
      >
        <Icon :name="icon" :size="16" class="text-faint" />
        <h2 class="text-panel uppercase tracking-[0.06em] text-muted">{{ title }}</h2>
        <Badge v-if="count !== null" size="sm" tone="muted" class="ml-0.5">{{ count }}</Badge>
        <span class="ml-auto flex items-center gap-1" @click.stop>
          <slot name="actions" />
        </span>
        <Icon
          v-if="collapsible"
          name="keyboard_arrow_down"
          :size="16"
          class="text-faint transition-transform duration-[var(--duration-base)] ease-[var(--ease-standard)]"
          :class="acik ? '' : '-rotate-90'"
        />
      </component>

      <div v-show="gosterilecekIcerik" class="flex flex-col gap-2 px-3 pb-3">
        <slot />
      </div>
    </template>
  </section>
</template>
