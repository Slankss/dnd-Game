<script setup>
/**
 * Başlatma ekranı (phase = 'ready') — kadro onaylandı, oyun henüz başlamadı.
 *
 * "Oyunu başlat" anlatıcı modelini çağırır ve 30-60 saniye sürebilir; bu
 * sürede ne olduğu açıkça yazılır ve geçen süre sayılır (docs §7).
 */
import { ref, watch, computed, onUnmounted } from 'vue'
import Panel from '../ui/Panel.vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import BaseButton from '../ui/BaseButton.vue'
import SkeletonLine from '../ui/SkeletonLine.vue'
import ResourcePanel from './ResourcePanel.vue'
import { colorFor, bashHarf } from '@/utils/characterColors'
import { kunyeOzeti, stokVarMi, dunyaSaatiMetni } from './gameFormat'

const props = defineProps({
  karakterler: { type: Object, default: () => ({}) },
  kaynaklar: { type: Object, default: () => ({}) },
  saat: { type: Object, default: null },
  mesgul: { type: Boolean, default: false },
  hata: { type: String, default: '' },
})

defineEmits(['basla'])

const kadro = computed(() => Object.entries(props.karakterler || {}))
const stok = computed(() => stokVarMi(props.kaynaklar))
const acilis = computed(() => dunyaSaatiMetni(props.saat))

/* Bekleme sırasında geçen süre — ekranın donmadığı görünsün. */
const gecenSaniye = ref(0)
let sayac = null
watch(
  () => props.mesgul,
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
</script>

<template>
  <div class="flex flex-col gap-4">
    <Panel title="Kadro hazır" icon="groups" :count="kadro.length">
      <p v-if="acilis" class="mb-3 flex items-center gap-1.5 text-meta text-muted">
        <Icon name="schedule" :size="15" class="text-faint" />
        {{ acilis }}
      </p>

      <ul v-if="kadro.length" class="flex flex-col gap-2">
        <li
          v-for="[ad, bilgi] in kadro"
          :key="ad"
          class="rounded-card border border-border bg-surface-2 px-3 py-2"
          :style="{ borderLeftWidth: '3px', borderLeftColor: colorFor(ad) }"
        >
          <div class="flex flex-wrap items-center gap-2">
            <span
              class="inline-flex size-6 shrink-0 items-center justify-center rounded-chip text-label font-semibold"
              :style="{
                color: colorFor(ad),
                backgroundColor: `color-mix(in oklab, ${colorFor(ad)} 16%, transparent)`,
              }"
              aria-hidden="true"
              >{{ bashHarf(ad) }}</span
            >
            <span class="text-card" :style="{ color: colorFor(ad) }">{{ ad }}</span>
            <span v-if="kunyeOzeti(bilgi)" class="text-meta text-muted">{{
              kunyeOzeti(bilgi)
            }}</span>
          </div>
          <p class="mt-1 flex flex-wrap items-center gap-1.5 text-label text-muted">
            <span v-if="bilgi.strength" class="inline-flex items-center gap-1">
              <Icon name="fitness_center" :size="13" class="text-ok" />{{ bilgi.strength }}
            </span>
            <span v-if="bilgi.weakness" class="inline-flex items-center gap-1">
              <Icon name="healing" :size="13" class="text-warn" />{{ bilgi.weakness }}
            </span>
          </p>
          <div v-if="(bilgi.inventory || []).length" class="mt-1 flex flex-wrap gap-1">
            <span
              v-for="(esya, i) in bilgi.inventory"
              :key="i"
              class="rounded-chip border border-border bg-surface px-1.5 py-0.5 text-[0.625rem] text-muted"
              >{{ esya }}</span
            >
          </div>
        </li>
      </ul>
      <p v-else class="text-meta text-faint">Kadro okunamadı — sayfayı yenilemeyi dene.</p>

      <p class="mt-3 flex items-start gap-1.5 text-label text-faint">
        <Icon name="lock" :size="13" class="mt-px shrink-0" />
        Yazdığınız sırlar yalnızca anlatıcıya gitti; bu ekranda hiçbir yerde görünmez.
      </p>
    </Panel>

    <Panel v-if="stok" title="Grup kaynakları" icon="inventory_2">
      <ResourcePanel :kaynaklar="kaynaklar" />
    </Panel>

    <!-- Bekleme durumu -->
    <Panel v-if="mesgul" tone="default" title="Açılış sahnesi yazılıyor" icon="auto_stories">
      <p class="text-meta text-muted">
        Anlatıcı dünyayı kuruyor, açılış olayını seçiyor ve herkesi künyesine göre sahneye sokuyor.
        Bu adım <b class="text-text">30-60 saniye</b> sürebilir — sayfayı kapatma.
      </p>
      <p class="mt-2 flex items-center gap-2 text-meta text-accent" role="status" aria-live="polite">
        <Icon name="progress_activity" :size="16" class="motion-safe:animate-spin" />
        <span class="nums-tabular">{{ gecenSaniye }} sn</span> geçti
      </p>
      <div class="mt-3">
        <SkeletonLine :lines="4" />
      </div>
    </Panel>

    <div class="flex flex-col gap-2">
      <p v-if="hata" class="flex items-center gap-1.5 text-meta text-danger" role="alert">
        <Icon name="warning" :size="15" />
        {{ hata }}
      </p>
      <div class="flex flex-wrap items-center gap-2">
        <Badge tone="muted" icon="casino">İlk turda zar atılmaz</Badge>
        <BaseButton
          class="ml-auto"
          variant="primary"
          size="lg"
          icon="play_arrow"
          :loading="mesgul"
          loading-text="Sahne hazırlanıyor…"
          :disabled="!kadro.length"
          @click="$emit('basla')"
        >
          Oyunu başlat
        </BaseButton>
      </div>
    </div>
  </div>
</template>
