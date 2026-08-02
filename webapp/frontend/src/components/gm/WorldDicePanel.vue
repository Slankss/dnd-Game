<script setup>
/**
 * Dünya zarı — oyuncunun zarından AYRI, dünyanın kendi hamlesi.
 *
 * Bu veri `GM_ONLY_FIELDS` içinde: `/api/state` ile oyuncuya hiç gitmez.
 * Ekranda bunu sürekli hatırlatıyoruz — anlatıcı yanlışlıkla "zar 69 geldi"
 * diye yazmasın.
 *
 * `compact` yan panel içindir: yalnızca sayı, band ve gizlilik uyarısı.
 */
import { computed } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { DUNYA_ZARI_BANTLARI, zarTonu, saatKisalt } from './gmYardimcilar'

const props = defineProps({
  /** `world_state.world_roll` — {roll, band, hint, ts} */
  roll: { type: Object, default: null },
  /** `world_state.world_roll_history` — eskiden yeniye */
  history: { type: Array, default: () => [] },
  /** Yan panel varyantı */
  compact: { type: Boolean, default: false },
})

const ton = computed(() => zarTonu(props.roll?.band, props.roll?.roll))

const TON_METIN = {
  ok: 'text-ok',
  warn: 'text-warn',
  danger: 'text-danger',
  neutral: 'text-text',
  muted: 'text-muted',
}

/** Geçmiş: en yeni en üstte, o anki atış listeden düşülür. */
const gecmis = computed(() => {
  const suAnki = props.roll
  return [...(props.history || [])]
    .reverse()
    .filter((h) => !(suAnki && h.ts && h.ts === suAnki.ts))
    .slice(0, props.compact ? 6 : 12)
})

/** Şu anki atış hangi bandın içinde (cetvelde işaretlemek için). */
function aktifBandMi(band) {
  return props.roll?.band === band.ad
}
</script>

<template>
  <div v-if="!roll" class="flex flex-col gap-2">
    <EmptyState
      :compact="compact"
      icon="casino"
      :title="compact ? '' : 'Dünya zarı henüz atılmadı'"
      text="İlk normal turda atılır; oyun başlamadan önce burada bir şey olmaz."
    />
  </div>

  <div v-else class="flex flex-col gap-3">
    <!-- Son atış -->
    <div class="flex items-center gap-3">
      <span
        class="nums-tabular text-[2rem] font-semibold leading-none"
        :class="TON_METIN[ton]"
        >{{ roll.roll }}</span
      >
      <div class="flex min-w-0 flex-col gap-1">
        <Badge :tone="ton" icon="casino">{{ roll.band }}</Badge>
        <span v-if="roll.ts" class="text-label text-faint" :title="roll.ts">
          {{ saatKisalt(roll.ts) }}
        </span>
      </div>
    </div>

    <p v-if="roll.hint" class="text-meta text-muted">{{ roll.hint }}</p>

    <!-- Gizlilik uyarısı — bu ekranın sebebi -->
    <p
      class="flex items-start gap-1.5 rounded-card border border-gm/30 bg-gm-soft px-2.5 py-2 text-label text-gm"
    >
      <Icon name="visibility_off" :size="14" class="mt-0.5 shrink-0" />
      <span>
        Oyuncular bu zarı ASLA görmez. Sahnede ondan söz etme; yalnızca sonucunu
        dünyaya işlet.
      </span>
    </p>

    <!-- Band cetveli (server.py WORLD_DICE_BANDS ile birebir) -->
    <div v-if="!compact" class="flex flex-col gap-1">
      <span class="text-panel uppercase tracking-[0.06em] text-muted">Band cetveli</span>
      <ul class="flex flex-col gap-0.5">
        <li
          v-for="band in DUNYA_ZARI_BANTLARI"
          :key="band.ad"
          class="flex items-center gap-2 rounded-md px-2 py-1 text-label"
          :class="aktifBandMi(band) ? 'bg-surface-2 text-text' : 'text-faint'"
        >
          <span class="nums-tabular w-14 shrink-0">{{ band.alt }}–{{ band.ust }}</span>
          <span class="truncate" :class="aktifBandMi(band) ? TON_METIN[band.ton] : ''">
            {{ band.ad }}
          </span>
          <Icon
            v-if="aktifBandMi(band)"
            name="radio_button_checked"
            :size="12"
            class="ml-auto shrink-0 text-muted"
            label="Şu anki band"
          />
        </li>
      </ul>
    </div>

    <!-- Geçmiş -->
    <div class="flex flex-col gap-1.5">
      <span class="text-panel uppercase tracking-[0.06em] text-muted">
        Önceki atışlar
      </span>
      <div v-if="gecmis.length" class="flex flex-wrap gap-1.5">
        <span
          v-for="(h, i) in gecmis"
          :key="`${h.ts}-${i}`"
          class="inline-flex items-center gap-1 rounded-chip border border-border bg-surface-2 px-2 py-0.5 text-label text-muted"
          :title="h.ts || ''"
        >
          <b class="nums-tabular" :class="TON_METIN[zarTonu(h.band, h.roll)]">{{ h.roll }}</b>
          <span class="truncate">{{ h.band }}</span>
        </span>
      </div>
      <p v-else class="text-label text-faint">Bu tek atıştan başka kayıt yok.</p>
    </div>
  </div>
</template>
