<script setup>
/**
 * Zombi tehdidi paneli — "dikkatli seyahat et" kararını ÖLÇÜLEBİLİR kılar.
 *
 * Üç sayı gösterilir:
 *   gürültü   — grubun çıkardığı ses. Silah/araç/bağırma yükseltir, sessiz
 *               geçen zaman söndürür. Yükseldikçe karşılaşma ihtimali artar.
 *   dikkat    — bölgenin gruba yönelmiş ilgisi (karşılaşmalar biriktirir).
 *   yoğunluk  — bulunulan yerin ölü nüfusu. YALNIZ keşfedilmiş yerler için
 *               gelir; gidilmemiş bir yerin yoğunluğu sunucudan hiç gönderilmez.
 *
 * Karşılaşmanın kendisini sunucu zarı belirler (app/models/threat.py); burası
 * sadece sonucu okur.
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import SkeletonLine from '../ui/SkeletonLine.vue'

const props = defineProps({
  /** world_state.threat (public_threat çıktısı) */
  tehdit: { type: Object, default: null },
  /** Grubun şu anki konumu */
  konum: { type: String, default: '' },
  yukleniyor: { type: Boolean, default: false },
})

const gurultu = computed(() => Number(props.tehdit?.noise ?? 0))
const dikkat = computed(() => Number(props.tehdit?.heat ?? 0))
const sessizTur = computed(() => Number(props.tehdit?.quiet_turns ?? 0))
const yolda = computed(() => !!props.tehdit?.travelling)
const son = computed(() => props.tehdit?.last || null)

/** Bulunulan yerin yoğunluğu (yoldaysak yolun). */
const yogunluk = computed(() => {
  const d = props.tehdit?.density || {}
  if (yolda.value && d.yol != null) return Number(d.yol)
  const deger = d[props.konum]
  return deger == null ? null : Number(deger)
})

function ton(deger) {
  if (deger >= 66) return 'danger'
  if (deger >= 38) return 'warn'
  return 'ok'
}

const RENK = { ok: 'bg-ok', warn: 'bg-warn', danger: 'bg-danger' }

const olcerler = computed(() => {
  const liste = [
    { ad: 'Gürültünüz', deger: gurultu.value, ikon: 'graphic_eq',
      ipucu: 'Silah sesi, araç ve bağırma yükseltir; sessiz geçen saatler söndürür.' },
    { ad: 'Bölgenin dikkati', deger: dikkat.value, ikon: 'visibility',
      ipucu: 'Karşılaşmalar biriktirir; uzun süre sessiz kalınca düşer.' },
  ]
  if (yogunluk.value !== null) {
    liste.unshift({
      ad: yolda.value ? 'Yol yoğunluğu' : 'Bölge yoğunluğu',
      deger: yogunluk.value, ikon: 'groups',
      ipucu: 'Buradaki ölü nüfusu. Yalnız keşfedilmiş yerler için bilinir.',
    })
  }
  return liste
})

/**
 * Son göç hareketi: bir olay (patlama, silah sesi) bir bölgeye ölü çekmişse
 * hangi bölgelerin boşaldığını gösterir. Nüfus korunur — gelenler komşu
 * bölgelerden eksilir, bu yüzden boşalan bölge bir süre daha sakindir.
 */
const goc = computed(() => {
  const liste = props.tehdit?.migrations || []
  const son = liste[liste.length - 1]
  if (!son?.from?.length) return null
  return {
    hedef: son.target,
    tur: son.type || 'ses',
    kaynaklar: son.from.map((k) => `${k.place} −${Math.round(k.amount)}`).join(', '),
  }
})

/** Son karşılaşmanın tek satırlık özeti. */
const sonMetin = computed(() => {
  if (!son.value?.var) return ''
  const tipler = (son.value.types || []).join(', ')
  return `${son.value.severity} · ~${son.value.count} ölü${tipler ? ` (${tipler})` : ''}`
})
</script>

<template>
  <div class="flex flex-col gap-2">
    <SkeletonLine v-if="yukleniyor" :lines="2" />

    <template v-else-if="tehdit">
      <div class="flex flex-wrap items-center gap-1.5">
        <Badge v-if="yolda" tone="danger" size="sm" icon="directions_walk">
          yolda — en tehlikeli hâl
        </Badge>
        <Badge v-else tone="muted" size="sm" icon="home_work">yerleşik</Badge>
        <Badge v-if="sessizTur >= 3" tone="warn" size="sm" icon="hourglass_top">
          {{ sessizTur }} turdur sessiz
        </Badge>
      </div>

      <ul class="flex flex-col gap-1.5">
        <li v-for="olcer in olcerler" :key="olcer.ad" :title="olcer.ipucu">
          <div class="flex items-center gap-1.5">
            <Icon :name="olcer.ikon" :size="13" class="text-faint" />
            <span class="text-label text-muted">{{ olcer.ad }}</span>
            <span class="ml-auto text-label nums-tabular text-muted">{{ olcer.deger }}/100</span>
          </div>
          <div class="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
            <div
              class="h-full rounded-full transition-[width] duration-[var(--duration-base)]"
              :class="RENK[ton(olcer.deger)]"
              :style="{ width: `${Math.max(2, olcer.deger)}%` }"
            />
          </div>
        </li>
      </ul>

      <p v-if="goc" class="flex items-start gap-1.5 text-label text-warn">
        <Icon name="moving" :size="13" class="mt-0.5 shrink-0" />
        <span>
          {{ goc.tur }} → <strong class="font-medium">{{ goc.hedef }}</strong> bölgesine ölü
          çekildi; boşalan komşular: {{ goc.kaynaklar }}
        </span>
      </p>

      <p v-if="sonMetin" class="flex items-start gap-1.5 text-label text-faint">
        <Icon name="skull" :size="13" class="mt-0.5 shrink-0" />
        <span>Son karşılaşma: {{ sonMetin }}</span>
      </p>

      <p class="text-label text-faint">
        Yola çıkmak karşılaşma ihtimalini kat kat artırır. Sessiz ilerlemek, gece yerine gündüz
        yürümek ve ateş etmemek gerçekten işe yarar.
      </p>
    </template>

    <p v-else class="text-label text-faint">Tehdit ölçümü henüz başlamadı.</p>
  </div>
</template>
