<script setup>
/**
 * PIN kilidi — anlatıcı ekranının kapısı.
 *
 * Kilit kapalıyken ekranda BAŞKA HİÇBİR ŞEY olmaz: dünya durumu, zar, sırlar
 * hiç istenmez. Doğru PIN girilince üst bileşen yoklamayı başlatır.
 */
import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

defineProps({
  /** Sunucu PIN'i doğrularken true */
  loading: { type: Boolean, default: false },
  /** Sunucudan gelen Türkçe hata mesajı */
  hata: { type: String, default: '' },
})

const emit = defineEmits(['ac'])

const pin = ref('')
const yerelHata = ref('')

function gonder() {
  const deger = pin.value.trim()
  if (!deger) {
    yerelHata.value = 'PIN boş olamaz.'
    return
  }
  yerelHata.value = ''
  emit('ac', deger)
  pin.value = ''
}
</script>

<template>
  <div class="flex min-h-[70dvh] items-center justify-center px-4 py-10">
    <section
      class="w-full max-w-sm rounded-panel border border-gm/40 bg-surface p-6 shadow-[var(--shadow-float)]"
    >
      <div class="flex flex-col items-center gap-2 text-center">
        <span
          class="inline-flex size-11 items-center justify-center rounded-full bg-gm-soft text-gm"
        >
          <Icon name="visibility_off" :size="24" label="Anlatıcı ekranı" />
        </span>
        <h1 class="text-card">Anlatıcı ekranı kilitli</h1>
        <p class="text-meta text-muted">
          Bu ekran yalnızca oyunu yöneten kişi içindir: dünya zarı, karakter sırları ve
          plan burada açıkça görünür. Oyuncularla asla paylaşma.
        </p>
      </div>

      <form class="mt-5 flex flex-col gap-3" @submit.prevent="gonder">
        <label class="flex flex-col gap-1.5">
          <span class="text-panel uppercase tracking-[0.06em] text-muted">Anlatıcı PIN'i</span>
          <input
            v-model="pin"
            type="password"
            inputmode="numeric"
            autocomplete="off"
            autofocus
            placeholder="••••"
            aria-label="Anlatıcı PIN'i"
            class="nums-tabular h-11 w-full rounded-md border border-border bg-surface-2 px-3 text-center text-scene tracking-[0.35em] text-text outline-none transition-colors duration-[var(--duration-fast)] placeholder:tracking-normal placeholder:text-faint focus-visible:border-gm focus-visible:outline-gm"
          />
        </label>

        <p
          v-if="yerelHata || hata"
          class="flex items-start gap-1.5 text-meta text-danger"
          role="alert"
        >
          <Icon name="error" :size="16" class="mt-0.5 shrink-0" />
          <span>{{ yerelHata || hata }}</span>
        </p>

        <BaseButton type="submit" variant="gm" icon="lock_open" block :loading="loading"
          loading-text="Doğrulanıyor…">
          Kilidi aç
        </BaseButton>
      </form>

      <p class="mt-4 flex items-start gap-1.5 text-label text-faint">
        <Icon name="info" :size="14" class="mt-0.5 shrink-0" />
        <span>
          PIN bu tarayıcıda saklanır ve ekran açılışında sessizce denenir. Ortak bir
          bilgisayardaysan işin bitince üstteki kilit düğmesini kullan.
        </span>
      </p>
    </section>
  </div>
</template>
