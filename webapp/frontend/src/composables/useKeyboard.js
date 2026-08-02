import { onMounted, onUnmounted, getCurrentInstance } from 'vue'

/**
 * Klavye kısayolu kaydı.
 *
 * Kombinasyon yazımı: `'mod+b'`, `'ctrl+shift+k'`, `'escape'`, `'enter'`.
 * `mod` = Windows/Linux'ta Ctrl, macOS'ta Cmd.
 *
 * Varsayılan olarak metin alanlarında (input/textarea/contenteditable) tetiklenmez;
 * `allowInInput: true` ile bu koruma kaldırılır (örn. composer'ın Enter'ı).
 *
 * @param {Record<string, (e: KeyboardEvent) => void>} baglantilar
 * @param {object} [secenekler]
 * @param {boolean} [secenekler.allowInInput=false]
 * @param {EventTarget} [secenekler.target=window]
 * @param {boolean} [secenekler.preventDefault=true]
 */
export function useKeyboard(baglantilar, secenekler = {}) {
  const { allowInInput = false, target = null, preventDefault = true } = secenekler

  const normalize = (combo) =>
    String(combo)
      .toLowerCase()
      .split('+')
      .map((p) => p.trim())
      .filter(Boolean)
      .sort()
      .join('+')

  // Kombinasyonları önceden normalleştir: 'ctrl+shift+k' ile 'shift+ctrl+k' aynı.
  const tablo = new Map(Object.entries(baglantilar).map(([k, v]) => [normalize(k), v]))

  function metinAlanindaMi(el) {
    if (!el) return false
    const tag = el.tagName
    return (
      tag === 'INPUT' ||
      tag === 'TEXTAREA' ||
      tag === 'SELECT' ||
      el.isContentEditable === true
    )
  }

  const macMi = () =>
    /Mac|iPhone|iPad/i.test(navigator.userAgentData?.platform || navigator.platform || navigator.userAgent || '')

  /**
   * Bir olay için eşleşebilecek tüm yazımlar. Hem `mod+b` hem `ctrl+b`
   * (macOS'ta `meta+b`) kabul edilir; ikisi de aynı kısayola bağlanabilir.
   */
  function adaylar(e) {
    const mac = macMi()
    const tus = String(e.key).toLowerCase()
    const ortak = []
    if (e.altKey) ortak.push('alt')
    if (e.shiftKey) ortak.push('shift')

    const sonuc = new Set()

    // 1) 'mod' yazımı: Windows/Linux'ta Ctrl, macOS'ta Cmd
    const modParcalari = [...ortak]
    if (mac ? e.metaKey : e.ctrlKey) modParcalari.push('mod')
    if (mac && e.ctrlKey) modParcalari.push('ctrl') // macOS'ta ayrıca gerçek Ctrl
    if (!mac && e.metaKey) modParcalari.push('meta')
    sonuc.add([...modParcalari, tus].sort().join('+'))

    // 2) Ham yazım: ctrl / meta doğrudan
    const hamParcalar = [...ortak]
    if (e.ctrlKey) hamParcalar.push('ctrl')
    if (e.metaKey) hamParcalar.push('meta')
    sonuc.add([...hamParcalar, tus].sort().join('+'))

    return sonuc
  }

  function isle(e) {
    if (!allowInInput && metinAlanindaMi(e.target)) return

    for (const aday of adaylar(e)) {
      const f = tablo.get(aday)
      if (f) {
        if (preventDefault) e.preventDefault()
        f(e)
        return
      }
    }
  }

  const hedef = () => target || window

  const bagla = () => hedef().addEventListener('keydown', isle)
  const coz = () => hedef().removeEventListener('keydown', isle)

  if (getCurrentInstance()) {
    onMounted(bagla)
    onUnmounted(coz)
  } else {
    bagla()
  }

  return { bagla, coz }
}

/**
 * Composer için Enter/Shift+Enter kuralı (docs §7).
 * @param {() => void} gonder
 * @returns {(e: KeyboardEvent) => void} textarea'ya `@keydown` olarak bağla
 */
export function enterGonderir(gonder) {
  return (e) => {
    if (e.key !== 'Enter') return
    if (e.shiftKey || e.isComposing) return // satır atla / IME
    e.preventDefault()
    gonder()
  }
}

export default useKeyboard
