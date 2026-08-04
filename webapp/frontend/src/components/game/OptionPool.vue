<script setup>
/**
 * Seçenek havuzu — bir karakterin bu turdaki 5-10 seçeneği.
 *
 * Akış: "Kararını seç" → seçenek POPUP'ı açılır → bir kart seçilir → popup
 * KENDİLİĞİNDEN kapanır → seçilen karar panelde AKTİF olarak durur. Zar
 * seçim anında sunucuda atılır ve burada animasyonla gösterilir.
 *
 * TUR İLERLEMEZ: seçim yapmak turu göndermez. Oyuncu "Turu Geç"e basana kadar
 * kararını istediği kadar değiştirebilir; turda SON seçtiği karar işlenir.
 * Zar tur başına bir kez atıldığı için karar değiştirmek zar atmak değildir.
 *
 * SERBEST HAMLE YOKTUR: hikaye yalnız sunulan tercihlerle ilerler. Hiçbiri
 * uymuyorsa tek çıkış "bu turda bekle"dir — sunucu her listede en az bir
 * düşük riskli seçenek bulunmasını garanti eder.
 */
import { ref, computed, watch } from 'vue'
import Panel from '../ui/Panel.vue'
import Modal from '../ui/Modal.vue'
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
  /** Bu karakter seçim yaptıysa seçim kaydı (değiştirilebilir) */
  secim: { type: Object, default: null },
  /** Seçim isteği uçuşta mı */
  mesgul: { type: Boolean, default: false },
  /** Tur açık mı */
  turAcik: { type: Boolean, default: true },
  /** Son atılan zar (store.lastRoll) — animasyonu bu tetikler */
  sonZar: { type: Object, default: null },
})

const emit = defineEmits(['sec', 'bekle'])

/** Seçenek popup'ı açık mı. */
const acik = ref(false)

/** Karakter değişince popup kapanır (başkasının listesi açık kalmasın). */
watch(
  () => props.oyuncu,
  () => {
    acik.value = false
  },
)

const secildi = computed(() => !!props.secim)
/** Bekleme de bir seçimdir ama havuzdaki bir seçeneğe karşılık gelmez. */
const bekliyor = computed(() => secildi.value && !props.secim.option_id)
const kilitli = computed(() => props.mesgul || !props.turAcik)

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

/** Seçim → popup KAPANIR, karar panelde aktif kalır. */
function sec(secenek) {
  if (kilitli.value) return
  acik.value = false
  emit('sec', secenek)
}

function bekle() {
  if (kilitli.value) return
  acik.value = false
  emit('bekle')
}
</script>

<template>
  <Panel icon="playing_cards" :title="`${oyuncu || 'Karakter'} — kararın`">
    <template #actions>
      <Badge v-if="secenekler.length" tone="muted" size="sm">
        {{ secenekler.length }} seçenek · {{ kategoriSayisi }} kategori
      </Badge>
    </template>

    <!-- Seçilen karar: popup kapandıktan sonra burada AKTİF durur -->
    <div
      v-if="secildi"
      class="mb-2 flex flex-wrap items-center gap-2 rounded-card border border-accent/50 bg-accent-soft p-2.5"
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
      <Badge tone="ok" icon="check_circle" size="sm">seçili</Badge>
      <p class="w-full text-meta text-text">
        {{ bekliyor ? 'Bu turda bekliyorsun — hamle yapmıyorsun.' : secim.text }}
      </p>
      <p class="flex w-full items-center gap-1.5 text-label text-faint">
        <Icon name="edit" :size="13" />
        Turu geçene kadar kararını değiştirebilirsin; son seçtiğin karar işlenir.
      </p>
    </div>

    <EmptyState
      v-else-if="!secenekler.length"
      compact
      icon="hourglass_empty"
      title="Seçenek yok"
      text="Anlatıcı bu karakter için henüz seçenek üretmedi — sahne yenilendiğinde görünecek."
    />

    <!-- Popup'ı açan düğme + tek çıkış: bu turda bekle -->
    <div class="flex flex-wrap items-center gap-2">
      <BaseButton
        v-if="secenekler.length"
        size="sm"
        :variant="secildi ? 'subtle' : 'primary'"
        :icon="secildi ? 'edit' : 'playing_cards'"
        :disabled="kilitli"
        @click="acik = true"
      >
        {{ secildi ? 'Kararı değiştir' : 'Kararını seç' }}
      </BaseButton>
      <BaseButton
        v-if="!bekliyor"
        size="sm"
        variant="subtle"
        icon="hourglass_empty"
        :disabled="kilitli"
        :loading="mesgul"
        loading-text="Zar atılıyor…"
        @click="bekle"
      >
        Bu turda bekle
      </BaseButton>
      <p v-if="!secildi" class="text-label text-faint">
        Hikaye yalnız sunulan seçeneklerle ilerler — kendi planını yazamazsın.
      </p>
    </div>

    <!-- Seçenek popup'ı: karar seçilince kendiliğinden kapanır -->
    <Modal v-model="acik" size="lg" icon="playing_cards" :title="`${oyuncu} — seçenekler`">
      <ul class="flex flex-col gap-1.5">
        <li v-for="secenek in secenekler" :key="secenek.id">
          <button
            type="button"
            class="flex w-full flex-col gap-1 rounded-card border border-border bg-surface-2 p-2.5 text-left transition-colors duration-[var(--duration-fast)] hover:border-accent/50 hover:bg-surface-3 disabled:opacity-50 disabled:hover:border-border disabled:hover:bg-surface-2"
            :class="secim?.option_id === secenek.id ? 'border-accent/70 ring-1 ring-accent/40' : ''"
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
              <Badge v-if="secim?.option_id === secenek.id" tone="ok" size="sm">seçili</Badge>
            </span>
            <span class="text-meta leading-relaxed text-text">{{ secenek.text }}</span>
          </button>
        </li>
      </ul>

      <template #footer>
        <p class="mr-auto text-label text-faint">
          Karar seçince bu pencere kapanır. Tur, sen "Turu Geç"e basana kadar ilerlemez.
        </p>
        <BaseButton size="sm" variant="subtle" icon="hourglass_empty" @click="bekle">
          Bu turda bekle
        </BaseButton>
      </template>
    </Modal>
  </Panel>
</template>
