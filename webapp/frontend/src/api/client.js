/**
 * HTTP API istemcisi — docs/mimari.md §4 "HTTP API sözleşmesi" ile birebir.
 *
 * Kural: bu dosyanın dışında hiçbir yerde `fetch` çağrılmaz. Ağ hatası,
 * HTTP hata kodu ve sunucunun `{error: "..."}` gövdesi tek tip `ApiError`'a
 * dönüşür; mesajlar Türkçe kalır.
 */

/** Tek tip hata nesnesi. */
export class ApiError extends Error {
  /**
   * @param {string} message Türkçe, kullanıcıya gösterilebilir mesaj
   * @param {object} [opts]
   * @param {number|null} [opts.status] HTTP durum kodu (ağ hatasında null)
   * @param {string} [opts.kind] 'ag' | 'http' | 'sunucu' | 'iptal' | 'bicim'
   * @param {unknown} [opts.cause] özgün hata
   * @param {unknown} [opts.body] sunucudan gelen ayrıştırılmış gövde
   */
  constructor(message, { status = null, kind = 'http', cause = null, body = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.kind = kind
    this.cause = cause
    this.body = body
  }

  /** Ağ kesildi / sunucu kapalı mı? Yoklama bunu görünce yavaşlar, durmaz. */
  get isNetwork() {
    return this.kind === 'ag'
  }

  /** İstek iptal edildi mi (AbortController)? */
  get isAborted() {
    return this.kind === 'iptal'
  }

  /** Oturum yok — arayüz giriş ekranını açmalı. */
  get isUnauthorized() {
    return this.status === 401
  }

  /** Giriş var ama bu işlem bu role ait değil. */
  get isForbidden() {
    return this.status === 403
  }
}

/** HTTP kodu → varsayılan Türkçe mesaj (sunucu `{error}` vermediyse). */
const VARSAYILAN_MESAJ = {
  400: 'İstek geçersiz.',
  401: 'Giriş yapın.',
  403: 'Bu işlem için yetkiniz yok.',
  404: 'İstenen uç nokta bulunamadı.',
  409: 'Durum çakıştı, sayfayı yenile.',
  500: 'Sunucuda beklenmeyen bir hata oluştu.',
  502: 'Anlatıcı modeli yanıt veremedi.',
  503: 'Sunucu şu anda meşgul.',
  504: 'Anlatıcı modeli zaman aşımına uğradı.',
}

/**
 * Tek giriş noktası. Yanıtı JSON'a çevirir, hata biçimini normalleştirir.
 * @param {string} yol '/api/...' ile başlayan yol
 * @param {object} [opts]
 * @param {'GET'|'POST'} [opts.method]
 * @param {object|null} [opts.body] JSON gövdesi
 * @param {Record<string, string|number|null|undefined>} [opts.query] sorgu dizesi
 * @param {AbortSignal} [opts.signal]
 * @param {number} [opts.timeout] ms; 0 = zaman aşımı yok
 */
async function istek(yol, { method = 'GET', body = null, query = null, signal, timeout = 0 } = {}) {
  let url = yol
  if (query) {
    const params = new URLSearchParams()
    for (const [k, v] of Object.entries(query)) {
      if (v !== null && v !== undefined && v !== '') params.set(k, String(v))
    }
    const qs = params.toString()
    if (qs) url += (url.includes('?') ? '&' : '?') + qs
  }

  // Zaman aşımı istenmişse çağıranın sinyaliyle birleştir.
  const controller = new AbortController()
  const temizle = []
  if (signal) {
    if (signal.aborted) controller.abort(signal.reason)
    else {
      const f = () => controller.abort(signal.reason)
      signal.addEventListener('abort', f, { once: true })
      temizle.push(() => signal.removeEventListener('abort', f))
    }
  }
  if (timeout > 0) {
    const t = setTimeout(() => controller.abort(new DOMException('timeout', 'TimeoutError')), timeout)
    temizle.push(() => clearTimeout(t))
  }

  let res
  try {
    res = await fetch(url, {
      method,
      // Oturum çerezi (kimlik) her istekte gitsin — sunucu "kim oynuyor"u
      // gövdeden değil bu çerezden okuyor.
      credentials: 'same-origin',
      signal: controller.signal,
      headers: body === null ? undefined : { 'Content-Type': 'application/json' },
      body: body === null ? undefined : JSON.stringify(body),
    })
  } catch (e) {
    if (e?.name === 'AbortError' && signal?.aborted) {
      throw new ApiError('İstek iptal edildi.', { kind: 'iptal', cause: e })
    }
    if (e?.name === 'TimeoutError' || e?.name === 'AbortError') {
      throw new ApiError('Sunucu zamanında yanıt vermedi.', { kind: 'ag', cause: e })
    }
    throw new ApiError('Sunucuya bağlanılamadı.', { kind: 'ag', cause: e })
  } finally {
    temizle.forEach((f) => f())
  }

  // Gövdeyi ayrıştır (boş gövde de olabilir).
  const ham = await res.text()
  let veri = null
  if (ham) {
    try {
      veri = JSON.parse(ham)
    } catch (e) {
      if (!res.ok) {
        throw new ApiError(VARSAYILAN_MESAJ[res.status] || `Sunucu hatası (${res.status}).`, {
          status: res.status,
          cause: e,
        })
      }
      throw new ApiError('Sunucudan beklenmeyen bir yanıt geldi.', {
        status: res.status,
        kind: 'bicim',
        cause: e,
      })
    }
  }

  if (!res.ok) {
    const mesaj =
      (veri && typeof veri.error === 'string' && veri.error) ||
      VARSAYILAN_MESAJ[res.status] ||
      `Sunucu hatası (${res.status}).`
    throw new ApiError(mesaj, { status: res.status, kind: 'http', body: veri })
  }

  // 200 ama gövdede `{error}` — sunucu bazı akışlarda böyle yanıtlıyor.
  if (veri && typeof veri.error === 'string' && veri.error) {
    throw new ApiError(veri.error, { status: res.status, kind: 'sunucu', body: veri })
  }

  return veri
}

/* ==========================================================================
 * Oyuncu uç noktaları
 * ========================================================================== */

/**
 * GET /api/state?since=<v>
 * Sürüm değişmediyse sunucu ağır gövdeyi hiç kurmaz: `{version, changed:false}`.
 * @param {number|null} [since] elimizdeki sürüm; null → tam gövde iste
 * @param {{signal?: AbortSignal}} [opts]
 */
export function getState(since = null, opts = {}) {
  return istek('/api/state', {
    query: { since: since === null ? undefined : since },
    signal: opts.signal,
  })
}

/**
 * POST /api/setup-characters
 * @param {Array<{name:string,item?:string,profession?:string,age?:string|number,
 *   strength?:string,weakness?:string,secret?:string}>} players
 */
export function setupCharacters(players, opts = {}) {
  return istek('/api/setup-characters', { method: 'POST', body: { players }, signal: opts.signal })
}

/** POST /api/start → `{gm_entry, world_state, started}` */
export function startGame(opts = {}) {
  return istek('/api/start', { method: 'POST', body: {}, signal: opts.signal, timeout: opts.timeout ?? 0 })
}

/**
 * POST /api/message — SADECE karakter oluşturma turları için. Asıl oyunda
 * serbest hamle yoktur; sunucu chargen bittiğinde bu ucu reddeder.
 * Model yanıtı 30-60 sn sürebilir.
 * @param {string} player
 * @param {string} text
 * @returns {Promise<{user_entries:any[], gm_entry:any, world_state:any,
 *   inventory_report:any, version:number}>}
 */
export function sendMessage(player, text, opts = {}) {
  return istek('/api/message', { method: 'POST', body: { player, text }, signal: opts.signal })
}

/**
 * POST /api/takeover — ölen oyuncunun yerine yeni karakter devralınır.
 * @param {string} deadPlayer
 * @param {string} newCharacter
 */
export function takeover(deadPlayer, newCharacter, opts = {}) {
  return istek('/api/takeover', {
    method: 'POST',
    body: { dead_player: deadPlayer, new_character: newCharacter },
    signal: opts.signal,
  })
}

/** POST /api/finish-chargen → `{ok, world_state}` */
export function finishChargen(opts = {}) {
  return istek('/api/finish-chargen', { method: 'POST', body: {}, signal: opts.signal })
}

/**
 * POST /api/settings — tur süresi, küfür dozu, tur bazlı akış.
 * @param {{turn_seconds?: number, profanity?: 'kapalı'|'hafif'|'sert', round_mode?: boolean}} ayarlar
 */
export function saveSettings(ayarlar, opts = {}) {
  return istek('/api/settings', { method: 'POST', body: ayarlar, signal: opts.signal })
}

/**
 * POST /api/reset → `{ok}` — oyunu sıfırlar.
 * Öğrenme defteri varsayılan olarak KORUNUR (oyun öğrendiklerini unutmasın).
 * @param {{keepLearning?: boolean}} [secenek]
 */
export function resetGame({ keepLearning = true } = {}, opts = {}) {
  return istek('/api/reset', {
    method: 'POST',
    body: { keep_learning: keepLearning },
    signal: opts.signal,
  })
}

/* ==========================================================================
 * Tur bazlı akış (seçenek havuzu)
 * ========================================================================== */

/**
 * POST /api/round/pick — sunulan seçeneklerden birini seç; zar SUNUCUDA o anda
 * atılır. Serbest hamle yoktur: sunucu metin gövdesini reddeder.
 * @param {string} player
 * @param {{optionId: string}} secim havuzdaki seçeneğin kimliği
 * @returns {Promise<{roll:number, band:string, round:object, all_picked:boolean}>}
 */
export function pickOption(player, { optionId = null } = {}, opts = {}) {
  return istek('/api/round/pick', {
    method: 'POST',
    body: { player, option_id: optionId },
    signal: opts.signal,
  })
}

/** POST /api/round/wait — bu turda hamle yapmadan bekle. */
export function waitRound(player, opts = {}) {
  return istek('/api/round/wait', { method: 'POST', body: { player }, signal: opts.signal })
}

/**
 * POST /api/round/commit — turu kapat, tüm seçimleri tek seferde gönder.
 * @param {'elle'|'sure'} reason süre dolduğunda 'sure' gönderilir
 * @param {number|null} roundNo aynı turu iki istemci göndermesin diye
 */
export function commitRound(reason = 'elle', roundNo = null, opts = {}) {
  return istek('/api/round/commit', {
    method: 'POST',
    body: { reason, round_no: roundNo },
    signal: opts.signal,
  })
}

/* ==========================================================================
 * Kare harita (ızgara)
 * ========================================================================== */

/** GET /api/grid → `{grid, world_state, version}` — sahne yoksa kurulur. */
export function getGrid(opts = {}) {
  return istek('/api/grid', { signal: opts.signal })
}

/**
 * POST /api/grid/move — bir karakteri BİR KARE hareket ettirir.
 * Hareket sunucudaki algoritmayla çözülür (yön → koordinat → sınır →
 * geçilebilirlik → kaldır → koordinat → ekle → sonuç).
 * @param {string} player
 * @param {'kuzey'|'güney'|'doğu'|'batı'|string} direction
 * @returns {Promise<{ok:boolean, result:object, grid:object, version:number}>}
 */
export function moveOnGrid(player, direction, opts = {}) {
  return istek('/api/grid/move', {
    method: 'POST',
    body: { player, direction },
    signal: opts.signal,
  })
}

/* ==========================================================================
 * Anlatıcı (GM) uç noktaları
 * ========================================================================== */

/**
 * Anlatıcı uçları artık PIN TAŞIMAZ: `/api/auth/gm` ile bir kez giriş yapılır,
 * sonraki her istek oturum çerezinden yetkilenir. Böylece PIN adres çubuğunda,
 * sunucu kayıtlarında ve tarayıcı geçmişinde dolaşmaz.
 */

/** GET /api/gm/state?since → `{version, changed, world_state, gm_log, log, started}` */
export function getGmState(since = null, opts = {}) {
  return istek('/api/gm/state', {
    query: { since: since === null ? undefined : since },
    signal: opts.signal,
  })
}

/**
 * POST /api/gm/note → `{gm_entry, world_state, published}`
 * @param {string} text
 * @param {'gizli'|'sahne'|'surpriz'} mode
 */
export function gmNote(text, mode, opts = {}) {
  return istek('/api/gm/note', { method: 'POST', body: { text, mode }, signal: opts.signal })
}

/** POST /api/gm/lesson → `{ok, learning}` — deftere elle ders ekler. */
export function gmLesson(text, opts = {}) {
  return istek('/api/gm/lesson', { method: 'POST', body: { text }, signal: opts.signal })
}

/** POST /api/gm/patch → `{ok, version, world_state}` */
export function gmPatch(patch, opts = {}) {
  return istek('/api/gm/patch', { method: 'POST', body: { patch }, signal: opts.signal })
}

/** GET /api/gm/items → `{surum, kategoriler, yer_turleri, esyalar}` */
export function gmItems(opts = {}) {
  return istek('/api/gm/items', { signal: opts.signal })
}

/**
 * POST /api/gm/items → `{ok, item, catalog}`
 * Kataloga KALICI eşya ekler: data/items.json'a yazılır ve o andan itibaren
 * TÜM oyunlarda geçerli olur (oyunun durumuna değil, içeriğine girer).
 */
export function gmAddItem(item, opts = {}) {
  return istek('/api/gm/items', { method: 'POST', body: { item }, signal: opts.signal })
}

/** GET /api/gm/accounts → `{accounts:[{player, claimed, last_login}], game_code}` */
export function gmAccounts(opts = {}) {
  return istek('/api/gm/accounts', { signal: opts.signal })
}

/** POST /api/gm/accounts/release — şifresini unutan oyuncunun sahipliğini bırakır. */
export function gmReleaseAccount(player, opts = {}) {
  return istek('/api/gm/accounts/release', {
    method: 'POST',
    body: { player },
    signal: opts.signal,
  })
}

/* ==========================================================================
 * Kimlik
 * ========================================================================== */

/** GET /api/auth/me → `{role, player, roster, available, claimed, single_screen}` */
export function authMe(opts = {}) {
  return istek('/api/auth/me', { signal: opts.signal })
}

/**
 * POST /api/auth/login — karakterle giriş.
 * Karakter sahipsizse `code` (oyun kodu) ZORUNLUDUR: o giriş karakteri
 * sahiplenir ve şifreyi kurar. Sahipliyse kod gerekmez.
 */
export function authLogin({ player, password, code = null }, opts = {}) {
  return istek('/api/auth/login', {
    method: 'POST',
    body: { player, password, code },
    signal: opts.signal,
  })
}

/** POST /api/auth/table — TEK EKRAN girişi: yalnız oyun kodu, karakter yok. */
export function authTable(code, opts = {}) {
  return istek('/api/auth/table', { method: 'POST', body: { code }, signal: opts.signal })
}

/** POST /api/auth/gm — anlatıcı oturumu (PIN). */
export function authGm(pin, opts = {}) {
  return istek('/api/auth/gm', { method: 'POST', body: { pin }, signal: opts.signal })
}

/** POST /api/auth/logout — oturumu kapat. */
export function authLogout(opts = {}) {
  return istek('/api/auth/logout', { method: 'POST', body: {}, signal: opts.signal })
}

/* ==========================================================================
 * Senaryo / oyun dışa-içe aktarma
 * ========================================================================== */

/** GET /api/scenario/export → senaryo JSON */
export function exportScenario(opts = {}) {
  return istek('/api/scenario/export', { signal: opts.signal })
}

/** POST /api/scenario/import → `{ok}` */
export function importScenario(scenario, opts = {}) {
  return istek('/api/scenario/import', { method: 'POST', body: scenario, signal: opts.signal })
}

/** POST /api/scenario/reset-default → `{ok}` */
export function resetScenarioDefault(opts = {}) {
  return istek('/api/scenario/reset-default', { method: 'POST', body: {}, signal: opts.signal })
}

/** GET /api/game/export → `{state, log, gm_log}` */
export function exportGame(opts = {}) {
  return istek('/api/game/export', { signal: opts.signal })
}

/**
 * POST /api/game/import → `{ok}`
 * @param {{state:object, log:any[], gm_log:any[]}} kayit
 */
export function importGame(kayit, opts = {}) {
  return istek('/api/game/import', { method: 'POST', body: kayit, signal: opts.signal })
}

/* ==========================================================================
 * Yardımcılar
 * ========================================================================== */

/**
 * Bilinmeyen bir hatayı ApiError'a çevirir (store'lar catch içinde kullanır).
 * @param {unknown} e
 * @returns {ApiError}
 */
export function toApiError(e) {
  if (e instanceof ApiError) return e
  return new ApiError(e?.message || 'Beklenmeyen bir hata oluştu.', { kind: 'bicim', cause: e })
}

/** Tarayıcıda dosya indirtir (senaryo/oyun dışa aktarma için). */
export function indirJson(veri, dosyaAdi) {
  const blob = new Blob([JSON.stringify(veri, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = dosyaAdi
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export default {
  ApiError,
  getState,
  setupCharacters,
  startGame,
  sendMessage,
  takeover,
  finishChargen,
  saveSettings,
  resetGame,
  pickOption,
  waitRound,
  commitRound,
  getGrid,
  moveOnGrid,
  getGmState,
  gmNote,
  gmLesson,
  gmPatch,
  gmItems,
  gmAddItem,
  gmAccounts,
  gmReleaseAccount,
  authMe,
  authLogin,
  authTable,
  authGm,
  authLogout,
  exportScenario,
  importScenario,
  resetScenarioDefault,
  exportGame,
  importGame,
  toApiError,
  indirJson,
}
