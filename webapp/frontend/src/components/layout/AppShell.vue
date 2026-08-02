<script setup>
/**
 * Uygulama kabuğu — üst bar + sidebar + ana alan.
 *
 *   <AppShell variant="player" :connection="store.baglantiDurumu">
 *     <template #topbar-center> …dünya künyesi… </template>
 *     <template #topbar-actions> …düğmeler… </template>
 *     <template #sidebar> <SidebarSection …/> </template>
 *     …ana içerik…
 *   </AppShell>
 *
 * Ctrl/Cmd+B kısayolu burada kurulur (docs §7).
 */
import TopBar from './TopBar.vue'
import SideBar from './SideBar.vue'
import { useSidebar } from '@/composables/useSidebar'
import { useKeyboard } from '@/composables/useKeyboard'

defineProps({
  /** 'player' | 'gm' — vurgu rengi ve etiketler */
  variant: { type: String, default: 'player' },
  title: { type: String, default: 'Kızıl Çöküş' },
  sidebarLabel: { type: String, default: 'Yan panel' },
  /** 'bagli' | 'yavas' | 'kopuk' */
  connection: { type: String, default: 'bagli' },
})

const { degistir } = useSidebar()

useKeyboard({ 'mod+b': degistir })
</script>

<template>
  <div class="flex min-h-dvh w-full bg-bg text-text">
    <SideBar :variant="variant" :label="sidebarLabel">
      <template #default="slotProps">
        <slot name="sidebar" v-bind="slotProps" />
      </template>
      <template #footer><slot name="sidebar-footer" /></template>
    </SideBar>

    <div class="flex min-w-0 flex-1 flex-col">
      <TopBar :title="title" :variant="variant" :connection="connection">
        <template #center><slot name="topbar-center" /></template>
        <template #actions><slot name="topbar-actions" /></template>
      </TopBar>

      <main class="min-w-0 flex-1">
        <slot />
      </main>

      <slot name="footer" />
    </div>
  </div>
</template>
