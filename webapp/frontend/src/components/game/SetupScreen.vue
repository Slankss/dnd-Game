<script setup>
/**
 * Kurulum ekranı (phase = 'setup') — 1-8 karakter künyesi.
 *
 * Künye oyunun gizli motorudur: meslek/yaş/güçlü-zayıf yan anlatıcı için
 * BAĞLAYICIDIR, `secret` ise yalnızca anlatıcıya gider (sunucu bu alanı
 * oyuncu arayüzüne hiç geri göndermez). Bu yüzden sır alanı ekranda açıkça
 * işaretlenir — aynı ekranı paylaşan oyuncular yanlış anlamasın.
 */
import { ref, computed, watch, useId } from 'vue'
import Panel from '../ui/Panel.vue'
import Icon from '../ui/Icon.vue'
import Badge from '../ui/Badge.vue'
import BaseButton from '../ui/BaseButton.vue'
import SkeletonLine from '../ui/SkeletonLine.vue'
import SheetSelect from './SheetSelect.vue'
import { colorFor } from '@/utils/characterColors'
import {
  MESLEKLER,
  GUCLU_YANLAR,
  ZAYIF_YANLAR,
  EN_AZ_KARAKTER,
  EN_COK_KARAKTER,
  bosKunye,
} from './setupOptions'

const props = defineProps({
  /** Senaryodan gelen hazır isimler */
  onerilenIsimler: { type: Array, default: () => [] },
  /** Senaryodan gelen başlangıç eşyası önerileri */
  esyaOnerileri: { type: Array, default: () => [] },
  /** Kurulum isteği uçuşta mı */
  mesgul: { type: Boolean, default: false },
  /** İlk durum çekilirken */
  yukleniyor: { type: Boolean, default: false },
  /** Sunucudan dönen hata */
  hata: { type: String, default: '' },
  /** Özel (içe aktarılmış) senaryo mu */
  ozelSenaryo: { type: Boolean, default: false },
})

const emit = defineEmits(['onayla'])

const esyaListesiKimlik = useId()
const kunyeler = ref([bosKunye()])
const yerelHata = ref('')

/** Hazır isimler sunucudan geç gelebiliyor; kullanıcı hiç dokunmadıysa doldur. */
const dokunuldu = ref(false)
watch(
  () => props.onerilenIsimler,
  (isimler) => {
    if (dokunuldu.value || !isimler?.length) return
    const bosMu = kunyeler.value.every((k) => !k.name && !k.profession && !k.item)
    if (!bosMu) return
    kunyeler.value = isimler.slice(0, EN_COK_KARAKTER).map((isim) => bosKunye(isim))
  },
  { immediate: true },
)

const doluIsimler = computed(() => kunyeler.value.map((k) => k.name.trim()).filter(Boolean))

const tekrarEdenler = computed(() => {
  const gorulen = new Set()
  const tekrar = new Set()
  for (const ad of doluIsimler.value) {
    const n = ad.toLocaleLowerCase('tr-TR')
    if (gorulen.has(n)) tekrar.add(ad)
    gorulen.add(n)
  }
  return [...tekrar]
})

const gecerli = computed(
  () =>
    doluIsimler.value.length >= EN_AZ_KARAKTER &&
    doluIsimler.value.length <= EN_COK_KARAKTER &&
    tekrarEdenler.value.length === 0,
)

function ekle() {
  if (kunyeler.value.length >= EN_COK_KARAKTER) return
  dokunuldu.value = true
  kunyeler.value.push(bosKunye())
}

function kaldir(anahtar) {
  if (kunyeler.value.length <= 1) return
  dokunuldu.value = true
  kunyeler.value = kunyeler.value.filter((k) => k.anahtar !== anahtar)
}

function onerilenleriGetir() {
  dokunuldu.value = true
  kunyeler.value = (props.onerilenIsimler.length ? props.onerilenIsimler : ['Oyuncu 1'])
    .slice(0, EN_COK_KARAKTER)
    .map((isim) => bosKunye(isim))
}

function temizle() {
  dokunuldu.value = true
  kunyeler.value = [bosKunye()]
}

function onayla() {
  yerelHata.value = ''
  if (!doluIsimler.value.length) {
    yerelHata.value = 'En az bir karakter ismi girin.'
    return
  }
  if (tekrarEdenler.value.length) {
    yerelHata.value = `Aynı isim iki kez var: ${tekrarEdenler.value.join(', ')}`
    return
  }
  const oyuncular = kunyeler.value
    .filter((k) => k.name.trim())
    .map((k) => ({
      name: k.name.trim(),
      profession: k.profession.trim(),
      age: k.age.trim(),
      strength: k.strength.trim(),
      weakness: k.weakness.trim(),
      secret: k.secret.trim(),
      item: k.item.trim(),
    }))
  emit('onayla', oyuncular)
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <Panel title="Kadroyu kur" icon="group_add">
      <template #actions>
        <Badge tone="muted" size="sm">{{ doluIsimler.length }}/{{ EN_COK_KARAKTER }}</Badge>
      </template>

      <p class="text-meta text-muted">
        Oyuna girecek herkes için bir künye doldur. Meslek, yaş, güçlü ve zayıf yan anlatıcı için
        bağlayıcıdır — hikaye bunların üzerine kurulur. En az bir, en çok
        {{ EN_COK_KARAKTER }} karakter olabilir.
      </p>
      <p v-if="ozelSenaryo" class="mt-1.5 flex items-center gap-1.5 text-label text-accent">
        <Icon name="menu_book" :size="14" />
        Özel bir senaryo yüklü — isim ve eşya önerileri o senaryodan geliyor.
      </p>

      <div class="mt-3 flex flex-wrap gap-2">
        <BaseButton
          size="sm"
          variant="subtle"
          icon="groups"
          :disabled="mesgul || !onerilenIsimler.length"
          @click="onerilenleriGetir"
        >
          Önerilen isimleri getir
        </BaseButton>
        <BaseButton size="sm" variant="subtle" icon="delete_forever" :disabled="mesgul" @click="temizle">
          Hepsini temizle
        </BaseButton>
      </div>
    </Panel>

    <!-- ilk durum yüklenirken -->
    <Panel v-if="yukleniyor" title="Yükleniyor" icon="progress_activity">
      <SkeletonLine :lines="4" />
    </Panel>

    <!-- künye kartları -->
    <Panel
      v-for="(kunye, i) in kunyeler"
      :key="kunye.anahtar"
      :icon="'person'"
      :title="`Karakter ${i + 1}`"
    >
      <template #actions>
        <BaseButton
          size="sm"
          variant="quiet"
          icon="close"
          icon-only
          :aria-label="`Karakter ${i + 1} künyesini kaldır`"
          :disabled="kunyeler.length <= 1 || mesgul"
          @click="kaldir(kunye.anahtar)"
        />
      </template>

      <div class="grid gap-3 sm:grid-cols-2">
        <!-- isim -->
        <div class="flex flex-col gap-1 sm:col-span-2">
          <label :for="`${kunye.anahtar}-ad`" class="text-label text-muted">İsim</label>
          <div class="flex items-center gap-2">
            <span
              class="size-2.5 shrink-0 rounded-full"
              :style="{ backgroundColor: colorFor(kunye.name) }"
              aria-hidden="true"
            />
            <input
              :id="`${kunye.anahtar}-ad`"
              v-model="kunye.name"
              type="text"
              placeholder="Karakter ismi"
              :disabled="mesgul"
              class="h-9 w-full rounded-card border border-border bg-surface-2 px-2 text-meta text-text placeholder:text-faint disabled:opacity-50"
              @input="dokunuldu = true"
            />
          </div>
        </div>

        <SheetSelect
          v-model="kunye.profession"
          etiket="Meslek"
          :gruplar="MESLEKLER"
          yer-tutucu="Mesleğini kendin yaz"
          :devre-disi="mesgul"
        />

        <div class="flex flex-col gap-1">
          <label :for="`${kunye.anahtar}-yas`" class="text-label text-muted">Yaş</label>
          <input
            :id="`${kunye.anahtar}-yas`"
            v-model="kunye.age"
            type="text"
            inputmode="numeric"
            placeholder="Örn: 34"
            :disabled="mesgul"
            class="h-9 w-full rounded-card border border-border bg-surface-2 px-2 text-meta text-text nums-tabular placeholder:text-faint disabled:opacity-50"
          />
        </div>

        <SheetSelect
          v-model="kunye.strength"
          etiket="Güçlü yan"
          :gruplar="GUCLU_YANLAR"
          yer-tutucu="Güçlü yanını kendin yaz"
          :devre-disi="mesgul"
        />

        <SheetSelect
          v-model="kunye.weakness"
          etiket="Zayıf yan"
          :gruplar="ZAYIF_YANLAR"
          yer-tutucu="Zayıf yanını kendin yaz"
          :devre-disi="mesgul"
        />

        <!-- sır -->
        <div class="flex flex-col gap-1 sm:col-span-2">
          <label
            :for="`${kunye.anahtar}-sir`"
            class="flex flex-wrap items-center gap-1.5 text-label text-muted"
          >
            Sır
            <Badge tone="gm" size="sm" icon="lock">sadece anlatıcı görür</Badge>
          </label>
          <input
            :id="`${kunye.anahtar}-sir`"
            v-model="kunye.secret"
            type="text"
            placeholder="Örn: ısırıldığını kimseye söylemedi"
            :disabled="mesgul"
            class="h-9 w-full rounded-card border border-gm/30 bg-surface-2 px-2 text-meta text-text placeholder:text-faint disabled:opacity-50"
          />
          <p class="text-label text-faint">
            Bu alan oyun ekranına hiç geri gelmez; hikayenin gizli motoru olarak kullanılır.
          </p>
        </div>

        <!-- başlangıç eşyası -->
        <div class="flex flex-col gap-1 sm:col-span-2">
          <label :for="`${kunye.anahtar}-esya`" class="text-label text-muted">
            Başlangıç eşyası
          </label>
          <input
            :id="`${kunye.anahtar}-esya`"
            v-model="kunye.item"
            type="text"
            :list="esyaListesiKimlik"
            placeholder="Listeden seç ya da kendin yaz"
            :disabled="mesgul"
            class="h-9 w-full rounded-card border border-border bg-surface-2 px-2 text-meta text-text placeholder:text-faint disabled:opacity-50"
          />
          <p v-if="!esyaOnerileri.length" class="text-label text-faint">
            Öneri listesi sunucudan gelmedi — eşyayı elle yazabilirsin.
          </p>
        </div>
      </div>
    </Panel>

    <datalist :id="esyaListesiKimlik">
      <option v-for="esya in esyaOnerileri" :key="esya" :value="esya" />
    </datalist>

    <!-- eylemler -->
    <div class="flex flex-col gap-2">
      <p
        v-if="yerelHata || hata"
        class="flex items-center gap-1.5 text-meta text-danger"
        role="alert"
      >
        <Icon name="warning" :size="15" />
        {{ yerelHata || hata }}
      </p>

      <div class="flex flex-wrap items-center gap-2">
        <BaseButton
          icon="add"
          variant="ghost"
          :disabled="kunyeler.length >= EN_COK_KARAKTER || mesgul"
          @click="ekle"
        >
          Karakter ekle
        </BaseButton>
        <BaseButton
          class="ml-auto"
          variant="primary"
          size="lg"
          icon="check_circle"
          :disabled="!gecerli"
          :loading="mesgul"
          loading-text="Kadro kaydediliyor…"
          @click="onayla"
        >
          Kadroyu onayla
        </BaseButton>
      </div>
      <p class="text-label text-faint">
        Onayladıktan sonra kadro değiştirilemez — değiştirmek için oyunu sıfırlaman gerekir.
      </p>
    </div>
  </div>
</template>
