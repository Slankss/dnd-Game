<script setup>
/**
 * Görsel harita — yerler, aralarındaki yollar ve grubun konumu.
 *
 * Sis perdesi (bu bileşenin asıl fikri): bir yer hakkında ne kadar biliniyorsa
 * o kadar çizilir.
 *
 *   duyuldu     silik, kesik çizgili küçük bir işaret + soru işareti.
 *               Adı dışında hiçbir şey görünmez (sunucu zaten ayrıntıyı
 *               göndermiyor — bkz. models/worldmap.public_place).
 *   görüldü     orta boy, kesik çerçeve, tehlike rengi, tür etiketi.
 *   keşfedildi  dolu düğüm, tam etiket, tehlike halkası, oradaki karakterler.
 *
 * Yerleşim `mapLayout.js`'te hesaplanır ve KARARLIDIR: aynı veri her zaman
 * aynı resmi verir, yoklama düğümleri oynatmaz.
 *
 * Çizim saf SVG'dir — dış kütüphane yok, `v-html` yok.
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import { haritaYerlesimi } from './mapLayout'
import { colorFor } from '@/utils/characterColors'

const props = defineProps({
  /** world_state.map */
  harita: { type: Object, default: () => ({}) },
  /** Seçili yer (dış panelde ayrıntısı gösterilen) */
  secili: { type: String, default: '' },
  /** Kompakt kip: kenar çubuğundaki mini harita (etiketler kısalır) */
  mini: { type: Boolean, default: false },
  /** Anlatıcı kipi: sis perdesi yok, her şey açık çizilir */
  gm: { type: Boolean, default: false },
  /** {yer: 0-100} zombi yoğunluğu — yalnız bilinen yerler için gelir */
  yogunluk: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['sec'])

const yerlesim = computed(() => haritaYerlesimi(props.harita))

/* --- yol çizimi --------------------------------------------------------- */

/** Aynı çiftin ikinci yolu yay yapılır ki üst üste binmesin. */
function yolCizgisi(kenar) {
  if (!kenar.egri) return `M ${kenar.x1} ${kenar.y1} L ${kenar.x2} ${kenar.y2}`
  const mx = (kenar.x1 + kenar.x2) / 2
  const my = (kenar.y1 + kenar.y2) / 2
  const dx = kenar.x2 - kenar.x1
  const dy = kenar.y2 - kenar.y1
  const boy = Math.hypot(dx, dy) || 1
  // Dik normal boyunca kaydırılmış kontrol noktası.
  const kx = mx + (-dy / boy) * kenar.egri
  const ky = my + (dx / boy) * kenar.egri
  return `M ${kenar.x1} ${kenar.y1} Q ${kx} ${ky} ${kenar.x2} ${kenar.y2}`
}

const YOL_RENGI = {
  ana: 'var(--color-border-strong)',
  ara: 'var(--color-border-strong)',
  patika: 'var(--color-border)',
}

function yolRengi(kenar) {
  if (kenar.kapali) return 'var(--color-danger)'
  if (kenar.durum && kenar.durum !== 'açık') return 'var(--color-warn)'
  if (kenar.zayif) return 'var(--color-border)'
  return YOL_RENGI[kenar.ton] || 'var(--color-border-strong)'
}

function yolDeseni(kenar) {
  if (kenar.kapali) return '3 6'
  if (kenar.tur === 'demiryolu') return '7 4'
  if (kenar.tur === 'patika') return '2 5'
  if (kenar.zayif) return '5 7'
  return ''
}

function yolBaslik(kenar) {
  const parcalar = [kenar.tur || 'yol']
  if (kenar.km !== null) parcalar.push(`${kenar.km} km`)
  if (kenar.durum && kenar.durum !== 'açık') parcalar.push(kenar.durum.toUpperCase())
  if (kenar.risk !== null) parcalar.push(`risk ${kenar.risk}/5`)
  return parcalar.join(' · ')
}

/** Tehlike → çizgi rengi (tasarım sistemindeki durum renkleri). */
const TEHLIKE_RENGI = {
  güvenli: 'var(--color-ok)',
  temkinli: 'var(--color-warn)',
  tehlikeli: 'var(--color-danger)',
  ölümcül: 'var(--color-danger)',
  bilinmiyor: 'var(--color-border-strong)',
}

/** Yer türü → ikon (yalnızca türü bilinen yerlerde kullanılır). */
const TUR_IKONU = [
  [/depo|ambar|stok/i, 'inventory_2'],
  [/kamp|yerleşim|sığınak|barınak/i, 'cabin'],
  [/harabe|kalıntı|yıkıntı|manastır/i, 'temple_buddhist'],
  [/tesis|fabrika|laboratuvar|sanayi/i, 'factory'],
  [/hastane|sağlık|revir|klinik/i, 'local_hospital'],
  [/kule|anten|verici|radyo/i, 'cell_tower'],
  [/su|baraj|göl|kuyu|liman|kıyı/i, 'water_drop'],
  [/yol|köprü|geçit|tünel|hat/i, 'alt_route'],
  [/tarla|sera|çiftlik|bahçe/i, 'potted_plant'],
  [/otopark|garaj|terminal|otogar/i, 'local_parking'],
  [/okul|üniversite|kütüphane/i, 'school'],
  [/otel|ev|apartman|bina/i, 'home_work'],
]

function turIkonu(dugum) {
  if (dugum.duzey === 'duyuldu' && !props.gm) return 'help'
  const metin = `${dugum.bilgi?.kind || ''} ${dugum.ad}`
  for (const [kalip, ikon] of TUR_IKONU) if (kalip.test(metin)) return ikon
  return 'location_on'
}

function tehlikeRengi(dugum) {
  if (dugum.duzey === 'duyuldu' && !props.gm) return TEHLIKE_RENGI.bilinmiyor
  return TEHLIKE_RENGI[dugum.bilgi?.danger] || TEHLIKE_RENGI.bilinmiyor
}

/** Etiket: mini haritada uzun yer adları kısaltılır. */
function etiket(dugum) {
  const ad = dugum.ad
  const sinir = props.mini ? 16 : 28
  return ad.length > sinir ? `${ad.slice(0, sinir - 1)}…` : ad
}

/** Ekran okuyucu için tek satırlık özet. */
function erisimMetni(dugum) {
  const parcalar = [dugum.ad, dugum.duzey]
  if (dugum.burada) parcalar.push('grubun konumu')
  if (dugum.duzey !== 'duyuldu') {
    if (dugum.bilgi?.kind) parcalar.push(dugum.bilgi.kind)
    if (dugum.bilgi?.danger && dugum.bilgi.danger !== 'bilinmiyor') {
      parcalar.push(`tehlike: ${dugum.bilgi.danger}`)
    }
  }
  if (dugum.kimler.length) parcalar.push(`burada: ${dugum.kimler.join(', ')}`)
  return parcalar.join(', ')
}

/** Karakter noktalarının düğüm çevresindeki konumu. */
function kisiKonumu(dugum, i, adet) {
  const aci = (i / Math.max(1, adet)) * Math.PI * 2 - Math.PI / 2
  const r = dugum.r + 10
  return { cx: dugum.x + Math.cos(aci) * r, cy: dugum.y + Math.sin(aci) * r }
}

function sec(dugum) {
  emit('sec', dugum.ad)
}

/**
 * Düğümün çevresindeki yoğunluk halkası: dolu yay = o bölgedeki ölü oranı.
 * Yalnız yoğunluğu BİLİNEN yerlerde çizilir (sunucu bilinmeyenleri zaten
 * göndermiyor) — haritaya bakıp keşfedilmemiş bir bölgenin kalabalığı
 * okunamaz.
 */
function yogunlukHalkasi(dugum) {
  const deger = props.yogunluk?.[dugum.ad]
  if (deger == null) return null
  const r = dugum.r + 4.5
  const cevre = 2 * Math.PI * r
  const dolu = (Math.max(0, Math.min(100, Number(deger))) / 100) * cevre
  const renk =
    deger >= 66 ? 'var(--color-danger)' : deger >= 38 ? 'var(--color-warn)' : 'var(--color-ok)'
  return { r, dash: `${dolu} ${cevre - dolu}`, renk, deger: Math.round(deger) }
}
</script>

<template>
  <div
    class="relative w-full overflow-hidden rounded-card border border-border bg-surface-2"
    :class="mini ? 'h-44' : 'h-[min(62vh,540px)]'"
  >
    <svg
      v-if="!yerlesim.bos"
      :viewBox="yerlesim.viewBox"
      class="size-full"
      role="img"
      aria-label="Oyun haritası"
      preserveAspectRatio="xMidYMid meet"
    >
      <defs>
        <!-- Bilinmeyen bölgenin puslu halkası -->
        <radialGradient id="sis" cx="50%" cy="50%" r="50%">
          <stop offset="60%" stop-color="var(--color-accent)" stop-opacity="0.10" />
          <stop offset="100%" stop-color="var(--color-accent)" stop-opacity="0" />
        </radialGradient>
      </defs>

      <!-- şehir etiketleri: mekanlar hangi şehre bağlı, göz kararı görünsün -->
      <g v-if="!mini" pointer-events="none">
        <text
          v-for="sehir in yerlesim.sehirler"
          :key="sehir.ad"
          :x="sehir.x"
          :y="sehir.y"
          text-anchor="middle"
          font-size="15"
          letter-spacing="1.6"
          fill="var(--color-text-faint)"
          opacity="0.75"
        >
          {{ sehir.ad.toLocaleUpperCase('tr-TR') }}
        </text>
      </g>

      <!-- yollar: tür kalınlığı belirler, çökük yol kırmızı ve kesik -->
      <g stroke-linecap="round" fill="none">
        <path
          v-for="kenar in yerlesim.kenarlar"
          :key="kenar.anahtar"
          :d="yolCizgisi(kenar)"
          :stroke="yolRengi(kenar)"
          :stroke-width="kenar.zayif ? kenar.kalinlik * 0.7 : kenar.kalinlik"
          :stroke-dasharray="yolDeseni(kenar)"
          :opacity="kenar.zayif ? 0.45 : kenar.kapali ? 0.75 : 0.9"
        >
          <title>{{ yolBaslik(kenar) }}</title>
        </path>
      </g>

      <!-- düğümler -->
      <g
        v-for="dugum in yerlesim.dugumler"
        :key="dugum.ad"
        class="cursor-pointer focus:outline-none"
        role="button"
        tabindex="0"
        :aria-label="erisimMetni(dugum)"
        :aria-pressed="secili === dugum.ad"
        @click="sec(dugum)"
        @keydown.enter.prevent="sec(dugum)"
        @keydown.space.prevent="sec(dugum)"
      >
        <!-- grubun konumu: yumuşak hale -->
        <circle
          v-if="dugum.burada"
          :cx="dugum.x"
          :cy="dugum.y"
          :r="dugum.r + 26"
          fill="url(#sis)"
        />
        <!-- seçim halkası -->
        <circle
          v-if="secili === dugum.ad"
          :cx="dugum.x"
          :cy="dugum.y"
          :r="dugum.r + 7"
          fill="none"
          stroke="var(--color-accent)"
          stroke-width="1.5"
          opacity="0.85"
        />
        <!-- zombi yoğunluğu halkası -->
        <circle
          v-if="yogunlukHalkasi(dugum)"
          :cx="dugum.x"
          :cy="dugum.y"
          :r="yogunlukHalkasi(dugum).r"
          fill="none"
          :stroke="yogunlukHalkasi(dugum).renk"
          stroke-width="2.5"
          :stroke-dasharray="yogunlukHalkasi(dugum).dash"
          stroke-linecap="round"
          :transform="`rotate(-90 ${dugum.x} ${dugum.y})`"
          opacity="0.75"
        >
          <title>zombi yoğunluğu: {{ yogunlukHalkasi(dugum).deger }}/100</title>
        </circle>

        <!-- düğüm gövdesi -->
        <circle
          :cx="dugum.x"
          :cy="dugum.y"
          :r="dugum.r"
          :fill="dugum.burada ? 'var(--color-accent-soft)' : 'var(--color-surface)'"
          :stroke="dugum.burada ? 'var(--color-accent)' : tehlikeRengi(dugum)"
          :stroke-width="dugum.duzey === 'keşfedildi' ? 2.5 : 1.75"
          :stroke-dasharray="dugum.duzey === 'duyuldu' && !gm ? '3 4' : dugum.duzey === 'görüldü' ? '7 4' : ''"
          :opacity="dugum.duzey === 'duyuldu' && !gm ? 0.55 : 1"
        />
        <!-- ikon -->
        <foreignObject
          :x="dugum.x - dugum.r * 0.6"
          :y="dugum.y - dugum.r * 0.6"
          :width="dugum.r * 1.2"
          :height="dugum.r * 1.2"
        >
          <div class="flex size-full items-center justify-center">
            <Icon
              :name="turIkonu(dugum)"
              :size="Math.round(dugum.r * 1.05)"
              :class="
                dugum.burada
                  ? 'text-accent'
                  : dugum.duzey === 'duyuldu' && !gm
                    ? 'text-faint'
                    : 'text-muted'
              "
            />
          </div>
        </foreignObject>

        <!-- karakter noktaları -->
        <circle
          v-for="(kisi, i) in dugum.kimler"
          :key="kisi"
          :cx="kisiKonumu(dugum, i, dugum.kimler.length).cx"
          :cy="kisiKonumu(dugum, i, dugum.kimler.length).cy"
          r="4.5"
          :fill="colorFor(kisi)"
          stroke="var(--color-bg)"
          stroke-width="1.5"
        >
          <title>{{ kisi }}</title>
        </circle>

        <!-- etiket -->
        <text
          :x="dugum.x"
          :y="dugum.y + dugum.r + 16"
          text-anchor="middle"
          :font-size="mini ? 11 : 12"
          :fill="dugum.duzey === 'duyuldu' && !gm ? 'var(--color-faint)' : 'var(--color-muted)'"
          :font-style="dugum.duzey === 'duyuldu' && !gm ? 'italic' : 'normal'"
        >
          {{ etiket(dugum) }}
        </text>
        <text
          v-if="!mini && dugum.duzey !== 'duyuldu' && dugum.bilgi?.kind"
          :x="dugum.x"
          :y="dugum.y + dugum.r + 30"
          text-anchor="middle"
          font-size="10"
          fill="var(--color-faint)"
        >
          {{ dugum.bilgi.kind }}
        </text>
      </g>
    </svg>

    <!-- harita boş -->
    <div v-else class="flex size-full flex-col items-center justify-center gap-1 text-center">
      <Icon name="explore_off" :size="22" class="text-faint" />
      <p class="text-label text-faint">Harita boş — henüz bir yer kaydedilmedi.</p>
    </div>
  </div>
</template>
