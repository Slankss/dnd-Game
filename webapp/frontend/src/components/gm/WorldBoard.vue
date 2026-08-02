<script setup>
/**
 * Dünya panosu — anlatıcının tek bakışta gördüğü künye.
 *
 * Oyuncu ekranından farkı: buradaki `world_state` SANSÜRSÜZDÜR. Aynı alanlar
 * orada da var, ama bu ekranda ayrıca bayraklar ve dünya zarı gibi gizli
 * eksenler de görünür.
 */
import { computed } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import { gerilimTonu, dizile } from './gmYardimcilar'

const props = defineProps({
  /** Tam (sansürsüz) dünya durumu */
  worldState: { type: Object, default: null },
})

const ws = computed(() => props.worldState || {})

/** Hava durumu metnine uygun ikon — kaba eşleme, yanlış eşleşirse bulut. */
const havaIkonu = computed(() => {
  const h = String(ws.value.weather || '').toLocaleLowerCase('tr-TR')
  if (h.includes('yağmur')) return 'rainy'
  if (h.includes('kar') || h.includes('dolu')) return 'ac_unit'
  if (h.includes('güneş') || h.includes('açık')) return 'sunny'
  if (h.includes('sis') || h.includes('pus')) return 'foggy'
  if (h.includes('fırtına')) return 'thunderstorm'
  if (h.includes('rüzgâr') || h.includes('rüzgar')) return 'air'
  return 'cloud'
})

const kutular = computed(() => [
  { ikon: 'calendar_month', etiket: 'Gün', deger: ws.value.day ?? '—', sayi: true },
  {
    ikon: 'schedule',
    etiket: 'Saat',
    deger: [ws.value.clock, ws.value.time_of_day].filter(Boolean).join(' ') || '—',
  },
  { ikon: 'park', etiket: 'Mevsim', deger: ws.value.season || '—' },
  {
    ikon: havaIkonu.value,
    etiket: 'Hava',
    deger: [ws.value.weather, ws.value.temperature].filter(Boolean).join(' · ') || '—',
  },
])

const bayraklar = computed(() => Object.entries(ws.value.flags || {}))
const gorulenler = computed(() => dizile(ws.value.zombie_sightings).filter(Boolean))
</script>

<template>
  <div class="flex flex-col gap-3">
    <!-- Künye kutuları -->
    <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <div
        v-for="k in kutular"
        :key="k.etiket"
        class="flex flex-col gap-1 rounded-card border border-border bg-surface-2 px-3 py-2"
      >
        <span class="flex items-center gap-1 text-panel uppercase tracking-[0.06em] text-muted">
          <Icon :name="k.ikon" :size="13" />
          {{ k.etiket }}
        </span>
        <span class="text-card text-text" :class="k.sayi ? 'nums-tabular' : ''">
          {{ k.deger }}
        </span>
      </div>
    </div>

    <!-- Konum + gerilim -->
    <div class="flex flex-wrap items-center gap-2">
      <span class="inline-flex min-w-0 items-center gap-1.5 text-meta text-text">
        <Icon name="location_on" :size="16" class="shrink-0 text-muted" />
        <span class="truncate">{{ ws.location || 'Konum bilinmiyor' }}</span>
      </span>
      <Badge :tone="gerilimTonu(ws.tension)" icon="local_fire_department" dot>
        gerilim: {{ ws.tension || 'belirsiz' }}
      </Badge>
    </div>

    <!-- Bölgedeki zombi türleri -->
    <div v-if="gorulenler.length" class="flex flex-wrap items-center gap-1.5">
      <span class="text-panel uppercase tracking-[0.06em] text-muted">Görülen türler</span>
      <Badge v-for="g in gorulenler" :key="g" tone="muted" icon="lucide:skull">{{ g }}</Badge>
    </div>

    <!-- Bayraklar: koşul motorunun okuduğu anahtarlar (flags_set/flags_unset) -->
    <div class="flex flex-col gap-1.5">
      <span class="text-panel uppercase tracking-[0.06em] text-muted">
        Bayraklar
        <span class="normal-case tracking-normal text-faint">
          — koşullarda `flags_set` / `flags_unset` olarak okunur
        </span>
      </span>
      <div v-if="bayraklar.length" class="flex flex-wrap gap-1.5">
        <Badge
          v-for="[ad, deger] in bayraklar"
          :key="ad"
          :tone="deger ? 'ok' : 'muted'"
          :icon="deger ? 'check_circle' : 'block'"
        >
          {{ ad }}
        </Badge>
      </div>
      <p v-else class="text-label text-faint">Henüz bayrak yok.</p>
    </div>
  </div>
</template>
