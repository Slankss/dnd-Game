<script setup>
/**
 * Seçenek havuzu — bir karakterin bu turdaki 3-8 seçeneği (sayı sabit değil;
 * sahne kaç farklı akla yatkın karara izin veriyorsa o kadarı gelir).
 *
 * POPUP olarak açılır: sahnenin altındaki "Karar Ver" butonu bunu tetikler
 * (bkz. PlayerView). Oyuncu istediği an kapatıp anlatıcı metnini tekrar
 * okuyabilir, sonra aynı butonla yeniden açıp karar verebilir — bu yüzden
 * kapatmak seçimi iptal etmez, sadece pencereyi gizler.
 *
 * Akış: karakter seçilir → kart seçilir → sunucu zarı ATAR → zar animasyonla
 * gösterilir → seçim turda kilitlenir (zar atıldıktan sonra geri alınamaz).
 * Seçim modele HEMEN gitmez; herkes seçince tur toplu gönderilir.
 *
 * SERBEST HAMLE YOKTUR: hikaye yalnız sunulan tercihlerle ilerler. Hiçbiri
 * uymuyorsa tek çıkış "bu turda bekle"dir — sunucu her listede en az bir
 * düşük riskli seçenek bulunmasını garanti eder.
 *
 * Her seçeneğin sunucu tarafında bir `category`/`cost` alanı vardır (öğrenme
 * katmanı ve anlatıcı ekranı bundan ders çıkarır) ama bu OYUNCUYA ASLA
 * GÖSTERİLMEZ — "Güvenli"/"Riskli"/"Önerilen" gibi hiçbir etiket, puan ya da
 * ipucu burada render edilmez; oyuncu bir seçeneğin ne getireceğini SADECE
 * `text`'in kendisinden ve sahnenin bağlamından çıkarabilmeli.
 */
import { ref, computed, watch } from 'vue'
import Modal from '../ui/Modal.vue'
import Icon from '../ui/Icon.vue'
import BaseButton from '../ui/BaseButton.vue'
import EmptyState from '../ui/EmptyState.vue'
import DiceRoll from './DiceRoll.vue'
import { colorFor } from '@/utils/characterColors'

const props = defineProps({
  /** Popup açık mı */
  modelValue: { type: Boolean, default: false },
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

const emit = defineEmits(['update:modelValue', 'sec', 'bekle'])

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

function sec(secenek) {
  if (kilitli.value) return
  secilenId.value = secenek.id
  emit('sec', secenek)
}
</script>

<template>
  <Modal
    :model-value="modelValue"
    size="lg"
    icon="playing_cards"
    :title="
      secenekler.length
        ? `${oyuncu || 'Karakter'} — seçenekler (${secenekler.length})`
        : `${oyuncu || 'Karakter'} — seçenekler`
    "
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <!-- Seçim yapıldıysa: zar + kilit -->
    <div
      v-if="secildi"
      class="flex flex-wrap items-center gap-2 rounded-card border border-border bg-surface-2 p-2.5"
    >
      <span
        class="size-2.5 shrink-0 rounded-full"
        :style="{ backgroundColor: colorFor(oyuncu) }"
        aria-hidden="true"
      />
      <DiceRoll :deger="zar?.roll ?? null" :bant="zar?.band ?? ''" :anahtar="zar?.ts ?? 0" />
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
            <span class="text-meta leading-relaxed text-text">{{ secenek.text }}</span>
          </button>
        </li>
      </ul>

      <!-- Tek çıkış: bu turda bekle. Serbest hamle yok. -->
      <div v-if="secenekler.length" class="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3">
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
  </Modal>
</template>
