/**
 * Anlatıcı metnini okunabilir bloklara ayırır.
 *
 * Model markdown'a yakın bir şey yazıyor: `**kalın**`, `*eğik*`, başlıklar ve
 * en sonda **DURUM** / **SEÇENEKLER** blokları. Sahne metni ekranın asıl
 * okuma alanı (docs §2: 16px/1.7, 65-75 karakter ölçü), o yüzden bu iki blok
 * gövde metninden görsel olarak ayrılır.
 *
 * Güvenlik: model çıktısı ASLA `v-html` ile basılmaz. Burada yalnızca veri
 * üretilir; SceneText.vue onu normal Vue düğümleriyle çizer.
 */

/** Kalın/eğik işaretleri. `**` her zaman `*`'dan önce denenir. */
const SATIR_ICI = /\*\*\*(?!\s)([^*]+?)\*\*\*|\*\*(?!\s)([^*]+?)\*\*|\*(?!\s)([^*\n]+?)\*/g

/** `# Başlık` biçimi. */
const DIYEZ_BASLIK = /^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$/

/** `**DURUM**`, `**SEÇENEKLER:**` gibi tek başına duran kalın başlık. */
const KALIN_BASLIK = /^\s*\*{2,3}\s*([^*]+?)\s*\*{2,3}\s*:?\s*$/

/** `DURUM:` gibi büyük harfle yazılıp iki nokta ile biten başlık. */
const BUYUK_BASLIK = /^\s*([A-ZÇĞİÖŞÜ0-9][A-ZÇĞİÖŞÜ0-9\s\-/&'()]{2,44})\s*:\s*$/

/** `- madde`, `• madde`, `1) madde`, `A. madde`, `* madde` */
const LISTE_OGESI = /^\s{0,6}(?:([-–—•])|(\d{1,2})[.)]|([A-Za-zÇĞİÖŞÜçğıöşü])[.)])\s+(.*)$/

/**
 * Bir satırı kalın/eğik parçalara böler.
 * @param {string} satir
 * @returns {Array<{v:string, kalin:boolean, egik:boolean}>}
 */
export function satiriParcala(satir) {
  const metin = String(satir ?? '')
  const parcalar = []
  let son = 0
  SATIR_ICI.lastIndex = 0
  let eslesme
  while ((eslesme = SATIR_ICI.exec(metin)) !== null) {
    if (eslesme.index > son) {
      parcalar.push({ v: metin.slice(son, eslesme.index), kalin: false, egik: false })
    }
    if (eslesme[1] !== undefined) parcalar.push({ v: eslesme[1], kalin: true, egik: true })
    else if (eslesme[2] !== undefined) parcalar.push({ v: eslesme[2], kalin: true, egik: false })
    else parcalar.push({ v: eslesme[3], kalin: false, egik: true })
    son = eslesme.index + eslesme[0].length
  }
  if (son < metin.length) parcalar.push({ v: metin.slice(son), kalin: false, egik: false })
  return parcalar.length ? parcalar : [{ v: '', kalin: false, egik: false }]
}

/** Başlık metninden bölüm türünü çıkarır. */
function bolumTuru(baslik) {
  const b = String(baslik || '').toLocaleUpperCase('tr-TR')
  if (b.includes('DURUM')) return 'durum'
  if (b.includes('SEÇENEK') || b.includes('SECENEK')) return 'secenekler'
  return 'genel'
}

function yeniBolum(baslik) {
  return { baslik: baslik || null, tur: baslik ? bolumTuru(baslik) : 'gövde', dugumler: [] }
}

/** Markdown işaretlerinden arındırılmış düz metin (özet/ipucu için). */
export function duzMetin(metin) {
  return String(metin ?? '')
    .replace(/\*{1,3}/g, '')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * Sahne metnini bölümlere ayırır.
 *
 * @param {string} metin
 * @returns {Array<{baslik:string|null, tur:'gövde'|'durum'|'secenekler'|'genel',
 *   dugumler:Array<{tip:'paragraf'|'liste', satirlar?:Array, ogeler?:Array}>}>}
 */
export function sahneAyristir(metin) {
  const ham = String(metin ?? '').replace(/\r\n?/g, '\n').trim()
  if (!ham) return []

  const bolumler = [yeniBolum(null)]
  let paragraf = null
  let liste = null

  const paragrafiKapat = () => {
    paragraf = null
  }
  const listeyiKapat = () => {
    liste = null
  }
  const sonBolum = () => bolumler[bolumler.length - 1]

  for (const hamSatir of ham.split('\n')) {
    const satir = hamSatir.trimEnd()

    if (!satir.trim()) {
      paragrafiKapat()
      listeyiKapat()
      continue
    }

    const diyez = DIYEZ_BASLIK.exec(satir)
    const kalin = diyez ? null : KALIN_BASLIK.exec(satir)
    const buyuk = diyez || kalin ? null : BUYUK_BASLIK.exec(satir)
    const baslik = (diyez && diyez[1]) || (kalin && kalin[1]) || (buyuk && buyuk[1])

    if (baslik) {
      paragrafiKapat()
      listeyiKapat()
      // Baştaki boş gövde bölümünü boşuna taşıma.
      if (bolumler.length === 1 && !sonBolum().dugumler.length && !sonBolum().baslik) {
        bolumler.pop()
      }
      bolumler.push(yeniBolum(baslik.trim()))
      continue
    }

    const oge = LISTE_OGESI.exec(satir)
    if (oge) {
      paragrafiKapat()
      if (!liste) {
        liste = { tip: 'liste', sirali: !oge[1], ogeler: [] }
        sonBolum().dugumler.push(liste)
      }
      liste.ogeler.push({
        etiket: oge[2] || oge[3] || '',
        parcalar: satiriParcala(oge[4]),
      })
      continue
    }

    listeyiKapat()
    if (!paragraf) {
      paragraf = { tip: 'paragraf', satirlar: [] }
      sonBolum().dugumler.push(paragraf)
    }
    paragraf.satirlar.push(satiriParcala(satir.trim()))
  }

  return bolumler.filter((b) => b.baslik || b.dugumler.length)
}

export default sahneAyristir
