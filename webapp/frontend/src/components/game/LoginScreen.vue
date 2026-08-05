<script setup>
/**
 * Oyuncu girişi — oyunun kapısı.
 *
 * Sunucu dışarı açık olduğu için "ben Okan'ım" iddiası artık yetmiyor:
 * karakteri ilk sahiplenen kendi şifresini belirler, sonrasında yalnız o
 * şifreyle girilir. İki hâl var ve ekran ikisini kendi ayırt eder:
 *
 *   sahipsiz karakter → oyun kodu + yeni şifre (sahiplenme)
 *   sahipli karakter  → sadece şifre
 *
 * Tek ekran kipi açıkken üçüncü bir yol var: masadaki tek cihaz oyun koduyla
 * girer ve kadronun tamamı adına oynar (herkesin ayrı cihazı yoksa).
 */
import { ref, computed, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { colorFor } from '@/utils/characterColors'

const props = defineProps({
  /** Hayattaki kadro */
  roster: { type: Array, default: () => [] },
  /** Henüz sahiplenilmemiş karakterler */
  available: { type: Array, default: () => [] },
  /** Anlatıcı kadroyu kurdu mu */
  rosterReady: { type: Boolean, default: false },
  /** Tek ekran kipi açık mı */
  singleScreen: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  hata: { type: String, default: '' },
})

const emit = defineEmits(['giris', 'masa'])

/** 'karakter' | 'masa' */
const kip = ref('karakter')
const secili = ref('')
const sifre = ref('')
const kod = ref('')
const yerelHata = ref('')

/** Seçilen karakter henüz sahiplenilmemişse bu giriş onu SAHİPLENİR. */
const sahipleniyor = computed(
  () => !!secili.value && props.available.includes(secili.value),
)

watch(
  () => props.roster.join('|'),
  () => {
    if (secili.value && !props.roster.includes(secili.value)) secili.value = ''
    if (!secili.value) secili.value = props.available[0] || props.roster[0] || ''
  },
  { immediate: true },
)

// Kip kapanırsa masa sekmesinde kalmayalım.
watch(
  () => props.singleScreen,
  (acik) => {
    if (!acik && kip.value === 'masa') kip.value = 'karakter'
  },
)

function gonder() {
  yerelHata.value = ''
  if (kip.value === 'masa') {
    if (!kod.value.trim()) {
      yerelHata.value = 'Oyun kodunu girin.'
      return
    }
    emit('masa', kod.value.trim())
    return
  }
  if (!secili.value) {
    yerelHata.value = 'Karakterini seç.'
    return
  }
  if (!sifre.value) {
    yerelHata.value = sahipleniyor.value ? 'Kendine bir şifre belirle.' : 'Şifreni gir.'
    return
  }
  if (sahipleniyor.value && !kod.value.trim()) {
    yerelHata.value = 'Karakteri ilk kez alıyorsun — anlatıcının verdiği oyun kodu gerekli.'
    return
  }
  emit('giris', {
    player: secili.value,
    password: sifre.value,
    code: sahipleniyor.value ? kod.value.trim() : null,
  })
}
</script>

<template>
  <div class="flex min-h-[70dvh] items-center justify-center px-4 py-10">
    <section
      class="w-full max-w-md rounded-panel border border-border bg-surface p-6 shadow-[var(--shadow-float)]"
    >
      <div class="flex flex-col items-center gap-2 text-center">
        <span
          class="inline-flex size-11 items-center justify-center rounded-full bg-accent-soft text-accent"
        >
          <Icon name="person" :size="24" label="Oyuncu girişi" />
        </span>
        <h1 class="text-card">Kızıl Çöküş</h1>
        <p class="text-meta text-muted">
          Kendi ekranından oynuyorsun: karakterini seç, hamlelerini yalnız sen yaparsın.
        </p>
      </div>

      <!-- Kadro yoksa girilecek bir şey de yok -->
      <div
        v-if="!rosterReady"
        class="mt-5 flex flex-col items-center gap-2 rounded-card border border-border bg-surface-2 p-4 text-center"
      >
        <Icon name="hourglass_empty" :size="20" class="text-muted" />
        <p class="text-meta text-text">Anlatıcı henüz kadroyu kurmadı.</p>
        <p class="text-label text-faint">
          Karakterler oluşturulunca bu ekrandan girebileceksin. Sayfayı açık bırakabilirsin.
        </p>
      </div>

      <template v-else>
        <!-- Tek ekran kipi açıksa iki yol arasında seçim -->
        <div v-if="singleScreen" class="mt-5 flex gap-1 rounded-md border border-border p-1">
          <button
            v-for="secenek in [
              { id: 'karakter', ad: 'Kendi ekranım', ikon: 'person' },
              { id: 'masa', ad: 'Tek ekran (masa)', ikon: 'groups' },
            ]"
            :key="secenek.id"
            type="button"
            class="flex flex-1 items-center justify-center gap-1.5 rounded px-2 py-1.5 text-meta transition-colors"
            :class="
              kip === secenek.id
                ? 'bg-accent-soft text-accent'
                : 'text-muted hover:text-text'
            "
            @click="kip = secenek.id"
          >
            <Icon :name="secenek.ikon" :size="15" />
            {{ secenek.ad }}
          </button>
        </div>

        <form class="mt-4 flex flex-col gap-3" @submit.prevent="gonder">
          <!-- TEK EKRAN: yalnız oyun kodu -->
          <template v-if="kip === 'masa'">
            <p class="rounded-card border border-border bg-surface-2 p-3 text-label text-muted">
              Bu cihaz kadronun tamamı adına oynar — herkes aynı masada, tek ekranın
              başında. Karakteri her turda ekranda değiştirirsin.
            </p>
            <label class="flex flex-col gap-1.5">
              <span class="text-panel uppercase tracking-[0.06em] text-muted">Oyun kodu</span>
              <input
                v-model="kod"
                type="password"
                autocomplete="off"
                class="h-11 w-full rounded-md border border-border bg-surface-2 px-3 text-scene text-text outline-none transition-colors duration-[var(--duration-fast)] placeholder:text-faint focus-visible:border-accent focus-visible:outline-accent"
              />
            </label>
          </template>

          <!-- KENDİ EKRANI: karakter + şifre (+ ilk kezse oyun kodu) -->
          <template v-else>
            <div class="flex flex-col gap-1.5">
              <span class="text-panel uppercase tracking-[0.06em] text-muted">Karakterin</span>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="ad in roster"
                  :key="ad"
                  type="button"
                  class="inline-flex items-center gap-1.5 rounded-chip border px-2.5 py-1.5 text-meta transition-colors"
                  :class="
                    secili === ad
                      ? 'border-accent bg-accent-soft text-text'
                      : 'border-border bg-surface-2 text-muted hover:text-text'
                  "
                  @click="secili = ad"
                >
                  <span
                    class="size-2 rounded-full"
                    :style="{ backgroundColor: colorFor(ad) }"
                    aria-hidden="true"
                  />
                  {{ ad }}
                  <Badge v-if="available.includes(ad)" tone="ok" size="sm">boş</Badge>
                </button>
              </div>
            </div>

            <label class="flex flex-col gap-1.5">
              <span class="text-panel uppercase tracking-[0.06em] text-muted">
                {{ sahipleniyor ? 'Kendine bir şifre belirle' : 'Şifren' }}
              </span>
              <input
                v-model="sifre"
                type="password"
                :autocomplete="sahipleniyor ? 'new-password' : 'current-password'"
                class="h-11 w-full rounded-md border border-border bg-surface-2 px-3 text-scene text-text outline-none transition-colors duration-[var(--duration-fast)] placeholder:text-faint focus-visible:border-accent focus-visible:outline-accent"
              />
              <span v-if="sahipleniyor" class="text-label text-faint">
                En az 6 karakter. Bu karakteri bundan sonra yalnız bu şifreyle açabilirsin.
              </span>
            </label>

            <label v-if="sahipleniyor" class="flex flex-col gap-1.5">
              <span class="text-panel uppercase tracking-[0.06em] text-muted">Oyun kodu</span>
              <input
                v-model="kod"
                type="password"
                autocomplete="off"
                class="h-11 w-full rounded-md border border-border bg-surface-2 px-3 text-scene text-text outline-none transition-colors duration-[var(--duration-fast)] placeholder:text-faint focus-visible:border-accent focus-visible:outline-accent"
              />
              <span class="text-label text-faint">
                Anlatıcının masaya söylediği kod — yalnız karakteri ilk alırken sorulur.
              </span>
            </label>
          </template>

          <p
            v-if="yerelHata || hata"
            class="flex items-start gap-1.5 text-meta text-danger"
            role="alert"
          >
            <Icon name="error" :size="16" class="mt-0.5 shrink-0" />
            <span>{{ yerelHata || hata }}</span>
          </p>

          <BaseButton
            type="submit"
            variant="primary"
            icon="login"
            block
            :loading="loading"
            loading-text="Giriliyor…"
          >
            {{ kip === 'masa' ? 'Masa olarak gir' : sahipleniyor ? 'Karakteri al' : 'Gir' }}
          </BaseButton>
        </form>
      </template>
    </section>
  </div>
</template>
