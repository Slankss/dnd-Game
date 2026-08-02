<script setup>
/**
 * Künye alanı: hazır seçenekler + "Kendim yazayım".
 *
 * `modelValue` her zaman ALANIN SON DEĞERİdir (hazır seçenek ya da serbest
 * metin); dışarısı hangi yoldan geldiğini bilmek zorunda kalmaz.
 */
import { ref, computed, watch, nextTick, useId } from 'vue'
import { OZEL_SECENEK } from './setupOptions'

const props = defineProps({
  modelValue: { type: String, default: '' },
  etiket: { type: String, required: true },
  /** `{ grupAdı: [seçenek, …] }` */
  gruplar: { type: Object, required: true },
  yerTutucu: { type: String, default: 'Kendin yaz' },
  devreDisi: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const kimlik = useId()
const ozelAlan = ref(null)

/** Değer hazır seçenekler arasında mı? */
const hazirDegerler = computed(() => Object.values(props.gruplar).flat())
const ozelMod = ref(false)

watch(
  () => props.modelValue,
  (v) => {
    if (v && !hazirDegerler.value.includes(v)) ozelMod.value = true
  },
  { immediate: true },
)

const secimDegeri = computed(() => {
  if (ozelMod.value) return OZEL_SECENEK
  return props.modelValue || ''
})

async function secimDegisti(e) {
  const v = e.target.value
  if (v === OZEL_SECENEK) {
    ozelMod.value = true
    emit('update:modelValue', '')
    await nextTick()
    ozelAlan.value?.focus()
    return
  }
  ozelMod.value = false
  emit('update:modelValue', v)
}
</script>

<template>
  <div class="flex flex-col gap-1">
    <label :for="kimlik" class="text-label text-muted">{{ etiket }}</label>
    <select
      :id="kimlik"
      :value="secimDegeri"
      :disabled="devreDisi"
      class="h-9 w-full rounded-card border border-border bg-surface-2 px-2 text-meta text-text disabled:opacity-50"
      @change="secimDegisti"
    >
      <option value="">— seç —</option>
      <optgroup v-for="(secenekler, grup) in gruplar" :key="grup" :label="grup">
        <option v-for="secenek in secenekler" :key="secenek" :value="secenek">
          {{ secenek }}
        </option>
      </optgroup>
      <option :value="OZEL_SECENEK">Kendim yazayım…</option>
    </select>
    <input
      v-if="ozelMod"
      ref="ozelAlan"
      type="text"
      :value="modelValue"
      :placeholder="yerTutucu"
      :disabled="devreDisi"
      :aria-label="`${etiket} — serbest metin`"
      class="h-9 w-full rounded-card border border-border bg-surface-2 px-2 text-meta text-text placeholder:text-faint disabled:opacity-50"
      @input="emit('update:modelValue', $event.target.value)"
    />
  </div>
</template>
