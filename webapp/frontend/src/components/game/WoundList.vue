<script setup>
/**
 * Açık yaralar. `vitals.condition` her tur üzerine yazıldığı için kalıcı
 * değil; yaralar iyileşene kadar burada durur (enfeksiyon riskiyle birlikte).
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import { yaralariDiziye, yaraTonu, enfeksiyonTonu, olcuyeAl } from './gameFormat'

const props = defineProps({
  yaralar: { type: Array, default: () => [] },
})

const TON_CUBUK = { ok: 'bg-ok', warn: 'bg-warn', danger: 'bg-danger' }

const liste = computed(() =>
  yaralariDiziye(props.yaralar).map((y) => {
    const risk = olcuyeAl(y.infection_risk)
    return {
      ...y,
      risk,
      riskTonu: enfeksiyonTonu(risk),
      siddetTonu: yaraTonu(y.severity),
    }
  }),
)
</script>

<template>
  <p v-if="!liste.length" class="flex items-center gap-1.5 text-meta text-faint">
    <Icon name="healing" :size="14" />
    Açık yara yok.
  </p>
  <ul v-else class="flex flex-col gap-2">
    <li
      v-for="(yara, i) in liste"
      :key="i"
      class="rounded-card border border-border bg-surface-2 px-2.5 py-2"
    >
      <div class="flex flex-wrap items-center gap-2">
        <Icon name="bloodtype" :size="15" class="shrink-0 text-danger" />
        <span class="min-w-0 flex-1 text-meta text-text">{{ yara.desc }}</span>
        <Badge :tone="yara.siddetTonu" size="sm">{{ yara.severity || 'orta' }}</Badge>
      </div>

      <div class="mt-1.5 flex items-center gap-2">
        <span class="w-20 shrink-0 text-label text-muted">Enfeksiyon</span>
        <span
          class="h-1.5 min-w-0 flex-1 overflow-hidden rounded-chip bg-surface-3"
          role="meter"
          :aria-valuenow="yara.risk"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-label="`Enfeksiyon riski: ${yara.risk}`"
        >
          <span
            class="block h-full rounded-chip"
            :class="TON_CUBUK[yara.riskTonu]"
            :style="{ width: `${yara.risk}%` }"
          />
        </span>
        <span class="w-7 shrink-0 text-right text-label text-muted nums-tabular">{{
          yara.risk
        }}</span>
      </div>

      <p class="mt-1 flex flex-wrap items-center gap-1.5 text-label text-faint">
        <Badge :tone="yara.treated ? 'ok' : 'warn'" size="sm" :icon="yara.treated ? 'task_alt' : 'priority_high'">
          {{ yara.treated ? 'tedavi edildi' : 'tedavi edilmedi' }}
        </Badge>
        <span v-if="yara.notes">{{ yara.notes }}</span>
      </p>
    </li>
  </ul>
</template>
