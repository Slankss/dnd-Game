<script setup>
/**
 * Kadro künyesi — anlatıcı sürümü.
 *
 * Oyuncu kartından farkı: `secret` alanı burada AÇIKÇA görünür (sunucu bu alanı
 * oyuncu gövdesine hiç koymuyor) ve sahne katılımının dönüş koşulu okunur
 * biçimde yazılır.
 */
import { computed } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { colorVars } from '@/utils/characterColors'
import { katilimOzeti, VITAL_ETIKET, vitalTonu, yaraTonu, yuzde, dizile } from './gmYardimcilar'

const props = defineProps({
  ad: { type: String, required: true },
  /** `world_state.characters[ad]` */
  bilgi: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['sahneyeDondur'])

const k = computed(() => props.bilgi || {})
const olu = computed(() => k.value.alive === false)
const katilim = computed(() => katilimOzeti(k.value.presence))

const kunye = computed(() => {
  const p = []
  if (k.value.age) p.push(`${k.value.age} yaşında`)
  if (k.value.profession) p.push(k.value.profession)
  if (!p.length && k.value.background) p.push(k.value.background)
  return p.join(' · ')
})

const vitaller = computed(() => {
  const v = k.value.vitals
  if (!v || typeof v !== 'object') return []
  return Object.entries(VITAL_ETIKET)
    .filter(([alan]) => v[alan] !== undefined && v[alan] !== null && v[alan] !== '')
    .map(([alan, tanim]) => ({
      alan,
      ...tanim,
      deger: yuzde(v[alan]),
      ton: vitalTonu(v[alan]),
    }))
})

const vitalKuyruk = computed(() => {
  const v = k.value.vitals || {}
  const p = []
  if (v.awake_hours !== undefined && v.awake_hours !== null && v.awake_hours !== '') {
    p.push(`${v.awake_hours} saattir uyanık`)
  }
  if (v.condition) p.push(v.condition)
  return p.join(' · ')
})

const yaralar = computed(() => dizile(k.value.wounds).filter((y) => y && y.desc))
const envanter = computed(() => dizile(k.value.inventory).filter(Boolean))
const kayipEsyalar = computed(() => dizile(k.value.lost_items).filter(Boolean))
const iliskiler = computed(() => Object.entries(k.value.relationships || {}))

const CUBUK = { ok: 'bg-ok', warn: 'bg-warn', danger: 'bg-danger', muted: 'bg-faint' }
</script>

<template>
  <article
    class="rounded-card border border-l-2 border-border bg-surface-2 p-3"
    :style="{ ...colorVars(ad), borderLeftColor: 'var(--kr)' }"
    :class="olu ? 'opacity-70' : ''"
  >
    <!-- Başlık -->
    <header class="flex flex-wrap items-center gap-2">
      <h3 class="text-card" :style="{ color: 'var(--kr)' }">{{ ad }}</h3>
      <Badge v-if="olu" tone="danger" icon="lucide:skull">
        ölü<template v-if="k.replaced_by"> → {{ k.replaced_by }}</template>
      </Badge>
      <Badge v-else :tone="katilim.ton" :icon="katilim.ikon">{{ katilim.etiket }}</Badge>
      <BaseButton
        v-if="!olu && !katilim.sahnede"
        class="ml-auto"
        size="sm"
        variant="subtle"
        icon="directions_walk"
        :aria-label="`${ad} karakterini sahneye döndürmek için yama taslağı hazırla`"
        @click="emit('sahneyeDondur', ad)"
      >
        Sahneye döndür
      </BaseButton>
    </header>

    <!-- Künye -->
    <p v-if="kunye" class="mt-1 text-label text-muted">{{ kunye }}</p>
    <p v-if="k.strength || k.weakness" class="text-label text-muted">
      <span v-if="k.strength">Güçlü: {{ k.strength }}</span>
      <span v-if="k.strength && k.weakness"> · </span>
      <span v-if="k.weakness">Zayıf: {{ k.weakness }}</span>
    </p>
    <p v-else-if="k.traits" class="text-label text-muted">{{ k.traits }}</p>

    <!-- Durum ve konum -->
    <div class="mt-1.5 flex flex-col gap-0.5 text-label text-muted">
      <span class="flex items-start gap-1.5">
        <Icon name="favorite" :size="13" class="mt-0.5 shrink-0" />
        <span>{{ k.status || 'durum yazılmamış' }}</span>
      </span>
      <span class="flex items-start gap-1.5">
        <Icon name="location_on" :size="13" class="mt-0.5 shrink-0" />
        <span>{{ k.location || 'konum yazılmamış' }}</span>
      </span>
    </div>

    <!-- Sahne katılımı ayrıntısı -->
    <div
      v-if="!olu && !katilim.sahnede"
      class="mt-2 flex flex-col gap-0.5 rounded-card border border-warn/35 bg-warn-soft px-2.5 py-1.5 text-label text-warn"
    >
      <span v-if="katilim.not">{{ katilim.not }}</span>
      <span>
        Dönüş:
        <template v-if="katilim.kosul">{{ katilim.kosul }}</template>
        <template v-else>koşul yok — elle döndürmen gerekir</template>
      </span>
    </div>

    <!-- Vitals -->
    <div v-if="vitaller.length" class="mt-2 flex flex-col gap-1">
      <div v-for="v in vitaller" :key="v.alan" class="flex items-center gap-2">
        <span class="flex w-24 shrink-0 items-center gap-1 text-label text-muted">
          <Icon :name="v.ikon" :size="12" />{{ v.etiket }}
        </span>
        <span
          class="h-1.5 flex-1 overflow-hidden rounded-chip bg-surface-3"
          role="progressbar"
          :aria-valuenow="v.deger"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-label="`${ad} — ${v.etiket}`"
        >
          <span class="block h-full rounded-chip" :class="CUBUK[v.ton]" :style="{ width: `${v.deger}%` }" />
        </span>
        <span class="nums-tabular w-7 shrink-0 text-right text-label text-muted">{{ v.deger }}</span>
      </div>
      <p v-if="vitalKuyruk" class="text-label text-faint">{{ vitalKuyruk }}</p>
    </div>

    <!-- Yaralar -->
    <div v-if="yaralar.length" class="mt-2 flex flex-col gap-1.5">
      <span class="text-panel uppercase tracking-[0.06em] text-muted">Yaralar</span>
      <div
        v-for="(y, i) in yaralar"
        :key="i"
        class="rounded-card border border-border bg-surface px-2.5 py-1.5"
      >
        <div class="flex flex-wrap items-center gap-1.5">
          <Icon name="bloodtype" :size="13" class="text-danger" />
          <span class="text-label text-text">{{ y.desc }}</span>
          <Badge size="sm" :tone="yaraTonu(y.severity)">{{ y.severity || 'orta' }}</Badge>
          <Badge size="sm" :tone="y.treated ? 'ok' : 'danger'">
            {{ y.treated ? 'tedavi edildi' : 'tedavi edilmedi' }}
          </Badge>
        </div>
        <div class="mt-1 flex items-center gap-2">
          <span class="w-24 shrink-0 text-label text-muted">Enfeksiyon</span>
          <span
            class="h-1.5 flex-1 overflow-hidden rounded-chip bg-surface-3"
            role="progressbar"
            :aria-valuenow="yuzde(y.infection_risk)"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-label="`${ad} — enfeksiyon riski`"
          >
            <span
              class="block h-full rounded-chip"
              :class="CUBUK[vitalTonu(y.infection_risk)]"
              :style="{ width: `${yuzde(y.infection_risk)}%` }"
            />
          </span>
          <span class="nums-tabular w-7 shrink-0 text-right text-label text-muted">
            {{ yuzde(y.infection_risk) }}
          </span>
        </div>
        <p v-if="y.notes" class="mt-0.5 text-label text-faint">{{ y.notes }}</p>
      </div>
    </div>

    <!-- Envanter -->
    <div class="mt-2 flex flex-col gap-1">
      <span class="text-panel uppercase tracking-[0.06em] text-muted">Envanter</span>
      <div v-if="envanter.length" class="flex flex-wrap gap-1">
        <Badge v-for="(e, i) in envanter" :key="i" size="sm" tone="neutral" icon="backpack">
          {{ e }}
        </Badge>
      </div>
      <p v-else class="text-label text-faint">Üstünde bir şey yok.</p>
      <div v-if="kayipEsyalar.length" class="flex flex-wrap items-center gap-1">
        <span class="text-label text-faint">kaybettikleri:</span>
        <Badge v-for="(e, i) in kayipEsyalar" :key="i" size="sm" tone="muted">{{ e }}</Badge>
      </div>
    </div>

    <!-- İlişkiler -->
    <div v-if="iliskiler.length" class="mt-2 flex flex-col gap-0.5">
      <span class="text-panel uppercase tracking-[0.06em] text-muted">İlişkiler</span>
      <p v-for="[kim, tanim] in iliskiler" :key="kim" class="text-label text-muted">
        <b class="text-text">{{ kim }}:</b> {{ tanim }}
      </p>
    </div>

    <p v-if="k.notes" class="mt-2 text-label text-muted">
      <Icon name="sticky_note_2" :size="13" class="mr-1" />{{ k.notes }}
    </p>

    <!-- Künyedeki sır — yalnızca bu ekranda -->
    <p
      v-if="k.secret"
      class="mt-2 flex items-start gap-1.5 rounded-card border border-gm/40 bg-gm-soft px-2.5 py-1.5 text-label text-gm"
    >
      <Icon name="visibility_off" :size="13" class="mt-0.5 shrink-0" />
      <span><b>SIR:</b> {{ k.secret }}</span>
    </p>
  </article>
</template>
