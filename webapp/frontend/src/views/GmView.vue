<script setup>
/**
 * Anlatıcı ekranı (/secrets).
 *
 * Vurgu rengi MOR (`--color-gm`) — oyuncu ekranı turuncudur; yanlış ekranda
 * oynanmasın diye ayrım göz seviyesinde tutulur.
 *
 * Burada görünen `world_state` SANSÜRSÜZDÜR: fraksiyonların gerçek tavrı,
 * zorlukların `gm_notes` alanı, karakter sırları, anlatıcı defteri ve dünya
 * zarı. Oyuncu gövdesi (`/api/state`) bunların hiçbirini içermez.
 */
import { ref, computed, watch, onMounted, onUnmounted, useTemplateRef } from 'vue'
import AppShell from '@/components/layout/AppShell.vue'
import SidebarSection from '@/components/layout/SidebarSection.vue'
import Panel from '@/components/ui/Panel.vue'
import Badge from '@/components/ui/Badge.vue'
import Icon from '@/components/ui/Icon.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import SkeletonLine from '@/components/ui/SkeletonLine.vue'
import { useGmStore } from '@/stores/gm'

import PinGate from '@/components/gm/PinGate.vue'
import WorldBoard from '@/components/gm/WorldBoard.vue'
import WorldDicePanel from '@/components/gm/WorldDicePanel.vue'
import FactionBoard from '@/components/gm/FactionBoard.vue'
import ChallengeBoard from '@/components/gm/ChallengeBoard.vue'
import NarratorNotebook from '@/components/gm/NarratorNotebook.vue'
import GmNoteComposer from '@/components/gm/GmNoteComposer.vue'
import StatePatchEditor from '@/components/gm/StatePatchEditor.vue'
import RosterPanel from '@/components/gm/RosterPanel.vue'
import NpcBoard from '@/components/gm/NpcBoard.vue'
import ResourceBoard from '@/components/gm/ResourceBoard.vue'
import GmLogList from '@/components/gm/GmLogList.vue'
import GmLogTabs from '@/components/gm/GmLogTabs.vue'
import PlotPanel from '@/components/gm/PlotPanel.vue'
import LearningPanel from '@/components/gm/LearningPanel.vue'
import ItemCatalogPanel from '@/components/gm/ItemCatalogPanel.vue'
import MapPanel from '@/components/game/MapPanel.vue'
import ScenarioTransfer from '@/components/gm/ScenarioTransfer.vue'
import AccountsPanel from '@/components/gm/AccountsPanel.vue'
import SetupScreen from '@/components/game/SetupScreen.vue'
import ReadyScreen from '@/components/game/ReadyScreen.vue'
import SettingsPanel from '@/components/game/SettingsPanel.vue'
import * as api from '@/api/client'
import { jsonYaz, gerilimTonu, yayinOnEkiniAt } from '@/components/gm/gmYardimcilar'

const gm = useGmStore()

/* ------------------------------------------------------------------ kilit */

const pinHatasi = ref('')

/**
 * Kilit ekranındaki mesaj: kullanıcının denemesi öncelikli; o yoksa saklanan
 * PIN'in sessiz denemesinden kalan hata gösterilir (403 → "PIN artık geçerli
 * değil", ağ hatası → sunucu kapalı).
 */
const gateHatasi = computed(() => {
  if (pinHatasi.value) return pinHatasi.value
  if (!gm.error) return ''
  return gm.error.isForbidden
    ? 'Bu tarayıcıda saklı PIN artık geçerli değil — yeniden gir.'
    : gm.error.message
})

async function kilidiAc(pin) {
  pinHatasi.value = ''
  try {
    await gm.unlock(pin)
  } catch (e) {
    pinHatasi.value = e?.message || 'PIN doğrulanamadı.'
  }
}

function kilitle() {
  pinHatasi.value = ''
  notSonucu.value = null
  yamaMetni.value = ''
  gm.lock()
}

/* --------------------------------------------------------------- yenileme */

const yenileniyor = ref(false)

/** Öğrenme defterine elle ders ekle (otomatik derslerin önünde okunur). */
async function dersEkle(metin) {
  try {
    await gm.addLesson(metin)
  } catch {
    /* hata store'da gösteriliyor */
  }
}

async function yenile() {
  yenileniyor.value = true
  try {
    await gm.refresh({ force: true })
  } catch {
    /* hata store'da tutuluyor, panelde görünüyor */
  } finally {
    yenileniyor.value = false
  }
}

/* ------------------------------------------------------- dünya künyesi (üst bar) */

const kunye = computed(() => {
  const ws = gm.worldState || {}
  return {
    gun: ws.day ?? '—',
    saat: [ws.clock, ws.time_of_day].filter(Boolean).join(' ') || '—',
    hava: [ws.weather, ws.temperature].filter(Boolean).join(' ') || '—',
    konum: ws.location || '',
    gerilim: ws.tension || '',
  }
})

/** İlk yükleme sürüyor mu (iskelet göster). */
const ilkYukleme = computed(() => gm.loading && !gm.worldState)

/* ---------------------------------------------------------- müdahale (note) */

const notSonucu = ref(null)
const notHatasi = ref('')

async function notGonder({ metin, mod }) {
  notHatasi.value = ''
  notSonucu.value = null
  try {
    const veri = await gm.sendNote(metin, mod)
    notSonucu.value = {
      published: !!veri?.published,
      // `reply_entry` anlatıcının bu ekrana yazdığı yanıt; yayınlanan modlarda
      // aynı metin oyuncu akışına da düşer (`gm_entry`).
      text: yayinOnEkiniAt(
        veri?.reply_entry?.text || veri?.gm_entry?.text || '(anlatıcı boş yanıt döndü)',
      ),
      // Gizli modda sunucunun uygulamadığı üst düzey alanlar (oyuncuya
      // görünen her şey) — bestecide uyarı olarak gösterilir.
      dropped: Array.isArray(veri?.dropped) ? veri.dropped : [],
    }
  } catch (e) {
    notHatasi.value = e?.message || 'Müdahale gönderilemedi.'
  }
}

/* --------------------------------------------------------- durum düzenleyici */

const yamaMetni = ref('')
const yamaHatasi = ref('')
const yamaBilgisi = ref('')
const yamaKutusu = useTemplateRef('yamaKutusu')

/** Hareket kısıtlaması açıksa yumuşak kaydırma yapma (docs §7). */
function kaydir(el) {
  if (!el) return
  const azHareket =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  el.scrollIntoView({ behavior: azHareket ? 'auto' : 'smooth', block: 'start' })
}

/** Panellerden gelen "şunu düzenle" isteği: taslağı yaz ve düzenleyiciye götür. */
function yamaTaslagi(nesne) {
  yamaHatasi.value = ''
  yamaBilgisi.value = ''
  yamaMetni.value = jsonYaz(nesne)
  kaydir(yamaKutusu.value)
}

function sahneyeDondur(ad) {
  yamaTaslagi({ characters: { [ad]: { presence: { state: 'sahnede', note: '' } } } })
}

async function yamaUygula(patch) {
  yamaHatasi.value = ''
  yamaBilgisi.value = ''
  try {
    const veri = await gm.applyPatch(patch)
    yamaBilgisi.value = `Yama uygulandı${
      typeof veri?.version === 'number' ? ` — sürüm ${veri.version}` : ''
    }.`
    yamaMetni.value = ''
  } catch (e) {
    yamaHatasi.value = e?.message || 'Yama uygulanamadı.'
  }
}

/* ----------------------------------------------------------------- yaşam döngüsü */

/** Katalog yoklamaya girmez: elle ya da kilit açılınca bir kez çekilir. */
async function katalogYenile() {
  try {
    await gm.fetchCatalog({ force: true })
  } catch {
    /* hata store'da */
  }
}

/** Kataloga kalıcı eşya ekle — dosyaya yazılır, tüm oyunlarda geçerli olur. */
async function esyaEkle(esya) {
  await gm.addItem(esya)
}

// Kilit açıldığında katalog bir kez çekilir.
watch(
  () => gm.unlocked,
  (acik) => {
    if (acik && !gm.catalog) katalogYenile()
  },
  { immediate: true },
)

/* ------------------------------------------------- kurulum, ayar, hesaplar
 *
 * Kadro kurma, oyunu başlatma, ayarlar ve sıfırlama ANLATICIYA ait: sunucu
 * bu uçları `gm_required` ile koruyor, arayüz de onları burada gösteriyor.
 * Oyuncu ekranında bu düğmeler artık yok.
 */

/** /api/state'in kurulum için gereken alanları (öneri isimleri, eşyalar). */
const kurulum = ref(null)
const kurulumMesgul = ref(false)
const kurulumHatasi = ref('')
const ayarlarAcik = ref(false)
const hesaplar = ref({})
const hesapMesgul = ref(false)

/** Kurulum aşaması: kadro yok, ya da kadro var ama oyun başlamadı. */
const kurulumAsamasi = computed(() => {
  if (!gm.unlocked) return null
  if (gm.started) return null
  return kurulum.value?.characters_confirmed ? 'ready' : 'setup'
})

async function kurulumuYenile() {
  try {
    kurulum.value = await api.getState()
  } catch {
    /* anlatıcı oturumu zaten var; geçici hata yoklamayla düzelir */
  }
}

async function kadroyuOnayla(oyuncular) {
  kurulumMesgul.value = true
  kurulumHatasi.value = ''
  try {
    await api.setupCharacters(oyuncular)
    await kurulumuYenile()
    await gm.refresh({ force: true })
    await hesaplariYenile()
  } catch (e) {
    kurulumHatasi.value = api.toApiError(e).message
  } finally {
    kurulumMesgul.value = false
  }
}

async function oyunuBaslat() {
  kurulumMesgul.value = true
  kurulumHatasi.value = ''
  try {
    // Açılış sahnesi modelden gelir: uzun sürebilir, zaman aşımı koymuyoruz.
    await api.startGame()
    await kurulumuYenile()
    await gm.refresh({ force: true })
  } catch (e) {
    kurulumHatasi.value = api.toApiError(e).message
  } finally {
    kurulumMesgul.value = false
  }
}

/** Karakter oluşturma turunu kapatır: bundan sonra her hamlede zar atılır. */
const chargenOnayi = ref(false)

async function chargenBitir() {
  if (!chargenOnayi.value) {
    chargenOnayi.value = true
    return
  }
  kurulumMesgul.value = true
  try {
    await api.finishChargen()
    chargenOnayi.value = false
    await gm.refresh({ force: true })
  } catch (e) {
    kurulumHatasi.value = api.toApiError(e).message
  } finally {
    kurulumMesgul.value = false
  }
}

async function ayarKaydet(patch) {
  try {
    await api.saveSettings(patch)
    await gm.refresh({ force: true })
  } catch (e) {
    kurulumHatasi.value = api.toApiError(e).message
  }
}

async function oyunuSifirla() {
  kurulumMesgul.value = true
  try {
    await api.resetGame({ keepLearning: true })
    ayarlarAcik.value = false
    kurulum.value = null
    await kurulumuYenile()
    await gm.refresh({ force: true })
    await hesaplariYenile()
  } catch (e) {
    kurulumHatasi.value = api.toApiError(e).message
  } finally {
    kurulumMesgul.value = false
  }
}

async function hesaplariYenile() {
  try {
    hesaplar.value = await api.gmAccounts()
  } catch {
    hesaplar.value = {}
  }
}

async function hesabiBirak(oyuncu) {
  hesapMesgul.value = true
  try {
    await api.gmReleaseAccount(oyuncu)
    await hesaplariYenile()
  } catch (e) {
    kurulumHatasi.value = api.toApiError(e).message
  } finally {
    hesapMesgul.value = false
  }
}

// Oturum açılınca kurulum durumu ve hesaplar bir kez çekilir.
watch(
  () => gm.unlocked,
  (acik) => {
    if (!acik) return
    kurulumuYenile()
    hesaplariYenile()
  },
  { immediate: true },
)

onMounted(() => {
  gm.tryStoredPin()
})
onUnmounted(() => {
  gm.stopPolling()
})
</script>

<template>
  <AppShell
    variant="gm"
    title="Anlatıcı Ekranı"
    sidebar-label="Anlatıcı paneli"
    :connection="gm.connectionStatus"
  >
    <!-- Üst bar: dünya künyesi (yalnızca kilit açıkken) -->
    <template #topbar-center>
      <Badge tone="gm" icon="visibility_off">anlatıcı</Badge>
      <template v-if="gm.unlocked && gm.worldState">
        <Badge tone="neutral" icon="calendar_month">Gün {{ kunye.gun }}</Badge>
        <Badge tone="muted" icon="schedule" class="hidden sm:inline-flex">{{ kunye.saat }}</Badge>
        <Badge tone="muted" icon="rainy" class="hidden md:inline-flex">{{ kunye.hava }}</Badge>
        <Badge
          v-if="kunye.gerilim"
          :tone="gerilimTonu(kunye.gerilim)"
          icon="local_fire_department"
          class="hidden md:inline-flex"
        >
          {{ kunye.gerilim }}
        </Badge>
        <span class="hidden truncate text-meta text-muted lg:inline">{{ kunye.konum }}</span>
      </template>
      <SkeletonLine v-else-if="gm.unlocked" width="12rem" height="1rem" />
    </template>

    <template #topbar-actions>
      <template v-if="gm.unlocked">
        <BaseButton
          variant="quiet"
          icon="settings"
          icon-only
          aria-label="Oyun ayarları"
          title="Oyun ayarları"
          @click="ayarlarAcik = true"
        />
        <BaseButton
          variant="quiet"
          icon="refresh"
          icon-only
          aria-label="Durumu yenile"
          :loading="yenileniyor"
          @click="yenile"
        />
        <BaseButton
          variant="quiet"
          icon="lock"
          icon-only
          aria-label="Anlatıcı ekranını kilitle"
          @click="kilitle"
        />
      </template>
    </template>

    <!-- Yan panel: dünya zarı, plan, gizli notlar, kilit (docs §4) -->
    <template #sidebar>
      <template v-if="gm.unlocked">
        <SidebarSection title="Dünya zarı" icon="casino">
          <WorldDicePanel compact :roll="gm.worldRoll" :history="gm.worldRollHistory" />
        </SidebarSection>

        <SidebarSection title="Plan" icon="bolt" :default-open="false">
          <PlotPanel :plan="gm.plot" compact />
        </SidebarSection>

        <SidebarSection
          title="Gizli notlar"
          icon="visibility_off"
          :count="gm.gmLog.length"
          :default-open="false"
        >
          <GmLogList compact tur="not" :entries="gm.gmLogNewestFirst" :limit="4" />
        </SidebarSection>

        <SidebarSection title="Kilit" icon="lock" :default-open="false">
          <p class="text-label text-muted">
            Sürüm {{ gm.version ?? '—' }} · yoklama
            {{ gm.polling ? 'açık' : 'kapalı' }}
          </p>
          <BaseButton size="sm" variant="subtle" icon="lock" block @click="kilitle">
            Ekranı kilitle
          </BaseButton>
        </SidebarSection>
      </template>

      <SidebarSection v-else title="Kilitli" icon="lock" :collapsible="false">
        <p class="text-label text-muted">
          Paneller PIN girildikten sonra açılır — kilitliyken hiçbir gizli veri istenmez.
        </p>
      </SidebarSection>
    </template>

    <!-- ------------------------------------------------------------ gövde -->

    <!-- Kilitli: yalnızca PIN ekranı -->
    <PinGate v-if="!gm.unlocked" :loading="gm.loading" :hata="gateHatasi" @ac="kilidiAc" />

    <div v-else class="mx-auto flex w-full max-w-6xl flex-col gap-4 p-4">
      <!-- Bağlantı hatası -->
      <Panel v-if="gm.error" tone="danger" title="Bağlantı" icon="cloud_off">
        <p class="text-meta text-danger">{{ gm.error.message }}</p>
        <BaseButton class="mt-2" size="sm" icon="refresh" :loading="yenileniyor" @click="yenile">
          Tekrar dene
        </BaseButton>
      </Panel>

      <!-- İlk yükleme -->
      <Panel v-if="ilkYukleme" tone="gm" title="Dünya durumu yükleniyor" icon="sync">
        <SkeletonLine :lines="5" />
      </Panel>

      <!-- KURULUM anlatıcıya ait: kadroyu burada kurar, oyunu burada başlatır.
           Oyuncular bu sırada kendi ekranlarında bekler. -->
      <template v-else-if="kurulumAsamasi">
        <Panel tone="gm" title="Oyun kurulumu" icon="group_add">
          <p class="mb-3 text-meta text-muted">
            Kadroyu sen kurarsın. Karakterler oluşturulunca oyuncular kendi
            ekranlarından karakterlerini alıp şifrelerini belirler.
          </p>
          <SetupScreen
            v-if="kurulumAsamasi === 'setup'"
            :onerilen-isimler="kurulum?.default_players || []"
            :esya-onerileri="kurulum?.start_item_suggestions || []"
            :ozel-senaryo="!!kurulum?.custom_scenario"
            :mesgul="kurulumMesgul"
            :hata="kurulumHatasi"
            @onayla="kadroyuOnayla"
          />
          <ReadyScreen
            v-else
            :karakterler="gm.worldState?.characters || {}"
            :kaynaklar="gm.worldState?.resources || {}"
            :saat="null"
            :mesgul="kurulumMesgul"
            :hata="kurulumHatasi"
            @basla="oyunuBaslat"
          />
        </Panel>

        <Panel title="Oyuncu hesapları" icon="key">
          <AccountsPanel
            :hesaplar="hesaplar.accounts || []"
            :oyun-kodu="hesaplar.game_code || ''"
            :mesgul="hesapMesgul"
            @birak="hesabiBirak"
            @yenile="hesaplariYenile"
          />
        </Panel>
      </template>

      <template v-else>
        <!-- Dünya panosu + dünya zarı -->
        <div class="grid gap-4 lg:grid-cols-[3fr_2fr]">
          <Panel title="Dünya panosu" icon="public">
            <template #actions>
              <Badge tone="gm" size="sm" icon="visibility_off">sansürsüz</Badge>
            </template>
            <WorldBoard :world-state="gm.worldState" />
          </Panel>

          <Panel tone="gm" title="Dünya zarı" icon="casino">
            <template #actions>
              <Badge tone="gm" size="sm" icon="visibility_off">oyuncular görmez</Badge>
            </template>
            <WorldDicePanel :roll="gm.worldRoll" :history="gm.worldRollHistory" />
          </Panel>
        </div>

        <!-- Harita: anlatıcı sis perdesi olmadan görür -->
        <Panel title="Harita" icon="map" collapsible>
          <template #actions>
            <Badge tone="gm" size="sm" icon="visibility_off">sis perdesi yok</Badge>
          </template>
          <MapPanel :harita="gm.worldState?.map || {}" :tehdit="gm.worldState?.threat" gm />
        </Panel>

        <!-- Müdahale bestecisi -->
        <Panel tone="gm" title="Senaryoya müdahale" icon="bolt">
          <GmNoteComposer
            :gonderiliyor="gm.sendingNote"
            :oyun-basladi="gm.started"
            :sonuc="notSonucu"
            :hata="notHatasi"
            @gonder="notGonder"
          />
        </Panel>

        <!-- Öğrenme defteri: oyunun kendi kendine çıkardığı dersler -->
        <LearningPanel :defter="gm.learning" :mesgul="gm.addingLesson" @ders-ekle="dersEkle" />

        <!-- Sabit eşya kataloğu: her oyunda aynı; buradan eklenen KALICI -->
        <ItemCatalogPanel
          :katalog="gm.catalog"
          :yukleniyor="gm.catalogLoading"
          :ekleniyor="gm.addingItem"
          @yenile="katalogYenile"
          @ekle="esyaEkle"
        />

        <!-- Anlatıcı defteri -->
        <Panel tone="gm" title="Anlatıcı defteri" icon="menu_book" collapsible>
          <template #actions>
            <Badge tone="gm" size="sm" icon="visibility_off">oyunculara gitmez</Badge>
          </template>
          <NarratorNotebook :narrator="gm.narrator" />
        </Panel>

        <!-- Zorluklar + fraksiyonlar -->
        <div class="grid gap-4 xl:grid-cols-2">
          <Panel title="Zorluklar" icon="crisis_alert" collapsible>
            <ChallengeBoard :challenges="gm.challenges" @yamala="yamaTaslagi" />
          </Panel>

          <Panel title="Fraksiyonlar" icon="handshake" collapsible>
            <FactionBoard :factions="gm.factions" @yamala="yamaTaslagi" />
          </Panel>
        </div>

        <!-- Kadro -->
        <Panel title="Kadro" icon="groups" :count="Object.keys(gm.characters).length" collapsible>
          <template #actions>
            <Badge tone="gm" size="sm" icon="visibility_off">sırlar açık</Badge>
          </template>
          <RosterPanel :characters="gm.characters" @sahneye-dondur="sahneyeDondur" />
        </Panel>

        <!-- NPC'ler + kaynaklar -->
        <div class="grid gap-4 xl:grid-cols-2">
          <Panel
            title="NPC'ler"
            icon="person"
            :count="Object.keys(gm.npcs).length"
            collapsible
            :default-open="false"
          >
            <NpcBoard :npcs="gm.npcs" />
          </Panel>

          <Panel title="Kaynaklar" icon="inventory_2" collapsible :default-open="false">
            <ResourceBoard :resources="gm.resources" />
          </Panel>
        </div>

        <!-- Durum düzenleyici -->
        <div ref="yamaKutusu">
          <Panel tone="gm" title="Durum düzenleyici" icon="data_object" collapsible>
            <template #actions>
              <Badge tone="muted" size="sm" icon="bolt">model çağrısı yok</Badge>
            </template>
            <StatePatchEditor
              v-model="yamaMetni"
              :characters="gm.characters"
              :world-state="gm.worldState"
              :patching="gm.patching"
              :hata="yamaHatasi"
              :bilgi="yamaBilgisi"
              @uygula="yamaUygula"
            />
          </Panel>
        </div>

        <!-- Kayıtlar -->
        <Panel title="Kayıtlar" icon="history" collapsible>
          <GmLogTabs :log="gm.logNewestFirst" :gm-log="gm.gmLogNewestFirst" />
        </Panel>

        <!-- Senaryo / oyun aktarma -->
        <Panel title="Senaryo ve oyun aktarma" icon="folder_open" collapsible :default-open="false">
          <!-- Karakter oluşturma turu: kapatma kararı ANLATICININ. -->
        <Panel
          v-if="gm.worldState?.flags && !gm.worldState.flags.chargen_done"
          tone="gm"
          title="Karakter oluşturma sürüyor"
          icon="badge"
        >
          <p class="text-meta text-muted">
            Bu turlarda zar atılmaz; oyuncular künyelerini anlatıyor. Herkes yazınca
            (ya da biri hiç yazmayacaksa) turu sen kapatırsın.
          </p>
          <p v-if="chargenOnayi" class="mt-2 text-meta text-warn" role="alert">
            Emin misin? Bundan sonra her hamlede zar atılır.
          </p>
          <div class="mt-2 flex flex-wrap gap-2">
            <BaseButton
              size="sm"
              :variant="chargenOnayi ? 'gm' : 'ghost'"
              icon="task_alt"
              :loading="kurulumMesgul"
              loading-text="Kapatılıyor…"
              @click="chargenBitir"
            >
              {{ chargenOnayi ? 'Evet, bitir' : 'Karakter oluşturmayı bitir' }}
            </BaseButton>
            <BaseButton
              v-if="chargenOnayi"
              size="sm"
              variant="subtle"
              @click="chargenOnayi = false"
            >
              Vazgeç
            </BaseButton>
          </div>
        </Panel>

        <Panel title="Oyuncu hesapları" icon="key">
          <AccountsPanel
            :hesaplar="hesaplar.accounts || []"
            :oyun-kodu="hesaplar.game_code || ''"
            :mesgul="hesapMesgul"
            @birak="hesabiBirak"
            @yenile="hesaplariYenile"
          />
        </Panel>

        <ScenarioTransfer @degisti="yenile" />
        </Panel>
      </template>

      <p class="flex items-center justify-center gap-1.5 text-label text-faint">
        <Icon name="keyboard" :size="14" />
        Ctrl/Cmd + B — yan paneli aç/kapat · Ctrl/Cmd + Enter — müdahaleyi gönder
      </p>
    </div>
    <!-- Oyun ayarları ve sıfırlama: yalnız anlatıcıda. -->
    <SettingsPanel
      v-model="ayarlarAcik"
      :mesgul="kurulumMesgul"
      :ayarlar="gm.settings"
      :basladi="gm.started"
      @sifirla="oyunuSifirla"
      @ayar-kaydet="ayarKaydet"
    />
  </AppShell>
</template>
