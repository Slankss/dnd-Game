<script setup>
/**
 * Kare harita paneli — sahne ızgarası + hareket tuşları.
 *
 * Hareketin kendisi SUNUCUDA çözülür (`/api/grid/move`): yön → yeni koordinat
 * → sınır → geçilebilirlik → eski kareden kaldır → koordinatı güncelle → yeni
 * kareye ekle → sonuç. Burada yalnız yön gönderilir ve dönen sonuç gösterilir;
 * arayüz hiçbir koordinatı kendi başına hesaplamaz.
 *
 * Klavye: ızgara odaktayken ok tuşları seçili karakteri hareket ettirir.
 */
import { computed, ref } from 'vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import BaseButton from '../ui/BaseButton.vue'
import Modal from '../ui/Modal.vue'
import GridCanvas from './GridCanvas.vue'
import { colorFor } from '@/utils/characterColors'

const props = defineProps({
  izgara: { type: Object, default: null },
  /** Hareket ettirilecek karakter */
  oyuncu: { type: String, default: '' },
  /** Hareket isteği uçuşta mı */
  mesgul: { type: Boolean, default: false },
  /** Son hareketin sonucu */
  sonHareket: { type: Object, default: null },
})

const emit = defineEmits(['hareket'])

/** Yön tuşları — 3×3 ızgara düzeninde (ortası boş). */
const YONLER = [
  ['kuzeybatı', 'kuzey', 'kuzeydoğu'],
  ['batı', null, 'doğu'],
  ['güneybatı', 'güney', 'güneydoğu'],
]

const YON_IKONU = {
  kuzey: 'north',
  güney: 'south',
  doğu: 'east',
  batı: 'west',
  kuzeydoğu: 'north_east',
  kuzeybatı: 'north_west',
  güneydoğu: 'south_east',
  güneybatı: 'south_west',
}

const KLAVYE = {
  ArrowUp: 'kuzey',
  ArrowDown: 'güney',
  ArrowRight: 'doğu',
  ArrowLeft: 'batı',
}

const kutu = ref(null)
const buyukAcik = ref(false)

const varlik = computed(() =>
  (props.izgara?.entities || []).find((e) => e.id === props.oyuncu) || null,
)

const konum = computed(() => (varlik.value ? `${varlik.value.x}, ${varlik.value.y}` : '—'))

/** Aynı karedeki diğerleri — etkileşim/savaş sistemleri buradan büyüyecek. */
const ayniKarede = computed(() => {
  if (!varlik.value) return []
  return (props.izgara?.entities || []).filter(
    (e) => e.id !== varlik.value.id && e.x === varlik.value.x && e.y === varlik.value.y,
  )
})

const hareketEdilebilir = computed(() => !!varlik.value && !props.mesgul)

/** Başarısız hareketin okunabilir nedeni. */
const hataMetni = computed(() => {
  const s = props.sonHareket
  if (!s || s.ok) return ''
  if (s.reason === 'sınır_dışı') return 'Harita sınırı — o yöne gidilmiyor.'
  if (s.reason === 'geçilemez') return `Geçilemez${s.blocked_by ? `: ${s.blocked_by}` : ''}.`
  if (s.reason === 'geçersiz_yön') return 'Yön anlaşılmadı.'
  if (s.reason === 'haritada_değil') return 'Bu karakter sahnede değil.'
  return s.blocked_by || 'Hareket başarısız.'
})

function git(yon) {
  if (!yon || !hareketEdilebilir.value) return
  emit('hareket', yon)
}

function tusla(e) {
  const yon = KLAVYE[e.key]
  if (!yon) return
  e.preventDefault()
  git(yon)
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <div class="flex flex-wrap items-center gap-1.5">
      <Badge tone="muted" size="sm" icon="grid_on">
        {{ izgara?.width || 0 }}×{{ izgara?.height || 0 }}
      </Badge>
      <span v-if="varlik" class="inline-flex items-center gap-1 text-label text-muted">
        <span
          class="size-1.5 rounded-full"
          :style="{ backgroundColor: colorFor(oyuncu) }"
          aria-hidden="true"
        />
        {{ oyuncu }} · <span class="nums-tabular">{{ konum }}</span>
      </span>
      <span v-else class="text-label text-faint">Seçili karakter sahnede değil</span>
      <BaseButton
        class="ml-auto"
        size="sm"
        variant="quiet"
        icon="open_in_full"
        icon-only
        aria-label="Kare haritayı büyüt"
        title="Kare haritayı büyüt"
        @click="buyukAcik = true"
      />
    </div>

    <div
      ref="kutu"
      tabindex="0"
      class="rounded-card outline-none focus-visible:ring-1 focus-visible:ring-accent/60"
      @keydown="tusla"
    >
      <GridCanvas :izgara="izgara" :secili="oyuncu" />
    </div>

    <!-- yön tuşları -->
    <div class="flex items-start gap-3">
      <div class="grid grid-cols-3 gap-1">
        <template v-for="(satir, i) in YONLER" :key="i">
          <template v-for="(yon, j) in satir" :key="`${i}-${j}`">
            <BaseButton
              v-if="yon"
              size="sm"
              variant="ghost"
              icon-only
              :icon="YON_IKONU[yon]"
              :aria-label="yon"
              :title="yon"
              :disabled="!hareketEdilebilir"
              @click="git(yon)"
            />
            <span v-else class="inline-flex size-7 items-center justify-center">
              <Icon name="my_location" :size="14" class="text-faint" />
            </span>
          </template>
        </template>
      </div>

      <div class="min-w-0 flex-1 text-label">
        <p v-if="hataMetni" class="flex items-center gap-1.5 text-warn" role="status">
          <Icon name="block" :size="13" />
          {{ hataMetni }}
        </p>
        <p v-else-if="sonHareket?.ok" class="flex items-center gap-1.5 text-ok" role="status">
          <Icon name="check" :size="13" />
          {{ sonHareket.direction }} →
          <span class="nums-tabular">{{ sonHareket.to?.x }}, {{ sonHareket.to?.y }}</span>
        </p>
        <p v-else class="text-faint">Ok tuşları ya da yön düğmeleriyle bir kare hareket et.</p>

        <p v-if="ayniKarede.length" class="mt-1 flex flex-wrap items-center gap-1 text-faint">
          <Icon name="groups" :size="13" />
          aynı karede:
          <span v-for="e in ayniKarede" :key="e.id" class="text-muted">
            {{ e.name || e.id }}
          </span>
        </p>
      </div>
    </div>

    <!-- Büyük görünüm: kenar çubuğu dar kaldığında sahne rahat okunsun. -->
    <Modal v-model="buyukAcik" size="xl" icon="grid_on" :title="`Kare harita — ${izgara?.name || 'sahne'}`">
      <div class="flex flex-col gap-3">
        <GridCanvas :izgara="izgara" :secili="oyuncu" :kare="48" />
        <div class="flex flex-wrap items-center gap-3">
          <div class="grid grid-cols-3 gap-1">
            <template v-for="(satir, i) in YONLER" :key="`b-${i}`">
              <template v-for="(yon, j) in satir" :key="`b-${i}-${j}`">
                <BaseButton
                  v-if="yon"
                  size="md"
                  variant="ghost"
                  icon-only
                  :icon="YON_IKONU[yon]"
                  :aria-label="yon"
                  :title="yon"
                  :disabled="!hareketEdilebilir"
                  @click="git(yon)"
                />
                <span v-else class="inline-flex size-9 items-center justify-center">
                  <Icon name="my_location" :size="16" class="text-faint" />
                </span>
              </template>
            </template>
          </div>
          <div class="min-w-0 flex-1 text-meta">
            <p v-if="varlik" class="text-muted">
              {{ oyuncu }} · <span class="nums-tabular">{{ konum }}</span>
            </p>
            <p v-if="hataMetni" class="text-warn">{{ hataMetni }}</p>
            <p v-else-if="sonHareket?.ok" class="text-ok">
              {{ sonHareket.direction }} →
              <span class="nums-tabular">{{ sonHareket.to?.x }}, {{ sonHareket.to?.y }}</span>
            </p>
            <p class="mt-1 text-label text-faint">
              Bir hamlede BİR kare ilerlenir; duvarlar ve engeller geçilmez. Aynı karede birden
              fazla oyuncu, NPC ve eşya bulunabilir.
            </p>
          </div>
        </div>
      </div>
    </Modal>
  </div>
</template>
