import { ref, onUnmounted, getCurrentInstance } from 'vue'

/**
 * Sürüm bazlı yoklama zamanlayıcısı — eski arayüzün mantığı korunur:
 *
 *  1. Aynı anda tek istek: yavaş bir yoklama sürerken ikincisi başlamaz.
 *  2. Sunucu düşerse yoklama DURMAZ, yavaşlar (üstel geri çekilme, tavanlı).
 *     İlk başarılı yanıtta yine normal aralığa döner.
 *  3. Sekme arkaplandayken yoklama beklemeye alınır; öne gelince hemen bir
 *     tur atılır (odak/görünürlük olayları).
 *
 * Not: `since` mantığı çağıranın işidir (bkz. stores/game.js) — bu composable
 * yalnızca "ne zaman" sorusunu çözer, "ne" sorusunu değil.
 *
 * @param {() => Promise<any>} gorev her turda çalışacak asenkron iş
 * @param {object} [secenekler]
 * @param {number} [secenekler.interval=4000] normal aralık (ms)
 * @param {number} [secenekler.maxInterval=30000] hata sonrası tavan aralık (ms)
 * @param {number} [secenekler.backoff=1.8] hata başına aralık çarpanı
 * @param {boolean} [secenekler.immediate=true] başlarken hemen bir tur at
 * @param {boolean} [secenekler.pauseWhenHidden=true] sekme gizliyken duraklat
 */
export function usePolling(gorev, secenekler = {}) {
  const {
    interval = 4000,
    maxInterval = 30000,
    backoff = 1.8,
    immediate = true,
    pauseWhenHidden = true,
  } = secenekler

  const aktif = ref(false)
  const calisiyor = ref(false)
  const hataSayaci = ref(0)
  const suAnkiAralik = ref(interval)

  let zamanlayici = null
  let iptalKontrolu = null

  function temizleZamanlayici() {
    if (zamanlayici !== null) {
      clearTimeout(zamanlayici)
      zamanlayici = null
    }
  }

  function siradakiAralik() {
    if (hataSayaci.value === 0) return interval
    const a = Math.min(interval * backoff ** hataSayaci.value, maxInterval)
    // %20'ye kadar dağıtım: birden çok sekme aynı anda vurmasın.
    return Math.round(a * (0.9 + Math.random() * 0.2))
  }

  function planla(gecikme = siradakiAralik()) {
    temizleZamanlayici()
    if (!aktif.value) return
    suAnkiAralik.value = gecikme
    zamanlayici = setTimeout(tur, gecikme)
  }

  /** Bir yoklama turu. Üst üste binmez. */
  async function tur() {
    if (!aktif.value) return
    if (calisiyor.value) return // 1) istekler üst üste binmesin
    if (pauseWhenHidden && typeof document !== 'undefined' && document.hidden) {
      planla(interval) // sekme gizli — sadece bekle
      return
    }

    calisiyor.value = true
    iptalKontrolu = new AbortController()
    try {
      await gorev({ signal: iptalKontrolu.signal })
      hataSayaci.value = 0
    } catch (e) {
      // 2) sunucu düştüyse durmuyoruz, yavaşlıyoruz
      if (!e?.isAborted) hataSayaci.value += 1
    } finally {
      calisiyor.value = false
      iptalKontrolu = null
      planla()
    }
  }

  /** Hemen bir tur at (zamanlayıcıyı da sıfırlar). */
  function hemenCalistir() {
    if (!aktif.value) return
    temizleZamanlayici()
    tur()
  }

  function gorunurlukDegisti() {
    if (!aktif.value) return
    if (!document.hidden) hemenCalistir()
  }

  function baslat() {
    if (aktif.value) return
    aktif.value = true
    hataSayaci.value = 0
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', gorunurlukDegisti)
      window.addEventListener('focus', gorunurlukDegisti)
      window.addEventListener('online', gorunurlukDegisti)
    }
    if (immediate) tur()
    else planla(interval)
  }

  function durdur({ iptalEt = false } = {}) {
    aktif.value = false
    temizleZamanlayici()
    if (iptalEt && iptalKontrolu) iptalKontrolu.abort()
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', gorunurlukDegisti)
      window.removeEventListener('focus', gorunurlukDegisti)
      window.removeEventListener('online', gorunurlukDegisti)
    }
  }

  if (getCurrentInstance()) onUnmounted(() => durdur({ iptalEt: true }))

  return {
    /** Yoklama açık mı */
    aktif,
    /** Şu anda bir istek uçuşta mı */
    calisiyor,
    /** Arka arkaya kaç hata alındı (0 = sağlıklı) */
    hataSayaci,
    /** Bir sonraki tur için kullanılan gecikme (ms) */
    suAnkiAralik,
    baslat,
    durdur,
    hemenCalistir,
  }
}

export default usePolling
