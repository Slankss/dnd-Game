<script setup>
/**
 * NPC listesi — ilişkiler ve anlatıcı notlarıyla.
 *
 * NPC'lerin `notes` alanı oyuncuya da gidiyor; buradaki değer ile oyuncu
 * ekranındaki aynıdır. Yine de anlatıcının tek yerden görmesi gerekiyor:
 * kim öldü, kim nerede, kim kime ne borçlu.
 */
import { computed } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { colorVars } from '@/utils/characterColors'

const props = defineProps({
  /** `world_state.npcs` */
  npcs: { type: Object, default: () => ({}) },
})

const liste = computed(() =>
  Object.entries(props.npcs || {})
    .map(([ad, bilgi]) => ({
      ad,
      ...(bilgi || {}),
      olu: bilgi?.alive === false,
      iliskiler: Object.entries(bilgi?.relationships || {}),
    }))
    // Ölüler dibe insin — sahnede kullanılabilecekler üstte kalsın.
    .sort((a, b) => Number(a.olu) - Number(b.olu)),
)
</script>

<template>
  <EmptyState
    v-if="!liste.length"
    icon="person"
    title="Kayıtlı NPC yok"
    text="Anlatıcı sahneye biri girdiğinde buraya yazar."
  />

  <ul v-else class="flex flex-col gap-2">
    <li
      v-for="n in liste"
      :key="n.ad"
      class="rounded-card border border-l-2 border-border bg-surface-2 p-3"
      :style="{ ...colorVars(n.ad), borderLeftColor: 'var(--kr)' }"
      :class="n.olu ? 'opacity-70' : ''"
    >
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="text-card" :style="{ color: 'var(--kr)' }">{{ n.ad }}</h3>
        <Badge v-if="n.olu" tone="danger" icon="lucide:skull">ölü</Badge>
        <Badge v-else-if="n.status" tone="muted">{{ n.status }}</Badge>
      </div>

      <p v-if="n.background || n.traits" class="mt-1 text-label text-muted">
        {{ [n.background, n.traits].filter(Boolean).join(' · ') }}
      </p>

      <p v-if="n.location" class="mt-0.5 flex items-start gap-1.5 text-label text-muted">
        <Icon name="location_on" :size="13" class="mt-0.5 shrink-0" />
        <span>{{ n.location }}</span>
      </p>

      <div v-if="n.iliskiler.length" class="mt-1.5 flex flex-col gap-0.5">
        <p v-for="[kim, tanim] in n.iliskiler" :key="kim" class="text-label text-muted">
          <b class="text-text">{{ kim }}:</b> {{ tanim }}
        </p>
      </div>

      <p v-if="n.notes" class="mt-1.5 text-label text-muted">
        <Icon name="sticky_note_2" :size="13" class="mr-1" />{{ n.notes }}
      </p>
    </li>
  </ul>
</template>
