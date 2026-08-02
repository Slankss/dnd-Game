import { ref, onUnmounted } from 'vue'

/**
 * Arka plan müziği — SADECE kullanıcının kendi koyduğu dosya.
 *
 * `static/audio/ambient.mp3` (ya da `.ogg`) varsa çalınır. Dosya yoksa düğme
 * pasif kalır ve nedeni yazılır: eski arayüzdeki tarayıcıda üretilen sentetik
 * drone kaldırıldı — telifsiz olsa da uzun oturumda yorucuydu ve ses motoru
 * arayüz koduna bağımlılık ekliyordu.
 *
 * Ses seviyesi localStorage'da hatırlanır.
 */

const DEPO_ANAHTARI = 'kizil-cokus:ses-seviyesi'
const ADAYLAR = ['/static/audio/ambient.mp3', '/static/audio/ambient.ogg']

function depodanOku() {
  try {
    const v = parseFloat(localStorage.getItem(DEPO_ANAHTARI))
    return Number.isFinite(v) ? Math.min(1, Math.max(0, v)) : 0.5
  } catch {
    return 0.5
  }
}

export function useAmbientAudio() {
  /** 'araniyor' | 'hazir' | 'yok' | 'hata' */
  const durum = ref('araniyor')
  const neden = ref('')
  const caliyor = ref(false)
  const seviye = ref(depodanOku())

  let ses = null

  /** Dosya gerçekten var mı? HEAD ile bakılır, indirilmez. */
  async function bul() {
    durum.value = 'araniyor'
    for (const yol of ADAYLAR) {
      try {
        const yanit = await fetch(yol, { method: 'HEAD' })
        if (yanit.ok) {
          ses = new Audio(yol)
          ses.loop = true
          ses.volume = seviye.value
          ses.addEventListener('ended', () => (caliyor.value = false))
          durum.value = 'hazir'
          return
        }
      } catch {
        /* bir sonraki uzantıyı dene */
      }
    }
    durum.value = 'yok'
    neden.value =
      'static/audio/ambient.mp3 bulunamadı. Kendi müziğini o adla koyarsan bu düğme çalışır.'
  }

  bul()

  async function degistir() {
    if (durum.value !== 'hazir' || !ses) return
    if (caliyor.value) {
      ses.pause()
      caliyor.value = false
      return
    }
    try {
      await ses.play()
      caliyor.value = true
    } catch (e) {
      // Tarayıcı otomatik oynatmayı engellemiş olabilir (kullanıcı etkileşimi şart).
      durum.value = 'hata'
      neden.value = 'Tarayıcı sesi başlatamadı. Sayfaya bir kez tıklayıp tekrar dene.'
      caliyor.value = false
    }
  }

  function seviyeAyarla(yeni) {
    const v = Math.min(1, Math.max(0, Number(yeni) || 0))
    seviye.value = v
    if (ses) ses.volume = v
    try {
      localStorage.setItem(DEPO_ANAHTARI, String(v))
    } catch {
      /* gizli sekme — sessizce geç */
    }
  }

  onUnmounted(() => {
    if (ses) {
      ses.pause()
      ses = null
    }
  })

  return { durum, neden, caliyor, seviye, degistir, seviyeAyarla, yenidenAra: bul }
}

export default useAmbientAudio
