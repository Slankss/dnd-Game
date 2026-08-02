/**
 * Material Symbols fontunu SADECE kullanılan ikonlara indirir.
 *
 * Tam değişken font 5,2 MB. Depoya da girdiği için hem her klon hem her sayfa
 * yüklemesi bu bedeli ödüyordu. Bu betik kaynakta geçen ikon adlarını toplar
 * ve fontu o adlara indirilmiş haliyle `public/fonts/` altına yazar.
 *
 * Alt kümeyi Google'ın `icon_names` uç noktası üretir. Kendi başımıza
 * (harfbuzz/subset-font) denemesi işe yaramıyor: ikon adları LİGATÜR olduğu
 * için alfabenin tamamını tutmak zorundayız, düzen kapanışı da o harflerden
 * erişilebilen ~3900 ikonun hepsini "gerekli" sayıp fontu 5,2 MB'ta bırakıyor.
 *
 * Ağ yoksa tam font olduğu gibi kopyalanır — build kırılmaz, sadece büyük olur.
 *
 * ÖNEMLİ: yeni ikon kullanmaya başlayınca tekrar çalışması gerekir; `npm run
 * build` bunu zaten kendisi çağırıyor.
 */

import { readFile, writeFile, mkdir, readdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import * as fontkit from 'fontkit'

const kok = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const TAM_FONT = path.join(kok, 'node_modules/material-symbols/material-symbols-rounded.woff2')
const IKON_LISTESI = path.join(kok, 'node_modules/material-symbols/index.d.ts')
const HEDEF_KLASOR = path.join(kok, 'public/fonts')
const HEDEF = path.join(HEDEF_KLASOR, 'material-symbols-rounded-subset.woff2')

// Değişken eksenler ALFABETİK sırada olmalı, yoksa Google 400 döner.
const CSS_URL = (adlar) =>
  'https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:' +
  'FILL,GRAD,opsz,wght@0..1,-50..200,20..48,100..700' +
  `&icon_names=${adlar.join(',')}&display=block`

const TARAYICI_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'

const kb = (n) => (n / 1024).toFixed(1) + ' kB'

/** Kaynakta tırnak içinde geçen, paketin ikon listesinde de bulunan adlar. */
async function kullanilanIkonlar() {
  const dosyalar = []
  const gez = async (d) => {
    for (const e of await readdir(d, { withFileTypes: true })) {
      const p = path.join(d, e.name)
      if (e.isDirectory()) await gez(p)
      else if (p.endsWith('.vue') || p.endsWith('.js')) dosyalar.push(p)
    }
  }
  await gez(path.join(kok, 'src'))

  const dts = await readFile(IKON_LISTESI, 'utf8')
  const gecerli = new Set([...dts.matchAll(/['"]([a-z0-9_]+)['"]/g)].map((m) => m[1]))

  const bulunan = new Set()
  for (const f of dosyalar) {
    const metin = await readFile(f, 'utf8')
    for (const m of metin.matchAll(/['"]([a-z][a-z0-9_]{2,30})['"]/g)) {
      if (gecerli.has(m[1])) bulunan.add(m[1])
    }
  }
  return [...bulunan].sort()
}

/** İndirilen alt küme gerçekten çalışıyor mu? Ligatür + eksen kontrolü. */
function dogrula(veri, ikonlar) {
  const font = fontkit.create(Buffer.from(veri))
  const eksenler = Object.keys(font.variationAxes || {})
  for (const gerekli of ['FILL', 'wght']) {
    if (!eksenler.includes(gerekli)) throw new Error(`'${gerekli}' ekseni kayıp`)
  }
  const bozuk = ikonlar.filter((ad) => {
    try {
      // Ligatür çalışıyorsa ad tek glife iner; çalışmıyorsa harf harf kalır.
      return font.layout(ad).glyphs.length !== 1
    } catch {
      return true
    }
  })
  if (bozuk.length) {
    throw new Error(`${bozuk.length} ikon ligatürü çözülmüyor: ${bozuk.slice(0, 8).join(', ')}`)
  }
  return eksenler
}

const ikonlar = await kullanilanIkonlar()
if (!ikonlar.length) {
  console.error('HATA: kaynakta hiç ikon adı bulunamadı.')
  process.exit(1)
}

await mkdir(HEDEF_KLASOR, { recursive: true })
const tamFont = await readFile(TAM_FONT)

try {
  const css = await fetch(CSS_URL(ikonlar), { headers: { 'User-Agent': TARAYICI_UA } })
  if (!css.ok) throw new Error(`css2 ${css.status}`)
  const metin = await css.text()
  const url = metin.match(/src:\s*url\(([^)]+)\)/)?.[1]
  if (!url) throw new Error('css2 yanıtında font adresi yok')

  const yanit = await fetch(url, { headers: { 'User-Agent': TARAYICI_UA } })
  if (!yanit.ok) throw new Error(`font indirilemedi (${yanit.status})`)
  const veri = new Uint8Array(await yanit.arrayBuffer())

  const eksenler = dogrula(veri, ikonlar)
  await writeFile(HEDEF, veri)
  console.log(
    `ikon fontu: ${ikonlar.length} ikon · ${kb(tamFont.length)} → ${kb(veri.length)} ` +
    `· eksenler: ${eksenler.join(', ')}`,
  )
} catch (e) {
  await writeFile(HEDEF, tamFont)
  console.warn(
    `UYARI: ikon alt kümesi alınamadı (${e.message}); tam font kullanılıyor (${kb(tamFont.length)}).`,
  )
}
