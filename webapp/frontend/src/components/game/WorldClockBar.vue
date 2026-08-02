<script setup>
/**
 * Üst bardaki dünya künyesi (docs §4):
 *   Gün 98 · 21:40 gece · yağmurlu 7°C · konum
 *
 * Dar ekranda sırayla sadeleşir: konum → hava → saat. Gün ve gerilim her
 * zaman görünür kalır.
 */
import { computed } from 'vue'
import Badge from '../ui/Badge.vue'
import SkeletonLine from '../ui/SkeletonLine.vue'
import Tooltip from '../ui/Tooltip.vue'
import { havaIkonu, sicaklikMetni, dunyaSaatiMetni, gerilimTonu } from './gameFormat'

const props = defineProps({
  saat: { type: Object, default: null },
  gerilim: { type: String, default: '' },
  /** Dünya durumu henüz gelmedi mi */
  yukleniyor: { type: Boolean, default: false },
})

const tamMetin = computed(() => dunyaSaatiMetni(props.saat))
const sicaklik = computed(() => sicaklikMetni(props.saat?.temperature))
const zaman = computed(() => [props.saat?.clock, props.saat?.timeOfDay].filter(Boolean).join(' '))
</script>

<template>
  <SkeletonLine v-if="yukleniyor" width="16rem" height="1rem" />

  <Tooltip v-else-if="saat" :text="tamMetin" placement="bottom">
    <span class="flex min-w-0 items-center gap-2">
      <Badge tone="neutral" icon="calendar_month">
        Gün <span class="nums-tabular">{{ saat.day ?? '—' }}</span>
      </Badge>

      <Badge v-if="zaman" tone="muted" icon="schedule" class="hidden sm:inline-flex">
        <span class="nums-tabular">{{ zaman }}</span>
      </Badge>

      <Badge v-if="saat.weather || sicaklik" tone="muted" :icon="havaIkonu(saat.weather)" class="hidden md:inline-flex">
        <span class="max-w-[12rem] truncate">{{ saat.weather }}</span>
        <span v-if="sicaklik" class="nums-tabular">{{ sicaklik }}</span>
      </Badge>

      <span v-if="saat.location" class="hidden min-w-0 truncate text-meta text-muted lg:inline">
        {{ saat.location }}
      </span>

      <Badge v-if="gerilim" :tone="gerilimTonu(gerilim)" size="sm" dot class="shrink-0">
        {{ gerilim }} gerilim
      </Badge>
    </span>
  </Tooltip>
</template>
