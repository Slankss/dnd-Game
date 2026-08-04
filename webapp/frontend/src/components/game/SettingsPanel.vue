<script setup>
/**
 * Ayarlar — müzik çalar ve oyunu sıfırlama.
 *
 * Sıfırlama iki adımlıdır: tek tıkla saatlerce süren bir oturum silinmesin.
 * Anlatıcı ekranına buradan BİLEREK bağlantı verilmez (oyuncu ekranından
 * /secrets'a hiçbir yol çıkmaz).
 */
import { ref, computed, watch } from 'vue'
import Modal from '../ui/Modal.vue'
import Icon from '../ui/Icon.vue'
import BaseButton from '../ui/BaseButton.vue'
import { useAmbientAudio } from './useAmbientAudio'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** Sıfırlama isteği uçuşta mı */
  mesgul: { type: Boolean, default: false },
  /** Sunucudaki oyun ayarları: {turn_seconds, profanity, round_mode, map_size} */
  ayarlar: { type: Object, default: () => ({}) },
  /** Oyun başladı mı — harita büyüklüğü ancak başlamadan önce değişir */
  basladi: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'sifirla', 'ayarKaydet'])

/* --------------------------------------------------------- oyun ayarları */

/** Tur süresi seçenekleri; 0 = süresiz (klasik akış). */
const SURELER = [
  { deger: 0, etiket: 'Süresiz' },
  { deger: 60, etiket: '1 dk' },
  { deger: 120, etiket: '2 dk' },
  { deger: 180, etiket: '3 dk' },
  { deger: 300, etiket: '5 dk' },
]

const KUFUR = [
  { deger: 'kapalı', etiket: 'Kapalı', aciklama: 'Küfür yok; öfke tonla verilir.' },
  { deger: 'hafif', etiket: 'Hafif', aciklama: 'Sert anlarda ölçülü küfür.' },
  { deger: 'sert', etiket: 'Sert', aciklama: 'Kriz anlarında sansürsüz argo.' },
]

/** Harita büyüklüğü — oyun BAŞLARKEN kaç şehir ve mekan üretileceği. */
const HARITA_BOYU = [
  { deger: 'küçük', etiket: 'Küçük', aciklama: '2 şehir · ~12-16 mekan — kısa oyun.' },
  { deger: 'orta', etiket: 'Orta', aciklama: '3 şehir · ~20-26 mekan — dengeli.' },
  { deger: 'büyük', etiket: 'Büyük', aciklama: '5 şehir · ~32-42 mekan — uzun keşif.' },
]

const sure = computed(() => Number(props.ayarlar?.turn_seconds ?? 0))
const kufur = computed(() => props.ayarlar?.profanity || 'hafif')
const haritaBoyu = computed(() => props.ayarlar?.map_size || 'orta')

const {
  durum: muzikDurumu,
  neden: muzikNedeni,
  caliyor: muzikCaliyor,
  seviye: muzikSeviyesi,
  degistir: muzigiDegistir,
  seviyeAyarla,
  yenidenAra,
} = useAmbientAudio()

const muzikHazir = computed(() => muzikDurumu.value === 'hazir')
const yuzde = computed(() => Math.round(muzikSeviyesi.value * 100))

const onayBekleniyor = ref(false)

watch(
  () => props.modelValue,
  (acik) => {
    if (!acik) onayBekleniyor.value = false
  },
)

function sifirla() {
  if (!onayBekleniyor.value) {
    onayBekleniyor.value = true
    return
  }
  emit('sifirla')
}
</script>

<template>
  <Modal
    :model-value="modelValue"
    size="md"
    icon="settings"
    title="Ayarlar"
    :kapatilabilir="!mesgul"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="flex flex-col gap-5">
      <!-- Tur akışı -->
      <section class="flex flex-col gap-2">
        <h3 class="flex items-center gap-1.5 text-panel uppercase tracking-[0.06em] text-muted">
          <Icon name="timer" :size="14" />
          Tur süresi
        </h3>
        <p class="text-label text-faint">
          Süre dolunca tur kendiliğinden gönderilir; seçim yapmayan karakter için anlatıcı
          <strong>ani sahne</strong> yazar — dünya kararsızı beklemez.
        </p>
        <div class="flex flex-wrap gap-1.5">
          <BaseButton
            v-for="s in SURELER"
            :key="s.deger"
            size="sm"
            :variant="sure === s.deger ? 'primary' : 'subtle'"
            :disabled="mesgul"
            @click="$emit('ayarKaydet', { turn_seconds: s.deger })"
          >
            {{ s.etiket }}
          </BaseButton>
        </div>
      </section>

      <!-- Harita büyüklüğü -->
      <section class="flex flex-col gap-2">
        <h3 class="flex items-center gap-1.5 text-panel uppercase tracking-[0.06em] text-muted">
          <Icon name="map" :size="14" />
          Harita büyüklüğü
        </h3>
        <p class="text-label text-faint">
          Harita oyun <strong>başlarken bir kez</strong> üretilir: şehirler, mekanlar,
          aralarındaki yollar ve mesafeler. Başladıktan sonra değiştirilemez.
        </p>
        <div class="flex flex-wrap gap-1.5">
          <BaseButton
            v-for="h in HARITA_BOYU"
            :key="h.deger"
            size="sm"
            :variant="haritaBoyu === h.deger ? 'primary' : 'subtle'"
            :disabled="mesgul || basladi"
            :title="h.aciklama"
            @click="$emit('ayarKaydet', { map_size: h.deger })"
          >
            {{ h.etiket }}
          </BaseButton>
        </div>
        <p v-if="basladi" class="flex items-center gap-1.5 text-label text-warn">
          <Icon name="lock" :size="13" />
          Harita üretildi — büyüklük ancak yeni oyunda değişir (önce sıfırla).
        </p>
        <p v-else class="text-label text-faint">
          {{ HARITA_BOYU.find((h) => h.deger === haritaBoyu)?.aciklama }}
        </p>
      </section>

      <!-- Küfür dozu -->
      <section class="flex flex-col gap-2">
        <h3 class="flex items-center gap-1.5 text-panel uppercase tracking-[0.06em] text-muted">
          <Icon name="record_voice_over" :size="14" />
          Küfür ve argo
        </h3>
        <div class="flex flex-wrap gap-1.5">
          <BaseButton
            v-for="k in KUFUR"
            :key="k.deger"
            size="sm"
            :variant="kufur === k.deger ? 'primary' : 'subtle'"
            :disabled="mesgul"
            :title="k.aciklama"
            @click="$emit('ayarKaydet', { profanity: k.deger })"
          >
            {{ k.etiket }}
          </BaseButton>
        </div>
        <p class="text-label text-faint">
          Küfür anlatıcının değil, karakterlerin ağzından çıkar; refleksleri künyeden gelir.
        </p>
      </section>

      <!-- Müzik -->
      <section class="flex flex-col gap-2">
        <h3 class="flex items-center gap-1.5 text-panel uppercase tracking-[0.06em] text-muted">
          <Icon name="music_note" :size="14" />
          Ortam müziği
        </h3>

        <div class="flex flex-wrap items-center gap-2">
          <BaseButton
            :icon="muzikCaliyor ? 'pause' : 'play_arrow'"
            :disabled="!muzikHazir"
            :loading="muzikDurumu === 'araniyor'"
            loading-text="Dosya aranıyor…"
            @click="muzigiDegistir()"
          >
            {{ muzikCaliyor ? 'Durdur' : 'Çal' }}
          </BaseButton>

          <label class="flex min-w-0 flex-1 items-center gap-2">
            <Icon
              :name="yuzde === 0 ? 'volume_off' : 'volume_up'"
              :size="16"
              class="shrink-0 text-faint"
            />
            <span class="sr-only">Ses seviyesi</span>
            <input
              type="range"
              min="0"
              max="100"
              :value="yuzde"
              :disabled="!muzikHazir"
              class="h-1.5 w-full min-w-24 accent-[var(--color-accent)] disabled:opacity-40"
              aria-label="Ses seviyesi"
              @input="seviyeAyarla($event.target.value / 100)"
            />
            <span class="w-9 shrink-0 text-right text-label text-muted nums-tabular">
              %{{ yuzde }}
            </span>
          </label>
        </div>

        <p
          v-if="muzikDurumu === 'yok' || muzikDurumu === 'hata'"
          class="flex items-start gap-1.5 text-label text-faint"
        >
          <Icon name="info" :size="13" class="mt-px shrink-0" />
          <span>
            {{ muzikNedeni }}
            <button
              type="button"
              class="ml-1 underline decoration-dotted underline-offset-2 hover:text-text"
              @click="yenidenAra()"
            >
              tekrar bak
            </button>
          </span>
        </p>
        <p v-else-if="muzikHazir" class="text-label text-faint">
          Kendi dosyan (static/audio/ambient.mp3) çalınıyor.
        </p>
      </section>

      <!-- Sıfırlama -->
      <section class="flex flex-col gap-2 rounded-card border border-danger/35 bg-danger-soft p-3">
        <h3 class="flex items-center gap-1.5 text-panel uppercase tracking-[0.06em] text-danger">
          <Icon name="delete_forever" :size="14" />
          Oyunu sıfırla
        </h3>
        <p class="text-meta text-muted">
          Tüm oyun geçmişi, dünya durumu ve kadro silinir. Geri alınamaz.
          <br />
          Oyunun öğrenme defteri (biriken dersler) KORUNUR — yeni oyun öğrendikleriyle başlar.
        </p>

        <p v-if="onayBekleniyor" class="text-meta text-danger" role="alert">
          Emin misin? Bu oturumdaki her şey silinecek.
        </p>

        <div class="flex flex-wrap gap-2">
          <BaseButton
            variant="danger"
            :icon="onayBekleniyor ? 'delete_forever' : 'refresh'"
            :loading="mesgul"
            loading-text="Sıfırlanıyor…"
            @click="sifirla"
          >
            {{ onayBekleniyor ? 'Evet, her şeyi sil' : 'Oyunu sıfırla' }}
          </BaseButton>
          <BaseButton
            v-if="onayBekleniyor"
            variant="subtle"
            :disabled="mesgul"
            @click="onayBekleniyor = false"
          >
            Vazgeç
          </BaseButton>
        </div>
      </section>
    </div>

    <template #footer>
      <BaseButton variant="subtle" :disabled="mesgul" @click="$emit('update:modelValue', false)">
        Kapat
      </BaseButton>
    </template>
  </Modal>
</template>
