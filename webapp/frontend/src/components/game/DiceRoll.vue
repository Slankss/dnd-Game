<script setup>
/**
 * Zar animasyonu — seçenek seçildiği anda dönen d100.
 *
 * Zar SUNUCUDA atılır (kriptografik RNG); buradaki animasyon sadece sonucu
 * SUNAR: ~900 ms boyunca rastgele sayılar döner, sonra gerçek sonuca oturur.
 * Sonuç asla animasyondan üretilmez — `deger` neyse o gösterilir.
 *
 * `prefers-reduced-motion` açıksa dönme atlanır, sonuç doğrudan yazılır.
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import Icon from '../ui/Icon.vue'

const props = defineProps({
  /** Sunucudan gelen gerçek zar (1-100) */
  deger: { type: Number, default: null },
  /** Bant adı: Felaket / Başarısız / … */
  bant: { type: String, default: '' },
  /** Aynı zar tekrar oynatılmasın diye değişen bir anahtar (ör. ts) */
  anahtar: { type: [String, Number], default: 0 },
  size: { type: String, default: 'md', validator: (v) => ['sm', 'md', 'lg'].includes(v) },
})

const emit = defineEmits(['bitti'])

/** Bant → renk tonu. Felaket kırmızı, kritik altın. */
const BANT_TONU = {
  Felaket: 'text-danger border-danger/45 bg-danger-soft',
  Başarısız: 'text-warn border-warn/45 bg-warn-soft',
  'Kısmi Başarı': 'text-warn border-warn/40 bg-warn-soft',
  Başarı: 'text-ok border-ok/45 bg-ok-soft',
  'Güçlü Başarı': 'text-ok border-ok/50 bg-ok-soft',
  Kritik: 'text-accent border-accent/55 bg-accent-soft',
}

const OLCU = {
  sm: 'h-8 min-w-12 text-meta',
  md: 'h-10 min-w-14 text-scene',
  lg: 'h-14 min-w-20 text-[1.5rem]',
}

const gosterilen = ref(props.deger)
const donuyor = ref(false)
let zamanlayici = null
let bitis = null

const azHareket = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function temizle() {
  clearInterval(zamanlayici)
  clearTimeout(bitis)
  zamanlayici = null
  bitis = null
}

function oynat(sonuc) {
  temizle()
  if (sonuc === null || sonuc === undefined) {
    gosterilen.value = null
    return
  }
  if (azHareket()) {
    gosterilen.value = sonuc
    donuyor.value = false
    emit('bitti', sonuc)
    return
  }
  donuyor.value = true
  zamanlayici = setInterval(() => {
    gosterilen.value = 1 + Math.floor(Math.random() * 100)
  }, 55)
  bitis = setTimeout(() => {
    temizle()
    gosterilen.value = sonuc
    donuyor.value = false
    emit('bitti', sonuc)
  }, 900)
}

watch(
  () => [props.deger, props.anahtar],
  () => oynat(props.deger),
  { immediate: true },
)

onUnmounted(temizle)

const siniflar = computed(() => [
  'inline-flex items-center justify-center gap-1.5 rounded-card border px-2 font-semibold nums-tabular',
  OLCU[props.size],
  donuyor.value ? 'border-border bg-surface-2 text-muted' : BANT_TONU[props.bant] || 'border-border bg-surface-2 text-text',
  donuyor.value ? 'motion-safe:animate-pulse' : '',
])
</script>

<template>
  <span
    :class="siniflar"
    role="status"
    :aria-label="donuyor ? 'Zar atılıyor' : `Zar ${deger}${bant ? ', ' + bant : ''}`"
  >
    <Icon
      name="casino"
      :size="size === 'lg' ? 20 : 15"
      :class="donuyor ? 'motion-safe:animate-spin' : ''"
    />
    <span>{{ gosterilen ?? '—' }}</span>
    <span v-if="!donuyor && bant" class="text-label font-medium opacity-80">{{ bant }}</span>
  </span>
</template>
