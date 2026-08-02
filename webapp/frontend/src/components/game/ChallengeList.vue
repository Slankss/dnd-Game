<script setup>
/**
 * Aktif Zorluklar — oyunun problem-çözüm omurgası.
 * Şiddet rengi YALNIZCA durum bildirir; kapananlar listenin sonunda soluk
 * kalır ki oyuncular ne başardıklarını görebilsin.
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import EmptyState from '../ui/EmptyState.vue'
import { zorluklariDiziye, zorlukTonu, zorlukKapali, olcuyeAl } from './gameFormat'

const props = defineProps({
  zorluklar: { type: [Object, Array], default: () => ({}) },
  yukleniyor: { type: Boolean, default: false },
})

const TON_CUBUK = { ok: 'bg-ok', warn: 'bg-warn', danger: 'bg-danger' }

const liste = computed(() =>
  zorluklariDiziye(props.zorluklar).map((z) => {
    // `progress` kimi turda 0-100 sayı, kimi turda serbest metin geliyor.
    const sayi = Number(z.progress)
    return {
      ...z,
      ton: zorlukTonu(z.severity),
      kapali: zorlukKapali(z.status),
      ilerlemeSayisi: Number.isFinite(sayi) && String(z.progress).trim() !== '' ? olcuyeAl(sayi) : null,
    }
  }),
)

function durumTonu(z) {
  const s = String(z.status || '').toLocaleLowerCase('tr-TR')
  if (s === 'çözüldü') return 'ok'
  if (s === 'başarısız') return 'danger'
  return 'muted'
}
</script>

<template>
  <div v-if="yukleniyor" class="flex flex-col gap-1.5 py-1">
    <span v-for="i in 2" :key="i" class="h-10 rounded-card bg-surface-2 motion-safe:animate-pulse" />
    <span class="sr-only">Zorluklar yükleniyor…</span>
  </div>

  <EmptyState
    v-else-if="!liste.length"
    compact
    icon="crisis_alert"
    title="Aktif zorluk yok"
    text="Anlatıcı bir tehdit ya da görev açtığında burada süresi ve ilerlemesiyle listelenir."
  />

  <ul v-else class="flex flex-col gap-2">
    <li
      v-for="zorluk in liste"
      :key="zorluk.ad"
      class="rounded-card border border-border bg-surface-2 px-2.5 py-2"
      :class="zorluk.kapali ? 'opacity-55' : ''"
      :style="
        zorluk.kapali
          ? undefined
          : {
              borderLeftWidth: '3px',
              borderLeftColor: `var(--color-${zorluk.ton})`,
            }
      "
    >
      <div class="flex items-start gap-1.5">
        <span class="min-w-0 flex-1 text-card text-text">{{ zorluk.ad }}</span>
        <Badge :tone="durumTonu(zorluk)" size="sm">{{ zorluk.status || 'açık' }}</Badge>
      </div>

      <p v-if="zorluk.description" class="mt-1 text-label text-muted">{{ zorluk.description }}</p>

      <p v-if="zorluk.clock" class="mt-1 flex items-start gap-1.5 text-label">
        <Icon name="hourglass_top" :size="13" class="mt-px shrink-0 text-warn" />
        <span class="text-text">{{ zorluk.clock }}</span>
      </p>

      <div v-if="zorluk.ilerlemeSayisi !== null" class="mt-1.5 flex items-center gap-2">
        <Icon name="trending_up" :size="13" class="shrink-0 text-faint" />
        <span
          class="h-1.5 min-w-0 flex-1 overflow-hidden rounded-chip bg-surface-3"
          role="meter"
          :aria-valuenow="zorluk.ilerlemeSayisi"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-label="`${zorluk.ad} ilerlemesi`"
        >
          <span
            class="block h-full rounded-chip"
            :class="TON_CUBUK[zorluk.ton]"
            :style="{ width: `${zorluk.ilerlemeSayisi}%` }"
          />
        </span>
        <span class="w-8 shrink-0 text-right text-label text-muted nums-tabular"
          >%{{ zorluk.ilerlemeSayisi }}</span
        >
      </div>
      <p v-else-if="zorluk.progress" class="mt-1 flex items-start gap-1.5 text-label">
        <Icon name="trending_up" :size="13" class="mt-px shrink-0 text-faint" />
        <span class="text-muted">{{ zorluk.progress }}</span>
      </p>

      <p
        v-if="zorluk.consequence && !zorluk.kapali"
        class="mt-1 flex items-start gap-1.5 text-label text-danger"
      >
        <Icon name="warning" :size="13" class="mt-px shrink-0" />
        <span>{{ zorluk.consequence }}</span>
      </p>
    </li>
  </ul>
</template>
