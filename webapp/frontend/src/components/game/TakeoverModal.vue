<script setup>
/**
 * Karakter devralma — ölen oyuncunun yerine hikayede ZATEN var olan bir
 * NPC'nin seçilmesi. Yeni isim uydurulamaz; liste yalnızca hayatta olan
 * NPC'lerden gelir (sunucu da bunu doğrular).
 */
import { ref, computed, watch } from 'vue'
import Modal from '../ui/Modal.vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import BaseButton from '../ui/BaseButton.vue'
import EmptyState from '../ui/EmptyState.vue'
import { colorFor } from '@/utils/characterColors'
import { kunyeOzeti, saglikTonu } from './gameFormat'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** Yerine geçilecek ölü karakterin adı */
  olen: { type: String, default: '' },
  /** world_state.npcs */
  npcler: { type: Object, default: () => ({}) },
  mesgul: { type: Boolean, default: false },
  /** Sunucudan dönen hata mesajı */
  hata: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'onayla'])

const secim = ref('')

watch(
  () => props.modelValue,
  (acik) => {
    if (acik) secim.value = ''
  },
)

const secenekler = computed(() =>
  Object.entries(props.npcler || {}).filter(([, bilgi]) => bilgi?.alive !== false),
)

function onayla() {
  if (!secim.value || props.mesgul) return
  emit('onayla', { olen: props.olen, yeni: secim.value })
}
</script>

<template>
  <Modal
    :model-value="modelValue"
    size="lg"
    icon="swap_horiz"
    :title="`${olen} öldü — kiminle devam edeceksin?`"
    :kapatilabilir="!mesgul"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <p class="mb-3 measure-scene text-meta text-muted">
      Yeni bir isim uyduramazsın: hikayede zaten tanıştığınız birini devralırsın. Seçtiğin kişi bu
      andan itibaren senin oyuncu karakterin olur, geçmişi ve envanteriyle birlikte.
    </p>

    <EmptyState
      v-if="!secenekler.length"
      icon="person_off"
      title="Devralınabilecek kimse yok"
      text="Hikayede henüz isimli bir karakterle tanışılmadı. Anlatıcı yeni birini sahneye soktuğunda burada listelenecek."
    />

    <ul v-else class="flex flex-col gap-2">
      <li v-for="[ad, bilgi] in secenekler" :key="ad">
        <button
          type="button"
          class="w-full rounded-card border px-3 py-2.5 text-left transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]"
          :class="
            secim === ad
              ? 'border-accent bg-accent-soft'
              : 'border-border bg-surface-2 hover:bg-surface-3'
          "
          :aria-pressed="secim === ad"
          :disabled="mesgul"
          @click="secim = ad"
        >
          <div class="flex items-center gap-2">
            <Icon
              :name="secim === ad ? 'check_circle' : 'radio_button_unchecked'"
              :size="16"
              :class="secim === ad ? 'text-accent' : 'text-faint'"
            />
            <span class="text-card" :style="{ color: colorFor(ad) }">{{ ad }}</span>
            <Badge :tone="saglikTonu(bilgi.status)" size="sm" class="ml-auto">
              {{ bilgi.status || 'durum bilinmiyor' }}
            </Badge>
          </div>
          <p class="mt-1 text-meta text-muted">
            {{ kunyeOzeti(bilgi) || bilgi.background || 'künye yok' }}
          </p>
          <p v-if="bilgi.traits" class="text-label text-faint">{{ bilgi.traits }}</p>
          <p v-if="bilgi.location" class="text-label text-faint">{{ bilgi.location }}</p>
        </button>
      </li>
    </ul>

    <p v-if="hata" class="mt-3 flex items-center gap-1.5 text-meta text-danger" role="alert">
      <Icon name="warning" :size="15" />
      {{ hata }}
    </p>

    <p v-if="mesgul" class="mt-3 flex items-center gap-1.5 text-meta text-accent" role="status">
      <Icon name="progress_activity" :size="15" class="motion-safe:animate-spin" />
      Geçiş sahnesi yazılıyor — 30-60 saniye sürebilir.
    </p>

    <template #footer>
      <BaseButton variant="subtle" :disabled="mesgul" @click="$emit('update:modelValue', false)">
        Vazgeç
      </BaseButton>
      <BaseButton
        variant="primary"
        icon="swap_horiz"
        :disabled="!secim || !secenekler.length"
        :loading="mesgul"
        loading-text="Sahne hazırlanıyor…"
        @click="onayla"
      >
        Bu karakterle devam et
      </BaseButton>
    </template>
  </Modal>
</template>
