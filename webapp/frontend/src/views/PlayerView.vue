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
import ActionComposer from '@/components/game/ActionComposer.vue'
import RoundBar from '@/components/game/RoundBar.vue'
import OptionPool from '@/components/game/OptionPool.vue'
import MapPanel from '@/components/game/MapPanel.vue'
import GridPanel from '@/components/game/GridPanel.vue'
import ThreatPanel from '@/components/game/ThreatPanel.vue'
import StoryItemList from '@/components/game/StoryItemList.vue'
import StoryFeed from '@/components/game/StoryFeed.vue'
import CharacterCard from '@/components/game/CharacterCard.vue'
import CharacterModal from '@/components/game/CharacterModal.vue'
import NpcList from '@/components/game/NpcList.vue'
import ResourcePanel from '@/components/game/ResourcePanel.vue'
import ChallengeList from '@/components/game/ChallengeList.vue'
import DeathBanner from '@/components/game/DeathBanner.vue'
import TakeoverModal from '@/components/game/TakeoverModal.vue'
import { zorluklariDiziye, zorlukKapali, stokVarMi } from '@/components/game/gameFormat'

import LoginScreen from '@/components/game/LoginScreen.vue'
import { useGameStore } from '@/stores/game'
import { useAuthStore } from '@/stores/auth'
import { useSidebar } from '@/composables/useSidebar'
import { colorFor } from '@/utils/characterColors'

const oyun = useGameStore()
const kimlik = useAuthStore()
const { ac: sidebariAc } = useSidebar()

/**
 * Açılış sırası: ÖNCE kimlik. Giriş yoksa dünya hiç istenmez — sunucu zaten
 * 401 döndürürdü, boşuna yoklamayalım. Giriş yapılınca yoklama başlar,
 * çıkışta durur.
 */
onMounted(async () => {
  await kimlik.yenile()
})
onUnmounted(() => oyun.stopPolling())

watch(
  () => kimlik.girisli,
  (girdi) => {
    if (girdi) {
      oyun.startPolling()
      if (oyun.phase === 'playing') oyun.fetchGrid().catch(() => {})
    } else {
      oyun.stopPolling()
    }
  },
  { immediate: true },
)

// Oturum sunucu tarafında düştüyse (401) giriş ekranına dön.
watch(
  () => oyun.error,
  (hata) => {
    if (hata?.status === 401) {
      kimlik.oturumDustu()
      oyun.stopPolling()
    }
  },
)

/* ------------------------------------------------------------------ giriş */

async function girisYap(bilgi) {
  if (await kimlik.giris(bilgi)) oyun.refresh({ force: true }).catch(() => {})
}

async function masaGirisi(kod) {
  if (await kimlik.masaGirisi(kod)) oyun.refresh({ force: true }).catch(() => {})
}

async function cikisYap() {
  await kimlik.cikis()
  masaSecimi.value = ''
}

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

/* --------------------------------------------------------- oyuncu kimliği */

/**
 * Kim oynuyor? Oyuncu oturumunda bu SORULMAZ — sunucu zaten biliyor ve
 * gövdedeki adı yok sayıyor; ekran yalnız onu yansıtır. Karakter değiştirici
 * SADECE tek ekran kipinde (masa oturumu) görünür: orada tek cihaz kadronun
 * tamamı adına oynar.
 */
const masaSecimi = ref('')

const seciliOyuncu = computed({
  get: () => (kimlik.masaKipi ? masaSecimi.value : kimlik.player || ''),
  set: (ad) => {
    if (kimlik.masaKipi) masaSecimi.value = ad
  },
})
/** Karakter değiştirici yalnız masa kipinde anlamlı. */
const karakterDegistirici = computed(() => kimlik.masaKipi)

watch(
  () => [oyun.aliveRoster.join('|'), kimlik.masaKipi],
  () => {
    if (!kimlik.masaKipi) return
    if (!masaSecimi.value || !oyun.aliveRoster.includes(masaSecimi.value)) {
      masaSecimi.value = oyun.aliveRoster[0] || ''
    }
  },
  { immediate: true },
)


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
  <!-- KAPI: kimlik gelmeden hiçbir şey çizilmez, giriş yoksa yalnız giriş
       ekranı. Oyun ekranı ancak oturum varken kurulur — sunucu zaten 401
       döndürürdü, dünyayı boşuna istemeyelim. -->
  <div v-if="!kimlik.hazir" class="flex min-h-[70dvh] items-center justify-center p-6">
    <SkeletonLine :lines="3" class="w-full max-w-sm" />
  </div>

  <LoginScreen
    v-else-if="!kimlik.girisli"
    :roster="kimlik.roster"
    :available="kimlik.available"
    :roster-ready="kimlik.rosterReady"
    :single-screen="kimlik.singleScreen"
    :loading="kimlik.busy"
    :hata="kimlik.error?.message || ''"
    @giris="girisYap"
    @masa="masaGirisi"
  />

  <AppShell
    v-else
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
      <!-- Kim olduğun — tek ekran kipinde karakter değil "masa" yazar. -->
      <span
        class="hidden items-center gap-1.5 rounded-chip border border-border bg-surface-2 px-2 py-1 text-label text-muted sm:inline-flex"
      >
        <span
          v-if="kimlik.player"
          class="size-1.5 rounded-full"
          :style="{ backgroundColor: colorFor(kimlik.player) }"
          aria-hidden="true"
        />
        <Icon v-else name="groups" :size="13" />
        {{ kimlik.player || 'tek ekran' }}
      </span>
      <BaseButton
        variant="quiet"
        size="md"
        icon="logout"
        icon-only
        aria-label="Çıkış yap"
        title="Çıkış yap"
        :loading="kimlik.busy"
        @click="cikisYap()"
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
        <MapPanel
          :harita="oyun.worldMap"
          :tehdit="oyun.threat"
          :taranan="oyun.searchedPlaces"
          :yukleniyor="ilkYukleme"
        />
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

      <SidebarSection
        title="Hikaye eşyaları"
        icon="local_offer"
        :count="Object.keys(oyun.storyItems).length"
        :default-open="false"
      >
        <StoryItemList :esyalar="oyun.storyItems" :yukleniyor="ilkYukleme" />
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

      <!-- 1-2) Kurulum ve başlatma ANLATICI ekranındadır (/secrets): dışarı
           açık bir sunucuda giren herkes kadroyu kurup oyunu sıfırlayamaz.
           Oyuncu ekranı bu iki aşamada yalnız bekler. -->
      <Panel
        v-else-if="oyun.phase === 'setup' || oyun.phase === 'ready'"
        :title="oyun.phase === 'setup' ? 'Kadro kuruluyor' : 'Oyun başlamak üzere'"
        icon="hourglass_empty"
      >
        <EmptyState
          compact
          icon="hourglass_empty"
          :title="
            oyun.phase === 'setup'
              ? 'Anlatıcı karakterleri hazırlıyor'
              : 'Anlatıcı sahneyi açmak üzere'
          "
          :text="
            oyun.phase === 'setup'
              ? 'Kadro oluşturulunca karakterin bu ekranda belirecek. Sayfayı açık bırakabilirsin.'
              : 'Açılış sahnesi yazıldığında oyun buradan devam edecek.'
          "
        />
      </Panel>

      <!-- 3) Oyun -->
      <template v-else>
        <DeathBanner :karakterler="oyun.characters" :mesgul="oyun.busy" @devral="devralmaAc" />

        <!-- Karakter oluşturma turu sürüyor. Turu KAPATMA anlatıcıya ait
             (/api/finish-chargen artık gm_required): oyuncu yalnız künyesini
             anlatır. -->
        <Panel v-if="!oyun.chargenDone" title="Karakter oluşturma" icon="badge">
          <p class="text-meta text-muted">
            Karakterini anlat: mesleğin, geçmişin, neye iyi gelirsin. Bu turlarda zar
            atılmaz. Herkes künyesini yazınca anlatıcı turu kapatır ve hikaye başlar.
          </p>
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
            <!-- Karakter değiştirici YALNIZ tek ekran kipinde: kendi
                 ekranından oynayan bir oyuncu zaten kendisidir. -->
            <div v-if="karakterDegistirici" class="flex flex-wrap items-center gap-1.5">
              <span class="mr-0.5 text-panel uppercase tracking-[0.06em] text-faint">
                Sıra kimde?
              </span>
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
              @bekle="turdaBekle"
            />
          </template>

          <!-- Serbest yazma alanı YALNIZ karakter oluşturma turlarında:
               asıl hikaye sunulan seçeneklerle ilerler. -->
          <ActionComposer
            v-else-if="!oyun.chargenDone"
            ref="composer"
            v-model:secili="seciliOyuncu"
            :kadro="oyun.aliveRoster"
            :grup-etiketi="oyun.groupLabel"
            :grup-adi="oyun.groupDisplayName || 'Ortak Karar (Grup)'"
            :gonderiliyor="oyun.sending"
            :chargen-bitti="oyun.chargenDone"
            :kadro-secilebilir="karakterDegistirici"
            :kilitli="oyun.busy"
            @gonder="turGonder"
          />

          <!-- Chargen bitti ama tur henüz açılmadı: sahne hazırlanıyor -->
          <p
            v-else
            class="flex items-center justify-center gap-2 rounded-panel border border-border bg-surface px-3 py-3 text-meta text-muted"
            role="status"
          >
            <Icon name="progress_activity" :size="16" class="motion-safe:animate-spin" />
            Sahne hazırlanıyor — seçenekler birazdan gelecek.
          </p>

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

  </AppShell>
</template>
