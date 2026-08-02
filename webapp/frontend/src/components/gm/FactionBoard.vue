<script setup>
/**
 * Fraksiyonlar — GERÇEK tavır ile OYUNCUNUN BİLDİĞİ yan yana.
 *
 * `disposition` + `notes` yalnızca bu ekranda görünür; `known` + `public_notes`
 * oyuncu ekranına da gider. İkisi ayrıştığında (ör. gerçekte "düşmanca" ama
 * oyuncular "bilinmiyor" sanıyor) bunu rozetle işaretliyoruz: anlatıcının
 * ağzından kaçırdığı tek kelime sürprizi yakar.
 */
import { computed } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { normTr } from './gmYardimcilar'

const props = defineProps({
  /** `world_state.factions` */
  factions: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['yamala'])

const satirlar = computed(() =>
  Object.entries(props.factions || {}).map(([ad, bilgi]) => {
    const gercek = bilgi?.disposition || ''
    const bilinen = bilgi?.known || ''
    return {
      ad,
      gercek,
      bilinen,
      notlar: bilgi?.notes || '',
      acikNotlar: bilgi?.public_notes || '',
      // "bilinmiyor" da bir ayrışmadır: oyuncular tavrı hiç bilmiyor demektir
      ayrisik: normTr(gercek) !== normTr(bilinen),
    }
  }),
)

/** Bu fraksiyonun tüm alanlarını durum düzenleyiciye taslak olarak gönderir. */
function duzenle(satir) {
  emit('yamala', {
    factions: {
      [satir.ad]: {
        disposition: satir.gercek,
        known: satir.bilinen,
        notes: satir.notlar,
        public_notes: satir.acikNotlar,
      },
    },
  })
}
</script>

<template>
  <EmptyState
    v-if="!satirlar.length"
    icon="handshake"
    title="Fraksiyon kaydı yok"
    text="Senaryo fraksiyon tanımlamamış ya da dünya durumu henüz yüklenmedi."
  />

  <ul v-else class="flex flex-col gap-2">
    <li
      v-for="satir in satirlar"
      :key="satir.ad"
      class="rounded-card border border-border bg-surface-2 p-3"
    >
      <div class="mb-2 flex flex-wrap items-center gap-2">
        <h3 class="text-card">{{ satir.ad }}</h3>
        <Badge v-if="satir.ayrisik" tone="gm" icon="visibility_off">
          oyuncular gerçeği bilmiyor
        </Badge>
        <Badge v-else tone="muted" icon="visibility">oyuncular gerçeği biliyor</Badge>
        <BaseButton
          class="ml-auto"
          size="sm"
          variant="quiet"
          icon="stylus"
          icon-only
          :aria-label="`${satir.ad} fraksiyonunu durum düzenleyiciye al`"
          @click="duzenle(satir)"
        />
      </div>

      <div class="grid gap-2 md:grid-cols-2">
        <!-- Gerçek: sadece anlatıcı -->
        <div class="rounded-card border border-gm/30 bg-gm-soft px-2.5 py-2">
          <span class="flex items-center gap-1 text-panel uppercase tracking-[0.06em] text-gm">
            <Icon name="visibility_off" :size="13" />
            gerçek — sadece sen
          </span>
          <p class="mt-1 text-meta text-text">
            {{ satir.gercek || 'tavır yazılmamış' }}
          </p>
          <p class="mt-0.5 text-label text-muted">
            {{ satir.notlar || 'anlatıcı notu yok' }}
          </p>
        </div>

        <!-- Oyuncunun bildiği -->
        <div class="rounded-card border border-border bg-surface px-2.5 py-2">
          <span class="flex items-center gap-1 text-panel uppercase tracking-[0.06em] text-muted">
            <Icon name="groups" :size="13" />
            oyuncular böyle biliyor
          </span>
          <p class="mt-1 text-meta text-text">
            {{ satir.bilinen || 'bilinmiyor' }}
          </p>
          <p class="mt-0.5 text-label text-muted">
            {{ satir.acikNotlar || 'oyuncuya görünen not yok' }}
          </p>
        </div>
      </div>
    </li>
  </ul>
</template>
