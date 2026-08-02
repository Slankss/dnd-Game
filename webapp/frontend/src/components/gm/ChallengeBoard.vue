<script setup>
/**
 * Zorluklar — oyuncunun gördüğü alanların yanında `gm_notes` de burada.
 *
 * `gm_notes` anlatıcının kendi hatırlatması: "üç grup aynı bölgede
 * yakınlaşıyor" gibi. Oyuncu ekranına giden gövdede bu alan yoktur, o yüzden
 * ayrı ve mor kutuda gösteriyoruz.
 */
import { computed } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { ciddiyetTonu, durumTonu, zorlukKapali } from './gmYardimcilar'

const props = defineProps({
  /** `world_state.challenges` — sunucu nesne yazar; dizi de gelirse tolere edilir */
  challenges: { type: [Object, Array], default: () => ({}) },
})

const emit = defineEmits(['yamala'])

const satirlar = computed(() => {
  const ham = props.challenges
  const cift = Array.isArray(ham)
    ? ham.map((v, i) => [v?.name || v?.title || `Zorluk ${i + 1}`, v || {}])
    : Object.entries(ham || {})

  return cift
    .map(([ad, bilgi]) => ({
      ad,
      ...(bilgi || {}),
      kapali: zorlukKapali(bilgi?.status),
    }))
    // Kapananlar dibe insin — anlatıcı açık olanlara baksın.
    .sort((a, b) => Number(a.kapali) - Number(b.kapali))
})

const KENAR = {
  ok: 'border-l-ok',
  warn: 'border-l-warn',
  danger: 'border-l-danger',
  muted: 'border-l-border-strong',
}

function duzenle(satir) {
  emit('yamala', {
    challenges: {
      [satir.ad]: {
        status: satir.status || 'açık',
        clock: satir.clock || '',
        progress: satir.progress || '',
        severity: satir.severity || 'orta',
        gm_notes: satir.gm_notes || '',
      },
    },
  })
}
</script>

<template>
  <EmptyState
    v-if="!satirlar.length"
    icon="crisis_alert"
    title="Aktif zorluk yok"
    text="Sahne boşta duruyor — bir sonraki turda yeni bir baskı açman gerekebilir."
  />

  <ul v-else class="flex flex-col gap-2">
    <li
      v-for="satir in satirlar"
      :key="satir.ad"
      class="rounded-card border border-l-2 border-border bg-surface-2 p-3"
      :class="[KENAR[ciddiyetTonu(satir.severity)], satir.kapali ? 'opacity-60' : '']"
    >
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="text-card">{{ satir.ad }}</h3>
        <Badge :tone="durumTonu(satir.status)">{{ satir.status || 'açık' }}</Badge>
        <Badge :tone="ciddiyetTonu(satir.severity)" icon="local_fire_department">
          {{ satir.severity || 'orta' }}
        </Badge>
        <BaseButton
          class="ml-auto"
          size="sm"
          variant="quiet"
          icon="stylus"
          icon-only
          :aria-label="`${satir.ad} zorluğunu durum düzenleyiciye al`"
          @click="duzenle(satir)"
        />
      </div>

      <p v-if="satir.description" class="mt-1.5 text-meta text-text">
        {{ satir.description }}
      </p>

      <div class="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-label text-muted">
        <span v-if="satir.clock" class="inline-flex items-center gap-1">
          <Icon name="timer" :size="13" />{{ satir.clock }}
        </span>
        <span v-if="satir.progress" class="inline-flex items-start gap-1">
          <Icon name="trending_up" :size="13" class="mt-0.5 shrink-0" />{{ satir.progress }}
        </span>
      </div>

      <p
        v-if="satir.consequence"
        class="mt-1.5 flex items-start gap-1.5 text-label text-warn"
      >
        <Icon name="warning" :size="13" class="mt-0.5 shrink-0" />
        <span>Çözülmezse: {{ satir.consequence }}</span>
      </p>

      <!-- Yalnızca anlatıcıya görünen not -->
      <p
        v-if="satir.gm_notes"
        class="mt-2 flex items-start gap-1.5 rounded-card border border-gm/30 bg-gm-soft px-2.5 py-1.5 text-label text-gm"
      >
        <Icon name="visibility_off" :size="13" class="mt-0.5 shrink-0" />
        <span>{{ satir.gm_notes }}</span>
      </p>
    </li>
  </ul>
</template>
