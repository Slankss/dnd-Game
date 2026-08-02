<script setup>
/**
 * Grup Kaynakları — ortak stok (kişisel envanterden AYRI).
 *
 * Stok bilerek boş başlar: ortada bir klan/topluluk/depo yokken stok da
 * yoktur. Bu yüzden boş hal bir hata değil, açıklanması gereken bir durum.
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import EmptyState from '../ui/EmptyState.vue'
import { kaynaklariDiziye, kaynakTonu } from './gameFormat'

const props = defineProps({
  kaynaklar: { type: Object, default: () => ({}) },
  yukleniyor: { type: Boolean, default: false },
})

const kategoriler = computed(() => kaynaklariDiziye(props.kaynaklar))

const TON = {
  danger: 'text-danger',
  warn: 'text-warn',
  neutral: 'text-text',
}
</script>

<template>
  <div v-if="yukleniyor" class="flex flex-col gap-1.5 py-1">
    <span v-for="i in 3" :key="i" class="h-4 rounded-md bg-surface-2 motion-safe:animate-pulse" />
    <span class="sr-only">Kaynaklar yükleniyor…</span>
  </div>

  <EmptyState
    v-else-if="!kategoriler.length"
    compact
    icon="inventory_2"
    title="Ortak stok yok"
    text="Grubun ortak deposu bilerek boş başlar. Bir topluluğa katılınca ya da sayım yapınca (“envanteri sayalım” yazarak) burada dolmaya başlar. Kişisel eşyalar kadro kartlarında durur."
  />

  <div v-else class="flex flex-col gap-3">
    <section v-for="kategori in kategoriler" :key="kategori.kategori" class="flex flex-col gap-1">
      <h3 class="text-panel uppercase tracking-[0.06em] text-faint">{{ kategori.kategori }}</h3>
      <ul class="flex flex-col gap-0.5">
        <li
          v-for="kalem in kategori.kalemler"
          :key="kalem.ad"
          class="flex items-baseline gap-2 rounded-md px-1 py-0.5 text-meta"
        >
          <span class="min-w-0 flex-1">
            <span class="text-text">{{ kalem.ad }}</span>
            <span v-if="kalem.not" class="ml-1 text-label text-faint">{{ kalem.not }}</span>
          </span>
          <span class="shrink-0 text-label nums-tabular" :class="TON[kaynakTonu(kalem)]">
            {{ kalem.birim ? `${kalem.miktar} ${kalem.birim}` : kalem.miktar }}
          </span>
          <Icon
            v-if="kaynakTonu(kalem) === 'danger'"
            name="warning"
            :size="13"
            class="shrink-0 text-danger"
            label="tükendi"
          />
        </li>
      </ul>
    </section>
  </div>
</template>
