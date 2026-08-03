import { defineStore } from 'pinia'
import { ref, computed, shallowRef } from 'vue'
import * as api from '@/api/client'
import { usePolling } from '@/composables/usePolling'

const PIN_ANAHTARI = 'kizil-cokus:gm-pin'

function pindenOku() {
  try {
    return localStorage.getItem(PIN_ANAHTARI) || ''
  } catch {
    return ''
  }
}

function pinYaz(deger) {
  try {
    if (deger) localStorage.setItem(PIN_ANAHTARI, deger)
    else localStorage.removeItem(PIN_ANAHTARI)
  } catch {
    /* sessizce geç */
  }
}

/**
 * Anlatıcı (GM) durumu — PIN kilidi ve `/api/gm/state` yoklaması.
 *
 * GM görünümü oyuncu görünümünden AYRIDIR: `world_state` burada sansürsüz
 * gelir (gizli notlar, faction iç görünürlüğü vb.). Bu yüzden ayrı store.
 * PIN localStorage'da tutulur — anlatıcı her yenilemede yeniden yazmasın.
 */
export const useGmStore = defineStore('gm', () => {
  /* ---------------------------------------------------------------- durum */
  const pin = ref(pindenOku())
  /** PIN sunucuca doğrulandı mı */
  const unlocked = ref(false)
  const version = ref(null)
  /** Tam (sansürsüz) dünya durumu */
  const worldState = shallowRef(null)
  /** Anlatıcı notları günlüğü */
  const gmLog = ref([])
  // Senarist planı (data/plot.json) — SADECE bu ekrana gelir.
  const plot = shallowRef(null)
  /** Oyuncu akışının son 40 girdisi (anlatıcı canlı izlesin) */
  const log = ref([])
  const started = ref(false)
  /** Öğrenme defteri özeti: dersler, seçim profili, tempo, havuz */
  const learning = shallowRef(null)
  /** Açık turun hali (kim seçti, süre) */
  const round = shallowRef(null)
  /** Oyun ayarları (tur süresi, küfür dozu) */
  const settings = ref({})
  /** Ders ekleme isteği uçuşta mı */
  const addingLesson = ref(false)

  const loading = ref(false)
  const error = ref(null)
  /** Not gönderimi sürüyor mu (model yanıtı uzun sürebilir) */
  const sendingNote = ref(false)
  /** Elle yama kaydediliyor mu */
  const patching = ref(false)
  const lastSyncAt = ref(null)

  /* -------------------------------------------------------------- getters */
  const characters = computed(() => worldState.value?.characters ?? {})
  const npcs = computed(() => worldState.value?.npcs ?? {})
  const resources = computed(() => worldState.value?.resources ?? {})
  // Sunucu `challenges`'ı isimle anahtarlanmış NESNE tutar (dizi değil) —
  // varsayılanı [] yapmak "boşsa dizi" yanılgısına yol açıyordu.
  const challenges = computed(() => worldState.value?.challenges ?? {})
  const factions = computed(() => worldState.value?.factions ?? {})
  const narrator = computed(() => worldState.value?.narrator ?? null)
  const worldRoll = computed(() => worldState.value?.world_roll ?? null)
  const worldRollHistory = computed(() => worldState.value?.world_roll_history ?? [])

  /** Akış için ters sıralı loglar — en yeni en üstte. */
  const logNewestFirst = computed(() => [...log.value].reverse())
  const gmLogNewestFirst = computed(() => [...gmLog.value].reverse())

  const connectionStatus = computed(() => {
    if (yoklama.hataSayaci.value === 0) return 'bagli'
    return yoklama.hataSayaci.value < 3 ? 'yavas' : 'kopuk'
  })

  /* ----------------------------------------------------------- aksiyonlar */

  /**
   * POST /api/gm/unlock — PIN'i doğrula, doğruysa sakla ve yoklamayı başlat.
   * @param {string} yeniPin
   */
  async function unlock(yeniPin) {
    loading.value = true
    try {
      await api.gmUnlock(yeniPin)
      pin.value = yeniPin
      pinYaz(yeniPin)
      unlocked.value = true
      error.value = null
      await refresh({ force: true })
      startPolling()
      return true
    } catch (e) {
      unlocked.value = false
      error.value = api.toApiError(e)
      throw error.value
    } finally {
      loading.value = false
    }
  }

  /** Kilidi kapat, saklanan PIN'i sil, yoklamayı durdur. */
  function lock() {
    stopPolling()
    unlocked.value = false
    pin.value = ''
    pinYaz('')
    version.value = null
    worldState.value = null
    plot.value = null
    learning.value = null
    round.value = null
    gmLog.value = []
    log.value = []
    error.value = null
  }

  /**
   * GET /api/gm/state?pin&since
   * @param {{force?: boolean, signal?: AbortSignal}} [opts]
   */
  async function refresh({ force = false, signal } = {}) {
    if (!pin.value) return null
    const ilkYukleme = worldState.value === null
    if (ilkYukleme) loading.value = true
    try {
      const data = await api.getGmState(pin.value, force ? null : version.value, { signal })
      if (typeof data.version === 'number') version.value = data.version
      if (data.changed !== false) {
        worldState.value = data.world_state ?? worldState.value
        if (Array.isArray(data.gm_log)) gmLog.value = data.gm_log
        if (data.plot !== undefined) plot.value = data.plot
        if (Array.isArray(data.log)) log.value = data.log
        if (data.learning) learning.value = data.learning
        if (data.round !== undefined) round.value = data.round
        if (data.settings) settings.value = data.settings
        started.value = !!data.started
      }
      unlocked.value = true
      error.value = null
      lastSyncAt.value = Date.now()
      return data
    } catch (e) {
      const hata = api.toApiError(e)
      // Yanlış PIN → kilit tekrar kapanır ve yoklama durur.
      if (hata.isForbidden) {
        unlocked.value = false
        stopPolling()
      }
      error.value = hata
      throw hata
    } finally {
      if (ilkYukleme) loading.value = false
    }
  }

  const yoklama = usePolling((ctx) => refresh({ signal: ctx?.signal }), {
    interval: 4000,
    maxInterval: 30000,
  })

  function startPolling() {
    if (!pin.value) return
    yoklama.baslat()
  }
  function stopPolling() {
    yoklama.durdur()
  }
  function pollNow() {
    yoklama.hemenCalistir()
  }

  /**
   * POST /api/gm/note — anlatıcı müdahalesi.
   * @param {string} text
   * @param {'gizli'|'sahne'|'surpriz'} mode
   */
  async function sendNote(text, mode = 'gizli') {
    if (sendingNote.value) return null
    sendingNote.value = true
    try {
      const data = await api.gmNote(pin.value, text, mode)
      if (data.world_state) worldState.value = data.world_state
      // Sunucu üç ayrı girdi döndürür: `note_entry` (anlatıcının notu) ve
      // `reply_entry` (modelin ona cevabı) anlatıcı günlüğüne, `gm_entry` ise
      // OYUNCU akışına düşen sahnedir (gizli modda null olur).
      const gmEklenecek = [data.note_entry, data.reply_entry].filter(Boolean)
      if (gmEklenecek.length) gmLog.value = [...gmLog.value, ...gmEklenecek]
      if (data.gm_entry) log.value = [...log.value, data.gm_entry]
      error.value = null
      await refresh({ force: true })
      return data
    } catch (e) {
      error.value = api.toApiError(e)
      throw error.value
    } finally {
      sendingNote.value = false
    }
  }

  /**
   * POST /api/gm/lesson — öğrenme defterine elle ders ekle.
   * Elle yazılan dersler otomatik olanların ÖNÜNDE prompt'a girer ve
   * `.claude/skills/kizil-cokus-anlatici/ogrenilenler.md` dosyasına da işlenir.
   * @param {string} text
   */
  async function addLesson(text) {
    addingLesson.value = true
    try {
      const data = await api.gmLesson(pin.value, text)
      if (data.learning) learning.value = data.learning
      error.value = null
      return data
    } catch (e) {
      error.value = api.toApiError(e)
      throw error.value
    } finally {
      addingLesson.value = false
    }
  }

  /**
   * POST /api/gm/patch — dünya durumuna elle kısmi yama.
   * @param {object} patch
   */
  async function applyPatch(patch) {
    patching.value = true
    try {
      const data = await api.gmPatch(pin.value, patch)
      if (typeof data.version === 'number') version.value = data.version
      if (data.world_state) worldState.value = data.world_state
      error.value = null
      return data
    } catch (e) {
      error.value = api.toApiError(e)
      throw error.value
    } finally {
      patching.value = false
    }
  }

  function clearError() {
    error.value = null
  }

  /** Sayfa açılışında saklı PIN varsa sessizce dene. */
  async function tryStoredPin() {
    if (!pin.value) return false
    try {
      await refresh({ force: true })
      startPolling()
      return true
    } catch {
      return false
    }
  }

  return {
    // durum
    pin,
    unlocked,
    version,
    worldState,
    plot,
    gmLog,
    log,
    started,
    learning,
    round,
    settings,
    addingLesson,
    loading,
    error,
    sendingNote,
    patching,
    lastSyncAt,
    // getters
    characters,
    npcs,
    resources,
    challenges,
    factions,
    narrator,
    worldRoll,
    worldRollHistory,
    logNewestFirst,
    gmLogNewestFirst,
    connectionStatus,
    // yoklama iç durumu
    polling: yoklama.aktif,
    // oyuncu store'unda olduğu gibi burada da açığa çıkarılır — "Yenile"
    // düğmesinin kilitlenmesi için görünümde yerel bayrak tutulmasın.
    pollingBusy: yoklama.calisiyor,
    pollErrorCount: yoklama.hataSayaci,
    pollInterval: yoklama.suAnkiAralik,
    // aksiyonlar
    unlock,
    lock,
    refresh,
    startPolling,
    stopPolling,
    pollNow,
    sendNote,
    addLesson,
    applyPatch,
    clearError,
    tryStoredPin,
  }
})

export default useGmStore
