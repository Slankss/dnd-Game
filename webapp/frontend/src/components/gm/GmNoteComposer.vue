<script setup>
/**
 * Müdahale bestecisi — `/api/gm/note` üç modda çalışır.
 *
 *   gizli   → yönlendirme; yanıt SADECE bu ekranda kalır, oyuncular hiçbir şey görmez
 *   sahne   → yazdığın olay doğrudan oyuncu akışına sahne olarak düşer
 *   surpriz → anlatıcı sürpriz gelişmeyi kendi uydurur ve yayınlar (metin boş olabilir)
 *
 * Yanlış modda gönderim oyunu bozar: modun ne yaptığı her zaman ekranda yazar
 * ve YAYINLANAN modlarda gönderim iki adımlıdır (yaz → onayla).
 */
import { ref, computed, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { metinBicimle } from './gmYardimcilar'

const props = defineProps({
  /** İstek uçuşta mı (model 30-60 sn sürebilir) */
  gonderiliyor: { type: Boolean, default: false },
  /** Oyun başlamadıysa sunucu 400 döner — düğmeyi baştan kapat */
  oyunBasladi: { type: Boolean, default: false },
  /** Son gönderimin sonucu: `{published, text}` */
  sonuc: { type: Object, default: null },
  /** Son gönderimin hatası (Türkçe) */
  hata: { type: String, default: '' },
})

const emit = defineEmits(['gonder'])

const MODLAR = [
  {
    ad: 'gizli',
    baslik: 'Gizli yönlendirme',
    ikon: 'visibility_off',
    ozet: 'oyunculara gitmez',
    aciklama:
      'Yalnızca sana görünür. Anlatıcı bu turda oyunculara hiçbir sahne yazmaz; ' +
      'talimatı sonraki turlarda hayata geçirir. Yanıt bu ekranda kalır. ' +
      'Bu turda dünya durumundan SADECE anlatıcı defteri kaydedilir: zorluk, ' +
      'NPC, karakter, kaynak gibi oyuncuya görünen alanlar uygulanmaz — yoksa ' +
      'oyuncular henüz yaşamadıkları olayı panelde görüp önceden hazırlanır.',
    yerTutucu:
      'Örn: Crimson Dawn devriyesi iki tur içinde bölgeye girsin, ama önce izlerini göster.',
    dugme: 'Gizli notu gönder',
    yayin: false,
    metinZorunlu: true,
  },
  {
    ad: 'sahne',
    baslik: 'Sahne olarak yayınla',
    ikon: 'theater_comedy',
    ozet: 'oyuncu ekranına düşer',
    aciklama:
      'Yazdığın olay ANINDA oyuncuların akışına sahne olarak düşer. Anlatıcı senden ' +
      'ya da müdahaleden hiç söz etmez; zar mekaniği uygulanmaz.',
    yerTutucu:
      'Örn: Sığınağın kapısına üç yabancı dayanıyor; biri yaralı ve grubun ismini biliyor.',
    dugme: 'Sahneyi yayınla',
    yayin: true,
    metinZorunlu: true,
  },
  {
    ad: 'surpriz',
    baslik: 'Sürpriz olay üret',
    ikon: 'casino',
    ozet: 'anlatıcı uydurur ve yayınlar',
    aciklama:
      'Olayı anlatıcı kendisi icat eder — kendi planlarından, çözülmemiş bulmacalardan, ' +
      'fraksiyon tavırlarından ve azalan kaynaklardan besleyerek — ve oyunculara yayınlar. ' +
      'Metin BOŞ bırakılabilir; yön vermek istersen yaz.',
    yerTutucu: 'İsteğe bağlı yön: "kaynaklarla ilgili olsun" ya da "eski bir NPC dönsün". Boş bırakabilirsin.',
    dugme: 'Sürpriz olay üret',
    yayin: true,
    metinZorunlu: false,
  },
]

const mod = ref('gizli')
const metin = ref('')
/** Yayınlanan modlarda ikinci adım: onay bekleniyor mu */
const onayBekliyor = ref(false)

const aktif = computed(() => MODLAR.find((m) => m.ad === mod.value) || MODLAR[0])

const metinVar = computed(() => metin.value.trim().length > 0)
const gonderilebilir = computed(
  () => props.oyunBasladi && !props.gonderiliyor && (metinVar.value || !aktif.value.metinZorunlu),
)

/** Mod değişince onay adımı sıfırlanır — yanlış modda onaylamak olmasın. */
watch(mod, () => {
  onayBekliyor.value = false
})
watch(metin, () => {
  onayBekliyor.value = false
})

function gonder() {
  if (!gonderilebilir.value) return
  if (aktif.value.yayin && !onayBekliyor.value) {
    onayBekliyor.value = true
    return
  }
  onayBekliyor.value = false
  emit('gonder', { metin: metin.value.trim(), mod: mod.value })
  metin.value = ''
}

function vazgec() {
  onayBekliyor.value = false
}

/** Ctrl/Cmd+Enter gönderir. Düz Enter BİLEREK satır atlar: yayınlanan
 *  modlarda yanlışlıkla gönderim oyunu bozar. */
function tusla(e) {
  if (e.key !== 'Enter' || e.isComposing) return
  if (!(e.ctrlKey || e.metaKey)) return
  e.preventDefault()
  gonder()
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <!-- Mod seçimi -->
    <div class="flex flex-wrap gap-2" role="group" aria-label="Müdahale modu">
      <button
        v-for="m in MODLAR"
        :key="m.ad"
        type="button"
        class="flex min-w-[10rem] flex-1 flex-col gap-0.5 rounded-card border px-3 py-2 text-left transition-colors duration-[var(--duration-base)] ease-[var(--ease-standard)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gm"
        :class="
          mod === m.ad
            ? 'border-gm bg-gm-soft text-text'
            : 'border-border bg-surface-2 text-muted hover:bg-surface-3 hover:text-text'
        "
        :aria-pressed="mod === m.ad"
        :disabled="gonderiliyor"
        @click="mod = m.ad"
      >
        <span class="flex items-center gap-1.5 text-card">
          <Icon :name="m.ikon" :size="16" :class="mod === m.ad ? 'text-gm' : ''" />
          {{ m.baslik }}
        </span>
        <span class="text-label" :class="m.yayin ? 'text-warn' : 'text-faint'">
          {{ m.ozet }}
        </span>
      </button>
    </div>

    <!-- Aktif modun ne yaptığı -->
    <p
      class="flex items-start gap-2 rounded-card border px-3 py-2 text-meta"
      :class="
        aktif.yayin
          ? 'border-warn/40 bg-warn-soft text-warn'
          : 'border-gm/30 bg-gm-soft text-gm'
      "
      aria-live="polite"
    >
      <Icon :name="aktif.yayin ? 'campaign' : 'visibility_off'" :size="16" class="mt-0.5 shrink-0" />
      <span>
        <b>{{ aktif.yayin ? 'Oyuncular bunu görecek.' : 'Oyuncular bunu görmeyecek.' }}</b>
        {{ aktif.aciklama }}
      </span>
    </p>

    <!-- Metin -->
    <label class="flex flex-col gap-1.5">
      <span class="sr-only">Müdahale metni</span>
      <textarea
        v-model="metin"
        rows="4"
        :placeholder="aktif.yerTutucu"
        :disabled="gonderiliyor"
        class="w-full resize-y rounded-md border border-border bg-surface-2 px-3 py-2 text-scene text-text outline-none transition-colors duration-[var(--duration-fast)] placeholder:text-faint focus-visible:border-gm focus-visible:outline-gm disabled:opacity-60"
        @keydown="tusla"
      />
    </label>

    <!-- Gönderim satırı -->
    <div class="flex flex-wrap items-center gap-2">
      <template v-if="!onayBekliyor">
        <BaseButton
          variant="gm"
          :icon="aktif.yayin ? 'campaign' : 'send'"
          :disabled="!gonderilebilir"
          :loading="gonderiliyor"
          loading-text="Anlatıcı işliyor…"
          @click="gonder"
        >
          {{ aktif.dugme }}
        </BaseButton>
        <span v-if="!oyunBasladi" class="text-label text-warn">
          Oyun henüz başlamadı — müdahale ancak ilk sahneden sonra gönderilebilir.
        </span>
        <span
          v-else-if="!metinVar && aktif.metinZorunlu"
          class="text-label text-faint"
        >
          Metin yaz ya da sürpriz moduna geç.
        </span>
        <span v-else class="text-label text-faint">Ctrl/Cmd + Enter ile de gönderilir.</span>
      </template>

      <!-- Yayınlanan modlarda ikinci adım -->
      <template v-else>
        <span class="flex items-center gap-1.5 text-meta text-warn">
          <Icon name="warning" :size="16" />
          Bu metin oyuncuların ekranına düşecek. Emin misin?
        </span>
        <BaseButton variant="gm" icon="campaign" @click="gonder">Evet, yayınla</BaseButton>
        <BaseButton variant="subtle" icon="close" @click="vazgec">Vazgeç</BaseButton>
      </template>
    </div>

    <!-- Bekleme hali -->
    <p
      v-if="gonderiliyor"
      class="flex items-center gap-2 rounded-card border border-border bg-surface-2 px-3 py-2 text-meta text-muted"
      role="status"
    >
      <Icon name="progress_activity" :size="16" class="text-gm motion-safe:animate-spin" />
      Anlatıcı modeli çalışıyor — 30-60 saniye sürebilir. Sayfayı kapatma.
    </p>

    <!-- Hata -->
    <p
      v-else-if="hata"
      class="flex items-start gap-2 rounded-card border border-danger/40 bg-danger-soft px-3 py-2 text-meta text-danger"
      role="alert"
    >
      <Icon name="error" :size="16" class="mt-0.5 shrink-0" />
      <span>{{ hata }}</span>
    </p>

    <!-- Son yanıt -->
    <div
      v-else-if="sonuc"
      class="rounded-card border bg-surface-2 px-3 py-2"
      :class="sonuc.published ? 'border-warn/40' : 'border-gm/30'"
    >
      <div class="mb-1 flex items-center gap-2">
        <Badge :tone="sonuc.published ? 'warn' : 'gm'" :icon="sonuc.published ? 'campaign' : 'visibility_off'">
          {{ sonuc.published ? 'oyunculara yayınlandı' : 'sadece sende kaldı' }}
        </Badge>
      </div>
      <div class="whitespace-pre-wrap text-meta text-text" v-html="metinBicimle(sonuc.text)" />

      <!-- Gizli modda uygulanmayan alanlar: anlatıcı yazdı ama sunucu
           düşürdü (oyuncu paneline sızmasın diye). GM bilsin ki gerekirse
           elle yama ile kendisi yazsın. -->
      <p v-if="sonuc.dropped?.length" class="mt-2 flex flex-wrap items-center gap-1 text-label text-muted">
        <Icon name="block" :size="14" class="text-warn" />
        <span>Oyuncuya görünen alanlar kaydedilmedi:</span>
        <code v-for="alan in sonuc.dropped" :key="alan" class="font-mono text-text">{{ alan }}</code>
        <span>— olay sahnede yaşandığında kaydedilecek.</span>
      </p>
    </div>
  </div>
</template>
