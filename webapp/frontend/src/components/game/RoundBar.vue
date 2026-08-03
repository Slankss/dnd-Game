<script setup>
/**
 * Tur çubuğu — kim seçti, ne kadar süre kaldı, tur ne zaman gönderilecek.
 *
 * Süre sunucunun saatine göre işler: store `clockSkew` ile istemci saatinin
 * farkını ölçüyor, burada sadece geri sayılıyor. Süre bittiğinde tur
 * KENDİLİĞİNDEN gönderilir (`sure` gerekçesiyle) — seçim yapmayanlar için
 * anlatıcı "ani sahne" yazar. Aynı turu iki tarayıcı birden göndermeye
 * kalkarsa sunucu ikincisini `skipped` ile geri çevirir.
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import BaseButton from '../ui/BaseButton.vue'
import { colorFor } from '@/utils/characterColors'
import { zarTonu } from './gameFormat'

const props = defineProps({
  /** public_round çıktısı */
  tur: { type: Object, default: null },
  /** Sunucu-istemci saat farkı (ms) */
  kayma: { type: Number, default: 0 },
  /** Tur gönderimi uçuşta mı */
  gonderiliyor: { type: Boolean, default: false },
  /** Süre dolunca otomatik gönderilsin mi (tek sekme yeter, hepsi denerse
      sunucu fazlasını eler) */
  otomatikGonder: { type: Boolean, default: true },
})

const emit = defineEmits(['gonder'])

const simdi = ref(Date.now())
let sayac = null

onMounted(() => {
  sayac = setInterval(() => (simdi.value = Date.now()), 500)
})
onUnmounted(() => clearInterval(sayac))

const acik = computed(() => props.tur?.status === 'acik')
const seciler = computed(() => Object.values(props.tur?.picks || {}))
const bekleyenler = computed(() => props.tur?.waiting || [])
const kadro = computed(() => props.tur?.actors || [])
const hepsiSecti = computed(() => !!props.tur?.all_picked)

/** Kalan saniye — süre yoksa null. */
const kalan = computed(() => {
  const bitis = props.tur?.deadline_ts
  if (!bitis || !acik.value) return null
  return Math.max(0, Math.round((bitis * 1000 + props.kayma - simdi.value) / 1000))
})

const sureDoldu = computed(() => kalan.value !== null && kalan.value <= 0)

const sureMetni = computed(() => {
  if (kalan.value === null) return ''
  const dk = Math.floor(kalan.value / 60)
  const sn = kalan.value % 60
  return `${dk}:${String(sn).padStart(2, '0')}`
})

const sureTonu = computed(() => {
  if (kalan.value === null) return 'muted'
  if (kalan.value <= 15) return 'danger'
  if (kalan.value <= 45) return 'warn'
  return 'muted'
})

/** İlerleme çubuğu: seçim yapanların oranı. */
const oran = computed(() => {
  if (!kadro.value.length) return 0
  return Math.round((seciler.value.length / kadro.value.length) * 100)
})

/* --- otomatik gönderim: herkes seçtiğinde ya da süre dolduğunda --- */
let gonderildi = null

function gonder(neden) {
  if (props.gonderiliyor || !acik.value) return
  if (gonderildi === props.tur?.no && neden !== 'elle') return
  gonderildi = props.tur?.no
  emit('gonder', neden)
}

watch([hepsiSecti, sureDoldu, acik], () => {
  if (!props.otomatikGonder || !acik.value) return
  if (hepsiSecti.value) gonder('elle')
  else if (sureDoldu.value && seciler.value.length) gonder('sure')
})

// Yeni tur açıldığında otomatik gönderim kilidi sıfırlanır.
watch(
  () => props.tur?.no,
  () => {
    gonderildi = null
  },
)
</script>

<template>
  <section
    v-if="tur && tur.no"
    class="rounded-panel border border-border bg-surface p-2.5 shadow-[var(--shadow-panel)]"
    aria-label="Tur durumu"
  >
    <div class="flex flex-wrap items-center gap-2">
      <Badge tone="accent" icon="hourglass_top" size="sm">Tur {{ tur.no }}</Badge>

      <Badge v-if="kalan !== null" :tone="sureTonu" icon="timer" size="sm">
        <span class="nums-tabular">{{ sureMetni }}</span>
      </Badge>
      <Badge v-else tone="muted" icon="timer_off" size="sm">süresiz</Badge>

      <span class="text-label text-faint">
        {{ seciler.length }}/{{ kadro.length }} seçim yapıldı
      </span>

      <BaseButton
        v-if="acik"
        class="ml-auto"
        size="sm"
        variant="primary"
        icon="send"
        :disabled="!seciler.length"
        :loading="gonderiliyor"
        loading-text="Tur gönderiliyor…"
        @click="gonder('elle')"
      >
        Turu şimdi gönder
      </BaseButton>
      <Badge v-else-if="gonderiliyor" tone="accent" icon="progress_activity" size="sm">
        anlatıcı yazıyor
      </Badge>
    </div>

    <!-- ilerleme -->
    <div class="mt-2 h-1 w-full overflow-hidden rounded-full bg-surface-2">
      <div
        class="h-full rounded-full bg-accent transition-[width] duration-[var(--duration-base)]"
        :style="{ width: `${oran}%` }"
      />
    </div>

    <!-- kim seçti / kim bekleniyor -->
    <div class="mt-2 flex flex-wrap items-center gap-1.5">
      <span
        v-for="secim in seciler"
        :key="secim.player"
        class="inline-flex items-center gap-1 rounded-chip border border-border bg-surface-2 px-2 py-0.5 text-label"
        :title="secim.text"
      >
        <span
          class="size-1.5 rounded-full"
          :style="{ backgroundColor: colorFor(secim.player) }"
          aria-hidden="true"
        />
        {{ secim.player }}
        <Badge :tone="zarTonu(secim.band)" size="sm">
          <span class="nums-tabular">{{ secim.roll }}</span>
        </Badge>
      </span>

      <span
        v-for="ad in bekleyenler"
        :key="ad"
        class="inline-flex items-center gap-1 rounded-chip border border-dashed border-border px-2 py-0.5 text-label text-faint"
      >
        <Icon name="more_horiz" :size="13" />
        {{ ad }} bekleniyor
      </span>
    </div>

    <p v-if="sureDoldu && bekleyenler.length" class="mt-2 flex items-center gap-1.5 text-label text-warn">
      <Icon name="bolt" :size="13" />
      Süre doldu — seçim yapmayanlar için ani sahne yazılacak.
    </p>
  </section>
</template>
