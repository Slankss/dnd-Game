<script setup>
/**
 * Kayıt listesi — hem oyun günlüğü hem anlatıcı defteri için.
 *
 * Sıralama ÇAĞIRANIN işidir; store `logNewestFirst` / `gmLogNewestFirst`
 * getter'larıyla EN YENİYİ EN ÜSTE koyar. Burada ters çevirme yapılmaz.
 */
import { computed } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { colorForEntry } from '@/utils/characterColors'
import { metinBicimle, saatKisalt, yayinOnEkiniAt } from './gmYardimcilar'

const props = defineProps({
  /** Girdiler — zaten sıralanmış gelir (en yeni en üstte) */
  entries: { type: Array, default: () => [] },
  /** 'oyun' → oyuncu akışı, 'not' → anlatıcı notları */
  tur: { type: String, default: 'oyun' },
  /** Yan panel varyantı: küçük yazı, kısaltılmış metin */
  compact: { type: Boolean, default: false },
  /** En fazla kaç girdi çizilsin (0 = hepsi) */
  limit: { type: Number, default: 0 },
})

/** Bir girdinin başlığı, rengi ve rozeti. */
function kimlik(e) {
  if (props.tur === 'not') {
    if (e.role === 'gm_note') {
      return {
        kim: 'Sen — anlatıcı notu',
        renk: 'var(--color-gm)',
        etiket: e.mode && e.mode !== 'gizli' ? e.mode : 'gizli',
        yayin: false,
      }
    }
    return {
      kim: e.published ? 'Anlatıcı yanıtı — oyunculara yayınlandı' : 'Anlatıcı yanıtı (gizli)',
      renk: e.published ? 'var(--color-warn)' : 'var(--color-muted)',
      etiket: e.mode || '',
      yayin: !!e.published,
    }
  }

  if (e.role === 'user') {
    const zar = e.roll != null ? `zar ${e.roll} · ${e.band || ''}` : 'karakter oluşturma'
    return { kim: `${e.player || 'Oyuncu'} — ${zar}`, renk: colorForEntry(e), etiket: '', yayin: false }
  }
  if (e.role === 'system') {
    return { kim: 'Sistem', renk: 'var(--color-muted)', etiket: '', yayin: false }
  }
  return {
    kim: e.kind === 'gm_scene' ? 'Anlatıcı — GM sahnesi' : 'Anlatıcı',
    renk: 'var(--color-accent)',
    etiket: e.kind === 'gm_scene' ? 'müdahale' : '',
    yayin: e.kind === 'gm_scene',
  }
}

const gorunen = computed(() =>
  (props.limit > 0 ? props.entries.slice(0, props.limit) : props.entries).map((e, i) => ({
    ham: e,
    anahtar: e.id ?? `${e.ts || ''}-${e.role || ''}-${i}`,
    ...kimlik(e),
  })),
)
</script>

<template>
  <EmptyState
    v-if="!gorunen.length"
    :compact="compact"
    :icon="tur === 'not' ? 'visibility_off' : 'forum'"
    :text="tur === 'not' ? 'Henüz anlatıcı notu yok.' : 'Henüz oynanan bir tur yok.'"
  />

  <ol v-else class="flex flex-col gap-2">
    <li
      v-for="g in gorunen"
      :key="g.anahtar"
      class="rounded-card border border-l-2 border-border bg-surface-2 px-3 py-2"
      :style="{ borderLeftColor: g.renk }"
    >
      <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5">
        <span class="text-label font-medium" :style="{ color: g.renk }">{{ g.kim }}</span>
        <span
          v-if="g.etiket"
          class="rounded-chip border border-border px-1.5 text-[0.625rem] leading-4 text-muted"
          >{{ g.etiket }}</span
        >
        <Icon
          v-if="g.yayin"
          name="campaign"
          :size="13"
          class="text-warn"
          label="Oyunculara görünür"
        />
        <span v-if="g.ham.ts" class="ml-auto text-label text-faint" :title="g.ham.ts">
          {{ saatKisalt(g.ham.ts) }}
        </span>
      </div>
      <div
        class="mt-1 whitespace-pre-wrap text-meta text-text"
        :class="compact ? 'line-clamp-4' : ''"
        v-html="metinBicimle(yayinOnEkiniAt(g.ham.text))"
      />
    </li>
  </ol>
</template>
