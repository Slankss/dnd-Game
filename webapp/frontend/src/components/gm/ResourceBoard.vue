<script setup>
/**
 * Grup kaynakları — klanın envanter sayımı.
 *
 * Bu veri oyuncuya da açıktır (gizli alan değil); anlatıcının burada olmasının
 * sebebi kararı beslemek: neyin bittiğini bilmeden baskı kurulamaz.
 * Azalan kalemler renkle öne çıkar.
 */
import { computed } from 'vue'
import EmptyState from '@/components/ui/EmptyState.vue'

const props = defineProps({
  /** `world_state.resources` — {kategori: {kalem: {qty, unit, notes} | sayı}} */
  resources: { type: Object, default: () => ({}) },
})

/** Sunucu kalemi düz sayı olarak da yazabiliyor; ikisini de karşıla. */
function kalemNormalle(deger) {
  if (deger && typeof deger === 'object') return deger
  return { qty: deger, unit: '', notes: '' }
}

const kategoriler = computed(() =>
  Object.entries(props.resources || {}).map(([ad, kalemler]) => ({
    ad,
    kalemler: Object.entries(kalemler || {}).map(([kalemAdi, ham]) => {
      const k = kalemNormalle(ham)
      const n = Number(k.qty)
      return {
        ad: kalemAdi,
        miktar: Number.isFinite(n) ? n : k.qty,
        birim: k.unit || '',
        not: k.notes || '',
        ton: !Number.isFinite(n) ? 'text-text' : n <= 0 ? 'text-danger' : n <= 5 ? 'text-warn' : 'text-text',
      }
    }),
  })),
)
</script>

<template>
  <EmptyState
    v-if="!kategoriler.length"
    icon="inventory_2"
    title="Kaynak kaydı yok"
    text="Senaryo kaynak tanımlamamış ya da henüz sayım yapılmadı."
  />

  <div v-else class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
    <section v-for="kat in kategoriler" :key="kat.ad" class="flex flex-col gap-1">
      <h3 class="text-panel uppercase tracking-[0.06em] text-muted">{{ kat.ad }}</h3>
      <ul class="flex flex-col gap-0.5">
        <li
          v-for="kalem in kat.kalemler"
          :key="kalem.ad"
          class="flex items-baseline justify-between gap-2 rounded-md bg-surface-2 px-2 py-1"
        >
          <span class="min-w-0 text-label text-text">
            {{ kalem.ad }}
            <span v-if="kalem.not" class="block text-label text-faint">{{ kalem.not }}</span>
          </span>
          <span class="nums-tabular shrink-0 text-label font-medium" :class="kalem.ton">
            {{ kalem.miktar }} {{ kalem.birim }}
          </span>
        </li>
      </ul>
    </section>
  </div>
</template>
