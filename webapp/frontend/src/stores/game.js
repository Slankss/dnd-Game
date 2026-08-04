import { defineStore } from 'pinia'
import { ref, computed, shallowRef } from 'vue'
import * as api from '@/api/client'
import { usePolling } from '@/composables/usePolling'

/**
 * Oyun durumu — dünya, log, yükleniyor/hata halleri ve sürüm bazlı yoklama.
 *
 * Yoklama sözleşmesi (eski arayüzden birebir korunan davranış):
 *   - `/api/state?since=<version>` ile sorulur; sunucu `changed:false` derse
 *     ağır gövde hiç kurulmaz, elimizdeki veri olduğu gibi kalır.
 *   - Aynı anda tek istek uçar (usePolling üst üste bindirmez).
 *   - Sunucu düşerse yoklama DURMAZ, yavaşlar; ilk başarılı yanıtta normale döner.
 *   - Tur gönderimi (`/api/message`) yanıtında gelen `version` doğrudan
 *     benimsenir; böylece hemen ardından gelen yoklama boşa gitmez.
 */
export const useGameStore = defineStore('game', () => {
  /* ---------------------------------------------------------------- durum */
  /** Sunucudaki durum sürümü; null → henüz hiç tam gövde alınmadı */
  const version = ref(null)
  /** public_world_state çıktısı (oyuncuya açık dünya) */
  const worldState = shallowRef(null)
  /** Oyun günlüğü — sunucu sırasıyla (eski → yeni) */
  const log = ref([])

  const started = ref(false)
  const charactersConfirmed = ref(false)
  const chargenDone = ref(false)
  const defaultPlayers = ref([])
  const startItemSuggestions = ref([])
  const customScenario = ref(false)
  const groupLabel = ref('')
  const groupDisplayName = ref('')

  /** İlk yükleme sürüyor mu (iskelet göstermek için) */
  const loading = ref(false)
  /** Son hata (ApiError) — kullanıcıya Türkçe mesajıyla gösterilir */
  const error = ref(null)
  /** Tur gönderimi sürüyor mu — composer bu sırada kilitli kalır */
  const sending = ref(false)
  /** Kurulum/başlatma gibi tekil işlemler sürüyor mu */
  const busy = ref(false)
  /** Son başarılı yanıtın zamanı (ms) */
  const lastSyncAt = ref(null)
  /** Son turda dönen envanter raporu (varsa) */
  const inventoryReport = ref(null)
  /** Yoklama sonrası okunmamış yeni girdi sayısı (docs §4: "yeni sahne" rozeti) */
  const unseenCount = ref(0)

  /* --- tur bazlı akış --- */
  /** Açık turun sunucudaki hali: {no, status, seconds, deadline_ts, picks, waiting…} */
  const round = ref(null)
  /** Oyun ayarları: {turn_seconds, profanity, round_mode} */
  const settings = ref({ turn_seconds: 0, profanity: 'hafif', round_mode: true })
  /** Seçim isteği uçuşta mı */
  const picking = ref(false)
  /** Tur gönderimi uçuşta mı (zar da bu sırada atılır) */
  const committing = ref(false)
  /** Sunucu saatiyle bizimki arasındaki fark (ms) — geri sayım kaymasın */
  const clockSkew = ref(0)

  /* --- kare harita (ızgara) --- */
  /** Sahnenin ızgarası: {width, height, cells, entities} */
  const grid = shallowRef(null)
  /** Hareket isteği uçuşta mı */
  const moving = ref(false)
  /** Son hareketin sonucu (başarısızsa nedeni ekranda gösterilir) */
  const lastMove = ref(null)

  /* -------------------------------------------------------------- getters */
  const characters = computed(() => worldState.value?.characters ?? {})
  const npcs = computed(() => worldState.value?.npcs ?? {})
  const resources = computed(() => worldState.value?.resources ?? {})
  // Sunucu `challenges`'ı isimle anahtarlanmış NESNE tutar (dizi değil) —
  // varsayılanı [] yapmak "boşsa dizi" yanılgısına yol açıyordu.
  const challenges = computed(() => worldState.value?.challenges ?? {})
  const factions = computed(() => worldState.value?.factions ?? {})
  const flags = computed(() => worldState.value?.flags ?? {})

  /** Kadro adları (state.json'daki sıra) */
  const roster = computed(() => Object.keys(characters.value))
  /** Hayatta olan karakter adları */
  const aliveRoster = computed(() =>
    roster.value.filter((ad) => characters.value[ad]?.alive !== false),
  )
  /** Ölen karakter adları */
  const deadRoster = computed(() =>
    roster.value.filter((ad) => characters.value[ad]?.alive === false),
  )

  /** Dünya künyesi — üst barın beslediği alanlar */
  const worldClock = computed(() => ({
    day: worldState.value?.day ?? null,
    clock: worldState.value?.clock ?? '',
    timeOfDay: worldState.value?.time_of_day ?? '',
    season: worldState.value?.season ?? '',
    weather: worldState.value?.weather ?? '',
    temperature: worldState.value?.temperature ?? null,
    location: worldState.value?.location ?? '',
  }))

  /** 'düşük' | 'orta' | 'yüksek' */
  const tension = computed(() => worldState.value?.tension ?? 'düşük')
  const worldRoll = computed(() => worldState.value?.world_roll ?? null)

  /** Harita: {current, places, party} */
  const worldMap = computed(() => worldState.value?.map ?? { current: '', places: {}, party: {} })
  /** Seçenek havuzu: {karakter: [{id, text, category, cost}]} */
  const options = computed(() => worldState.value?.options ?? {})
  /** Zombi tehdidi: {noise, heat, density, last, travelling…} */
  const threat = computed(() => worldState.value?.threat ?? null)
  /** Hikayeye özel eşyalar: {ad: {sahip, not, nerede, gun}} — mekaniği YOK */
  const storyItems = computed(() => worldState.value?.story_items ?? {})
  /** Taranmış mekanlar: {yer: {found}} — bir mekan bir kez taranır */
  const searchedPlaces = computed(() => worldState.value?.searched ?? {})

  /** Bir karakterin bu turdaki seçenekleri */
  function optionsFor(ad) {
    return options.value?.[ad] ?? []
  }
  /** Bir karakterin bu turdaki seçimi (yapmışsa) */
  function pickOf(ad) {
    return round.value?.picks?.[ad] ?? null
  }

  /** Turda seçim bekleyen karakterler */
  const waiting = computed(() => round.value?.waiting ?? [])
  /** Herkes seçtiyse tur gönderilmeye hazırdır */
  const roundReady = computed(() => !!round.value?.all_picked)
  const roundOpen = computed(() => round.value?.status === 'acik')
  /** Tur bazlı akış açık mı (kapalıysa serbest metin turu) */
  const roundMode = computed(() => settings.value?.round_mode !== false)

  /** Akış için ters sıralı log — EN YENİ EN ÜSTTE (docs §4). */
  const logNewestFirst = computed(() => [...log.value].reverse())

  /** Uygulamanın hangi ekranda olduğu: kurulum → hazır → oyun */
  const phase = computed(() => {
    if (!charactersConfirmed.value) return 'setup'
    if (!started.value) return 'ready'
    return 'playing'
  })

  /** Üst bardaki bağlantı göstergesi: 'bagli' | 'yavas' | 'kopuk' */
  const connectionStatus = computed(() => {
    if (yoklama.hataSayaci.value === 0) return 'bagli'
    return yoklama.hataSayaci.value < 3 ? 'yavas' : 'kopuk'
  })

  /* ------------------------------------------------------------- yardımcı */
  function veriyiBenimse(data) {
    if (typeof data.version === 'number') version.value = data.version
    if (data.changed === false) return false

    worldState.value = data.world_state ?? worldState.value
    // Izgara dünya durumunun içinde geliyor: yoklama onu da tazeler.
    if (data.world_state?.grid) grid.value = data.world_state.grid
    if (Array.isArray(data.log)) {
      const oncekiUzunluk = log.value.length
      log.value = data.log
      if (oncekiUzunluk && data.log.length > oncekiUzunluk) {
        unseenCount.value += data.log.length - oncekiUzunluk
      }
    }
    started.value = !!data.started
    charactersConfirmed.value = !!data.characters_confirmed
    chargenDone.value = !!data.chargen_done
    if (Array.isArray(data.default_players)) defaultPlayers.value = data.default_players
    if (Array.isArray(data.start_item_suggestions)) {
      startItemSuggestions.value = data.start_item_suggestions
    }
    customScenario.value = !!data.custom_scenario
    if (data.group_label) groupLabel.value = data.group_label
    if (data.group_display_name) groupDisplayName.value = data.group_display_name
    if (data.settings) settings.value = data.settings
    if (data.round) turuBenimse(data.round)
    return true
  }

  /**
   * Turu benimse. Geri sayım sunucunun saatine göre yürür: `server_ts` ile
   * bizim saatimizin farkı ölçülür, böylece istemci saati kaymışsa bile
   * sayaç sunucudaki gerçek süreyi gösterir.
   */
  function turuBenimse(yeni) {
    if (!yeni) return
    if (typeof yeni.server_ts === 'number') {
      clockSkew.value = Date.now() - yeni.server_ts * 1000
    }
    round.value = yeni
  }

  /** Tur/GM yanıtlarında gelen kısmi güncellemeyi uygula. */
  function turYanitiniIsle(data) {
    if (typeof data.version === 'number') version.value = data.version
    if (data.world_state) worldState.value = data.world_state
    if (data.world_state?.grid) grid.value = data.world_state.grid
    const yeni = []
    if (Array.isArray(data.user_entries)) yeni.push(...data.user_entries)
    if (data.gm_entry) yeni.push(data.gm_entry)
    if (data.system_entry) yeni.unshift(data.system_entry)
    if (yeni.length) log.value = [...log.value, ...yeni]
    if ('started' in data) started.value = !!data.started
    if (data.round) turuBenimse(data.round)
  }

  function hatayiKur(e) {
    error.value = api.toApiError(e)
    return error.value
  }

  /* ------------------------------------------------------------- aksiyonlar */

  /**
   * Durumu sunucudan çek.
   * @param {{force?: boolean, signal?: AbortSignal}} [opts] force → `since` gönderme
   */
  async function refresh({ force = false, signal } = {}) {
    const ilkYukleme = worldState.value === null
    if (ilkYukleme) loading.value = true
    try {
      const data = await api.getState(force ? null : version.value, { signal })
      veriyiBenimse(data)
      error.value = null
      lastSyncAt.value = Date.now()
      return data
    } catch (e) {
      throw hatayiKur(e)
    } finally {
      if (ilkYukleme) loading.value = false
    }
  }

  /* --- sürüm bazlı yoklama --- */
  const yoklama = usePolling((ctx) => refresh({ signal: ctx?.signal }), {
    interval: 4000,
    maxInterval: 30000,
  })

  function startPolling() {
    yoklama.baslat()
  }
  function stopPolling() {
    yoklama.durdur()
  }
  /** Hemen bir yoklama turu (örn. sekmeye dönünce ya da düğmeyle). */
  function pollNow() {
    yoklama.hemenCalistir()
  }

  /**
   * POST /api/setup-characters
   * @param {Array<object>} players
   */
  async function setupCharacters(players) {
    busy.value = true
    try {
      const data = await api.setupCharacters(players)
      if (data.world_state) worldState.value = data.world_state
      charactersConfirmed.value = !!data.characters_confirmed
      error.value = null
      await refresh({ force: true })
      return data
    } catch (e) {
      throw hatayiKur(e)
    } finally {
      busy.value = false
    }
  }

  /** POST /api/start — ilk sahneyi anlatıcı yazar (uzun sürebilir). */
  async function start() {
    busy.value = true
    try {
      const data = await api.startGame()
      turYanitiniIsle({ ...data, started: true })
      error.value = null
      await refresh({ force: true })
      return data
    } catch (e) {
      throw hatayiKur(e)
    } finally {
      busy.value = false
    }
  }

  /**
   * POST /api/message — bir oyuncu turu. Model 30-60 sn sürebilir; bu sırada
   * `sending` true kalır, composer kilitlenir.
   * @param {string} player
   * @param {string} text
   */
  async function sendAction(player, text) {
    if (sending.value) return null
    sending.value = true
    try {
      const data = await api.sendMessage(player, text)
      turYanitiniIsle(data)
      inventoryReport.value = data.inventory_report ?? null
      error.value = null
      lastSyncAt.value = Date.now()
      return data
    } catch (e) {
      throw hatayiKur(e)
    } finally {
      sending.value = false
    }
  }

  /**
   * POST /api/takeover — ölen oyuncunun yerine yeni karakter.
   * @param {string} deadPlayer
   * @param {string} newCharacter
   */
  async function takeover(deadPlayer, newCharacter) {
    busy.value = true
    try {
      const data = await api.takeover(deadPlayer, newCharacter)
      turYanitiniIsle(data)
      error.value = null
      await refresh({ force: true })
      return data
    } catch (e) {
      throw hatayiKur(e)
    } finally {
      busy.value = false
    }
  }

  /**
   * POST /api/round/pick — SUNULAN seçeneklerden birini seç.
   *
   * Serbest hamle yoktur: sunucu yalnız `option_id` kabul eder. Seçim TURU
   * İLERLETMEZ; oyuncu turu geçene kadar kararını değiştirebilir ve sunucu
   * son seçimi işler.
   *
   * ZAR BURADA ATILMAZ: turun zarı "Turu Geç"e basılınca (`commitRound`)
   * herkes için birlikte atılır ve sonucu akışta (StoryEntry) görünür.
   * @param {string} player
   * @param {{optionId: string}} secim
   */
  async function pickOption(player, secim) {
    if (picking.value) return null
    picking.value = true
    try {
      const data = await api.pickOption(player, secim)
      if (typeof data.version === 'number') version.value = data.version
      turuBenimse(data.round)
      error.value = null
      return data
    } catch (e) {
      throw hatayiKur(e)
    } finally {
      picking.value = false
    }
  }

  /** POST /api/round/wait — bu turda hamle yapmadan bekle. */
  async function waitRound(player) {
    picking.value = true
    try {
      const data = await api.waitRound(player)
      if (typeof data.version === 'number') version.value = data.version
      turuBenimse(data.round)
      error.value = null
      return data
    } catch (e) {
      throw hatayiKur(e)
    } finally {
      picking.value = false
    }
  }

  /**
   * POST /api/round/commit — turu kapat ve tüm seçimleri tek seferde gönder.
   * Süre dolduğunda arayüz bunu `reason: 'sure'` ile kendisi çağırır; sunucu
   * aynı turun iki kez gönderilmesini `round_no` ile engeller.
   * @param {'elle'|'sure'} reason
   */
  async function commitRound(reason = 'elle') {
    if (committing.value || sending.value) return null
    committing.value = true
    sending.value = true
    try {
      const data = await api.commitRound(reason, round.value?.no ?? null)
      if (!data?.skipped) {
        turYanitiniIsle(data)
        lastSyncAt.value = Date.now()
      } else if (data.round) {
        turuBenimse(data.round)
      }
      error.value = null
      return data
    } catch (e) {
      throw hatayiKur(e)
    } finally {
      committing.value = false
      sending.value = false
    }
  }

  /**
   * GET /api/grid — sahnenin ızgarasını çeker (yoksa sunucu kurar).
   * Oyun ekranı açılırken bir kez çağrılır; sonrasında yoklama tazeler.
   */
  async function fetchGrid() {
    try {
      const data = await api.getGrid()
      if (data.grid) grid.value = data.grid
      if (typeof data.version === 'number') version.value = data.version
      return data
    } catch (e) {
      throw hatayiKur(e)
    }
  }

  /**
   * POST /api/grid/move — karakteri BİR KARE hareket ettirir.
   * Hareketi sunucu çözer; burada yalnız sonuç ve yeni ızgara benimsenir.
   * @param {string} player
   * @param {string} direction 'kuzey' | 'güney' | 'doğu' | 'batı' | çaprazlar
   */
  async function moveOnGrid(player, direction) {
    if (moving.value) return null
    moving.value = true
    try {
      const data = await api.moveOnGrid(player, direction)
      if (data.grid) grid.value = data.grid
      if (typeof data.version === 'number') version.value = data.version
      lastMove.value = { ...data.result, ts: Date.now() }
      error.value = null
      return data
    } catch (e) {
      lastMove.value = { ok: false, reason: 'hata', blocked_by: e?.message || '', ts: Date.now() }
      throw hatayiKur(e)
    } finally {
      moving.value = false
    }
  }

  /** POST /api/settings — tur süresi / küfür dozu / tur bazlı akış. */
  async function saveSettings(ayarlar) {
    busy.value = true
    try {
      const data = await api.saveSettings(ayarlar)
      if (data.settings) settings.value = data.settings
      if (data.round) turuBenimse(data.round)
      if (typeof data.version === 'number') version.value = data.version
      error.value = null
      return data
    } catch (e) {
      throw hatayiKur(e)
    } finally {
      busy.value = false
    }
  }

  /** POST /api/finish-chargen */
  async function finishChargen() {
    busy.value = true
    try {
      const data = await api.finishChargen()
      if (data.world_state) worldState.value = data.world_state
      chargenDone.value = true
      error.value = null
      return data
    } catch (e) {
      throw hatayiKur(e)
    } finally {
      busy.value = false
    }
  }

  /**
   * POST /api/reset — oyunu sıfırlar.
   * @param {{keepLearning?: boolean}} [secenek] öğrenme defteri korunsun mu
   */
  async function reset({ keepLearning = true } = {}) {
    busy.value = true
    try {
      const data = await api.resetGame({ keepLearning })
      version.value = null
      worldState.value = null
      log.value = []
      started.value = false
      charactersConfirmed.value = false
      chargenDone.value = false
      unseenCount.value = 0
      round.value = null
      grid.value = null
      lastMove.value = null
      error.value = null
      await refresh({ force: true })
      return data
    } catch (e) {
      throw hatayiKur(e)
    } finally {
      busy.value = false
    }
  }

  function clearError() {
    error.value = null
  }

  /** "Yeni sahne" rozetini söndür. */
  function markSeen() {
    unseenCount.value = 0
  }

  return {
    // durum
    version,
    worldState,
    log,
    started,
    charactersConfirmed,
    chargenDone,
    defaultPlayers,
    startItemSuggestions,
    customScenario,
    groupLabel,
    groupDisplayName,
    loading,
    error,
    sending,
    busy,
    lastSyncAt,
    inventoryReport,
    unseenCount,
    round,
    settings,
    picking,
    committing,
    clockSkew,
    grid,
    moving,
    lastMove,
    // getters
    characters,
    npcs,
    resources,
    challenges,
    factions,
    flags,
    roster,
    aliveRoster,
    deadRoster,
    worldClock,
    tension,
    worldRoll,
    worldMap,
    options,
    threat,
    storyItems,
    searchedPlaces,
    optionsFor,
    pickOf,
    waiting,
    roundReady,
    roundOpen,
    roundMode,
    logNewestFirst,
    phase,
    connectionStatus,
    // yoklama iç durumu (gösterge için)
    polling: yoklama.aktif,
    pollingBusy: yoklama.calisiyor,
    pollErrorCount: yoklama.hataSayaci,
    pollInterval: yoklama.suAnkiAralik,
    // aksiyonlar
    refresh,
    startPolling,
    stopPolling,
    pollNow,
    setupCharacters,
    start,
    sendAction,
    pickOption,
    waitRound,
    commitRound,
    fetchGrid,
    moveOnGrid,
    saveSettings,
    takeover,
    finishChargen,
    reset,
    clearError,
    markSeen,
  }
})

export default useGameStore
