<script setup>
/**
 * Üst bar — sidebar anahtarı + dünya künyesi + sağ eylemler.
 *
 * Yerleşim (docs §4):
 *   ☰  Gün 98 · 21:40 gece · yağmurlu 7°C · konum        [eylemler]
 *
 * Dünya bilgisini oyun ekranları `#center` yuvasına koyar; burada yalnızca
 * iskelet ve bağlantı durumu vardır.
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import Tooltip from '../ui/Tooltip.vue'
import { useSidebar } from '@/composables/useSidebar'

const props = defineProps({
  /** Sol üstte görünen kısa başlık */
  title: { type: String, default: 'Kızıl Çöküş' },
  /** 'player' | 'gm' */
  variant: { type: String, default: 'player' },
  /** 'bagli' | 'yavas' | 'kopuk' — sağdaki bağlantı göstergesi */
  connection: { type: String, default: 'bagli' },
})

const { degistir, daraltilmis, mobil } = useSidebar()

const vurgu = computed(() => (props.variant === 'gm' ? 'text-gm' : 'text-accent'))

const BAGLANTI = {
  bagli: { icon: 'cloud_done', sinif: 'text-faint', metin: 'Sunucuya bağlı' },
  yavas: { icon: 'cloud_sync', sinif: 'text-warn', metin: 'Bağlantı yavaş — yeniden deneniyor' },
  kopuk: { icon: 'cloud_off', sinif: 'text-danger', metin: 'Sunucuya bağlanılamıyor' },
}

const baglanti = computed(() => BAGLANTI[props.connection] || BAGLANTI.bagli)
</script>

<template>
  <header
    class="sticky top-0 z-30 flex h-[var(--spacing-topbar)] shrink-0 items-center gap-2 border-b border-border bg-bg/95 px-2 backdrop-blur-sm sm:px-3"
  >
    <Tooltip text="Yan panel (Ctrl+B)" placement="bottom">
      <button
        type="button"
        class="inline-flex size-9 items-center justify-center rounded-md text-muted transition-colors duration-[var(--duration-fast)] hover:bg-surface-2 hover:text-text"
        :aria-label="daraltilmis || mobil ? 'Yan paneli aç' : 'Yan paneli kapat'"
        @click="degistir"
      >
        <Icon :name="mobil ? 'menu' : daraltilmis ? 'left_panel_open' : 'left_panel_close'" :size="20" />
      </button>
    </Tooltip>

    <span class="hidden items-center gap-1.5 sm:inline-flex">
      <Icon name="skull" :size="18" :class="vurgu" filled />
      <span class="text-card">{{ title }}</span>
    </span>

    <div class="mx-1 hidden h-5 w-px shrink-0 bg-border sm:block" aria-hidden="true" />

    <!-- Dünya künyesi: gün, saat, hava, konum -->
    <div class="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
      <slot name="center" />
    </div>

    <div class="flex shrink-0 items-center gap-1">
      <slot name="actions" />
      <Tooltip :text="baglanti.metin" placement="bottom">
        <span class="inline-flex size-9 items-center justify-center">
          <Icon :name="baglanti.icon" :size="18" :class="baglanti.sinif" :label="baglanti.metin" />
        </span>
      </Tooltip>
    </div>
  </header>
</template>
