<script setup>
/**
 * Kenar çubuğundaki harita — küçük görsel harita + kısa yer listesi.
 *
 * Görsel harita `MapCanvas`, büyük görünüm `MapModal`'dadır; burası ikisinin
 * girişi. Liste, haritada okunamayacak kadar küçük kalan ayrıntıyı (durum,
 * kim nerede) verir ve haritayla AYNI sis perdesine uyar: duyulmuş bir yer
 * için ad dışında bir şey yazılmaz — çünkü sunucu ayrıntıyı zaten
 * göndermiyor (bkz. models/worldmap.public_place).
 */
import { ref, computed } from 'vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import BaseButton from '../ui/BaseButton.vue'
import EmptyState from '../ui/EmptyState.vue'
import SkeletonLine from '../ui/SkeletonLine.vue'
import MapCanvas from './MapCanvas.vue'
import MapModal from './MapModal.vue'
import { TEHLIKE_TONU, yerleriDiziye, partiDagilmis } from './gameFormat'
import { bilgiDuzeyi } from './mapLayout'
import { colorFor } from '@/utils/characterColors'

const props = defineProps({
  harita: { type: Object, default: () => ({}) },
  yukleniyor: { type: Boolean, default: false },
  /** Anlatıcı kipi: sis perdesi yok */
  gm: { type: Boolean, default: false },
  /** world_state.threat — yoğunluk halkaları ve göç bilgisi için */
  tehdit: { type: Object, default: null },
})

const buyukAcik = ref(false)

const yerler = computed(() =>
  yerleriDiziye(props.harita).map((yer) => ({ ...yer, duzey: bilgiDuzeyi(yer) })),
)
const dagilmis = computed(() => partiDagilmis(props.harita))
const kesfedilen = computed(() => yerler.value.filter((y) => y.duzey === 'keşfedildi').length)
const bilinmeyen = computed(() => yerler.value.filter((y) => y.duzey === 'duyuldu').length)
</script>

<template>
  <div class="flex flex-col gap-2">
    <SkeletonLine v-if="yukleniyor" :lines="3" />

    <EmptyState
      v-else-if="!yerler.length"
      compact
      icon="explore_off"
      title="Harita boş"
      text="Grup bir yere yerleştiğinde ve yeni yerler keşfedildiğinde burada görünecek."
    />

    <template v-else>
      <!-- mini harita: tıklayınca büyük görünüm açılır -->
      <button
        type="button"
        class="group relative block w-full text-left"
        title="Haritayı büyüt"
        @click="buyukAcik = true"
      >
        <MapCanvas
          :harita="harita"
          mini
          :gm="gm"
          :yogunluk="tehdit?.density || {}"
          @sec="buyukAcik = true"
        />
        <span
          class="pointer-events-none absolute right-1.5 top-1.5 inline-flex items-center gap-1 rounded-chip border border-border bg-surface/90 px-1.5 py-0.5 text-[0.625rem] text-muted transition-colors group-hover:text-text"
        >
          <Icon name="open_in_full" :size="12" />
          büyüt
        </span>
      </button>

      <p class="flex flex-wrap items-center gap-x-2 gap-y-1 text-label text-faint">
        <span>{{ kesfedilen }} keşfedildi</span>
        <span v-if="bilinmeyen">· {{ bilinmeyen }} yer sadece duyuldu</span>
        <span v-if="dagilmis" class="inline-flex items-center gap-1 text-warn">
          <Icon name="call_split" :size="12" />
          grup dağılmış
        </span>
      </p>

      <!-- kısa liste -->
      <ul class="flex flex-col gap-1.5">
        <li
          v-for="yer in yerler"
          :key="yer.ad"
          class="rounded-card border p-2"
          :class="[
            yer.burada ? 'border-accent/55 bg-accent-soft' : 'border-border bg-surface-2',
            yer.duzey === 'duyuldu' ? 'opacity-70' : '',
          ]"
        >
          <div class="flex flex-wrap items-center gap-1.5">
            <Icon
              :name="
                yer.burada ? 'my_location' : yer.duzey === 'duyuldu' ? 'help' : 'location_on'
              "
              :size="14"
              :class="yer.burada ? 'text-accent' : 'text-faint'"
            />
            <span
              class="text-meta"
              :class="yer.duzey === 'duyuldu' ? 'italic text-muted' : 'text-text'"
            >
              {{ yer.ad }}
            </span>
            <Badge v-if="yer.burada" tone="accent" size="sm">buradayız</Badge>
            <Badge
              v-if="yer.duzey !== 'duyuldu' && yer.danger && yer.danger !== 'bilinmiyor'"
              :tone="TEHLIKE_TONU[yer.danger] || 'muted'"
              size="sm"
            >
              {{ yer.danger }}
            </Badge>
            <Badge v-if="yer.duzey === 'görüldü'" tone="warn" size="sm" icon="visibility">
              uzaktan
            </Badge>
            <Badge
              v-if="tehdit?.density?.[yer.ad] != null"
              :tone="
                tehdit.density[yer.ad] >= 66
                  ? 'danger'
                  : tehdit.density[yer.ad] >= 38
                    ? 'warn'
                    : 'ok'
              "
              size="sm"
              icon="skull"
            >
              {{ Math.round(tehdit.density[yer.ad]) }}
            </Badge>
          </div>

          <!-- Duyulmuş yer: ad dışında hiçbir ayrıntı yok. -->
          <p v-if="yer.duzey === 'duyuldu'" class="mt-0.5 text-label text-faint">
            hakkında bilgi yok
          </p>
          <template v-else>
            <p v-if="yer.kind || yer.status" class="mt-0.5 text-label text-muted">
              {{ [yer.kind, yer.status].filter(Boolean).join(' · ') }}
            </p>
            <p v-if="yer.notes" class="mt-0.5 text-label text-faint">{{ yer.notes }}</p>
          </template>

          <div v-if="yer.kimler.length" class="mt-1 flex flex-wrap gap-1">
            <span
              v-for="kisi in yer.kimler"
              :key="kisi"
              class="inline-flex items-center gap-1 rounded-chip border px-1.5 py-0.5 text-[0.625rem]"
              :style="{
                color: colorFor(kisi),
                borderColor: `color-mix(in oklab, ${colorFor(kisi)} 45%, transparent)`,
              }"
            >
              <span class="size-1 rounded-full bg-current" aria-hidden="true" />
              {{ kisi }}
            </span>
          </div>
        </li>
      </ul>

      <BaseButton size="sm" variant="subtle" icon="map" block @click="buyukAcik = true">
        Haritayı büyüt
      </BaseButton>
    </template>

    <MapModal v-model="buyukAcik" :harita="harita" :gm="gm" :tehdit="tehdit" />
  </div>
</template>
