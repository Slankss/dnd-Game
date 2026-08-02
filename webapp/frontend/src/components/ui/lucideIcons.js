/**
 * Material Symbols'ta karşılığı olmayan ikonlar için Lucide kaydı.
 *
 * Kullanım: `<Icon name="lucide:swords" />`
 * Yeni ikon eklerken buraya ADI AÇIKÇA import et — böylece tree-shaking
 * korunur, paket tümüyle bundle'a girmez. Emoji ASLA kullanılmaz.
 */
import { Swords, Dices, Skull } from 'lucide-vue-next'

export const LUCIDE_KAYIT = {
  swords: Swords,
  dices: Dices,
  skull: Skull,
}

/**
 * @param {string} ad 'lucide:' önekli veya öneksiz ad
 * @returns {object|null} Vue bileşeni ya da null
 */
export function lucideBul(ad) {
  const anahtar = String(ad || '').replace(/^lucide:/, '').trim()
  return LUCIDE_KAYIT[anahtar] || null
}
