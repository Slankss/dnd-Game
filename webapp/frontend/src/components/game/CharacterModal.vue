<script setup>
/**
 * Karakter künyesi — kadro kartına tıklayınca açılır.
 * Tam künye + göstergeler + yaralar + envanter + ilişkiler.
 *
 * NOT: `secret` alanı sunucuda (public_world_state) ayıklanır, oyuncu
 * arayüzüne hiç gelmez. Burada da hiçbir yerde gösterilmez.
 */
import { computed } from 'vue'
import Modal from '../ui/Modal.vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import VitalBars from './VitalBars.vue'
import WoundList from './WoundList.vue'
import { colorFor, GRUP_RENGI } from '@/utils/characterColors'
import { saglikTonu, katilimBilgisi, kunyeOzeti, envanteriDiziye } from './gameFormat'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  ad: { type: String, default: '' },
  bilgi: { type: Object, default: null },
  npc: { type: Boolean, default: false },
})

defineEmits(['update:modelValue'])

const renk = computed(() => (props.npc ? GRUP_RENGI : colorFor(props.ad)))
const olu = computed(() => props.bilgi?.alive === false)
const kunye = computed(() => kunyeOzeti(props.bilgi))
const katilim = computed(() => katilimBilgisi(props.bilgi))
const envanter = computed(() => envanteriDiziye(props.bilgi))
const iliskiler = computed(() => Object.entries(props.bilgi?.relationships || {}))
const durumTonu = computed(() => (olu.value ? 'danger' : saglikTonu(props.bilgi?.status)))
</script>

<template>
  <Modal
    :model-value="modelValue"
    size="lg"
    icon="person"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <template #header>
      <h2 class="flex min-w-0 flex-wrap items-center gap-2">
        <span class="truncate text-card text-base" :style="{ color: renk }">{{ ad }}</span>
        <Badge v-if="npc" tone="muted" size="sm" icon="person">NPC</Badge>
        <Badge v-if="olu" tone="danger" size="sm" icon="lucide:skull">ölü</Badge>
        <Badge v-else-if="katilim" :tone="katilim.ton" size="sm" :icon="katilim.ikon">
          {{ katilim.etiket }}
        </Badge>
      </h2>
    </template>

    <p v-if="!bilgi" class="text-meta text-muted">Bu karakterin kaydı bulunamadı.</p>

    <div v-else class="flex flex-col gap-4">
      <!-- Künye -->
      <section class="flex flex-col gap-1.5">
        <h3 class="text-panel uppercase tracking-[0.06em] text-muted">Künye</h3>
        <p class="text-meta text-text">
          {{ kunye || bilgi.background || 'Karakter henüz oluşturulmadı.' }}
        </p>
        <p v-if="bilgi.strength" class="flex items-start gap-1.5 text-meta text-muted">
          <Icon name="fitness_center" :size="14" class="mt-0.5 shrink-0 text-ok" />
          <span><span class="text-faint">güçlü yan:</span> {{ bilgi.strength }}</span>
        </p>
        <p v-if="bilgi.weakness" class="flex items-start gap-1.5 text-meta text-muted">
          <Icon name="healing" :size="14" class="mt-0.5 shrink-0 text-warn" />
          <span><span class="text-faint">zayıf yan:</span> {{ bilgi.weakness }}</span>
        </p>
        <p
          v-if="!bilgi.strength && !bilgi.weakness && bilgi.traits"
          class="text-meta text-muted"
        >
          {{ bilgi.traits }}
        </p>
        <p v-if="bilgi.notes" class="text-meta text-faint italic">{{ bilgi.notes }}</p>
      </section>

      <!-- Durum / konum -->
      <section class="flex flex-wrap items-center gap-2">
        <Badge :tone="durumTonu" icon="favorite" icon-filled>{{ bilgi.status || '—' }}</Badge>
        <Badge tone="muted" icon="location_on">{{ bilgi.location || 'konum bilinmiyor' }}</Badge>
        <Badge v-if="bilgi.replaced_by" tone="accent" icon="swap_horiz">
          yerine {{ bilgi.replaced_by }} oynanıyor
        </Badge>
      </section>
      <p v-if="katilim?.not" class="-mt-2 text-meta text-faint">{{ katilim.not }}</p>

      <!-- Göstergeler -->
      <section class="flex flex-col gap-2">
        <h3 class="text-panel uppercase tracking-[0.06em] text-muted">Göstergeler</h3>
        <VitalBars :vitals="bilgi.vitals" />
      </section>

      <!-- Yaralar -->
      <section class="flex flex-col gap-2">
        <h3 class="text-panel uppercase tracking-[0.06em] text-muted">Yaralar</h3>
        <WoundList :yaralar="bilgi.wounds" />
      </section>

      <!-- Envanter -->
      <section class="flex flex-col gap-2">
        <h3 class="flex items-center gap-1.5 text-panel uppercase tracking-[0.06em] text-muted">
          <Icon name="backpack" :size="14" />
          Envanter
        </h3>
        <div v-if="envanter.length" class="flex flex-wrap gap-1.5">
          <span
            v-for="(esya, i) in envanter"
            :key="i"
            class="inline-flex items-center gap-1 rounded-chip border bg-surface-2 px-2 py-0.5 text-label"
            :class="esya.az ? 'border-warn/40 text-warn' : 'border-border text-text'"
          >
            {{ esya.ad }}
            <span v-if="esya.adet !== null" class="nums-tabular font-semibold"
              >×{{ esya.adet }}</span
            >
          </span>
        </div>
        <p v-else class="text-meta text-faint">Envanter boş.</p>
      </section>

      <!-- İlişkiler -->
      <section class="flex flex-col gap-2">
        <h3 class="flex items-center gap-1.5 text-panel uppercase tracking-[0.06em] text-muted">
          <Icon name="handshake" :size="14" />
          İlişkiler
        </h3>
        <ul v-if="iliskiler.length" class="flex flex-col gap-1.5">
          <li v-for="([kisi, aciklama], i) in iliskiler" :key="i" class="text-meta text-muted">
            <span class="text-text">{{ kisi }}:</span> {{ aciklama }}
          </li>
        </ul>
        <p v-else class="text-meta text-faint">Henüz belirgin bir ilişki gelişmedi.</p>
      </section>
    </div>
  </Modal>
</template>
