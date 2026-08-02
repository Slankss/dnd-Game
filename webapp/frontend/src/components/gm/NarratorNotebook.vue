<script setup>
/**
 * Anlatıcı defteri — `world_state.narrator`.
 *
 * Üç bölüm: olay örgüsü özeti, bulmacalar (ilerleme/ipuçları/sonraki adım) ve
 * yaklaşan olaylar. Tamamı `GM_ONLY_FIELDS` içinde: oyuncuya hiç gitmez.
 * `solution` alanı bulmacanın gerçek cevabıdır — ayrı ve mor kutuda.
 */
import { computed } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { durumTonu, yuzde, dizile } from './gmYardimcilar'

const props = defineProps({
  /** `world_state.narrator` */
  narrator: { type: Object, default: null },
})

const ozet = computed(() => props.narrator?.plot_summary || '')

const bulmacalar = computed(() =>
  Object.entries(props.narrator?.puzzles || {}).map(([ad, bilgi]) => ({
    ad,
    ...(bilgi || {}),
    oran: yuzde(bilgi?.progress),
    ipuclari: dizile(bilgi?.clues_found).filter(Boolean),
  })),
)

const olaylar = computed(() =>
  Object.entries(props.narrator?.upcoming_events || {}).map(([ne_zaman, aciklama]) => ({
    ne_zaman,
    aciklama: typeof aciklama === 'string' ? aciklama : JSON.stringify(aciklama),
  })),
)

const CUBUK = { ok: 'bg-ok', warn: 'bg-warn', danger: 'bg-danger', neutral: 'bg-gm', muted: 'bg-faint' }
</script>

<template>
  <div class="flex flex-col gap-5">
    <!-- Olay örgüsü özeti -->
    <section class="flex flex-col gap-1.5">
      <h3 class="flex items-center gap-1.5 text-panel uppercase tracking-[0.06em] text-muted">
        <Icon name="menu_book" :size="14" />
        Olay örgüsü özeti
      </h3>
      <p v-if="ozet" class="measure-scene text-scene text-text">{{ ozet }}</p>
      <p v-else class="text-meta text-faint">
        Anlatıcı henüz özet yazmadı — ilk turlardan sonra kendisi doldurur.
      </p>
    </section>

    <!-- Bulmacalar -->
    <section class="flex flex-col gap-2">
      <h3 class="flex items-center gap-1.5 text-panel uppercase tracking-[0.06em] text-muted">
        <Icon name="extension" :size="14" />
        Bulmacalar
        <Badge v-if="bulmacalar.length" size="sm" tone="muted">{{ bulmacalar.length }}</Badge>
      </h3>

      <EmptyState
        v-if="!bulmacalar.length"
        compact
        icon="extension"
        text="Şu an açık bir bulmaca yok."
      />

      <ul v-else class="flex flex-col gap-2">
        <li
          v-for="b in bulmacalar"
          :key="b.ad"
          class="rounded-card border border-border bg-surface-2 p-3"
        >
          <div class="flex flex-wrap items-center gap-2">
            <h4 class="text-card">{{ b.ad }}</h4>
            <Badge :tone="durumTonu(b.status)">{{ b.status || 'çözülmedi' }}</Badge>
            <span class="nums-tabular ml-auto text-label text-muted">%{{ b.oran }}</span>
          </div>

          <p v-if="b.description" class="mt-1 text-meta text-muted">{{ b.description }}</p>

          <div
            class="mt-2 h-1.5 w-full overflow-hidden rounded-chip bg-surface-3"
            role="progressbar"
            :aria-valuenow="b.oran"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-label="`${b.ad} ilerlemesi`"
          >
            <div
              class="h-full rounded-chip transition-[width] duration-[var(--duration-slow)] ease-[var(--ease-standard)]"
              :class="CUBUK[durumTonu(b.status)] || CUBUK.neutral"
              :style="{ width: `${b.oran}%` }"
            />
          </div>

          <p v-if="b.next_step" class="mt-2 flex items-start gap-1.5 text-label text-text">
            <Icon name="my_location" :size="13" class="mt-0.5 shrink-0 text-muted" />
            <span>Sonraki adım: {{ b.next_step }}</span>
          </p>

          <div v-if="b.ipuclari.length" class="mt-2 flex flex-col gap-1">
            <span class="text-label text-faint">Bulunan ipuçları ({{ b.ipuclari.length }})</span>
            <ul class="flex flex-col gap-0.5">
              <li
                v-for="(ip, i) in b.ipuclari"
                :key="i"
                class="flex items-start gap-1.5 text-label text-muted"
              >
                <Icon name="troubleshoot" :size="13" class="mt-0.5 shrink-0" />
                <span>{{ ip }}</span>
              </li>
            </ul>
          </div>

          <p
            v-if="b.solution"
            class="mt-2 flex items-start gap-1.5 rounded-card border border-gm/30 bg-gm-soft px-2.5 py-1.5 text-label text-gm"
          >
            <Icon name="visibility_off" :size="13" class="mt-0.5 shrink-0" />
            <span>Gerçek cevap: {{ b.solution }}</span>
          </p>

          <p v-if="b.notes" class="mt-1.5 text-label text-muted">{{ b.notes }}</p>
        </li>
      </ul>
    </section>

    <!-- Yaklaşan olaylar -->
    <section class="flex flex-col gap-2">
      <h3 class="flex items-center gap-1.5 text-panel uppercase tracking-[0.06em] text-muted">
        <Icon name="event_upcoming" :size="14" />
        Yaklaşan olaylar
        <span class="normal-case tracking-normal text-faint">— plan, taahhüt değil</span>
      </h3>

      <EmptyState
        v-if="!olaylar.length"
        compact
        icon="event_upcoming"
        text="Planlanmış bir şey not edilmemiş."
      />

      <ul v-else class="flex flex-col gap-1.5">
        <li
          v-for="o in olaylar"
          :key="o.ne_zaman"
          class="flex flex-col gap-0.5 rounded-card border border-border bg-surface-2 px-3 py-2"
        >
          <span class="text-label uppercase tracking-[0.06em] text-gm">{{ o.ne_zaman }}</span>
          <span class="text-meta text-text">{{ o.aciklama }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>
