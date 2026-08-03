<script setup>
/**
 * Harita paneli — grubun şu an nerede olduğu ve bilinen yerler.
 *
 * Anlatıcı `map` alanını her turda güncelliyor, sunucu da `location` /
 * karakter konumlarından haritayı ayrıca besliyor; burada sadece okunur.
 * Grup dağıldığında (kimi bodrumda, kimi çatıda) kimin nerede olduğu
 * yerin altında kendi rengiyle görünür.
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import EmptyState from '../ui/EmptyState.vue'
import SkeletonLine from '../ui/SkeletonLine.vue'
import { TEHLIKE_TONU, yerleriDiziye, partiDagilmis } from './gameFormat'
import { colorFor } from '@/utils/characterColors'

const props = defineProps({
  harita: { type: Object, default: () => ({}) },
  yukleniyor: { type: Boolean, default: false },
})

const yerler = computed(() => yerleriDiziye(props.harita))
const dagilmis = computed(() => partiDagilmis(props.harita))
const simdiki = computed(() => props.harita?.current || '')
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
      <p v-if="dagilmis" class="flex items-center gap-1.5 text-label text-warn">
        <Icon name="call_split" :size="13" />
        Grup dağılmış durumda.
      </p>

      <ul class="flex flex-col gap-1.5">
        <li
          v-for="yer in yerler"
          :key="yer.ad"
          class="rounded-card border p-2"
          :class="yer.burada ? 'border-accent/55 bg-accent-soft' : 'border-border bg-surface-2'"
        >
          <div class="flex flex-wrap items-center gap-1.5">
            <Icon
              :name="yer.burada ? 'my_location' : yer.visited ? 'location_on' : 'help'"
              :size="14"
              :class="yer.burada ? 'text-accent' : 'text-faint'"
            />
            <span class="text-meta text-text">{{ yer.ad }}</span>
            <Badge v-if="yer.burada" tone="accent" size="sm">buradayız</Badge>
            <Badge
              v-if="yer.danger && yer.danger !== 'bilinmiyor'"
              :tone="TEHLIKE_TONU[yer.danger] || 'muted'"
              size="sm"
            >
              {{ yer.danger }}
            </Badge>
            <Badge v-if="!yer.visited" tone="muted" size="sm">gidilmedi</Badge>
          </div>

          <p v-if="yer.kind || yer.status" class="mt-0.5 text-label text-muted">
            {{ [yer.kind, yer.status].filter(Boolean).join(' · ') }}
          </p>
          <p v-if="yer.notes" class="mt-0.5 text-label text-faint">{{ yer.notes }}</p>

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

          <p
            v-if="Array.isArray(yer.links) && yer.links.length"
            class="mt-1 flex items-start gap-1 text-label text-faint"
          >
            <Icon name="alt_route" :size="12" class="mt-0.5 shrink-0" />
            <span>{{ yer.links.join(', ') }}</span>
          </p>
        </li>
      </ul>

      <p v-if="simdiki" class="sr-only">Şu anki konum: {{ simdiki }}</p>
    </template>
  </div>
</template>
