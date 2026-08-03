/**
 * Harita yerleşimi — yer kayıtlarından çizilebilir düğüm/kenar geometrisi.
 *
 * Kural: yerleşim **kararlıdır**. Aynı veri her zaman aynı resmi verir; yoklama
 * her 4 saniyede bir yeni gövde getirdiğinde düğümler zıplamaz. Bu yüzden
 * rastgelelik yok: konum yalnızca (a) grubun konumuna olan bağlantı uzaklığı,
 * (b) isim sırası ve (c) isimden türeyen sabit bir sapmadan hesaplanır.
 *
 * Yerleşim halkalıdır (radyal BFS):
 *   halka 0 → grubun bulunduğu yer (merkez)
 *   halka 1 → oraya komşu yerler
 *   halka 2 → onların komşuları …
 *   en dış halka → hiçbir bağlantısı bilinmeyen yerler (duyulmuş adlar)
 *
 * Çıktı saf veridir (SVG bilmez): `MapCanvas.vue` onu çizer.
 */

/** Halkalar arası mesafe (SVG birimi). */
const HALKA = 120
/** Düğüm yarıçapları — bilgi düzeyine göre. */
export const YARICAP = { keşfedildi: 20, görüldü: 15, duyuldu: 9 }
/** Kenar boşluğu (etiketler taşmasın). */
const KENAR = 90

/** FNV-1a — isimden türeyen sabit sapma için. */
function hash(s) {
  let h = 0x811c9dc5
  for (let i = 0; i < String(s).length; i++) {
    h ^= String(s).charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return h >>> 0
}

/** Türkçeye duyarlı, kararlı sıralama anahtarı. */
function sirala(a, b) {
  return String(a).localeCompare(String(b), 'tr')
}

/**
 * Yer kaydından bilgi düzeyi. Sunucu `known` gönderiyor; eski kayıtlar için
 * (alan eklenmeden önce başlamış oyunlar) mevcut alanlardan türetilir —
 * sunucudaki `knowledge_of` ile aynı mantık.
 */
export function bilgiDuzeyi(yer) {
  const k = String(yer?.known || '').toLowerCase()
  if (k === 'keşfedildi' || k === 'görüldü' || k === 'duyuldu') return k
  if (yer?.visited) return 'keşfedildi'
  if (yer?.kind || yer?.status || (yer?.danger && yer.danger !== 'bilinmiyor')) return 'görüldü'
  return 'duyuldu'
}

/** Bir yer hakkında gösterilecek ayrıntı var mı (yoksa kart açılmaz). */
export function ayrintiVar(yer) {
  return bilgiDuzeyi(yer) !== 'duyuldu'
}

/**
 * Komşuluk listesi: `links` tek yönlü yazılmış olsa bile iki yönlü sayılır.
 * @param {Record<string, object>} yerler
 * @returns {Map<string, Set<string>>}
 */
function komsuluk(yerler) {
  const komsu = new Map(Object.keys(yerler).map((ad) => [ad, new Set()]))
  for (const [ad, bilgi] of Object.entries(yerler)) {
    for (const hedef of bilgi?.links || []) {
      if (!komsu.has(hedef)) continue // bilinmeyen yere bağlantı çizilmez
      komsu.get(ad).add(hedef)
      komsu.get(hedef).add(ad)
    }
  }
  return komsu
}

/**
 * Haritayı çizilebilir geometriye çevirir.
 *
 * @param {{current?:string, places?:object, party?:object}} harita
 * @returns {{dugumler:Array, kenarlar:Array, viewBox:string, bos:boolean}}
 */
export function haritaYerlesimi(harita) {
  const yerler = harita?.places && typeof harita.places === 'object' ? harita.places : {}
  const adlar = Object.keys(yerler).sort(sirala)
  if (!adlar.length) {
    return { dugumler: [], kenarlar: [], viewBox: '-100 -100 200 200', bos: true }
  }

  const simdiki = harita?.current && yerler[harita.current] ? harita.current : adlar[0]
  const komsu = komsuluk(yerler)

  /* --- halka (BFS derinliği) --- */
  const derinlik = new Map([[simdiki, 0]])
  const kuyruk = [simdiki]
  while (kuyruk.length) {
    const ad = kuyruk.shift()
    for (const hedef of [...(komsu.get(ad) || [])].sort(sirala)) {
      if (derinlik.has(hedef)) continue
      derinlik.set(hedef, derinlik.get(ad) + 1)
      kuyruk.push(hedef)
    }
  }
  // Bağlantısı bilinmeyen yerler (çoğu "duyuldu") en dış halkaya iner.
  const enDerin = Math.max(0, ...derinlik.values())
  const kopukHalka = enDerin + 1
  for (const ad of adlar) if (!derinlik.has(ad)) derinlik.set(ad, kopukHalka)

  /* --- halka başına açısal dağılım --- */
  const halkalar = new Map()
  for (const ad of adlar) {
    const d = derinlik.get(ad)
    if (!halkalar.has(d)) halkalar.set(d, [])
    halkalar.get(d).push(ad)
  }

  const konum = new Map()
  for (const [d, uyeler] of halkalar) {
    uyeler.sort(sirala)
    if (d === 0) {
      konum.set(uyeler[0], { x: 0, y: 0 })
      // Merkezde birden fazla olamaz; olursa kalanlar bir sonraki halkaya.
      for (const fazla of uyeler.slice(1)) konum.set(fazla, { x: HALKA, y: 0 })
      continue
    }
    // Halka kalabalıksa yarıçapı bir miktar aç: düğümler üst üste binmesin.
    const yaricap = HALKA * d * (1 + Math.max(0, uyeler.length - 6) * 0.08)
    uyeler.forEach((ad, i) => {
      // Sabit sapma: mükemmel simetri yapay duruyor, ama rastgelelik yok —
      // sapma yalnızca ismin hash'inden gelir, yani her zaman aynı.
      const sapma = ((hash(ad) % 100) / 100 - 0.5) * (Math.PI / uyeler.length) * 0.5
      const aci = (i / uyeler.length) * Math.PI * 2 - Math.PI / 2 + sapma
      konum.set(ad, { x: Math.cos(aci) * yaricap, y: Math.sin(aci) * yaricap })
    })
  }

  /* --- düğümler --- */
  const parti = harita?.party && typeof harita.party === 'object' ? harita.party : {}
  const dugumler = adlar.map((ad) => {
    const bilgi = yerler[ad] || {}
    const duzey = bilgiDuzeyi(bilgi)
    return {
      ad,
      bilgi,
      duzey,
      r: YARICAP[duzey],
      burada: ad === harita?.current,
      kopuk: derinlik.get(ad) === kopukHalka && kopukHalka > 0,
      kimler: Object.entries(parti)
        .filter(([, yer]) => yer === ad)
        .map(([kisi]) => kisi)
        .sort(sirala),
      ...konum.get(ad),
    }
  })

  /* --- kenarlar (tekilleştirilmiş, yönsüz) --- */
  const gorulen = new Set()
  const kenarlar = []
  for (const [ad, hedefler] of komsu) {
    for (const hedef of hedefler) {
      const anahtar = [ad, hedef].sort(sirala).join('→')
      if (gorulen.has(anahtar)) continue
      gorulen.add(anahtar)
      const a = konum.get(ad)
      const b = konum.get(hedef)
      if (!a || !b) continue
      // Kenarın "kesinliği" iki ucun en düşük bilgi düzeyine bağlıdır:
      // duyulmuş bir yere giden yol kesik çizgiyle çizilir.
      const zayif =
        bilgiDuzeyi(yerler[ad]) === 'duyuldu' || bilgiDuzeyi(yerler[hedef]) === 'duyuldu'
      kenarlar.push({ anahtar, x1: a.x, y1: a.y, x2: b.x, y2: b.y, zayif })
    }
  }

  /* --- görüş alanı --- */
  const xs = dugumler.map((d) => d.x)
  const ys = dugumler.map((d) => d.y)
  const minX = Math.min(...xs) - KENAR
  const maxX = Math.max(...xs) + KENAR
  const minY = Math.min(...ys) - KENAR
  const maxY = Math.max(...ys) + KENAR
  const genislik = Math.max(240, maxX - minX)
  const yukseklik = Math.max(200, maxY - minY)

  return {
    dugumler,
    kenarlar,
    viewBox: `${minX} ${minY} ${genislik} ${yukseklik}`,
    bos: false,
  }
}

export default haritaYerlesimi
