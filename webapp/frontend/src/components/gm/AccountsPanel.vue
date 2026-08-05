<script setup>
/**
 * Oyuncu hesapları — kim karakterini almış, kim henüz girmemiş.
 *
 * Oyuncu şifresini unutursa anlatıcı sahipliği bırakır; oyuncu bir sonraki
 * girişte karakteri yeniden alır ve yeni şifresini belirler. Şifreler burada
 * GÖRÜNMEZ — sunucuda yalnız özetleri (scrypt) durur, geri okunamaz.
 */
import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { colorFor } from '@/utils/characterColors'

defineProps({
  /** [{player, claimed, last_login}] */
  hesaplar: { type: Array, default: () => [] },
  /** Oyunculara söylenecek davet kodu */
  oyunKodu: { type: String, default: '' },
  mesgul: { type: Boolean, default: false },
})

const emit = defineEmits(['birak', 'yenile'])

const kodGorunur = ref(false)

function tarih(ts) {
  if (!ts) return 'hiç girmedi'
  return new Date(ts * 1000).toLocaleString('tr-TR', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <!-- Oyun kodu: karakteri İLK KEZ alan oyuncuya söylenir -->
    <div class="flex flex-wrap items-center gap-2 rounded-card border border-border bg-surface-2 p-2.5">
      <Icon name="key" :size="16" class="text-gm" />
      <span class="text-panel uppercase tracking-[0.06em] text-muted">Oyun kodu</span>
      <code class="rounded bg-surface px-2 py-0.5 text-meta text-text">
        {{ kodGorunur ? oyunKodu : '••••••' }}
      </code>
      <BaseButton
        size="sm"
        variant="quiet"
        :icon="kodGorunur ? 'visibility_off' : 'visibility'"
        @click="kodGorunur = !kodGorunur"
      >
        {{ kodGorunur ? 'gizle' : 'göster' }}
      </BaseButton>
      <BaseButton size="sm" variant="quiet" icon="refresh" @click="emit('yenile')" />
    </div>
    <p class="text-label text-faint">
      Bu kodu masaya söyle: oyuncu karakterini ilk kez alırken sorulur, sonraki
      girişlerde gerekmez. Kodu değiştirmek için <code>.env</code> içindeki
      <code>GAME_CODE</code> satırını düzenle.
    </p>

    <EmptyState
      v-if="!hesaplar.length"
      compact
      icon="group_off"
      title="Kadro yok"
      text="Karakterler oluşturulunca hesaplar burada görünür."
    />

    <ul v-else class="flex flex-col gap-1.5">
      <li
        v-for="hesap in hesaplar"
        :key="hesap.player"
        class="flex flex-wrap items-center gap-2 rounded-card border border-border bg-surface-2 p-2"
      >
        <span
          class="size-2 rounded-full"
          :style="{ backgroundColor: colorFor(hesap.player) }"
          aria-hidden="true"
        />
        <span class="text-meta text-text">{{ hesap.player }}</span>
        <Badge :tone="hesap.claimed ? 'ok' : 'muted'" size="sm">
          {{ hesap.claimed ? 'sahiplendi' : 'boşta' }}
        </Badge>
        <span class="text-label text-faint">{{ tarih(hesap.last_login) }}</span>
        <BaseButton
          v-if="hesap.claimed"
          class="ml-auto"
          size="sm"
          variant="quiet"
          icon="lock_reset"
          :loading="mesgul"
          title="Şifresini unuttuysa: sahipliği bırak, yeniden alsın"
          @click="emit('birak', hesap.player)"
        >
          şifreyi sıfırla
        </BaseButton>
      </li>
    </ul>
  </div>
</template>
