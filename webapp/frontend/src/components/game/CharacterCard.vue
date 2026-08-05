<script setup>
/**
 * Kadro kartı — sidebar'daki tek karakter özeti (docs §6).
 * Durum, yaralar, dikkat çeken vitals, envanter çipleri, sahne katılım rozeti.
 * Tıklanınca tam künye modalı açılır.
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import { colorFor, bashHarf, GRUP_RENGI } from '@/utils/characterColors'
import {
  saglikTonu,
  katilimBilgisi,
  dikkatCekenVitals,
  yaralariDiziye,
  enKotuEnfeksiyon,
  kunyeOzeti,
  envanteriDiziye,
} from './gameFormat'

const props = defineProps({
  ad: { type: String, required: true },
  bilgi: { type: Object, default: () => ({}) },
  /** NPC kartı mı (renk nötr, künye daha kısa) */
  npc: { type: Boolean, default: false },
})

defineEmits(['ac'])

const olu = computed(() => props.bilgi?.alive === false)
const renk = computed(() => (props.npc ? GRUP_RENGI : colorFor(props.ad)))
const kunye = computed(() => kunyeOzeti(props.bilgi) || props.bilgi?.background || '')
const katilim = computed(() => katilimBilgisi(props.bilgi))
const vitals = computed(() => dikkatCekenVitals(props.bilgi?.vitals))
const yaraSayisi = computed(() => yaralariDiziye(props.bilgi?.wounds).length)
const enfeksiyon = computed(() => enKotuEnfeksiyon(props.bilgi?.wounds))
const envanter = computed(() => envanteriDiziye(props.bilgi))
const durumTonu = computed(() => (olu.value ? 'danger' : saglikTonu(props.bilgi?.status)))

const VITAL_TONU = { ok: 'text-muted', warn: 'text-warn', danger: 'text-danger' }
</script>

<template>
  <button
    type="button"
    class="w-full rounded-card border border-border bg-surface-2 px-2.5 py-2 text-left transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)] hover:bg-surface-3"
    :class="olu ? 'opacity-60' : ''"
    :style="{ borderLeftWidth: '3px', borderLeftColor: renk }"
    :aria-label="`${ad} künyesini aç`"
    @click="$emit('ac', ad)"
  >
    <!-- İsim satırı -->
    <div class="flex items-center gap-1.5">
      <span
        class="inline-flex size-5 shrink-0 items-center justify-center rounded-chip text-[0.625rem] font-semibold"
        :style="{
          color: renk,
          backgroundColor: `color-mix(in oklab, ${renk} 16%, transparent)`,
        }"
        aria-hidden="true"
        >{{ bashHarf(ad) }}</span
      >
      <span class="min-w-0 flex-1 truncate text-card" :style="{ color: renk }">{{ ad }}</span>
      <Badge v-if="olu" tone="danger" size="sm" icon="lucide:skull">ölü</Badge>
      <Badge v-else-if="katilim" :tone="katilim.ton" size="sm" :icon="katilim.ikon">
        {{ katilim.etiket }}
      </Badge>
    </div>

    <!-- Künye + durum -->
    <p v-if="kunye" class="mt-1 line-clamp-2 text-label text-muted">{{ kunye }}</p>
    <p v-else class="mt-1 text-label text-faint italic">künye henüz doldurulmadı</p>

    <p class="mt-1 flex items-center gap-1.5 text-label">
      <Icon
        name="favorite"
        :size="13"
        filled
        :class="{
          'text-ok': durumTonu === 'ok',
          'text-warn': durumTonu === 'warn',
          'text-danger': durumTonu === 'danger',
          'text-faint': durumTonu === 'muted',
        }"
      />
      <span class="min-w-0 truncate text-muted">{{ bilgi.status || 'durum bilinmiyor' }}</span>
    </p>

    <!-- Yaralar -->
    <p v-if="yaraSayisi" class="mt-1 flex items-center gap-1.5 text-label">
      <Icon name="bloodtype" :size="13" class="text-danger" />
      <span :class="enfeksiyon >= 60 ? 'text-danger' : 'text-muted'">
        {{ yaraSayisi }} açık yara<template v-if="enfeksiyon >= 60">
          · enfeksiyon {{ enfeksiyon }}</template
        >
      </span>
    </p>

    <!-- Katılım notu -->
    <p v-if="katilim?.not" class="mt-1 line-clamp-2 text-label text-faint">{{ katilim.not }}</p>

    <!-- Dikkat çeken göstergeler -->
    <p v-if="vitals.length" class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-label">
      <span
        v-for="v in vitals"
        :key="v.anahtar"
        class="inline-flex items-center gap-0.5"
        :class="VITAL_TONU[v.ton]"
      >
        <Icon :name="v.ikon" :size="12" />
        <span class="nums-tabular">{{ v.deger }}</span>
      </span>
    </p>

    <!-- Konum -->
    <p v-if="bilgi.location" class="mt-1 flex items-center gap-1.5 text-label text-faint">
      <Icon name="location_on" :size="13" />
      <span class="min-w-0 truncate">{{ bilgi.location }}</span>
    </p>

    <!-- Envanter çipleri -->
    <div v-if="envanter.length" class="mt-1.5 flex flex-wrap gap-1">
      <span
        v-for="(esya, i) in envanter.slice(0, 6)"
        :key="i"
        class="inline-flex max-w-full items-center gap-1 truncate rounded-chip border border-border bg-surface px-1.5 py-0.5 text-[0.625rem]"
        :class="esya.az ? 'border-warn/40 text-warn' : 'text-muted'"
      >
        {{ esya.ad }}
        <span v-if="esya.adet !== null" class="nums-tabular font-semibold"
          >×{{ esya.adet }}</span
        >
      </span>
      <span v-if="envanter.length > 6" class="text-[0.625rem] text-faint"
        >+{{ envanter.length - 6 }}</span
      >
    </div>
    <!-- Başkasının envanteri sunucudan HİÇ gelmez: "boş" ile "gizli"yi
         karıştırmayalım (bkz. serializers.mask_inventory). -->
    <p
      v-else-if="bilgi.envanter_gizli"
      class="mt-1.5 flex items-center gap-1.5 text-label text-faint"
      title="Kimde ne var, masada konuşarak öğrenilir"
    >
      <Icon name="lock" :size="13" />
      envanteri gizli
    </p>
    <p v-else class="mt-1.5 flex items-center gap-1.5 text-label text-faint">
      <Icon name="backpack" :size="13" />
      envanter boş
    </p>

    <!-- Devralma -->
    <p v-if="bilgi.replaced_by" class="mt-1 flex items-center gap-1.5 text-label text-accent">
      <Icon name="swap_horiz" :size="13" />
      yerine {{ bilgi.replaced_by }} oynanıyor
    </p>
  </button>
</template>
