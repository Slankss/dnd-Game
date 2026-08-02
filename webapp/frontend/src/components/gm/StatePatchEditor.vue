<script setup>
/**
 * Durum düzenleyici — `/api/gm/patch` için serbest JSON yama alanı.
 *
 * Model çağrısı yoktur: yama doğrudan `world_state`'e derin birleştirilir.
 * Sunucu BEYAZ LİSTE uygular — tanımadığı üst alanı sessizce atar. Bu yüzden
 * gönderimden önce hem JSON geçerliliğini hem de alan adlarını denetliyoruz;
 * yoksa anlatıcı "yamayı yolladım ama hiçbir şey değişmedi" ile baş başa kalır.
 */
import { ref, computed, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { jsonDenetle, jsonYaz, katilimOzeti } from './gmYardimcilar'

const props = defineProps({
  /** Düzenleyicideki ham metin (v-model) */
  modelValue: { type: String, default: '' },
  /** `world_state.characters` — sahneye döndürme kısayolu için */
  characters: { type: Object, default: () => ({}) },
  /** Tam dünya durumu — kısayolların mevcut değerle doldurulması için */
  worldState: { type: Object, default: null },
  /** İstek uçuşta mı */
  patching: { type: Boolean, default: false },
  /** Sunucudan gelen hata (Türkçe) */
  hata: { type: String, default: '' },
  /** Başarı bilgisi */
  bilgi: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'uygula'])

/** server.py `deep_merge_world_state` içinde gerçekten okunan üst alanlar. */
const KABUL_EDILEN = [
  'day',
  'time_of_day',
  'clock',
  'season',
  'weather',
  'temperature',
  'location',
  'tension',
  'factions',
  'characters',
  'npcs',
  'resources',
  'challenges',
  'zombie_sightings_add',
  'flags',
  'narrator',
]

const GERILIM_DEGERLERI = ['düşük', 'orta', 'yüksek']

const metin = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const denetim = computed(() => jsonDenetle(props.modelValue))

/** Geçerli JSON'da bile sessizce düşecek alanlar için uyarı üret. */
const uyarilar = computed(() => {
  if (!denetim.value.gecerli) return []
  const veri = denetim.value.veri
  const liste = []

  const bilinmeyen = Object.keys(veri).filter((k) => !KABUL_EDILEN.includes(k))
  if (bilinmeyen.length) {
    liste.push(`Sunucu şu üst alanları yok sayar: ${bilinmeyen.join(', ')}.`)
  }
  if ('tension' in veri && !GERILIM_DEGERLERI.includes(veri.tension)) {
    liste.push(`\`tension\` yalnızca ${GERILIM_DEGERLERI.join(' / ')} olabilir.`)
  }
  if ('day' in veri) {
    const g = typeof veri.day === 'string' ? veri.day.trim() : veri.day
    const sayi = typeof g === 'number' ? Number.isFinite(g) : /^\d+$/.test(String(g))
    if (!sayi) liste.push('`day` bir tam sayı olmalı, yoksa yok sayılır.')
  }
  for (const alan of ['time_of_day', 'clock', 'season', 'weather', 'temperature']) {
    if (alan in veri && !String(veri[alan] ?? '').trim()) {
      liste.push(`Boş \`${alan}\` yok sayılır — mevcut değer korunur.`)
    }
  }
  return liste
})

/* ------------------------------------------------------------- kısayollar */

const ws = computed(() => props.worldState || {})

/** Sahne dışındaki karakterler önce gelsin. */
const kadro = computed(() =>
  Object.entries(props.characters || {})
    .filter(([, k]) => k?.alive !== false)
    .map(([ad, k]) => ({ ad, ...katilimOzeti(k?.presence) }))
    .sort((a, b) => Number(a.sahnede) - Number(b.sahnede)),
)

const secilenKarakter = ref('')
watch(
  kadro,
  (liste) => {
    if (!liste.length) {
      secilenKarakter.value = ''
    } else if (!liste.some((k) => k.ad === secilenKarakter.value)) {
      secilenKarakter.value = liste[0].ad
    }
  },
  { immediate: true },
)

function taslakYaz(nesne) {
  metin.value = jsonYaz(nesne)
}

const KISAYOLLAR = computed(() => [
  {
    ad: 'Gün ve saat',
    ikon: 'schedule',
    yap: () =>
      taslakYaz({
        day: ws.value.day ?? 1,
        clock: ws.value.clock || '06:00',
        time_of_day: ws.value.time_of_day || 'sabah',
      }),
  },
  {
    ad: 'Hava',
    ikon: 'rainy',
    yap: () =>
      taslakYaz({
        weather: ws.value.weather || 'kapalı',
        temperature: ws.value.temperature || '7°C',
        season: ws.value.season || 'geç sonbahar',
      }),
  },
  {
    ad: 'Konum',
    ikon: 'location_on',
    yap: () => taslakYaz({ location: ws.value.location || '' }),
  },
  {
    ad: 'Gerilim',
    ikon: 'local_fire_department',
    yap: () => taslakYaz({ tension: ws.value.tension || 'orta' }),
  },
  {
    ad: 'Bayrak',
    ikon: 'flag',
    yap: () => taslakYaz({ flags: { yeni_bayrak: true } }),
  },
  {
    ad: 'Özet',
    ikon: 'menu_book',
    yap: () =>
      taslakYaz({
        narrator: { plot_summary: ws.value.narrator?.plot_summary || '' },
      }),
  },
])

/** Bir karakteri sahneye döndürür — `presence.until` koşulu beklenmeden. */
function sahneyeDondur() {
  if (!secilenKarakter.value) return
  taslakYaz({
    characters: {
      [secilenKarakter.value]: { presence: { state: 'sahnede', note: '' } },
    },
  })
}

function bicimlendir() {
  if (!denetim.value.gecerli) return
  taslakYaz(denetim.value.veri)
}

function temizle() {
  metin.value = ''
}

function uygula() {
  if (!denetim.value.gecerli || props.patching) return
  emit('uygula', denetim.value.veri)
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <p class="text-meta text-muted">
      Yama doğrudan dünya durumuna işlenir — anlatıcı modeli devreye girmez, oyunculara
      hiçbir sahne düşmez. Alanlar <b>derin birleştirilir</b>: yalnızca yazdığın anahtarlar
      değişir.
    </p>

    <!-- Hazır kısayollar -->
    <div class="flex flex-col gap-2">
      <span class="text-panel uppercase tracking-[0.06em] text-muted">Sık kullanılanlar</span>
      <div class="flex flex-wrap gap-1.5">
        <BaseButton
          v-for="k in KISAYOLLAR"
          :key="k.ad"
          size="sm"
          variant="subtle"
          :icon="k.ikon"
          @click="k.yap()"
        >
          {{ k.ad }}
        </BaseButton>
      </div>

      <!-- Sahneye döndürme -->
      <div class="flex flex-wrap items-center gap-2">
        <label class="flex items-center gap-1.5">
          <span class="text-label text-muted">Karakteri sahneye döndür</span>
          <select
            v-model="secilenKarakter"
            :disabled="!kadro.length"
            aria-label="Sahneye döndürülecek karakter"
            class="h-7 rounded-md border border-border bg-surface-2 px-2 text-label text-text outline-none focus-visible:border-gm focus-visible:outline-gm disabled:opacity-50"
          >
            <option v-for="k in kadro" :key="k.ad" :value="k.ad">
              {{ k.ad }} — {{ k.etiket }}
            </option>
          </select>
        </label>
        <BaseButton
          size="sm"
          variant="subtle"
          icon="directions_walk"
          :disabled="!secilenKarakter"
          @click="sahneyeDondur"
        >
          Taslağa yaz
        </BaseButton>
      </div>
    </div>

    <!-- JSON alanı -->
    <label class="flex flex-col gap-1.5">
      <span class="text-panel uppercase tracking-[0.06em] text-muted">Yama (JSON)</span>
      <textarea
        v-model="metin"
        rows="8"
        spellcheck="false"
        placeholder='{"characters": {"Okan": {"presence": {"state": "sahnede"}}}}'
        :disabled="patching"
        class="w-full resize-y rounded-md border bg-surface-2 px-3 py-2 font-mono text-meta text-text outline-none transition-colors duration-[var(--duration-fast)] placeholder:text-faint focus-visible:outline-gm disabled:opacity-60"
        :class="
          denetim.bos
            ? 'border-border focus-visible:border-gm'
            : denetim.gecerli
              ? 'border-ok/50'
              : 'border-danger/60'
        "
        :aria-invalid="!denetim.bos && !denetim.gecerli"
      />
    </label>

    <!-- Denetim sonucu -->
    <p
      v-if="!denetim.bos && !denetim.gecerli"
      class="flex flex-col gap-0.5 rounded-card border border-danger/40 bg-danger-soft px-3 py-2 text-meta text-danger"
      role="alert"
    >
      <span class="flex items-start gap-1.5">
        <Icon name="error" :size="16" class="mt-0.5 shrink-0" />
        <span>{{ denetim.mesaj }}</span>
      </span>
      <span v-if="denetim.ayrinti" class="pl-6 font-mono text-label opacity-80">
        {{ denetim.ayrinti }}
      </span>
    </p>

    <p
      v-else-if="denetim.gecerli"
      class="flex flex-wrap items-center gap-1.5 text-meta text-ok"
      role="status"
    >
      <Icon name="check_circle" :size="16" />
      JSON geçerli.
      <Badge
        v-for="alan in Object.keys(denetim.veri)"
        :key="alan"
        size="sm"
        :tone="KABUL_EDILEN.includes(alan) ? 'muted' : 'warn'"
      >
        {{ alan }}
      </Badge>
    </p>

    <ul v-if="uyarilar.length" class="flex flex-col gap-1">
      <li
        v-for="(u, i) in uyarilar"
        :key="i"
        class="flex items-start gap-1.5 text-label text-warn"
      >
        <Icon name="warning" :size="13" class="mt-0.5 shrink-0" />
        <span>{{ u }}</span>
      </li>
    </ul>

    <!-- Eylemler -->
    <div class="flex flex-wrap items-center gap-2">
      <BaseButton
        variant="gm"
        icon="save"
        :disabled="!denetim.gecerli"
        :loading="patching"
        loading-text="Uygulanıyor…"
        @click="uygula"
      >
        Yamayı uygula
      </BaseButton>
      <BaseButton
        size="md"
        variant="subtle"
        icon="data_object"
        :disabled="!denetim.gecerli"
        @click="bicimlendir"
      >
        Biçimlendir
      </BaseButton>
      <BaseButton
        size="md"
        variant="quiet"
        icon="delete_forever"
        :disabled="denetim.bos || patching"
        @click="temizle"
      >
        Temizle
      </BaseButton>
    </div>

    <p
      v-if="hata"
      class="flex items-start gap-1.5 text-meta text-danger"
      role="alert"
    >
      <Icon name="error" :size="16" class="mt-0.5 shrink-0" />
      <span>{{ hata }}</span>
    </p>
    <p v-else-if="bilgi" class="flex items-center gap-1.5 text-meta text-ok" role="status">
      <Icon name="check_circle" :size="16" />
      {{ bilgi }}
    </p>

    <details class="rounded-card border border-border bg-surface-2 px-3 py-2">
      <summary class="cursor-pointer text-label text-muted">
        Sunucunun kabul ettiği üst alanlar
      </summary>
      <div class="mt-2 flex flex-wrap gap-1">
        <code
          v-for="alan in KABUL_EDILEN"
          :key="alan"
          class="rounded-chip border border-border bg-surface px-2 py-0.5 font-mono text-label text-muted"
          >{{ alan }}</code
        >
      </div>
      <p class="mt-2 text-label text-faint">
        Bunların dışındaki alanlar sessizce atılır. Kadro `characters` altına yeni isim
        eklenemez; tanınmayan isim `npcs`'e yönlendirilir.
      </p>
    </details>
  </div>
</template>
