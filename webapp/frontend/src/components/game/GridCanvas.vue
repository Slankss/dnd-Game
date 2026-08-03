<script setup>
/**
 * Kare harita (ızgara) — sahnenin 2D görünümü.
 *
 * Veri sunucudan `grid[y][x]` biçiminde gelir: her eleman bir HÜCRE kaydıdır
 * (zemin + geçilebilirlik). Oyuncular dizinin içinde DEĞİLDİR; ayrı bir
 * `entities` listesinde kendi x/y'leriyle gelirler ve burada o koordinata
 * çizilirler. Böylece çizim de veri modeliyle aynı ayrımı korur.
 *
 * Çizim saf SVG: her kare bir <rect>, her varlık kendi şekliyle üstte.
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import { colorFor, bashHarf } from '@/utils/characterColors'

const props = defineProps({
  /** {width, height, cells, entities, name} */
  izgara: { type: Object, default: null },
  /** Seçili karakterin kimliği (vurgulanır) */
  secili: { type: String, default: '' },
  /** Kare kenarı (SVG birimi) */
  kare: { type: Number, default: 34 },
})

const emit = defineEmits(['kareSec'])

/** Zemin türü → dolgu rengi. Geçilemeyen kareler belirgin şekilde koyudur. */
const ZEMIN = {
  zemin: 'var(--color-surface-2)',
  yol: 'var(--color-surface-3)',
  moloz: 'color-mix(in oklab, var(--color-warn) 12%, var(--color-surface-2))',
  su: 'color-mix(in oklab, #4a6c9c 26%, var(--color-surface-2))',
  çimen: 'color-mix(in oklab, var(--color-ok) 14%, var(--color-surface-2))',
  duvar: 'var(--color-border-strong)',
  enkaz: 'color-mix(in oklab, var(--color-danger) 18%, var(--color-surface))',
  uçurum: 'var(--color-bg)',
  boşluk: 'var(--color-bg)',
}

const en = computed(() => Number(props.izgara?.width) || 0)
const boy = computed(() => Number(props.izgara?.height) || 0)
const varMi = computed(() => en.value > 0 && boy.value > 0)

/** Hücre kayıtları (yalnız zemin) — dizideki sıra korunur. */
const kareler = computed(() => {
  if (!varMi.value) return []
  const cells = props.izgara?.cells || []
  const out = []
  for (let y = 0; y < boy.value; y++) {
    for (let x = 0; x < en.value; x++) {
      const hucre = cells?.[y]?.[x] || {}
      out.push({
        x,
        y,
        terrain: hucre.terrain || 'zemin',
        passable: hucre.passable !== false,
      })
    }
  }
  return out
})

/** Varlıklar koordinatlarına göre gruplanır: aynı karede birden fazla olabilir. */
const kareVarliklari = computed(() => {
  const harita = new Map()
  for (const varlik of props.izgara?.entities || []) {
    const anahtar = `${varlik.x},${varlik.y}`
    if (!harita.has(anahtar)) harita.set(anahtar, [])
    harita.get(anahtar).push(varlik)
  }
  return harita
})

/** Bir karedeki varlıklar, çizim sırası: bina → eşya → NPC → oyuncu. */
const SIRA = { building: 0, item: 1, npc: 2, player: 3 }
function varliklar(x, y) {
  const liste = kareVarliklari.value.get(`${x},${y}`) || []
  return [...liste].sort((a, b) => (SIRA[a.kind] ?? 9) - (SIRA[b.kind] ?? 9))
}

const KIND_IKONU = { item: 'inventory_2', building: 'domain', npc: 'person' }

/** Aynı karedeki varlıklar üst üste binmesin: küçük bir açılım. */
function kayma(i, adet) {
  if (adet <= 1) return { dx: 0, dy: 0 }
  const aci = (i / adet) * Math.PI * 2 - Math.PI / 2
  const r = props.kare * 0.2
  return { dx: Math.cos(aci) * r, dy: Math.sin(aci) * r }
}

const viewBox = computed(() => `0 0 ${en.value * props.kare} ${boy.value * props.kare}`)
</script>

<template>
  <div
    class="relative w-full overflow-auto rounded-card border border-border bg-surface"
  >
    <svg
      v-if="varMi"
      :viewBox="viewBox"
      class="block w-full"
      role="img"
      :aria-label="`Kare harita: ${izgara?.name || 'sahne'} — ${en}×${boy}`"
      preserveAspectRatio="xMidYMid meet"
    >
      <!-- zemin -->
      <g>
        <rect
          v-for="kutu in kareler"
          :key="`${kutu.x},${kutu.y}`"
          :x="kutu.x * kare"
          :y="kutu.y * kare"
          :width="kare"
          :height="kare"
          :fill="ZEMIN[kutu.terrain] || ZEMIN.zemin"
          stroke="var(--color-border)"
          stroke-width="0.75"
          class="cursor-pointer"
          @click="emit('kareSec', { x: kutu.x, y: kutu.y })"
        >
          <title>{{ kutu.x }},{{ kutu.y }} — {{ kutu.terrain }}{{ kutu.passable ? '' : ' (geçilemez)' }}</title>
        </rect>
      </g>

      <!-- varlıklar: dizinin içinde değil, kendi x/y'leriyle çizilir -->
      <template v-for="kutu in kareler" :key="`v-${kutu.x},${kutu.y}`">
        <g
          v-for="(varlik, i) in varliklar(kutu.x, kutu.y)"
          :key="varlik.id"
          :transform="`translate(${kutu.x * kare + kare / 2 + kayma(i, varliklar(kutu.x, kutu.y).length).dx}, ${
            kutu.y * kare + kare / 2 + kayma(i, varliklar(kutu.x, kutu.y).length).dy
          })`"
        >
          <title>{{ varlik.name || varlik.id }} ({{ varlik.kind }})</title>

          <!-- oyuncu: renkli daire + baş harf -->
          <template v-if="varlik.kind === 'player'">
            <circle
              :r="kare * 0.32"
              :fill="colorFor(varlik.id)"
              :stroke="secili === varlik.id ? 'var(--color-accent)' : 'var(--color-bg)'"
              :stroke-width="secili === varlik.id ? 2.5 : 1.5"
            />
            <text
              text-anchor="middle"
              dominant-baseline="central"
              :font-size="kare * 0.34"
              font-weight="600"
              fill="#0b0d0f"
            >
              {{ bashHarf(varlik.name || varlik.id) }}
            </text>
          </template>

          <!-- NPC: eşkenar dörtgen -->
          <template v-else-if="varlik.kind === 'npc'">
            <rect
              :x="-kare * 0.22"
              :y="-kare * 0.22"
              :width="kare * 0.44"
              :height="kare * 0.44"
              transform="rotate(45)"
              fill="var(--color-surface-3)"
              stroke="var(--color-muted)"
              stroke-width="1.5"
            />
          </template>

          <!-- bina/eşya: ikon -->
          <template v-else>
            <foreignObject
              :x="-kare * 0.26"
              :y="-kare * 0.26"
              :width="kare * 0.52"
              :height="kare * 0.52"
            >
              <div class="flex size-full items-center justify-center">
                <Icon
                  :name="KIND_IKONU[varlik.kind] || 'circle'"
                  :size="Math.round(kare * 0.42)"
                  :class="varlik.kind === 'building' ? 'text-faint' : 'text-warn'"
                />
              </div>
            </foreignObject>
          </template>
        </g>
      </template>
    </svg>

    <div v-else class="flex h-32 flex-col items-center justify-center gap-1">
      <Icon name="grid_off" :size="20" class="text-faint" />
      <p class="text-label text-faint">Sahne ızgarası henüz kurulmadı.</p>
    </div>
  </div>
</template>
