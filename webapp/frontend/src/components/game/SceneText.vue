<script setup>
/**
 * Anlatıcı sahnesinin gövdesi — ekranın asıl okuma alanı.
 *
 *   <SceneText :metin="entry.text" />
 *
 * Model çıktısı `v-html` ile BASILMAZ: sceneText.js metni veri düğümlerine
 * çevirir, burada normal Vue etiketleriyle çizilir. Böylece modelin ürettiği
 * hiçbir HTML çalışmaz.
 *
 * **DURUM** ve **SEÇENEKLER** blokları gövdeden ayrı bir kutuya alınır —
 * oyuncu sahneyi okuduktan sonra "ne var, ne yapabilirim"i tek bakışta bulur.
 */
import { computed } from 'vue'
import Icon from '../ui/Icon.vue'
import { sahneAyristir } from './sceneText'

const props = defineProps({
  metin: { type: String, default: '' },
})

const bolumler = computed(() => sahneAyristir(props.metin))

const BOLUM_BICIMI = {
  durum: {
    ikon: 'monitor_heart',
    kutu: 'border-l-2 border-warn/50 bg-warn-soft/40',
    baslik: 'text-warn',
  },
  secenekler: {
    ikon: 'playlist_add_check',
    kutu: 'border-l-2 border-accent/50 bg-accent-soft/40',
    baslik: 'text-accent',
  },
  genel: {
    ikon: '',
    kutu: 'border-l-2 border-border',
    baslik: 'text-muted',
  },
}

function bicim(tur) {
  return BOLUM_BICIMI[tur] || BOLUM_BICIMI.genel
}
</script>

<template>
  <div class="measure-scene flex flex-col gap-3 text-scene text-text">
    <template v-for="(bolum, bi) in bolumler" :key="bi">
      <!-- Başlıksız gövde: düz sahne anlatısı -->
      <div v-if="bolum.tur === 'gövde'" class="flex flex-col gap-3">
        <template v-for="(dugum, di) in bolum.dugumler" :key="di">
          <p v-if="dugum.tip === 'paragraf'">
            <template v-for="(satir, si) in dugum.satirlar" :key="si">
              <br v-if="si > 0" />
              <template v-for="(parca, pi) in satir" :key="pi">
                <strong v-if="parca.kalin && parca.egik" class="font-semibold italic">{{
                  parca.v
                }}</strong>
                <strong v-else-if="parca.kalin" class="font-semibold text-text">{{
                  parca.v
                }}</strong>
                <em v-else-if="parca.egik" class="italic text-muted">{{ parca.v }}</em>
                <template v-else>{{ parca.v }}</template>
              </template>
            </template>
          </p>
          <ul v-else class="flex flex-col gap-1.5 pl-1">
            <li v-for="(oge, oi) in dugum.ogeler" :key="oi" class="flex gap-2">
              <span class="mt-[0.55em] size-1.5 shrink-0 rounded-full bg-faint" aria-hidden="true" />
              <span>
                <template v-for="(parca, pi) in oge.parcalar" :key="pi">
                  <strong v-if="parca.kalin" class="font-semibold text-text">{{ parca.v }}</strong>
                  <em v-else-if="parca.egik" class="italic text-muted">{{ parca.v }}</em>
                  <template v-else>{{ parca.v }}</template>
                </template>
              </span>
            </li>
          </ul>
        </template>
      </div>

      <!-- Başlıklı blok: DURUM / SEÇENEKLER / diğer -->
      <section v-else class="rounded-card px-3 py-2.5" :class="bicim(bolum.tur).kutu">
        <h3
          class="mb-1.5 flex items-center gap-1.5 text-panel uppercase tracking-[0.06em]"
          :class="bicim(bolum.tur).baslik"
        >
          <Icon v-if="bicim(bolum.tur).ikon" :name="bicim(bolum.tur).ikon" :size="14" />
          {{ bolum.baslik }}
        </h3>
        <div class="flex flex-col gap-2 text-meta text-text">
          <template v-for="(dugum, di) in bolum.dugumler" :key="di">
            <p v-if="dugum.tip === 'paragraf'">
              <template v-for="(satir, si) in dugum.satirlar" :key="si">
                <br v-if="si > 0" />
                <template v-for="(parca, pi) in satir" :key="pi">
                  <strong v-if="parca.kalin" class="font-semibold">{{ parca.v }}</strong>
                  <em v-else-if="parca.egik" class="italic text-muted">{{ parca.v }}</em>
                  <template v-else>{{ parca.v }}</template>
                </template>
              </template>
            </p>
            <ol v-else class="flex flex-col gap-1.5">
              <li v-for="(oge, oi) in dugum.ogeler" :key="oi" class="flex gap-2">
                <span
                  class="mt-0.5 inline-flex min-w-5 shrink-0 justify-center rounded-chip border border-border bg-surface-2 px-1 text-label text-muted nums-tabular"
                  aria-hidden="true"
                >
                  {{ oge.etiket || '•' }}
                </span>
                <span>
                  <template v-for="(parca, pi) in oge.parcalar" :key="pi">
                    <strong v-if="parca.kalin" class="font-semibold">{{ parca.v }}</strong>
                    <em v-else-if="parca.egik" class="italic text-muted">{{ parca.v }}</em>
                    <template v-else>{{ parca.v }}</template>
                  </template>
                </span>
              </li>
            </ol>
          </template>
        </div>
      </section>
    </template>
  </div>
</template>
