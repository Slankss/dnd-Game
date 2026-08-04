<script setup>
/**
 * Sabit eşya kataloğu — anlatıcı ekranı.
 *
 * Katalog oyunun İÇERİĞİDİR, durumu değil: her oyunda aynıdır, `/api/reset`
 * onu silmez. Bir yerde ne bulunacağını yer türüne göre ağırlıklar belirler —
 * bu panel hem o ağırlıkları okunur kılar hem de kataloğu genişletmeyi sağlar.
 *
 * Buradan eklenen eşya KALICIDIR: `data/items.json`'a yazılır ve o andan
 * itibaren TÜM oyunlarda aranırken çıkabilir. Bu yüzden form doğrulaması
 * sunucuda da var — bozuk bir kayıt tek bir oyunu değil, hepsini etkiler.
 */
import { ref, computed, watch } from 'vue'
import Panel from '../ui/Panel.vue'
import Badge from '../ui/Badge.vue'
import Icon from '../ui/Icon.vue'
import BaseButton from '../ui/BaseButton.vue'
import EmptyState from '../ui/EmptyState.vue'

const props = defineProps({
  /** GET /api/gm/items çıktısı */
  katalog: { type: Object, default: null },
  yukleniyor: { type: Boolean, default: false },
  /** Ekleme isteği uçuşta mı */
  ekleniyor: { type: Boolean, default: false },
})

const emit = defineEmits(['yenile', 'ekle'])

const NADIRLIKLER = ['yaygın', 'nadir', 'çok nadir']
const NADIRLIK_TONU = { yaygın: 'muted', nadir: 'warn', 'çok nadir': 'danger' }

/* ------------------------------------------------------------- listeleme */
const arama = ref('')
const kategoriSuzgeci = ref('')
const yerSuzgeci = ref('')
const formAcik = ref(false)
const hata = ref('')

const kategoriler = computed(() => Object.keys(props.katalog?.kategoriler ?? {}))
const yerTurleri = computed(() => Object.entries(props.katalog?.yer_turleri ?? {}))
const esyalar = computed(() => props.katalog?.esyalar ?? [])

const suzulmus = computed(() => {
  const q = arama.value.trim().toLocaleLowerCase('tr-TR')
  return esyalar.value.filter((e) => {
    if (kategoriSuzgeci.value && e.kategori !== kategoriSuzgeci.value) return false
    if (yerSuzgeci.value && !(e.nerede || []).some((n) => n.tur === yerSuzgeci.value)) return false
    if (q && !e.ad.toLocaleLowerCase('tr-TR').includes(q)) return false
    return true
  })
})

/** Kategoriye göre gruplanmış görünüm — liste tek yığın olmasın. */
const gruplar = computed(() => {
  const harita = new Map()
  for (const esya of suzulmus.value) {
    if (!harita.has(esya.kategori)) harita.set(esya.kategori, [])
    harita.get(esya.kategori).push(esya)
  }
  return [...harita.entries()]
})

/* ------------------------------------------------------------ yeni eşya */
function bosForm() {
  return {
    ad: '',
    kategori: kategoriler.value[0] || '',
    nadirlik: 'yaygın',
    taban: 0,
    sayilabilir: false,
    adet_min: 1,
    adet_max: 1,
    doyum: 0,
    susuzluk: 0,
    mermi: '',
    not: '',
    bulunur: {},
  }
}

const form = ref(bosForm())

watch(kategoriler, (yeni) => {
  if (!form.value.kategori && yeni.length) form.value.kategori = yeni[0]
})

/** Formda ağırlık verilmiş yerler — özet satırı için. */
const secilenYerler = computed(() =>
  Object.entries(form.value.bulunur).filter(([, a]) => Number(a) > 0),
)

const yiyecekMi = computed(() => ['yiyecek', 'içecek'].includes(form.value.kategori))
const silahMi = computed(() => form.value.kategori === 'menzilli silah')

function agirlikYaz(tur, deger) {
  const sayi = Math.max(0, Math.min(100, Number(deger) || 0))
  if (sayi) form.value.bulunur[tur] = sayi
  else delete form.value.bulunur[tur]
}

async function gonder() {
  hata.value = ''
  if (!form.value.ad.trim()) {
    hata.value = 'Eşyanın adı gerekli.'
    return
  }
  if (!secilenYerler.value.length && !Number(form.value.taban)) {
    hata.value = 'En az bir yer türüne ağırlık ver ya da taban ağırlığı gir.'
    return
  }
  try {
    await emit('ekle', { ...form.value })
    form.value = bosForm()
    formAcik.value = false
  } catch (e) {
    hata.value = e?.message || 'Eşya eklenemedi.'
  }
}
</script>

<template>
  <Panel title="Eşya kataloğu" icon="inventory_2" tone="gm" collapsible>
    <template #actions>
      <Badge v-if="katalog" tone="muted" size="sm">
        {{ esyalar.length }} eşya · {{ kategoriler.length }} kategori
      </Badge>
      <BaseButton
        size="sm"
        variant="quiet"
        icon="refresh"
        icon-only
        aria-label="Katalogu yenile"
        :loading="yukleniyor"
        @click="$emit('yenile')"
      />
    </template>

    <EmptyState
      v-if="!katalog && !yukleniyor"
      compact
      icon="inventory_2"
      title="Katalog yüklenmedi"
      text="Yenile düğmesine basınca sabit eşya listesi buraya gelir."
    />

    <div v-else-if="katalog" class="flex flex-col gap-3">
      <p class="text-label leading-relaxed text-faint">
        Bu katalog <strong class="text-muted">her oyunda aynıdır</strong> ve oyunun mekanik
        eşyalarını tanımlar. Bir yerde ne bulunacağını yer türüne göre ağırlıklar belirler;
        oyunu sıfırlamak katalogu silmez.
      </p>

      <!-- Süzgeçler -->
      <div class="flex flex-wrap items-center gap-1.5">
        <input
          v-model="arama"
          type="search"
          placeholder="Eşya ara…"
          class="h-8 min-w-40 flex-1 rounded-card border border-border bg-surface-2 px-2.5 text-label text-text placeholder:text-faint"
        />
        <select
          v-model="kategoriSuzgeci"
          class="h-8 rounded-card border border-border bg-surface-2 px-2 text-label text-text"
        >
          <option value="">tüm kategoriler</option>
          <option v-for="ad in kategoriler" :key="ad" :value="ad">{{ ad }}</option>
        </select>
        <select
          v-model="yerSuzgeci"
          class="h-8 rounded-card border border-border bg-surface-2 px-2 text-label text-text"
        >
          <option value="">tüm yerler</option>
          <option v-for="[tur, ad] in yerTurleri" :key="tur" :value="tur">{{ ad }}</option>
        </select>
      </div>

      <!-- Liste -->
      <p v-if="!suzulmus.length" class="text-label text-faint">Süzgece uyan eşya yok.</p>
      <section v-for="[kategori, liste] in gruplar" :key="kategori" class="flex flex-col gap-1">
        <h3 class="text-panel uppercase tracking-[0.06em] text-muted">
          {{ kategori }} ({{ liste.length }})
        </h3>
        <ul class="flex flex-col gap-1">
          <li
            v-for="esya in liste"
            :key="esya.id"
            class="rounded-card border border-border bg-surface-2 p-2"
          >
            <div class="flex flex-wrap items-center gap-1.5">
              <span class="text-meta text-text">{{ esya.ad }}</span>
              <Badge :tone="NADIRLIK_TONU[esya.nadirlik] || 'muted'" size="sm">
                {{ esya.nadirlik }}
              </Badge>
              <Badge v-if="esya.sayilabilir" tone="neutral" size="sm">sayılabilir</Badge>
              <Badge v-if="esya.doyum" tone="ok" size="sm">doyum {{ esya.doyum }}</Badge>
              <Badge v-if="esya.susuzluk" tone="accent" size="sm">su {{ esya.susuzluk }}</Badge>
              <Badge v-if="esya.mermi" tone="warn" size="sm">{{ esya.mermi }}</Badge>
            </div>
            <p v-if="esya.nerede?.length" class="mt-0.5 flex items-start gap-1 text-label text-muted">
              <Icon name="location_on" :size="12" class="mt-0.5 shrink-0" />
              <span>
                <span v-for="(n, i) in esya.nerede" :key="n.tur">
                  <template v-if="i">· </template>{{ n.ad }}
                  <span class="text-faint nums-tabular">{{ n.agirlik }}</span>
                </span>
              </span>
            </p>
            <p v-if="esya.not" class="mt-0.5 text-label text-faint">{{ esya.not }}</p>
          </li>
        </ul>
      </section>

      <!-- Yeni eşya -->
      <section class="rounded-card border border-gm/30 bg-surface-2 p-2.5">
        <BaseButton
          size="sm"
          variant="gm"
          :icon="formAcik ? 'expand_less' : 'add'"
          @click="formAcik = !formAcik"
        >
          {{ formAcik ? 'Formu kapat' : 'Kataloga kalıcı eşya ekle' }}
        </BaseButton>
        <p class="mt-1.5 flex items-start gap-1 text-label text-warn">
          <Icon name="warning" :size="13" class="mt-0.5 shrink-0" />
          Buradan eklenen eşya <strong>kalıcıdır</strong>: dosyaya yazılır ve bundan sonraki
          TÜM oyunlarda bulunabilir.
        </p>

        <div v-if="formAcik" class="mt-2.5 flex flex-col gap-2">
          <label class="flex flex-col gap-1">
            <span class="text-label text-muted">Ad</span>
            <input
              v-model="form.ad"
              type="text"
              maxlength="60"
              placeholder="ör. Telsiz anteni"
              class="h-8 rounded-card border border-border bg-surface px-2.5 text-label text-text placeholder:text-faint"
            />
          </label>

          <div class="flex flex-wrap gap-2">
            <label class="flex min-w-36 flex-1 flex-col gap-1">
              <span class="text-label text-muted">Kategori</span>
              <select
                v-model="form.kategori"
                class="h-8 rounded-card border border-border bg-surface px-2 text-label text-text"
              >
                <option v-for="ad in kategoriler" :key="ad" :value="ad">{{ ad }}</option>
              </select>
            </label>
            <label class="flex min-w-28 flex-1 flex-col gap-1">
              <span class="text-label text-muted">Nadirlik</span>
              <select
                v-model="form.nadirlik"
                class="h-8 rounded-card border border-border bg-surface px-2 text-label text-text"
              >
                <option v-for="n in NADIRLIKLER" :key="n" :value="n">{{ n }}</option>
              </select>
            </label>
            <label class="flex w-24 flex-col gap-1">
              <span class="text-label text-muted" title="Hiçbir yer eşleşmezse geçerli ağırlık">
                Taban
              </span>
              <input
                v-model.number="form.taban"
                type="number"
                min="0"
                max="100"
                class="h-8 rounded-card border border-border bg-surface px-2 text-label text-text nums-tabular"
              />
            </label>
          </div>

          <!-- Kategoriye özel alanlar -->
          <div v-if="yiyecekMi" class="flex flex-wrap gap-2">
            <label class="flex w-32 flex-col gap-1">
              <span class="text-label text-muted">Doyum (açlık −)</span>
              <input
                v-model.number="form.doyum"
                type="number"
                min="0"
                max="100"
                class="h-8 rounded-card border border-border bg-surface px-2 text-label text-text nums-tabular"
              />
            </label>
            <label class="flex w-32 flex-col gap-1">
              <span class="text-label text-muted">Susuzluk −</span>
              <input
                v-model.number="form.susuzluk"
                type="number"
                min="0"
                max="100"
                class="h-8 rounded-card border border-border bg-surface px-2 text-label text-text nums-tabular"
              />
            </label>
          </div>
          <label v-if="silahMi" class="flex flex-col gap-1">
            <span class="text-label text-muted">Harcadığı mühimmat</span>
            <input
              v-model="form.mermi"
              type="text"
              placeholder="ör. 9mm fişek — katalogdaki adıyla"
              class="h-8 rounded-card border border-border bg-surface px-2.5 text-label text-text placeholder:text-faint"
            />
          </label>

          <div class="flex flex-wrap items-end gap-2">
            <label class="flex items-center gap-1.5 text-label text-muted">
              <input v-model="form.sayilabilir" type="checkbox" class="size-3.5" />
              Sayılabilir (mermi/erzak gibi miktarla takip edilir)
            </label>
            <template v-if="form.sayilabilir">
              <label class="flex w-20 flex-col gap-1">
                <span class="text-label text-muted">En az</span>
                <input
                  v-model.number="form.adet_min"
                  type="number"
                  min="1"
                  class="h-8 rounded-card border border-border bg-surface px-2 text-label text-text nums-tabular"
                />
              </label>
              <label class="flex w-20 flex-col gap-1">
                <span class="text-label text-muted">En çok</span>
                <input
                  v-model.number="form.adet_max"
                  type="number"
                  min="1"
                  class="h-8 rounded-card border border-border bg-surface px-2 text-label text-text nums-tabular"
                />
              </label>
            </template>
          </div>

          <label class="flex flex-col gap-1">
            <span class="text-label text-muted">Not (anlatıcıya gider)</span>
            <input
              v-model="form.not"
              type="text"
              maxlength="240"
              placeholder="ör. Sessiz; menzili artırır ama kurulumu zaman alır."
              class="h-8 rounded-card border border-border bg-surface px-2.5 text-label text-text placeholder:text-faint"
            />
          </label>

          <!-- Yer ağırlıkları -->
          <div class="flex flex-col gap-1">
            <span class="text-label text-muted">
              Nerede bulunur (0-100 ağırlık — 0 = orada çıkmaz)
            </span>
            <div class="grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] gap-1">
              <label
                v-for="[tur, ad] in yerTurleri"
                :key="tur"
                class="flex items-center gap-1.5 rounded-card border border-border bg-surface px-2 py-1"
              >
                <span class="min-w-0 flex-1 truncate text-label text-muted" :title="ad">
                  {{ ad }}
                </span>
                <input
                  type="number"
                  min="0"
                  max="100"
                  :value="form.bulunur[tur] ?? 0"
                  class="h-6 w-14 rounded border border-border bg-surface-2 px-1 text-label text-text nums-tabular"
                  @input="agirlikYaz(tur, $event.target.value)"
                />
              </label>
            </div>
            <p class="text-label text-faint">
              {{ secilenYerler.length }} yer seçildi. Örnek: 9mm tabanca karakolda 55,
              metro istasyonunda 2.
            </p>
          </div>

          <p v-if="hata" class="text-label text-danger" role="alert">{{ hata }}</p>

          <BaseButton
            size="sm"
            variant="gm"
            icon="save"
            :loading="ekleniyor"
            loading-text="Ekleniyor…"
            :disabled="!form.ad.trim()"
            @click="gonder"
          >
            Kataloga kalıcı olarak ekle
          </BaseButton>
        </div>
      </section>
    </div>
  </Panel>
</template>
