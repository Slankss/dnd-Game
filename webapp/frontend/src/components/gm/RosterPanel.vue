<script setup>
/**
 * Kadro paneli — sahne katılımı özeti + karakter künyeleri.
 *
 * Üstteki özet şeridi anlatıcının en sık sorduğu soruyu yanıtlar: bu turda
 * kim sahnede? Sahne dışındakine replik yazmak turu bozar.
 */
import { computed } from 'vue'
import Badge from '@/components/ui/Badge.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import GmCharacterCard from './GmCharacterCard.vue'
import { katilimOzeti } from './gmYardimcilar'

const props = defineProps({
  /** `world_state.characters` */
  characters: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['sahneyeDondur'])

const kadro = computed(() =>
  Object.entries(props.characters || {}).map(([ad, bilgi]) => ({
    ad,
    bilgi: bilgi || {},
    olu: bilgi?.alive === false,
    katilim: katilimOzeti(bilgi?.presence),
  })),
)

/** Sahne dışındakiler üstte dursun; ölüler en altta. */
const sirali = computed(() =>
  [...kadro.value].sort((a, b) => {
    if (a.olu !== b.olu) return Number(a.olu) - Number(b.olu)
    return Number(a.katilim.sahnede) - Number(b.katilim.sahnede)
  }),
)

const ozet = computed(() => {
  const canli = kadro.value.filter((k) => !k.olu)
  const sahnede = canli.filter((k) => k.katilim.sahnede)
  const disarida = canli.filter((k) => !k.katilim.sahnede)
  return {
    sahnede: sahnede.length,
    disarida: disarida.length,
    olu: kadro.value.length - canli.length,
    disaridakiler: disarida,
  }
})
</script>

<template>
  <EmptyState
    v-if="!kadro.length"
    icon="groups"
    title="Kadro boş"
    text="Karakter kurulumu henüz yapılmadı."
  />

  <div v-else class="flex flex-col gap-3">
    <!-- Sahne katılımı özeti -->
    <div class="flex flex-wrap items-center gap-1.5">
      <Badge tone="ok" icon="person">{{ ozet.sahnede }} sahnede</Badge>
      <Badge v-if="ozet.disarida" tone="warn" icon="directions_walk">
        {{ ozet.disarida }} sahne dışında
      </Badge>
      <Badge v-if="ozet.olu" tone="danger" icon="lucide:skull">{{ ozet.olu }} ölü</Badge>
    </div>

    <p v-if="ozet.disaridakiler.length" class="text-label text-warn">
      Sahne dışındakilere replik yazma:
      <template v-for="(k, i) in ozet.disaridakiler" :key="k.ad">
        <template v-if="i"> · </template>{{ k.ad }} ({{ k.katilim.etiket }})
      </template>
    </p>

    <div class="grid gap-2 xl:grid-cols-2">
      <GmCharacterCard
        v-for="k in sirali"
        :key="k.ad"
        :ad="k.ad"
        :bilgi="k.bilgi"
        @sahneye-dondur="emit('sahneyeDondur', $event)"
      />
    </div>
  </div>
</template>
