<script setup>
/**
 * Sidebar — masaüstünde sabit sütun, <1024px'te overlay çekmece.
 *
 * Durum `useSidebar()` içinde tutulur (localStorage + Ctrl/Cmd+B).
 * İçerik `SidebarSection` bileşenleriyle doldurulur; oyun ekranlarını
 * yazan ajanlar yalnızca varsayılan yuvayı (slot) doldurur.
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import Tooltip from '../ui/Tooltip.vue'
import { useSidebar } from '@/composables/useSidebar'

const props = defineProps({
  /** 'player' | 'gm' — vurgu rengi */
  variant: { type: String, default: 'player' },
  /** Çekmece başlığı (ekran okuyucu için) */
  label: { type: String, default: 'Yan panel' },
})

const { daraltilmis, mobil, cekmeceAcik, kapat, degistir } = useSidebar()

const genislikSinifi = computed(() =>
  daraltilmis.value ? 'w-[var(--spacing-rail)]' : 'w-[var(--spacing-sidebar)]',
)

const vurguSinifi = computed(() => (props.variant === 'gm' ? 'text-gm' : 'text-accent'))
</script>

<template>
  <!-- Mobil: karartma katmanı -->
  <Transition
    enter-active-class="transition-opacity duration-[var(--duration-slow)] ease-[var(--ease-standard)]"
    leave-active-class="transition-opacity duration-[var(--duration-base)] ease-[var(--ease-standard)]"
    enter-from-class="opacity-0"
    leave-to-class="opacity-0"
  >
    <div
      v-if="mobil && cekmeceAcik"
      class="fixed inset-0 z-40 bg-black/60"
      aria-hidden="true"
      @click="kapat"
    />
  </Transition>

  <aside
    :aria-label="label"
    class="flex shrink-0 flex-col overflow-hidden border-r border-border bg-surface transition-[width,transform] duration-[var(--duration-slow)] ease-[var(--ease-standard)]"
    :class="[
      mobil
        ? [
            'fixed inset-y-0 left-0 z-50 w-[min(20rem,85vw)] shadow-[var(--shadow-float)]',
            cekmeceAcik ? 'translate-x-0' : '-translate-x-full',
          ]
        : ['sticky top-0 h-dvh', genislikSinifi],
    ]"
  >
    <!-- Çekmece başlığı yalnızca mobilde -->
    <div v-if="mobil" class="flex h-[var(--spacing-topbar)] items-center gap-2 border-b border-border px-3">
      <Icon name="menu_open" :size="20" :class="vurguSinifi" />
      <span class="text-panel uppercase tracking-[0.06em] text-muted">{{ label }}</span>
      <button
        type="button"
        class="ml-auto inline-flex size-8 items-center justify-center rounded-md text-muted transition-colors duration-[var(--duration-fast)] hover:bg-surface-2 hover:text-text"
        aria-label="Yan paneli kapat"
        @click="kapat"
      >
        <Icon name="close" :size="18" />
      </button>
    </div>

    <div class="flex-1 overflow-y-auto overscroll-contain">
      <slot :daraltilmis="daraltilmis" />
    </div>

    <!-- Alt: daralt/genişlet düğmesi (masaüstü) -->
    <div v-if="!mobil" class="border-t border-border p-1">
      <Tooltip
        :text="daraltilmis ? 'Yan paneli aç (Ctrl+B)' : 'Yan paneli kapat (Ctrl+B)'"
        placement="right"
        class="w-full"
      >
        <button
          type="button"
          class="flex h-10 w-full items-center gap-2 rounded-md px-2.5 text-muted transition-colors duration-[var(--duration-fast)] hover:bg-surface-2 hover:text-text"
          :aria-label="daraltilmis ? 'Yan paneli aç' : 'Yan paneli kapat'"
          @click="degistir"
        >
          <Icon :name="daraltilmis ? 'left_panel_open' : 'left_panel_close'" :size="20" />
          <span v-if="!daraltilmis" class="text-meta">Paneli kapat</span>
        </button>
      </Tooltip>
    </div>

    <slot name="footer" />
  </aside>
</template>
