<script setup>
/**
 * Oyuncu ekranı — kurulum → başlatma → oyun.
 *
 * Yerleşim (docs/tasarim-sistemi.md §4):
 *   üst bar: dünya künyesi · sidebar: kadro / kaynak / zorluk / NPC
 *   ana alan: aksiyon yazma alanı SABİT ÜSTTE, akış EN YENİ EN ÜSTTE.
 *
 * Otomatik kaydırma yoktur; yeni içerik geldiğinde composer'ın altındaki
 * "yeni sahne" rozeti haber verir.
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import AppShell from '@/components/layout/AppShell.vue'
import SidebarSection from '@/components/layout/SidebarSection.vue'
import Panel from '@/components/ui/Panel.vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SkeletonLine from '@/components/ui/SkeletonLine.vue'

import WorldClockBar from '@/components/game/WorldClockBar.vue'
import SetupScreen from '@/components/game/SetupScreen.vue'
import ReadyScreen from '@/components/game/ReadyScreen.vue'
import ActionComposer from '@/components/game/ActionComposer.vue'
import RoundBar from '@/components/game/RoundBar.vue'
import OptionPool from '@/components/game/OptionPool.vue'
import MapPanel from '@/components/game/MapPanel.vue'
import GridPanel from '@/components/game/GridPanel.vue'
import ThreatPanel from '@/components/game/ThreatPanel.vue'
import StoryFeed from '@/components/game/StoryFeed.vue'
import CharacterCard from '@/components/game/CharacterCard.vue'
import CharacterModal from '@/components/game/CharacterModal.vue'
import NpcList from '@/components/game/NpcList.vue'
import ResourcePanel from '@/components/game/ResourcePanel.vue'
import ChallengeList from '@/components/game/ChallengeList.vue'
import DeathBanner from '@/components/game/DeathBanner.vue'
import TakeoverModal from '@/components/game/TakeoverModal.vue'
import SettingsPanel from '@/components/game/SettingsPanel.vue'
import { zorluklariDiziye, zorlukKapali, stokVarMi } from '@/components/game/gameFormat'

import { useGameStore } from '@/stores/game'
import { useSidebar } from '@/composables/useSidebar'
import { colorFor } from '@/utils/characterColors'

const oyun = useGameStore()
const { ac: sidebariAc } = useSidebar()

onMounted(() => {
  oyun.startPolling()
  // Sahne ızgarası: ilk açılışta bir kez istenir (sunucu yoksa kurar),
  // sonrasında yoklama dünya durumuyla birlikte tazeler.
  if (oyun.phase === 'playing') oyun.fetchGrid().catch(() => {})
})
onUnmounted(() => oyun.stopPolling())

/* ------------------------------------------------------------- genel hal */

/** Hiç veri yokken ilk istek sürüyor. */
const ilkYukleme = computed(() => oyun.loading && !oyun.worldState)
/** Hiç veri gelmedi ve hata var — kurulum formu yerine bağlantı hatası göster. */
const baglantiCokmus = computed(() => !!oyun.error && !oyun.worldState && !oyun.loading)

const hataMetni = computed(() => oyun.error?.message || '')

const npcSayisi = computed(() => Object.keys(oyun.npcs).length)
const acikZorlukSayisi = computed(
  () => zorluklariDiziye(oyun.challenges).filter((z) => !zorlukKapali(z.status)).length,
)
const stokVar = computed(() => stokVarMi(oyun.resources))

/* --------------------------------------------------------- oyuncu seçimi */

const seciliOyuncu = ref('')

watch(
  () => [oyun.aliveRoster.join('|'), oyun.groupLabel],
  () => {
    const gecerli =
      seciliOyuncu.value &&
      (seciliOyuncu.value === oyun.groupLabel || oyun.aliveRoster.includes(seciliOyuncu.value))
    if (!gecerli) seciliOyuncu.value = oyun.aliveRoster[0] || oyun.groupLabel || ''
  },
  { immediate: true },
)

/* ------------------------------------------------------------- kurulum */

async function kadroyuOnayla(oyuncular) {
  try {
    await oyun.setupCharacters(oyuncular)
  } catch {
    /* hata store'da; ekranda gösteriliyor */
  }
}

async function oyunuBaslat() {
  try {
    await oyun.start()
  } catch {
    /* hata store'da */
  }
}

/* ----------------------------------------------------------------- tur */

const composer = ref(null)

async function turGonder({ oyuncu, metin }) {
  try {
    await oyun.sendAction(oyuncu, metin)
    composer.value?.temizle()
    oyun.markSeen()
  } catch {
    /* metin alanda kalsın ki kullanıcı tekrar deneyebilsin */
  }
}

// Oyun başladığında (kurulumdan oyuna geçiş) ızgarayı hazırla.
watch(
  () => oyun.phase,
  (asama) => {
    if (asama === 'playing' && !oyun.grid) oyun.fetchGrid().catch(() => {})
  },
)

async function kareHareketi(yon) {
  try {
    await oyun.moveOnGrid(seciliOyuncu.value, yon)
  } catch {
    /* hata store'da; panelde gösteriliyor */
  }
}

/* ------------------------------------------------------ tur bazlı akış */

/** Seçenek havuzu ekranı: tur bazlı akış açık ve oyun gerçekten oynanıyorken. */
const havuzAcik = computed(
  () => oyun.roundMode && oyun.chargenDone && oyun.phase === 'playing' && !!oyun.round?.no,
)

const seciliSecim = computed(() => oyun.pickOf(seciliOyuncu.value))
const seciliSecenekler = computed(() => oyun.optionsFor(seciliOyuncu.value))

async function secenekSec(secenek) {
  try {
    await oyun.pickOption(seciliOyuncu.value, { optionId: secenek.id })
  } catch {
    /* hata store'da; ekranda gösteriliyor */
  }
}

async function kendiHamlesi(metin) {
  try {
    await oyun.pickOption(seciliOyuncu.value, { text: metin })
  } catch {
    /* hata store'da */
  }
}

async function turdaBekle() {
  try {
    await oyun.waitRound(seciliOyuncu.value)
  } catch {
    /* hata store'da */
  }
}

/**
 * Turu gönder. Süre dolduğunda RoundBar bunu `sure` gerekçesiyle kendisi
 * çağırır; açık olan her sekme dener ama sunucu turu bir kez işler.
 */
async function turuGonder(neden) {
  try {
    await oyun.commitRound(neden)
    oyun.markSeen()
  } catch {
    /* hata store'da */
  }
}

/* ------------------------------------------------- karakter oluşturma turu */

const chargenOnayi = ref(false)

async function chargenBitir() {
  if (!chargenOnayi.value) {
    chargenOnayi.value = true
    return
  }
  try {
    await oyun.finishChargen()
  } catch {
    /* hata store'da */
  } finally {
    chargenOnayi.value = false
  }
}

/* -------------------------------------------------------------- devralma */

const devralmaAcik = ref(false)
const devralinacak = ref('')
const devralmaHatasi = ref('')

function devralmaAc(ad) {
  devralinacak.value = ad
  devralmaHatasi.value = ''
  devralmaAcik.value = true
}

async function devral({ olen, yeni }) {
  devralmaHatasi.value = ''
  try {
    await oyun.takeover(olen, yeni)
    devralmaAcik.value = false
  } catch (e) {
    devralmaHatasi.value = e?.message || 'Devralma başarısız oldu.'
  }
}

/* ----------------------------------------------------------- künye modalı */

const kunyeAcik = ref(false)
const kunyeAdi = ref('')

const kunyeNpcMi = computed(() => !!kunyeAdi.value && !(kunyeAdi.value in oyun.characters))
const kunyeBilgisi = computed(
  () => oyun.characters[kunyeAdi.value] || oyun.npcs[kunyeAdi.value] || null,
)

function kunyeAc(ad) {
  kunyeAdi.value = ad
  kunyeAcik.value = true
}

/* --------------------------------------------------------- anlatıcı ekranı */

/** `/secrets` yeni sekmede açılır — oyun ekranındaki tur akışı bozulmasın. */
function anlaticiEkraniniAc() {
  window.open('/secrets', '_blank', 'noopener')
}

/* ---------------------------------------------------------------- ayarlar */

const ayarlarAcik = ref(false)

async function oyunuSifirla() {
  try {
    await oyun.reset()
    ayarlarAcik.value = false
    seciliOyuncu.value = ''
  } catch {
    /* hata store'da */
  }
}

async function ayarKaydet(patch) {
  try {
    await oyun.saveSettings(patch)
  } catch {
    /* hata store'da */
  }
}

/* ------------------------------------------------------- kaynak paneli */

// Kaynak paneli dışarıdan açılabiliyor: SidebarSection `v-model:acik` kabul
// ediyor (envanter sayımı dönünce paneli biz açıyoruz).
const kaynaklarAcik = ref(false)
const kaynakVurgusu = ref(false)
let sonKaynakImzasi = null

let vurguZamanlayici = null

function kaynaklariAc() {
  kaynaklarAcik.value = true
  kaynakVurgusu.value = true
  sidebariAc()
  // Vurgu noktası dikkat çeksin ama kalıcı gürültüye dönüşmesin.
  clearTimeout(vurguZamanlayici)
  vurguZamanlayici = setTimeout(() => (kaynakVurgusu.value = false), 12000)
}

onUnmounted(() => clearTimeout(vurguZamanlayici))

// Bir turda envanter sayımı istendiyse sunucu `inventory_report: true` döner.
watch(
  () => oyun.inventoryReport,
  (rapor) => {
    if (rapor) kaynaklariAc()
  },
)

// Stok ilk kez doğduğunda ya da değiştiğinde de paneli aç.
watch(
  () => JSON.stringify(oyun.resources || {}),
  (imza) => {
    if (sonKaynakImzasi !== null && sonKaynakImzasi !== imza && stokVar.value) kaynaklariAc()
    sonKaynakImzasi = imza
  },
  { immediate: true },
)

/* --------------------------------------------------------- yeni sahne */

function yeniSahneyeGit() {
  oyun.markSeen()
  kaynakVurgusu.value = false
  if (typeof window !== 'undefined') {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}
</script>

<template>
  <AppShell
    variant="player"
    title="Kızıl Çöküş"
    sidebar-label="Oyun paneli"
    :connection="oyun.connectionStatus"
  >
    <!-- ------------------------------------------------------- üst bar -->
    <template #topbar-center>
      <WorldClockBar
        :saat="oyun.worldClock"
        :gerilim="oyun.tension"
        :yukleniyor="!oyun.worldState"
      />
    </template>

    <template #topbar-actions>
      <BaseButton
        variant="quiet"
        size="md"
        icon="refresh"
        icon-only
        aria-label="Durumu yenile"
        :loading="oyun.pollingBusy"
        @click="oyun.pollNow()"
      />
      <!-- Anlatıcı ekranı: PIN'le kilitli, yeni sekmede açılır ki oyun
           ekranı olduğu gibi kalsın. -->
      <BaseButton
        variant="quiet"
        size="md"
        icon="visibility_off"
        icon-only
        aria-label="Anlatıcı ekranı (/secrets)"
        title="Anlatıcı ekranı"
        @click="anlaticiEkraniniAc()"
      />
      <BaseButton
        variant="quiet"
        size="md"
        icon="settings"
        icon-only
        aria-label="Ayarlar"
        @click="ayarlarAcik = true"
      />
    </template>

    <!-- ------------------------------------------------------- sidebar -->
    <template #sidebar>
      <SidebarSection title="Kadro" icon="groups" :count="oyun.roster.length">
        <div v-if="ilkYukleme" class="flex flex-col gap-1.5">
          <span
            v-for="i in 3"
            :key="i"
            class="h-16 rounded-card bg-surface-2 motion-safe:animate-pulse"
          />
          <span class="sr-only">Kadro yükleniyor…</span>
        </div>
        <EmptyState
          v-else-if="!oyun.roster.length"
          compact
          icon="group_add"
          title="Kadro yok"
          text="Karakter kurulumu tamamlanınca kartlar burada görünür."
        />
        <template v-else>
          <CharacterCard
            v-for="ad in oyun.roster"
            :key="ad"
            :ad="ad"
            :bilgi="oyun.characters[ad]"
            @ac="kunyeAc"
          />
        </template>
      </SidebarSection>

      <SidebarSection
        v-if="oyun.phase === 'playing'"
        title="Zombi tehdidi"
        icon="skull"
        :vurgu="(oyun.threat?.noise ?? 0) >= 55 || !!oyun.threat?.travelling"
      >
        <ThreatPanel
          :tehdit="oyun.threat"
          :konum="oyun.worldClock.location"
          :yukleniyor="ilkYukleme"
        />
      </SidebarSection>

      <SidebarSection
        title="Harita"
        icon="map"
        :count="Object.keys(oyun.worldMap?.places || {}).length"
      >
        <MapPanel :harita="oyun.worldMap" :yukleniyor="ilkYukleme" />
      </SidebarSection>

      <SidebarSection
        v-if="oyun.phase === 'playing'"
        title="Kare harita"
        icon="grid_on"
        :count="(oyun.grid?.entities || []).length"
        :default-open="false"
      >
        <GridPanel
          :izgara="oyun.grid"
          :oyuncu="seciliOyuncu"
          :mesgul="oyun.moving"
          :son-hareket="oyun.lastMove"
          @hareket="kareHareketi"
        />
      </SidebarSection>

      <SidebarSection
        title="Aktif zorluklar"
        icon="crisis_alert"
        :count="acikZorlukSayisi"
        :vurgu="acikZorlukSayisi > 0"
      >
        <ChallengeList :zorluklar="oyun.challenges" :yukleniyor="ilkYukleme" />
      </SidebarSection>

      <SidebarSection
        v-model:acik="kaynaklarAcik"
        title="Grup kaynakları"
        icon="inventory_2"
        :vurgu="kaynakVurgusu"
      >
        <ResourcePanel :kaynaklar="oyun.resources" :yukleniyor="ilkYukleme" />
      </SidebarSection>

      <SidebarSection title="NPC'ler" icon="person" :count="npcSayisi" :default-open="false">
        <NpcList :npcler="oyun.npcs" :yukleniyor="ilkYukleme" @ac="kunyeAc" />
      </SidebarSection>
    </template>

    <!-- ------------------------------------------------------ ana alan -->
    <div class="mx-auto flex w-full max-w-4xl flex-col gap-4 p-3 sm:p-4">
      <!-- Hata şeridi (yoklama başarılı olunca kendiliğinden kalkar) -->
      <Panel
        v-if="hataMetni && !baglantiCokmus && oyun.phase === 'playing'"
        tone="danger"
        title="Hata"
        icon="warning"
      >
        <template #actions>
          <BaseButton
            size="sm"
            variant="quiet"
            icon="close"
            icon-only
            aria-label="Hatayı gizle"
            @click="oyun.clearError()"
          />
        </template>
        <p class="text-meta text-danger">{{ hataMetni }}</p>
        <BaseButton class="mt-2" size="sm" icon="refresh" @click="oyun.refresh({ force: true })">
          Tekrar dene
        </BaseButton>
      </Panel>

      <!-- Sunucuya hiç ulaşılamadı -->
      <Panel v-if="baglantiCokmus" tone="danger" title="Bağlantı" icon="cloud_off">
        <EmptyState
          tone="danger"
          icon="cloud_off"
          title="Sunucuya bağlanılamadı"
          :text="hataMetni || 'Oyun sunucusu yanıt vermiyor. Sunucunun açık olduğundan emin ol.'"
        >
          <template #action>
            <BaseButton icon="refresh" @click="oyun.refresh({ force: true })">
              Tekrar dene
            </BaseButton>
          </template>
        </EmptyState>
      </Panel>

      <!-- İlk yükleme -->
      <Panel v-else-if="ilkYukleme" title="Yükleniyor" icon="progress_activity">
        <SkeletonLine :lines="5" />
      </Panel>

      <!-- 1) Kurulum -->
      <SetupScreen
        v-else-if="oyun.phase === 'setup'"
        :onerilen-isimler="oyun.defaultPlayers"
        :esya-onerileri="oyun.startItemSuggestions"
        :ozel-senaryo="oyun.customScenario"
        :mesgul="oyun.busy"
        :hata="hataMetni"
        @onayla="kadroyuOnayla"
      />

      <!-- 2) Başlatma -->
      <ReadyScreen
        v-else-if="oyun.phase === 'ready'"
        :karakterler="oyun.characters"
        :kaynaklar="oyun.resources"
        :saat="oyun.worldClock"
        :mesgul="oyun.busy"
        :hata="hataMetni"
        @basla="oyunuBaslat"
      />

      <!-- 3) Oyun -->
      <template v-else>
        <DeathBanner :karakterler="oyun.characters" :mesgul="oyun.busy" @devral="devralmaAc" />

        <!-- Karakter oluşturma turu sürüyor -->
        <Panel v-if="!oyun.chargenDone" title="Karakter oluşturma" icon="badge">
          <p class="text-meta text-muted">
            Anlatıcı hâlâ karakter oluşturma turunda. Bu turlarda zar atılmaz. Herkes künyesini
            anlattıysa (ya da biri hiç yazmayacaksa) turu elle kapatabilirsin.
          </p>
          <p v-if="chargenOnayi" class="mt-2 text-meta text-warn" role="alert">
            Emin misin? Bundan sonra her mesajda zar atılır.
          </p>
          <div class="mt-2 flex flex-wrap gap-2">
            <BaseButton
              size="sm"
              :variant="chargenOnayi ? 'primary' : 'ghost'"
              icon="task_alt"
              :loading="oyun.busy"
              loading-text="Kapatılıyor…"
              @click="chargenBitir"
            >
              {{ chargenOnayi ? 'Evet, bitir' : 'Karakter oluşturmayı bitir' }}
            </BaseButton>
            <BaseButton v-if="chargenOnayi" size="sm" variant="subtle" @click="chargenOnayi = false">
              Vazgeç
            </BaseButton>
          </div>
        </Panel>

        <!-- Composer: akışın ÜSTÜNDE sabit -->
        <div
          class="sticky top-[var(--spacing-topbar)] z-20 -mx-3 flex flex-col gap-2 bg-bg/95 px-3 py-2 backdrop-blur-sm sm:-mx-4 sm:px-4"
        >
          <!-- Tur bazlı akış: tur çubuğu + seçilen karakterin seçenek havuzu -->
          <template v-if="havuzAcik">
            <RoundBar
              :tur="oyun.round"
              :kayma="oyun.clockSkew"
              :gonderiliyor="oyun.committing"
              @gonder="turuGonder"
            />
            <div class="flex flex-wrap items-center gap-1.5">
              <span class="mr-0.5 text-panel uppercase tracking-[0.06em] text-faint">Kimsin?</span>
              <button
                v-for="ad in oyun.aliveRoster"
                :key="ad"
                type="button"
                class="inline-flex h-7 items-center gap-1.5 rounded-chip border px-2.5 text-label transition-colors duration-[var(--duration-fast)]"
                :class="
                  seciliOyuncu === ad
                    ? 'border-accent/60 bg-accent-soft text-text'
                    : 'border-border bg-surface-2 text-muted hover:text-text'
                "
                :aria-pressed="seciliOyuncu === ad"
                @click="seciliOyuncu = ad"
              >
                <span
                  class="size-1.5 rounded-full"
                  :style="{ backgroundColor: colorFor(ad) }"
                  aria-hidden="true"
                />
                {{ ad }}
                <Icon v-if="oyun.pickOf(ad)" name="check" :size="13" class="text-ok" />
              </button>
            </div>
            <OptionPool
              :oyuncu="seciliOyuncu"
              :secenekler="seciliSecenekler"
              :secim="seciliSecim"
              :mesgul="oyun.picking"
              :tur-acik="oyun.roundOpen"
              :son-zar="oyun.lastRoll"
              @sec="secenekSec"
              @kendi-hamlesi="kendiHamlesi"
              @bekle="turdaBekle"
            />
          </template>

          <ActionComposer
            v-else
            ref="composer"
            v-model:secili="seciliOyuncu"
            :kadro="oyun.aliveRoster"
            :grup-etiketi="oyun.groupLabel"
            :grup-adi="oyun.groupDisplayName || 'Ortak Karar (Grup)'"
            :gonderiliyor="oyun.sending"
            :chargen-bitti="oyun.chargenDone"
            :kilitli="oyun.busy"
            @gonder="turGonder"
          />

          <!-- Yeni sahne rozeti -->
          <button
            v-if="oyun.unseenCount > 0"
            type="button"
            class="mx-auto inline-flex items-center gap-1.5 rounded-chip border border-accent/50 bg-accent-soft px-3 py-1 text-label text-accent transition-colors duration-[var(--duration-fast)] hover:bg-accent/25 motion-safe:animate-pulse"
            @click="yeniSahneyeGit"
          >
            <Icon name="arrow_upward" :size="14" />
            {{ oyun.unseenCount }} yeni sahne — en üste git
          </button>
        </div>

        <StoryFeed
          :girdiler="oyun.logNewestFirst"
          :yukleniyor="oyun.loading"
          :bekleniyor="oyun.sending"
        />

        <p class="flex items-center justify-center gap-3 pb-4 text-label text-faint">
          <span class="inline-flex items-center gap-1.5">
            <Icon name="keyboard" :size="13" />
            Ctrl/Cmd + B — yan paneli aç/kapat
          </span>
          <Badge tone="muted" size="sm" icon="history">{{ oyun.log.length }} kayıt</Badge>
        </p>
      </template>
    </div>

    <!-- ------------------------------------------------------- modallar -->
    <CharacterModal
      v-model="kunyeAcik"
      :ad="kunyeAdi"
      :bilgi="kunyeBilgisi"
      :npc="kunyeNpcMi"
    />

    <TakeoverModal
      v-model="devralmaAcik"
      :olen="devralinacak"
      :npcler="oyun.npcs"
      :mesgul="oyun.busy"
      :hata="devralmaHatasi"
      @onayla="devral"
    />

    <SettingsPanel
      v-model="ayarlarAcik"
      :mesgul="oyun.busy"
      :ayarlar="oyun.settings"
      @sifirla="oyunuSifirla"
      @ayar-kaydet="ayarKaydet"
    />
  </AppShell>
</template>
