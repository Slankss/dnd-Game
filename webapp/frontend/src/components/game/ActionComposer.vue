<script setup>
/**
 * Aksiyon yazma alanı — akışın ÜSTÜNDE sabit durur (docs §4).
 *
 *   [Kimsin? ▾ chip'ler]  ne yapıyorsun…            [Gönder]
 *
 * Klavye: `Enter` gönderir, `Shift+Enter` satır atlar (docs §7).
 * Gönderim sırasında her şey kilitlenir ve geçen süre sayılır — model yanıtı
 * 30-60 sn sürebiliyor, kullanıcı ekranın donmadığını görmeli.
 */
import { ref, computed, watch, onUnmounted, nextTick, useId } from 'vue'
import Icon from '../ui/Icon.vue'
import BaseButton from '../ui/BaseButton.vue'
import { enterGonderir } from '@/composables/useKeyboard'
import { colorFor } from '@/utils/characterColors'

const props = defineProps({
  /** Hayatta olan karakter adları */
  kadro: { type: Array, default: () => [] },
  /** Seçili oyuncu: karakter adı ya da grup etiketi */
  secili: { type: String, default: '' },
  /** Sunucudaki grup etiketi (`__grup_ortak_karar__`) */
  grupEtiketi: { type: String, default: '' },
  /** Grup seçeneğinin ekranda görünen adı */
  grupAdi: { type: String, default: 'Ortak Karar (Grup)' },
  /** Tur gönderimi sürüyor mu */
  gonderiliyor: { type: Boolean, default: false },
  /** Karakter oluşturma turu bitti mi (bitmediyse zar atılmaz) */
  chargenBitti: { type: Boolean, default: true },
  /** Başka bir işlem (başlatma/devralma) yüzünden kilitli mi */
  kilitli: { type: Boolean, default: false },
})

const emit = defineEmits(['update:secili', 'gonder'])

const metin = ref('')
const alan = ref(null)
const alanKimlik = useId()

const grupSecili = computed(() => props.secili && props.secili === props.grupEtiketi)
const kadroYok = computed(() => props.kadro.length === 0)

const etkisiz = computed(() => props.gonderiliyor || props.kilitli || kadroYok.value)
const gonderilebilir = computed(() => metin.value.trim().length > 0 && !etkisiz.value && !!props.secili)

const yerTutucu = computed(() => {
  if (kadroYok.value) return 'Hayatta karakter yok — devralma bekleniyor.'
  if (grupSecili.value) return 'Grup olarak ne yapıyorsunuz? (ortak karar — tek zar atılır)'
  return 'Ne yapıyorsun?'
})

function sec(ad) {
  if (props.gonderiliyor) return
  emit('update:secili', ad)
  nextTick(() => alan.value?.focus())
}

function gonder() {
  if (!gonderilebilir.value) return
  emit('gonder', { oyuncu: props.secili, metin: metin.value.trim() })
}

/** Gönderim başarıyla bittiğinde alanı temizlemesi için PlayerView çağırır. */
function temizle() {
  metin.value = ''
}

defineExpose({ temizle, odaklan: () => alan.value?.focus() })

const tuslar = enterGonderir(gonder)

/* --- geçen süre sayacı: "anlatıcı düşünüyor… 24 sn" --- */
const gecenSaniye = ref(0)
let sayac = null

watch(
  () => props.gonderiliyor,
  (aktif) => {
    clearInterval(sayac)
    if (!aktif) return
    gecenSaniye.value = 0
    sayac = setInterval(() => {
      gecenSaniye.value += 1
    }, 1000)
  },
)

onUnmounted(() => clearInterval(sayac))

/** Metin alanı içeriğe göre büyüsün (uzun planlar tek satıra sıkışmasın). */
function boyutla(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 240)}px`
}

function chipStili(ad) {
  const c = colorFor(ad)
  return {
    '--kr': c,
    '--kr-soft': `color-mix(in oklab, ${c} 18%, transparent)`,
  }
}
</script>

<template>
  <section
    class="rounded-panel border border-border bg-surface p-2.5 shadow-[var(--shadow-float)]"
    aria-label="Aksiyon gönder"
  >
    <!-- Kimsin? -->
    <div class="mb-2 flex flex-wrap items-center gap-1.5">
      <span class="mr-0.5 text-panel uppercase tracking-[0.06em] text-faint">Kimsin?</span>

      <button
        v-for="ad in kadro"
        :key="ad"
        type="button"
        class="inline-flex h-7 items-center gap-1.5 rounded-chip border px-2.5 text-label transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)] disabled:opacity-45"
        :class="
          secili === ad
            ? 'border-[var(--kr)] bg-[var(--kr-soft)] text-text'
            : 'border-border bg-surface-2 text-muted hover:text-text'
        "
        :style="chipStili(ad)"
        :aria-pressed="secili === ad"
        :disabled="gonderiliyor"
        @click="sec(ad)"
      >
        <span class="size-1.5 rounded-full bg-[var(--kr)]" aria-hidden="true" />
        {{ ad }}
      </button>

      <template v-if="grupEtiketi">
        <span class="mx-0.5 h-4 w-px bg-border" aria-hidden="true" />
        <button
          type="button"
          class="inline-flex h-7 items-center gap-1.5 rounded-chip border px-2.5 text-label transition-colors duration-[var(--duration-fast)] disabled:opacity-45"
          :class="
            grupSecili
              ? 'border-accent/60 bg-accent-soft text-accent'
              : 'border-border bg-surface-2 text-muted hover:text-text'
          "
          :aria-pressed="grupSecili"
          :disabled="gonderiliyor"
          :title="
            chargenBitti
              ? 'Mesajı tek bir karakterin değil, tüm grubun ortak kararı olarak gönder'
              : 'Grup olarak yaz — karakter oluşturma sürerken zar atılmaz'
          "
          @click="sec(grupEtiketi)"
        >
          <Icon name="groups" :size="14" />
          {{ grupAdi }}
        </button>
      </template>
    </div>

    <!-- Metin + gönder -->
    <div class="flex items-end gap-2">
      <label :for="alanKimlik" class="sr-only">Aksiyon metni</label>
      <textarea
        :id="alanKimlik"
        ref="alan"
        v-model="metin"
        rows="2"
        :placeholder="yerTutucu"
        :disabled="etkisiz"
        class="min-h-[3.25rem] w-full resize-none rounded-card border border-border bg-surface-2 px-3 py-2 text-meta leading-relaxed text-text placeholder:text-faint focus-visible:border-accent/60 disabled:opacity-60"
        @keydown="tuslar"
        @input="boyutla"
      />
      <BaseButton
        variant="primary"
        size="lg"
        icon="send"
        :disabled="!gonderilebilir"
        :loading="gonderiliyor"
        loading-text="Gönderiliyor…"
        @click="gonder"
      >
        Gönder
      </BaseButton>
    </div>

    <!-- İpucu satırı / ilerleme göstergesi -->
    <p
      v-if="gonderiliyor"
      class="mt-2 flex items-center gap-2 text-label text-accent"
      role="status"
      aria-live="polite"
    >
      <Icon name="progress_activity" :size="14" class="motion-safe:animate-spin" />
      Zar atıldı, anlatıcı sahneyi yazıyor…
      <span class="nums-tabular text-muted">{{ gecenSaniye }} sn</span>
      <span class="text-faint">— 30-60 saniye sürebilir, sayfayı kapatma.</span>
    </p>
    <p v-else-if="kadroYok" class="mt-2 flex items-center gap-1.5 text-label text-danger">
      <Icon name="person_off" :size="14" />
      Hayatta karakter kalmadı. Aşağıdaki devralma bandından yeni bir karakter seç.
    </p>
    <p v-else class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-label text-faint">
      <span class="inline-flex items-center gap-1">
        <Icon name="keyboard" :size="13" />
        Enter gönderir · Shift+Enter satır atlar
      </span>
      <span v-if="!grupSecili" class="inline-flex items-center gap-1">
        <Icon name="group_add" :size="13" />
        Birden fazla karakter için her satıra “İsim: aksiyon” yaz
      </span>
      <span v-if="!chargenBitti" class="inline-flex items-center gap-1 text-warn">
        <Icon name="badge" :size="13" />
        Karakter oluşturma sürüyor — bu turlarda zar atılmaz
      </span>
    </p>
  </section>
</template>
