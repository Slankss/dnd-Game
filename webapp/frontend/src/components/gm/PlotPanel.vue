<script setup>
/**
 * Plan paneli (senarist katmanı) — SALT OKUNUR.
 *
 * `/api/gm/state` artık `data/plot.json`'u da yolluyor (Faz 2). Burada yalnız
 * gösterilir: beat ekleme / veto / "şimdi ateşle" Faz 3'te `/api/gm/plot` ile
 * gelecek. Plan oyunculara ASLA gitmez, bu ekrana özeldir.
 *
 * Beat halleri: pending (bekliyor) · fired (ateşlendi) · expired (vadesi
 * doldu) · vetoed (anlatıcı iptal etti). Tur başına en fazla bir beat
 * ateşlenir; koşulu `when`, dönüşü sunucu (models.conditions) çözer.
 */
import { computed } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { kosuluAnlat } from './gmYardimcilar'

const props = defineProps({
  /** `/api/gm/state` → `plot` */
  plan: { type: Object, default: null },
  /** Yan panel varyantı: kısa liste */
  compact: { type: Boolean, default: false },
})

const HAL = {
  pending: { etiket: 'bekliyor', ton: 'accent', ikon: 'pending' },
  fired: { etiket: 'ateşlendi', ton: 'ok', ikon: 'bolt' },
  expired: { etiket: 'vadesi doldu', ton: 'muted', ikon: 'history' },
  vetoed: { etiket: 'iptal', ton: 'muted', ikon: 'block' },
}
const SIRA = { pending: 0, fired: 1, expired: 2, vetoed: 3 }

const beatler = computed(() => {
  const ham = Array.isArray(props.plan?.beats) ? props.plan.beats : []
  return ham
    .map((b) => ({ ...b, hal: HAL[b?.state] ? b.state : 'pending' }))
    .sort((a, b) => SIRA[a.hal] - SIRA[b.hal] || String(a.id).localeCompare(String(b.id)))
})

const bekleyen = computed(() => beatler.value.filter((b) => b.hal === 'pending'))
const gosterilecek = computed(() => (props.compact ? beatler.value.slice(0, 4) : beatler.value))
const iplikler = computed(() => Object.entries(props.plan?.threads || {}))
const tohumlar = computed(() => (Array.isArray(props.plan?.seeds) ? props.plan.seeds : []))
const bosMu = computed(
  () => !beatler.value.length && !iplikler.value.length && !tohumlar.value.length,
)
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex flex-wrap items-center gap-2">
      <Badge tone="gm" icon="visibility_off">oyunculara gitmez</Badge>
      <Badge v-if="bekleyen.length" tone="accent" icon="pending">
        {{ bekleyen.length }} bekleyen
      </Badge>
    </div>

    <EmptyState
      v-if="bosMu"
      icon="account_tree"
      title="Plan boş"
      text="data/plot.json içine beat yazıldığında, koşulu sağlanan turda anlatıcıya
            gizli direktif olarak girer. Tur başına en fazla bir beat ateşlenir;
            vadesi (expires_day) geçen çürür."
    />

    <template v-else>
      <ul v-if="gosterilecek.length" class="flex flex-col gap-2">
        <li
          v-for="beat in gosterilecek"
          :key="beat.id"
          class="rounded-card border border-border bg-surface-2 p-2"
          :class="beat.hal === 'pending' ? 'border-l-2 border-l-gm' : 'opacity-75'"
        >
          <div class="flex flex-wrap items-center gap-2">
            <Icon :name="HAL[beat.hal].ikon" :size="15" class="shrink-0 text-faint" />
            <span class="font-mono text-label text-text">{{ beat.id || '(adsız)' }}</span>
            <Badge :tone="HAL[beat.hal].ton">{{ HAL[beat.hal].etiket }}</Badge>
            <span v-if="beat.thread" class="text-label text-muted">iplik: {{ beat.thread }}</span>
          </div>

          <p v-if="beat.directive" class="mt-1 text-meta text-text">{{ beat.directive }}</p>

          <div class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-label text-muted">
            <span>koşul: {{ kosuluAnlat(beat.when) || 'koşulsuz' }}</span>
            <span v-if="beat.expires_day != null">vade: gün {{ beat.expires_day }}</span>
            <span v-if="beat.fired_day != null">ateşlendi: gün {{ beat.fired_day }}</span>
          </div>
        </li>
      </ul>

      <p v-if="compact && beatler.length > gosterilecek.length" class="text-label text-muted">
        +{{ beatler.length - gosterilecek.length }} beat daha
      </p>

      <div v-if="!compact && iplikler.length" class="flex flex-col gap-1">
        <h4 class="text-label uppercase tracking-wide text-muted">İplikler</h4>
        <div v-for="[ad, bilgi] in iplikler" :key="ad" class="text-meta text-text">
          <span class="font-medium">{{ ad }}</span>
          <span v-if="bilgi?.premise" class="text-muted"> — {{ bilgi.premise }}</span>
          <span v-if="bilgi?.status" class="text-label text-muted"> ({{ bilgi.status }})</span>
        </div>
      </div>

      <div v-if="!compact && tohumlar.length" class="flex flex-col gap-1">
        <h4 class="text-label uppercase tracking-wide text-muted">Tohumlar</h4>
        <ul class="list-disc pl-4 text-meta text-muted">
          <li v-for="(tohum, i) in tohumlar" :key="i">{{ tohum }}</li>
        </ul>
      </div>
    </template>

    <p v-if="!compact" class="text-label text-faint">
      Beat ekleme / veto / "şimdi ateşle" Faz 3'te gelecek; şimdilik plan
      <code class="font-mono">data/plot.json</code> dosyasından elle yazılır.
    </p>
  </div>
</template>
