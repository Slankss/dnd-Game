/**
 * Karakter renkleri — isim → SABİT renk.
 *
 * Eski arayüz rengi kadro dizisindeki sıraya göre veriyordu; biri ölünce ya da
 * yeni karakter eklenince herkesin rengi kayıyordu. Burada renk yalnızca ismin
 * kendisinden türetilir: aynı isim, her oturumda, her ekranda aynı renk.
 */

/** Zemin üzerinde AA kontrastı tutan sabit palet (tokens.css --color-char-*). */
export const KARAKTER_PALETI = [
  '#4a7c59',
  '#4a6c9c',
  '#9c6c4a',
  '#8a4a9c',
  '#c9a227',
  '#4a9c8f',
  '#c05a4a',
  '#5a5ac0',
]

/** Grup / ortak girdiler için nötr renk. */
export const GRUP_RENGI = '#7a8590'

/** Anlatıcı ve sistem girdileri (tokens.css ile aynı). */
export const ANLATICI_RENGI = '#d4703a'
export const SISTEM_RENGI = '#8b959f'

/**
 * Türkçe'ye duyarlı normalleştirme: "İSMAİL" ile "ismail" aynı rengi alsın.
 * @param {string} ad
 */
function normalize(ad) {
  return String(ad ?? '')
    .replace(/İ/g, 'i')
    .replace(/I/g, 'ı')
    .toLowerCase()
    .trim()
}

/**
 * FNV-1a — kısa, kararlı, çakışması palet boyutunda önemsiz bir hash.
 * @param {string} s
 * @returns {number} 32-bit işaretsiz
 */
function hash(s) {
  let h = 0x811c9dc5
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return h >>> 0
}

/**
 * İsme karşılık gelen sabit renk.
 * @param {string} ad karakter/NPC adı
 * @returns {string} hex renk
 */
export function colorFor(ad) {
  const n = normalize(ad)
  if (!n) return GRUP_RENGI
  return KARAKTER_PALETI[hash(n) % KARAKTER_PALETI.length]
}

/**
 * Log girdisi → renk. Grup girdileri ve anlatıcı/sistem ayrı ele alınır.
 * @param {{player?:string, role?:string, is_group?:boolean}} entry
 */
export function colorForEntry(entry) {
  if (!entry) return SISTEM_RENGI
  if (entry.is_group) return GRUP_RENGI
  if (entry.role === 'gm' || entry.role === 'narrator') return ANLATICI_RENGI
  if (entry.role === 'system') return SISTEM_RENGI
  return colorFor(entry.player)
}

/**
 * Bileşenlerde doğrudan `:style` olarak kullanılabilen CSS değişken seti.
 * Kullanım: `<div :style="colorVars(ad)" class="border-l-2 border-[var(--kr)]">`
 * @param {string} ad
 * @param {{soft?: number, dim?: number}} [opts] yüzde karışım oranları
 */
export function colorVars(ad, { soft = 16, dim = 55 } = {}) {
  const c = colorFor(ad)
  return {
    '--kr': c,
    '--kr-soft': `color-mix(in oklab, ${c} ${soft}%, transparent)`,
    '--kr-dim': `color-mix(in oklab, ${c} ${dim}%, var(--color-text))`,
  }
}

/**
 * İsimden baş harf(ler)i — avatar/çip için.
 * @param {string} ad
 */
export function bashHarf(ad) {
  const parcalar = String(ad ?? '').trim().split(/\s+/).filter(Boolean)
  if (!parcalar.length) return '?'
  if (parcalar.length === 1) return parcalar[0].slice(0, 1).toLocaleUpperCase('tr-TR')
  return (parcalar[0][0] + parcalar[parcalar.length - 1][0]).toLocaleUpperCase('tr-TR')
}
