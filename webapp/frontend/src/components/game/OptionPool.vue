<script setup>
/**
 * Seçenek havuzu — bir karakterin bu turdaki 5-10 seçeneği.
 *
 * Akış: karakter seçilir → kart seçilir → sunucu zarı ATAR → zar animasyonla
 * gösterilir → seçim turda kilitlenir (zar atıldıktan sonra geri alınamaz).
 * Seçim modele HEMEN gitmez; herkes seçince tur toplu gönderilir.
 *
 * SERBEST HAMLE YOKTUR: hikaye yalnız sunulan tercihlerle ilerler. Hiçbiri
 * uymuyorsa tek çıkış "bu turda bekle"dir — sunucu her listede en az bir
 * düşük riskli seçenek bulunmasını garanti eder.
 *
 * Kategoriler sadece etiket değil: her biri farklı bir takas vaat eder ve
 * seçim havuza not edilir (oyun bundan öğrenir).
 */
import { ref, computed, watch } from 'vue'
import Panel from '../ui/Panel.vue'
import Badge from '../ui/Badge.vue'
import Icon from '../ui/Icon.vue'
import BaseButton from '../ui/BaseButton.vue'
import EmptyState from '../ui/EmptyState.vue'
import DiceRoll from './DiceRoll.vue'
import { KATEGORI_TONU, KATEGORI_IKONU } from './gameFormat'
import { colorFor } from '@/utils/characterColors'

const props = defineProps({
  /** Seçim yapan karakter */
  oyuncu: { type: String, default: '' },
  /** [{id, text, category, cost}] */
  secenekler: { type: Array, default: () => [] },
  /** Bu karakter zaten seçtiyse seçim kaydı */
  secim: { type: Object, default: null },
  /** Seçim isteği uçuşta mı */
  mesgul: { type: Boolean, default: false },
  /** Tur açık mı */
  turAcik: { type: Boolean, default: true },
  /** Son atılan zar (store.lastRoll) — animasyonu bu tetikler */
  sonZar: { type: Object, default: null },
})

const emit = defineEmits(['sec', 'bekle'])

const secilenId = ref('')

/** Karakter değişince seçim vurgusu sıfırlanır. */
watch(
  () => props.oyuncu,
  () => {
    secilenId.value = ''
  },
)

const secildi = computed(() => !!props.secim)
const kilitli = computed(() => secildi.value || props.mesgul || !props.turAcik)

/** Zar animasyonu: sadece bu karakterin kendi zarı için oynasın. */
const zar = computed(() => {
  if (props.sonZar?.player === props.oyuncu) return props.sonZar
  if (props.secim?.roll != null) {
    return { roll: props.secim.roll, band: props.secim.band, ts: props.secim.ts }
  }
  return null
})

const kategoriSayisi = computed(
  () => new Set(props.secenekler.map((s) => s.category)).size,
)

function sec(secenek) {
  if (kilitli.value) return
  secilenId.value = secenek.id
  emit('sec', secenek)
}
</script>

<template>
  <Panel icon="playing_cards" :title="`${oyuncu || 'Karakter'} — seçenekler`">
    <template #actions>
      <Badge v-if="secenekler.length" tone="muted" size="sm">
        {{ secenekler.length }} seçenek · {{ kategoriSayisi }} kategori
      </Badge>
    </template>

    <!-- Seçim yapıldıysa: zar + kilit -->
    <div
      v-if="secildi"
      class="mb-3 flex flex-wrap items-center gap-2 rounded-card border border-border bg-surface-2 p-2.5"
    >
      <span
        class="size-2.5 shrink-0 rounded-full"
        :style="{ backgroundColor: colorFor(oyuncu) }"
        aria-hidden="true"
      />
      <DiceRoll :deger="zar?.roll ?? null" :bant="zar?.band ?? ''" :anahtar="zar?.ts ?? 0" />
      <Badge
        v-if="secim.category"
        :tone="KATEGORI_TONU[secim.category] || 'neutral'"
        :icon="KATEGORI_IKONU[secim.category] || 'bolt'"
        size="sm"
      >
        {{ secim.category }}
      </Badge>
      <p class="w-full text-meta text-text">{{ secim.text }}</p>
      <p class="flex items-center gap-1.5 text-label text-faint">
        <Icon name="lock" :size="13" />
        Zar atıldı — bu seçim değiştirilemez. Diğer oyuncular da seçince tur gönderilecek.
      </p>
    </div>

    <!-- Seçenek kartları -->
    <template v-else>
      <EmptyState
        v-if="!secenekler.length"
        compact
        icon="hourglass_empty"
        title="Seçenek yok"
        text="Anlatıcı bu karakter için henüz seçenek üretmedi — sahne yenilendiğinde görünecek."
      />
      <ul v-else class="flex flex-col gap-1.5">
        <li v-for="secenek in secenekler" :key="secenek.id">
          <button
            type="button"
            class="flex w-full flex-col gap-1 rounded-card border border-border bg-surface-2 p-2.5 text-left transition-colors duration-[var(--duration-fast)] hover:border-accent/50 hover:bg-surface-3 disabled:opacity-50 disabled:hover:border-border disabled:hover:bg-surface-2"
            :class="secilenId === secenek.id ? 'border-accent/70 ring-1 ring-accent/40' : ''"
            :disabled="kilitli"
            @click="sec(secenek)"
          >
            <span class="flex flex-wrap items-center gap-1.5">
              <Badge
                :tone="KATEGORI_TONU[secenek.category] || 'neutral'"
                :icon="KATEGORI_IKONU[secenek.category] || 'bolt'"
                size="sm"
              >
                {{ secenek.category }}
              </Badge>
              <span v-if="secenek.cost" class="text-label text-faint">
                bedel: {{ secenek.cost }}
              </span>
            </span>
            <span class="text-meta leading-relaxed text-text">{{ secenek.text }}</span>
          </button>
        </li>
      </ul>

      <!-- Tek çıkış: bu turda bekle. Serbest hamle yok. -->
      <div class="mt-2 flex flex-wrap items-center gap-2">
        <BaseButton
          size="sm"
          variant="subtle"
          icon="hourglass_empty"
          :disabled="kilitli"
          :loading="mesgul"
          loading-text="Zar atılıyor…"
          @click="$emit('bekle')"
        >
          Bu turda bekle
        </BaseButton>
        <p class="text-label text-faint">
          Hikaye yalnız sunulan seçeneklerle ilerler — kendi planını yazamazsın.
        </p>
      </div>

    </template>
  </Panel>
</template>
