<script setup>
/**
 * Öğrenme defteri — oyunun kendi oynanışından çıkardığı dersler.
 *
 * Bu panel yalnızca anlatıcı ekranındadır: oyuncular ne dersleri ne de
 * istatistikleri görür. Buradaki her ders bir sonraki turun promptuna girer
 * ve `.claude/skills/kizil-cokus-anlatici/ogrenilenler.md` dosyasına yazılır —
 * yani oyun oynandıkça Claude yeteneği de büyür.
 *
 * Anlatıcı elle ders ekleyebilir; elle yazılanlar otomatik olanların önünde
 * okunur (kaynak rozeti "gm").
 */
import { ref, computed } from 'vue'
import Panel from '../ui/Panel.vue'
import Badge from '../ui/Badge.vue'
import Icon from '../ui/Icon.vue'
import BaseButton from '../ui/BaseButton.vue'
import EmptyState from '../ui/EmptyState.vue'
import { KATEGORI_TONU } from '../game/gameFormat'

const props = defineProps({
  /** /api/gm/state → learning */
  defter: { type: Object, default: null },
  /** Ders ekleme isteği uçuşta mı */
  mesgul: { type: Boolean, default: false },
})

const emit = defineEmits(['dersEkle'])

const yeniDers = ref('')

const dersler = computed(() => props.defter?.lessons ?? [])
const kategoriler = computed(() => Object.entries(props.defter?.categories ?? {}))
const tempo = computed(() => props.defter?.pace ?? {})
const olaylar = computed(() => props.defter?.events ?? {})
const havuz = computed(() => props.defter?.pool ?? null)

const KAYNAK_TONU = { gm: 'gm', anlatıcı: 'accent', otomatik: 'muted' }

/** En yüksek seçim sayısı — çubukların ölçeği. */
const enYuksek = computed(() =>
  kategoriler.value.reduce((m, [, s]) => Math.max(m, s.secim || 0), 0),
)

function dersEkle() {
  const metin = yeniDers.value.trim()
  if (!metin) return
  emit('dersEkle', metin)
  yeniDers.value = ''
}
</script>

<template>
  <Panel title="Öğrenme defteri" icon="neurology" tone="gm" collapsible>
    <template #actions>
      <Badge v-if="defter" tone="muted" size="sm">
        {{ defter.turns }} tur · {{ defter.picks }} seçim
      </Badge>
    </template>

    <EmptyState
      v-if="!defter"
      compact
      icon="neurology"
      title="Defter yüklenmedi"
      text="Anlatıcı durumu yenilendiğinde burada görünecek."
    />

    <div v-else class="flex flex-col gap-4">
      <!-- Dersler -->
      <section class="flex flex-col gap-1.5">
        <h3 class="text-panel uppercase tracking-[0.06em] text-muted">
          Dersler ({{ dersler.length }})
        </h3>
        <p v-if="!dersler.length" class="text-label text-faint">
          Henüz ders çıkmadı — birkaç tur oynandıkça sayaçlardan üretilir.
        </p>
        <ul v-else class="flex flex-col gap-1">
          <li
            v-for="ders in dersler"
            :key="ders.key"
            class="flex items-start gap-1.5 rounded-card border border-border bg-surface-2 p-2"
          >
            <Badge :tone="KAYNAK_TONU[ders.source] || 'muted'" size="sm">
              {{ ders.source }}
            </Badge>
            <span class="min-w-0 flex-1 text-label leading-relaxed text-text">
              {{ ders.text }}
            </span>
            <span v-if="ders.weight > 1" class="shrink-0 text-label text-faint nums-tabular">
              ×{{ ders.weight }}
            </span>
          </li>
        </ul>

        <div class="mt-1 flex flex-col gap-1.5">
          <textarea
            v-model="yeniDers"
            rows="2"
            placeholder="Deftere kendi dersini yaz (bir sonraki turdan itibaren anlatıcıya verilir)"
            :disabled="mesgul"
            class="w-full resize-none rounded-card border border-gm/30 bg-surface-2 px-2.5 py-2 text-label leading-relaxed text-text placeholder:text-faint disabled:opacity-60"
          />
          <BaseButton
            size="sm"
            variant="gm"
            icon="add_notes"
            :disabled="!yeniDers.trim()"
            :loading="mesgul"
            loading-text="Ekleniyor…"
            @click="dersEkle"
          >
            Deftere ekle
          </BaseButton>
        </div>
      </section>

      <!-- Kategori profili -->
      <section v-if="kategoriler.length" class="flex flex-col gap-1.5">
        <h3 class="text-panel uppercase tracking-[0.06em] text-muted">Masanın seçim profili</h3>
        <ul class="flex flex-col gap-1">
          <li v-for="[ad, stat] in kategoriler" :key="ad" class="flex flex-col gap-0.5">
            <div class="flex items-center gap-1.5">
              <Badge :tone="KATEGORI_TONU[ad] || 'neutral'" size="sm">{{ ad }}</Badge>
              <span class="text-label text-muted nums-tabular">
                {{ stat.secim }} seçim · %{{ stat.oran }}
              </span>
              <span v-if="stat.ortalama_zar" class="text-label text-faint nums-tabular">
                ort. zar {{ stat.ortalama_zar }}
              </span>
              <span v-if="stat.felaket" class="text-label text-danger nums-tabular">
                {{ stat.felaket }} felaket
              </span>
              <span v-if="stat.kritik" class="text-label text-accent nums-tabular">
                {{ stat.kritik }} kritik
              </span>
            </div>
            <div class="h-1 w-full overflow-hidden rounded-full bg-surface-2">
              <div
                class="h-full rounded-full bg-gm"
                :style="{ width: `${enYuksek ? (stat.secim / enYuksek) * 100 : 0}%` }"
              />
            </div>
          </li>
        </ul>
      </section>

      <!-- Tempo + olaylar -->
      <section class="flex flex-col gap-1">
        <h3 class="text-panel uppercase tracking-[0.06em] text-muted">Tempo</h3>
        <p class="text-label text-muted">
          Havuzdan {{ tempo.havuzdan || 0 }} · kendi yazdığı {{ tempo.serbest || 0 }} · süre aşımı
          {{ tempo.zaman_asimi || 0 }}
          <template v-if="tempo.ortalama_saniye">
            · ortalama karar {{ tempo.ortalama_saniye }} sn
          </template>
        </p>
        <p v-if="Object.keys(olaylar).length" class="text-label text-muted">
          Olaylar:
          <span v-for="(sayi, ad) in olaylar" :key="ad" class="mr-2 nums-tabular">
            {{ ad }}={{ sayi }}
          </span>
        </p>
        <p v-if="havuz" class="text-label text-faint">
          Havuz: {{ havuz.sunulan }} seçenek sunuldu, {{ havuz.secilen }} tanesi seçildi.
        </p>
      </section>

      <!-- Tekrar etmeyecekler -->
      <section v-if="defter.used_starts?.length || defter.used_factions?.length" class="flex flex-col gap-1">
        <h3 class="text-panel uppercase tracking-[0.06em] text-muted">Kullanılanlar</h3>
        <p v-if="defter.used_starts?.length" class="flex items-start gap-1 text-label text-faint">
          <Icon name="pin_drop" :size="13" class="mt-0.5 shrink-0" />
          <span>{{ defter.used_starts.join(' · ') }}</span>
        </p>
        <p v-if="defter.used_factions?.length" class="flex items-start gap-1 text-label text-faint">
          <Icon name="groups" :size="13" class="mt-0.5 shrink-0" />
          <span>{{ defter.used_factions.join(' · ') }}</span>
        </p>
        <p class="text-label text-faint">
          Yeni oyunlar bu başlangıç noktalarını ve fraksiyon adlarını tekrar seçmez.
        </p>
      </section>
    </div>
  </Panel>
</template>
