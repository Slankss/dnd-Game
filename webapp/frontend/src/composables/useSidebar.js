import { ref, computed, readonly, watch } from 'vue'

/**
 * Sidebar durumu — uygulama boyunca TEK örnek (modül kapsamında paylaşılır).
 *
 *  - Açık/kapalı durumu localStorage'da hatırlanır.
 *  - `Ctrl/Cmd + B` kısayolu AppShell içinde bu composable'a bağlanır.
 *  - Kapalıyken 48px ikon şeridi kalır (tooltip'li).
 *  - <1024px: sidebar bir overlay çekmeceye dönüşür; gövde kaymaz.
 */

const DEPO_ANAHTARI = 'kizil-cokus:sidebar-collapsed'
const MOBIL_ESIK = '(max-width: 1023.98px)'

function depodanOku() {
  try {
    return localStorage.getItem(DEPO_ANAHTARI) === '1'
  } catch {
    return false
  }
}

function depoyaYaz(deger) {
  try {
    localStorage.setItem(DEPO_ANAHTARI, deger ? '1' : '0')
  } catch {
    /* gizli sekme vb. — sessizce geç */
  }
}

const kapali = ref(depodanOku())
const cekmeceAcik = ref(false)
const mobil = ref(false)

// matchMedia dinleyicisi bir kez kurulur.
if (typeof window !== 'undefined' && window.matchMedia) {
  const mql = window.matchMedia(MOBIL_ESIK)
  mobil.value = mql.matches
  mql.addEventListener('change', (e) => {
    mobil.value = e.matches
    if (!e.matches) cekmeceAcik.value = false // masaüstüne dönünce çekmece kapansın
  })
}

watch(kapali, depoyaYaz)

// Çekmece açıkken arka plan kaymasın.
watch(cekmeceAcik, (acik) => {
  if (typeof document === 'undefined') return
  document.body.style.overflow = acik ? 'hidden' : ''
})

export function useSidebar() {
  /** Masaüstünde kapalı mı? (mobilde her zaman çekmece mantığı geçerli) */
  const daraltilmis = computed(() => !mobil.value && kapali.value)

  /** Sidebar içeriği o an ekranda mı? */
  const gorunur = computed(() => (mobil.value ? cekmeceAcik.value : true))

  /** Ana gövdenin sol boşluğu için kullanılacak genişlik. */
  const genislik = computed(() => {
    if (mobil.value) return '0px'
    return kapali.value ? 'var(--spacing-rail)' : 'var(--spacing-sidebar)'
  })

  function degistir() {
    if (mobil.value) cekmeceAcik.value = !cekmeceAcik.value
    else kapali.value = !kapali.value
  }

  function ac() {
    if (mobil.value) cekmeceAcik.value = true
    else kapali.value = false
  }

  function kapat() {
    if (mobil.value) cekmeceAcik.value = false
    else kapali.value = true
  }

  return {
    /** true → yalnızca 48px ikon şeridi */
    daraltilmis,
    /** true → ekran <1024px */
    mobil: readonly(mobil),
    /** mobil çekmece açık mı */
    cekmeceAcik,
    gorunur,
    genislik,
    degistir,
    ac,
    kapat,
  }
}

export default useSidebar
