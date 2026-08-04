<script setup>
/**
 * Büyük harita — görsel harita + seçilen yerin künyesi + lejant.
 *
 * Künye yalnızca BİLİNEN kadarını gösterir: duyulmuş bir yer seçildiğinde
 * "hakkında hiçbir şey bilinmiyor" denir, çünkü sunucu ayrıntıyı zaten
 * göndermemiştir (bkz. models/worldmap.public_place).
 */
import { ref, computed, watch } from 'vue'
import Modal from '../ui/Modal.vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import MapCanvas from './MapCanvas.vue'
import { bilgiDuzeyi } from './mapLayout'
import { TEHLIKE_TONU } from './gameFormat'
import { colorFor } from '@/utils/characterColors'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  harita: { type: Object, default: () => ({}) },
  /** Anlatıcı kipi: sis perdesi yok */
  gm: { type: Boolean, default: false },
  /** world_state.threat — yoğunluk ve göç bilgisi */
  tehdit: { type: Object, default: null },
})

defineEmits(['update:modelValue'])

const secili = ref('')

/** Açılışta grubun konumu seçili gelsin. */
watch(
  () => props.modelValue,
  (acik) => {
    if (acik) secili.value = props.harita?.current || ''
  },
)

const yer = computed(() => (secili.value ? props.harita?.places?.[secili.value] : null))
const duzey = computed(() => (yer.value ? bilgiDuzeyi(yer.value) : ''))
const kimler = computed(() =>
  Object.entries(props.harita?.party || {})
    .filter(([, nerede]) => nerede === secili.value)
    .map(([kisi]) => kisi),
)

/** Seçilen yerin bilinen zombi yoğunluğu (yoksa null). */
const yogunluk = computed(() => {
  const deger = props.tehdit?.density?.[secili.value]
  return deger == null ? null : Math.round(Number(deger))
})

/** Bu yere/yerden son göç hareketi — "patlama sonrası buraya akıyorlar". */
const gocMetni = computed(() => {
  const gocler = props.tehdit?.migrations || []
  for (const goc of [...gocler].reverse()) {
    if (goc.target === secili.value) {
      const kaynak = (goc.from || []).map((k) => k.place).join(', ')
      return `${goc.type || 'Ses'} sonrası buraya ölü çekildi${kaynak ? ` (${kaynak} boşaldı)` : ''}.`
    }
    if ((goc.from || []).some((k) => k.place === secili.value)) {
      return `Buradan ${goc.target} yönüne ölü çekildi — bölge geçici olarak boşaldı.`
    }
  }
  return ''
})

const DUZEY_TONU = {
  bilinmiyor: 'gm',
  duyuldu: 'muted',
  görüldü: 'warn',
  keşfedildi: 'ok',
}
const DUZEY_IKONU = {
  bilinmiyor: 'visibility_off',
  duyuldu: 'help',
  görüldü: 'visibility',
  keşfedildi: 'explore',
}
</script>

<template>
  <Modal
    :model-value="modelValue"
    size="xl"
    icon="map"
    title="Harita"
    :tone="gm ? 'gm' : 'default'"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="flex flex-col gap-3">
      <MapCanvas
        :harita="harita"
        :secili="secili"
        :gm="gm"
        :yogunluk="tehdit?.density || {}"
        @sec="secili = $event"
      />

      <!-- lejant -->
      <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-label text-faint">
        <span class="inline-flex items-center gap-1.5">
          <Icon name="my_location" :size="13" class="text-accent" />
          grubun konumu
        </span>
        <span class="inline-flex items-center gap-1.5">
          <Icon name="explore" :size="13" class="text-ok" />
          keşfedildi — her şey biliniyor
        </span>
        <span class="inline-flex items-center gap-1.5">
          <Icon name="visibility" :size="13" class="text-warn" />
          görüldü — uzaktan bakıldı
        </span>
        <span class="inline-flex items-center gap-1.5">
          <Icon name="help" :size="13" />
          duyuldu — sadece adı biliniyor
        </span>
        <span v-if="gm" class="inline-flex items-center gap-1.5">
          <Icon name="visibility_off" :size="13" class="text-gm" />
          grup bilmiyor — yalnız anlatıcı görür
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="h-px w-5 border-t border-dashed border-border" aria-hidden="true" />
          kesin olmayan yol
        </span>
        <span class="inline-flex items-center gap-1.5">
          <Icon name="donut_large" :size="13" />
          dış halka: zombi yoğunluğu
        </span>
      </div>

      <!-- seçilen yerin künyesi -->
      <section v-if="yer" class="rounded-card border border-border bg-surface-2 p-3">
        <div class="flex flex-wrap items-center gap-1.5">
          <h3 class="text-card text-text">{{ secili }}</h3>
          <Badge :tone="DUZEY_TONU[duzey]" :icon="DUZEY_IKONU[duzey]" size="sm">
            {{ duzey }}
          </Badge>
          <Badge v-if="secili === harita.current" tone="accent" icon="my_location" size="sm">
            buradayız
          </Badge>
          <Badge
            v-if="yer.danger && yer.danger !== 'bilinmiyor'"
            :tone="TEHLIKE_TONU[yer.danger] || 'muted'"
            size="sm"
          >
            {{ yer.danger }}
          </Badge>
        </div>

        <p
          v-if="duzey === 'bilinmiyor'"
          class="mt-1.5 flex items-start gap-1.5 text-meta text-gm"
        >
          <Icon name="visibility_off" :size="15" class="mt-0.5 shrink-0" />
          Grup burayı henüz DUYMADI. Dünyada var, haritası ve mesafeleri hazır — ama
          oyuncu ekranında hiç görünmüyor. Sahnede adı geçtiği anda "duyuldu"ya yükselir.
        </p>

        <p v-else-if="duzey === 'duyuldu'" class="mt-1.5 flex items-start gap-1.5 text-meta text-faint">
          <Icon name="help" :size="15" class="mt-0.5 shrink-0" />
          Bu yerin sadece adı duyuldu — nasıl bir yer olduğu, kimin elinde olduğu ve ne kadar
          tehlikeli olduğu bilinmiyor. Yaklaşıp bakmak ya da birinden bilgi almak gerek.
        </p>

        <template v-else>
          <p v-if="yer.kind || yer.status" class="mt-1 text-meta text-muted">
            {{ [yer.kind, yer.status].filter(Boolean).join(' · ') }}
          </p>
          <p v-if="yer.notes" class="mt-1 text-meta text-text">{{ yer.notes }}</p>
          <p v-else-if="duzey === 'görüldü'" class="mt-1 text-label text-faint">
            İçeri girilmedi — yalnızca dışarıdan görülenler biliniyor.
          </p>
          <p
            v-if="Array.isArray(yer.links) && yer.links.length"
            class="mt-1.5 flex items-start gap-1.5 text-label text-faint"
          >
            <Icon name="alt_route" :size="13" class="mt-0.5 shrink-0" />
            <span>Komşu: {{ yer.links.join(', ') }}</span>
          </p>
          <p v-if="yer.discovered_day" class="mt-1 text-label text-faint">
            {{ yer.discovered_day }}. günden beri biliniyor
          </p>

          <!-- zombi yoğunluğu: yalnız bilinen yerler için gelir -->
          <div v-if="yogunluk !== null" class="mt-2">
            <div class="flex items-center gap-1.5">
              <Icon name="skull" :size="13" class="text-faint" />
              <span class="text-label text-muted">Zombi yoğunluğu</span>
              <span class="ml-auto text-label nums-tabular text-muted">{{ yogunluk }}/100</span>
            </div>
            <div class="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-surface">
              <div
                class="h-full rounded-full"
                :class="yogunluk >= 66 ? 'bg-danger' : yogunluk >= 38 ? 'bg-warn' : 'bg-ok'"
                :style="{ width: `${Math.max(2, yogunluk)}%` }"
              />
            </div>
            <p v-if="gocMetni" class="mt-1 flex items-start gap-1.5 text-label text-warn">
              <Icon name="moving" :size="13" class="mt-0.5 shrink-0" />
              <span>{{ gocMetni }}</span>
            </p>
          </div>
        </template>

        <div v-if="kimler.length" class="mt-2 flex flex-wrap gap-1">
          <span
            v-for="kisi in kimler"
            :key="kisi"
            class="inline-flex items-center gap-1 rounded-chip border px-2 py-0.5 text-label"
            :style="{
              color: colorFor(kisi),
              borderColor: `color-mix(in oklab, ${colorFor(kisi)} 45%, transparent)`,
            }"
          >
            <span class="size-1.5 rounded-full bg-current" aria-hidden="true" />
            {{ kisi }} burada
          </span>
        </div>
      </section>

      <p v-else class="text-label text-faint">
        Ayrıntısını görmek için haritadan bir yer seç.
      </p>
    </div>
  </Modal>
</template>
