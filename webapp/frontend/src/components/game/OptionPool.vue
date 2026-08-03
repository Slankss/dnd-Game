<script setup>
/**
 * Seçenek havuzu — bir karakterin bu turdaki 5-10 seçeneği.
 *
 * Akış: karakter seçilir → kart seçilir → sunucu zarı ATAR → zar animasyonla
 * gösterilir → seçim turda kilitlenir (zar atıldıktan sonra geri alınamaz).
 * Seçim modele HEMEN gitmez; herkes seçince tur toplu gönderilir.
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

const emit = defineEmits(['sec', 'kendiHamlesi', 'bekle'])

const serbestAcik = ref(false)
const serbestMetin = ref('')
const secilenId = ref('')

/** Karakter değişince form sıfırlanır. */
watch(
  () => props.oyuncu,
  () => {
    serbestAcik.value = false
    serbestMetin.value = ''
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

function kendiHamlesiniGonder() {
  const metin = serbestMetin.value.trim()
  if (!metin || kilitli.value) return
  emit('kendiHamlesi', metin)
  serbestMetin.value = ''
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

      <!-- Kendi hamlesi -->
      <div class="mt-2 flex flex-col gap-2">
        <BaseButton
          v-if="!serbestAcik"
          size="sm"
          variant="subtle"
          icon="edit"
          :disabled="kilitli"
          @click="serbestAcik = true"
        >
          Kendi hamleni yaz — listeyle sınırlı değilsin
        </BaseButton>

        <template v-else>
          <textarea
            v-model="serbestMetin"
            rows="2"
            placeholder="Ne yapıyorsun? (senaryonun dışına çıkma — anlatıcı zar ile çözecek)"
            :disabled="kilitli"
            class="w-full resize-none rounded-card border border-border bg-surface-2 px-3 py-2 text-meta leading-relaxed text-text placeholder:text-faint focus-visible:border-accent/60 disabled:opacity-60"
          />
          <div class="flex flex-wrap gap-2">
            <BaseButton
              size="sm"
              variant="primary"
              icon="casino"
              :disabled="!serbestMetin.trim() || kilitli"
              :loading="mesgul"
              loading-text="Zar atılıyor…"
              @click="kendiHamlesiniGonder"
            >
              Zarı at ve kilitle
            </BaseButton>
            <BaseButton size="sm" variant="subtle" :disabled="mesgul" @click="serbestAcik = false">
              Vazgeç
            </BaseButton>
            <BaseButton
              size="sm"
              variant="quiet"
              icon="hourglass_empty"
              :disabled="kilitli"
              @click="$emit('bekle')"
            >
              Bu turda bekle
            </BaseButton>
          </div>
        </template>
      </div>
    </template>
  </Panel>
</template>
