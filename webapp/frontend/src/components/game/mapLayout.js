/**
 * Harita yerleşimi — yer kayıtlarından çizilebilir düğüm/kenar geometrisi.
 *
 * İki yerleşim kipi var:
 *
 *   **coğrafi** (asıl kip) — harita oyunun başında bütünüyle üretiliyor ve her
 *   mekanın gerçek bir koordinatı (`x`, `y`, km) var. O zaman düğümler oldukları
 *   yere çizilir: mesafeler göz kararı doğru okunur, aynı şehrin mekanları
 *   birbirine yakın durur, iki şehir arası boşluk görünür.
 *
 *   **halkalı** (yedek) — koordinatı olmayan eski kayıtlar için radyal BFS:
 *   halka 0 grubun yeri, halka 1 komşuları… Böylece koordinat alanı eklenmeden
 *   önce başlamış oyunlar da çizilmeye devam eder.
 *
 * Her iki kipte de yerleşim KARARLIDIR: aynı veri her zaman aynı resmi verir,
 * yoklama düğümleri oynatmaz. Rastgelelik yok; sapmalar isimden türer.
 *
 * Kenarlar artık YOLdur (`map.roads`): türü, uzunluğu ve durumu olan kayıtlar.
 * İki yer arasında birden fazla yol olabilir — o zaman ikisi de çizilir, biri
 * yaylandırılarak.
 *
 * Çıktı saf veridir (SVG bilmez): `MapCanvas.vue` onu çizer.
 */

/** Halkalar arası mesafe (SVG birimi) — yedek kip. */
const HALKA = 120
/** Coğrafi kipte 1 km kaç SVG birimi. */
const KM_OLCEK = 22
/**
 * Şehir içi büyütme.
 *
 * Gerçek oranlar okunmuyor: 48 km'lik bir bölgede 2 km'lik bir kasaba haritanın
 * %4'ü kadar yer kaplıyor ve o kasabanın on mekanı üst üste biniyor. Bu yüzden
 * şehirlerin BİRBİRİNE göre konumu gerçek ölçekte kalır, şehrin İÇİNDEKİ
 * dağılım büyütülerek çizilir.
 *
 * Bu bir ÇİZİM kararıdır: gösterilen km değerleri ve rota mesafeleri sunucudan
 * geldiği gibi durur, büyütmeden etkilenmez.
 */
const SEHIR_BUYUTME = 4.2
/** Düğüm yarıçapları — bilgi düzeyine göre. */
export const YARICAP = { keşfedildi: 20, görüldü: 15, duyuldu: 9 }
/** Kenar boşluğu (etiketler taşmasın). */
const KENAR = 90

/** Yol türü → çizgi biçimi. */
export const YOL_STILI = {
  anayol: { kalinlik: 3.2, ton: 'ana' },
  cadde: { kalinlik: 2.4, ton: 'ana' },
  'ara sokak': { kalinlik: 1.4, ton: 'ara' },
  'kır yolu': { kalinlik: 1.8, ton: 'ara' },
  patika: { kalinlik: 1.1, ton: 'patika' },
  köprü: { kalinlik: 3.0, ton: 'ana' },
  tünel: { kalinlik: 2.6, ton: 'ara' },
  demiryolu: { kalinlik: 1.6, ton: 'patika' },
}

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
 * mevcut alanlardan türetilir — sunucudaki `knowledge_of` ile aynı mantık.
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

/** Koordinatı olan kayıt mı (coğrafi kip kullanılabilir mi). */
function koordinatli(yer) {
  return typeof yer?.x === 'number' && typeof yer?.y === 'number'
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

/** Coğrafi kip: gerçek koordinatları SVG düzlemine ölçekler. */
function cografiKonumlar(yerler, adlar) {
  const konum = new Map()
  for (const ad of adlar) {
    const yer = yerler[ad]
    if (!koordinatli(yer)) continue
    // SVG'de y aşağı doğru büyür; kuzey yukarıda kalsın diye ters çevrilir.
    konum.set(ad, { x: yer.x * KM_OLCEK, y: -yer.y * KM_OLCEK })
  }
  if (!konum.size) return konum

  // Şehir içi büyütme: şehrin ağırlık merkezi yerinde kalır, üyeler merkezden
  // uzaklaştırılır. Şehirler arası mesafe gerçek ölçekte kalmaya devam eder.
  const sehirler = new Map()
  for (const ad of adlar) {
    if (!konum.has(ad) || !koordinatli(yerler[ad])) continue
    const sehir = yerler[ad]?.city || ''
    if (!sehir) continue
    if (!sehirler.has(sehir)) sehirler.set(sehir, [])
    sehirler.get(sehir).push(ad)
  }
  for (const uyeler of sehirler.values()) {
    if (uyeler.length < 2) continue
    const merkez = uyeler.reduce(
      (a, ad) => ({
        x: a.x + konum.get(ad).x / uyeler.length,
        y: a.y + konum.get(ad).y / uyeler.length,
      }),
      { x: 0, y: 0 },
    )
    for (const ad of uyeler) {
      const p = konum.get(ad)
      konum.set(ad, {
        x: merkez.x + (p.x - merkez.x) * SEHIR_BUYUTME,
        y: merkez.y + (p.y - merkez.y) * SEHIR_BUYUTME,
      })
    }
  }
  // Koordinatsız kalan kayıtlar (anlatıcının elle eklediği yerler) merkezin
  // etrafına, isimlerinden türeyen sabit bir noktaya konur — zıplamasınlar.
  const merkez = [...konum.values()].reduce(
    (a, p) => ({ x: a.x + p.x / konum.size, y: a.y + p.y / konum.size }),
    { x: 0, y: 0 },
  )
  const yaricap = KM_OLCEK * 6
  for (const ad of adlar) {
    if (konum.has(ad)) continue
    const aci = ((hash(ad) % 360) * Math.PI) / 180
    konum.set(ad, {
      x: merkez.x + Math.cos(aci) * yaricap,
      y: merkez.y + Math.sin(aci) * yaricap,
    })
  }
  return konum
}

/** Yedek kip: radyal BFS (koordinat yoksa). */
function halkaliKonumlar(yerler, adlar, simdiki, komsu) {
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
  const enDerin = Math.max(0, ...derinlik.values())
  const kopukHalka = enDerin + 1
  for (const ad of adlar) if (!derinlik.has(ad)) derinlik.set(ad, kopukHalka)

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
      for (const fazla of uyeler.slice(1)) konum.set(fazla, { x: HALKA, y: 0 })
      continue
    }
    const yaricap = HALKA * d * (1 + Math.max(0, uyeler.length - 6) * 0.08)
    uyeler.forEach((ad, i) => {
      // Sabit sapma: mükemmel simetri yapay duruyor ama rastgelelik yok.
      const sapma = ((hash(ad) % 100) / 100 - 0.5) * (Math.PI / uyeler.length) * 0.5
      const aci = (i / uyeler.length) * Math.PI * 2 - Math.PI / 2 + sapma
      konum.set(ad, { x: Math.cos(aci) * yaricap, y: Math.sin(aci) * yaricap })
    })
  }
  return { konum, derinlik, kopukHalka }
}

/**
 * Haritayı çizilebilir geometriye çevirir.
 *
 * @param {{current?:string, places?:object, party?:object, roads?:Array, cities?:object}} harita
 * @returns {{dugumler:Array, kenarlar:Array, sehirler:Array, viewBox:string, bos:boolean, cografi:boolean}}
 */
export function haritaYerlesimi(harita) {
  const yerler = harita?.places && typeof harita.places === 'object' ? harita.places : {}
  const adlar = Object.keys(yerler).sort(sirala)
  if (!adlar.length) {
    return {
      dugumler: [],
      kenarlar: [],
      sehirler: [],
      viewBox: '-100 -100 200 200',
      bos: true,
      cografi: false,
    }
  }

  const simdiki = harita?.current && yerler[harita.current] ? harita.current : adlar[0]
  const komsu = komsuluk(yerler)
  const cografi = adlar.some((ad) => koordinatli(yerler[ad]))

  let konum
  let derinlik = new Map()
  let kopukHalka = -1
  if (cografi) {
    konum = cografiKonumlar(yerler, adlar)
  } else {
    const sonuc = halkaliKonumlar(yerler, adlar, simdiki, komsu)
    konum = sonuc.konum
    derinlik = sonuc.derinlik
    kopukHalka = sonuc.kopukHalka
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
      sehir: bilgi.city || '',
      kopuk: !cografi && derinlik.get(ad) === kopukHalka && kopukHalka > 0,
      kimler: Object.entries(parti)
        .filter(([, yer]) => yer === ad)
        .map(([kisi]) => kisi)
        .sort(sirala),
      ...konum.get(ad),
    }
  })

  /* --- kenarlar: önce yollar, sonra eski `links` --- */
  const kenarlar = []
  const gorulen = new Set()
  const ciftSayaci = new Map()

  for (const yol of Array.isArray(harita?.roads) ? harita.roads : []) {
    const a = konum.get(yol?.a)
    const b = konum.get(yol?.b)
    if (!a || !b) continue
    const cift = [yol.a, yol.b].sort(sirala).join('→')
    // Aynı çiftin ikinci/üçüncü yolu yay yapılır ki üst üste binmesin.
    const sira = ciftSayaci.get(cift) || 0
    ciftSayaci.set(cift, sira + 1)
    gorulen.add(cift)
    const stil = YOL_STILI[yol.kind] || { kalinlik: 1.6, ton: 'ara' }
    kenarlar.push({
      anahtar: `${cift}#${yol.kind}#${sira}`,
      x1: a.x,
      y1: a.y,
      x2: b.x,
      y2: b.y,
      // Yay yüksekliği: 0, sonra +18, -18, +36 … kararlı ve simetrik.
      egri: sira === 0 ? 0 : (sira % 2 ? 1 : -1) * 18 * Math.ceil(sira / 2),
      tur: yol.kind || '',
      km: typeof yol.km === 'number' ? yol.km : null,
      durum: yol.status || 'açık',
      kapali: yol.status === 'çökük',
      risk: yol.risk ?? null,
      kalinlik: stil.kalinlik,
      ton: stil.ton,
      zayif:
        bilgiDuzeyi(yerler[yol.a]) === 'duyuldu' || bilgiDuzeyi(yerler[yol.b]) === 'duyuldu',
    })
  }

  for (const [ad, hedefler] of komsu) {
    for (const hedef of hedefler) {
      const anahtar = [ad, hedef].sort(sirala).join('→')
      if (gorulen.has(anahtar)) continue
      gorulen.add(anahtar)
      const a = konum.get(ad)
      const b = konum.get(hedef)
      if (!a || !b) continue
      kenarlar.push({
        anahtar,
        x1: a.x,
        y1: a.y,
        x2: b.x,
        y2: b.y,
        egri: 0,
        tur: '',
        km: null,
        durum: 'açık',
        kapali: false,
        risk: null,
        kalinlik: 1.6,
        ton: 'ara',
        zayif:
          bilgiDuzeyi(yerler[ad]) === 'duyuldu' || bilgiDuzeyi(yerler[hedef]) === 'duyuldu',
      })
    }
  }

  /* --- şehir etiketleri: üyelerin ağırlık merkezi --- */
  const sehirGruplari = new Map()
  for (const dugum of dugumler) {
    if (!dugum.sehir) continue
    if (!sehirGruplari.has(dugum.sehir)) sehirGruplari.set(dugum.sehir, [])
    sehirGruplari.get(dugum.sehir).push(dugum)
  }
  const sehirler = [...sehirGruplari.entries()]
    .filter(([, uyeler]) => uyeler.length >= 2)
    .map(([ad, uyeler]) => ({
      ad,
      x: uyeler.reduce((t, d) => t + d.x, 0) / uyeler.length,
      // Etiket en üstteki üyenin biraz üstünde dursun.
      y: Math.min(...uyeler.map((d) => d.y)) - 26,
      sayi: uyeler.length,
    }))
    .sort((a, b) => sirala(a.ad, b.ad))

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
    sehirler,
    viewBox: `${minX} ${minY} ${genislik} ${yukseklik}`,
    bos: false,
    cografi,
  }
}

export default haritaYerlesimi
