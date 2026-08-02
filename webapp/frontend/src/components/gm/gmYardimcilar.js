/**
 * Anlatıcı ekranı yardımcıları — etiket tabloları, koşul özeti, JSON denetimi.
 *
 * Buradaki hiçbir şey ağa gitmez; yalnızca `world_state` içinden gelen ham
 * veriyi ekrana okunur hale getirir. Renkler tasarım sistemindeki durum
 * anlamlarına bağlıdır: düşük=ok, orta=warn, yüksek/kritik=danger.
 */

/* ------------------------------------------------------------------ metin */

/** Türkçe'ye duyarlı küçültme ("YÜKSEK" ile "yüksek" aynı sayılsın). */
export function normTr(deger) {
  return String(deger ?? '')
    .replace(/İ/g, 'i')
    .replace(/I/g, 'ı')
    .toLocaleLowerCase('tr-TR')
    .trim()
}

/** Her zaman dizi döndürür (sunucu tek string de yazabiliyor). */
export function dizile(deger) {
  if (deger === null || deger === undefined) return []
  return Array.isArray(deger) ? deger : [deger]
}

/** 0-100 arası tam sayı. */
export function yuzde(deger) {
  const n = Number(deger)
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(100, Math.round(n)))
}

const HTML_KACIS = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }

/** HTML kaçışı — `metinBicimle` dışında da kullanılabilir. */
export function kacir(deger) {
  return String(deger ?? '').replace(/[&<>"']/g, (k) => HTML_KACIS[k])
}

/**
 * Anlatıcı metnindeki `**kalın**` / `*eğik*` işaretlerini etikete çevirir.
 * ÖNCE kaçış yapılır: gelen metin her koşulda güvenli HTML'e dönüşür.
 * @param {string} metin
 * @returns {string} v-html ile basılabilir güvenli HTML
 */
export function metinBicimle(metin) {
  return kacir(metin)
    .replace(/\*\*\*(?!\s)([\s\S]+?)\*\*\*/g, '<b><i>$1</i></b>')
    .replace(/\*\*(?!\s)([\s\S]+?)\*\*/g, '<b>$1</b>')
    .replace(/(^|[^*\w])\*(?!\s)([^*\n]+?)\*(?![*\w])/g, '$1<i>$2</i>')
}

/**
 * Sunucu, yayınlanan yanıtın başına "✅ Sahne oyuncu akışına yayınlandı:" satırı
 * ekliyor. Arayüzde bunu rozet zaten söylüyor ve emoji kullanmıyoruz — satırı
 * gösterimden düşürüyoruz (sunucudaki kayıt olduğu gibi kalır).
 */
export function yayinOnEkiniAt(metin) {
  return String(metin ?? '').replace(/^\s*✅[^\n]*\n+/, '')
}

/** "2026-08-02 16:42:26" → "16:42" (tam değer başlık olarak verilir). */
export function saatKisalt(ts) {
  const m = String(ts ?? '').match(/(\d{2}):(\d{2})/)
  return m ? `${m[1]}:${m[2]}` : String(ts ?? '')
}

/* ------------------------------------------------------- durum → renk tonu */

/** Gerilim: düşük=ok, orta=warn, yüksek/kritik=danger. */
export function gerilimTonu(deger) {
  const t = normTr(deger)
  if (t.includes('düşük') || t.includes('sakin')) return 'ok'
  if (t.includes('orta')) return 'warn'
  if (t) return 'danger'
  return 'muted'
}

/** Zorluk ciddiyeti (düşük/orta/yüksek/kritik/kriz). */
export function ciddiyetTonu(deger) {
  const t = normTr(deger)
  if (t.includes('düşük')) return 'ok'
  if (t.includes('orta')) return 'warn'
  if (t.includes('kriz') || t.includes('kritik')) return 'danger'
  if (t) return 'danger'
  return 'muted'
}

/** Zorluk/bulmaca durumu → rozet tonu. */
export function durumTonu(deger) {
  const t = normTr(deger)
  if (!t) return 'muted'
  if (t.includes('kısmen')) return 'warn'
  if (t.includes('çözüldü')) return 'ok'
  if (t.includes('başarısız')) return 'danger'
  return 'neutral'
}

/** Zorluk kapandı mı (liste sıralaması ve soluklaştırma için). */
export function zorlukKapali(durum) {
  const t = normTr(durum)
  return t.includes('çözüldü') || t.includes('başarısız')
}

/* ------------------------------------------------------------------ vitals */

/** Hayatta kalma göstergeleri: 0 = gayet iyi, 100 = dayanılmaz. */
export const VITAL_ETIKET = {
  fatigue: { etiket: 'Yorgunluk', ikon: 'hourglass_top' },
  hunger: { etiket: 'Açlık', ikon: 'restaurant' },
  thirst: { etiket: 'Susuzluk', ikon: 'water_drop' },
  stress: { etiket: 'Stres', ikon: 'psychology' },
}

/** Vital/enfeksiyon değeri → durum tonu (yüksek = kötü). */
export function vitalTonu(deger) {
  const v = yuzde(deger)
  if (v >= 65) return 'danger'
  if (v >= 40) return 'warn'
  return 'ok'
}

/** Yara ciddiyeti metni → ton. */
export function yaraTonu(deger) {
  const t = normTr(deger)
  if (t.includes('ağır') || t.includes('kritik')) return 'danger'
  if (t.includes('orta')) return 'warn'
  return 'muted'
}

/* -------------------------------------------------------- sahne katılımı */

/**
 * `presence.state` → ekran etiketi. Sunucu tanımadığı değeri `sahnede`'ye
 * düşürüyor; yine de bilinmeyen bir değer gelirse olduğu gibi gösteriyoruz.
 */
export const KATILIM_ETIKET = {
  sahnede: { etiket: 'sahnede', ikon: 'person', ton: 'ok' },
  uyuyor: { etiket: 'uyuyor', ikon: 'bedtime', ton: 'muted' },
  uzakta: { etiket: 'sahne dışında', ikon: 'directions_walk', ton: 'warn' },
  baygın: { etiket: 'baygın', ikon: 'blur_on', ton: 'danger' },
  esir: { etiket: 'esir', ikon: 'lock', ton: 'danger' },
}

/**
 * Karakterin sahne katılımını okunur hale getirir.
 * @param {object|string|null} presence
 * @returns {{durum:string, etiket:string, ikon:string, ton:string, not:string,
 *   kosul:string, sahnede:boolean}}
 */
export function katilimOzeti(presence) {
  const ham = typeof presence === 'string' ? { state: presence } : presence || {}
  const durum = normTr(ham.state) || 'sahnede'
  const tablo = KATILIM_ETIKET[durum] || {
    etiket: ham.state || 'sahnede',
    ikon: 'person',
    ton: 'neutral',
  }
  return {
    durum,
    etiket: tablo.etiket,
    ikon: tablo.ikon,
    ton: tablo.ton,
    not: ham.note || '',
    kosul: kosuluAnlat(ham.until),
    sahnede: durum === 'sahnede',
  }
}

/**
 * Dönüş/randevu koşulunu Türkçe tek satıra çevirir (director.matches ile aynı
 * alanlar). Koşulu SUNUCU değerlendirir; burada yalnızca özetliyoruz.
 * @param {object|null} kosul
 * @returns {string} boş string → koşul yok
 */
export function kosuluAnlat(kosul) {
  if (!kosul || typeof kosul !== 'object') return ''
  const p = []
  // gün + saat birlikte verilirse tek randevu anıdır (bkz. senarist-yetenegi.md §2)
  if (kosul.day_gte != null && kosul.clock_gte) {
    p.push(`gün ${kosul.day_gte}, saat ${kosul.clock_gte} sonrası`)
  } else {
    if (kosul.day_gte != null) p.push(`gün ≥ ${kosul.day_gte}`)
    if (kosul.clock_gte) p.push(`saat ≥ ${kosul.clock_gte}`)
  }
  if (kosul.day_lte != null) p.push(`gün ≤ ${kosul.day_lte}`)
  if (kosul.clock_lte) p.push(`saat ≤ ${kosul.clock_lte}`)
  if (kosul.location_in) p.push(`konum: ${dizile(kosul.location_in).join(' / ')}`)
  if (kosul.tension_gte) p.push(`gerilim ≥ ${kosul.tension_gte}`)
  if (kosul.flags_set) p.push(`bayrak açık: ${dizile(kosul.flags_set).join(', ')}`)
  if (kosul.flags_unset) p.push(`bayrak kapalı: ${dizile(kosul.flags_unset).join(', ')}`)
  if (kosul.world_roll_gte != null) p.push(`dünya zarı ≥ ${kosul.world_roll_gte}`)
  if (kosul.world_roll_lte != null) p.push(`dünya zarı ≤ ${kosul.world_roll_lte}`)
  return p.join(' ve ')
}

/* -------------------------------------------------------------- dünya zarı */

/**
 * Dünya zarı bantları — server.py `WORLD_DICE_BANDS` ile birebir. Anlatıcı
 * bir sayı görünce bandın nereye düştüğünü tahmin etmek zorunda kalmasın.
 */
export const DUNYA_ZARI_BANTLARI = [
  { alt: 1, ust: 10, ad: 'Lehte Kırılma', ton: 'ok' },
  { alt: 11, ust: 35, ad: 'Durgun', ton: 'neutral' },
  { alt: 36, ust: 65, ad: 'Sızıntı', ton: 'warn' },
  { alt: 66, ust: 88, ad: 'Baskı', ton: 'danger' },
  { alt: 89, ust: 100, ad: 'Kriz', ton: 'danger' },
]

/** Band adı (ya da zar değeri) → ton. */
export function zarTonu(band, zar = null) {
  const t = normTr(band)
  const bulunan = DUNYA_ZARI_BANTLARI.find((b) => normTr(b.ad) === t)
  if (bulunan) return bulunan.ton
  const n = Number(zar)
  if (Number.isFinite(n)) {
    const aralik = DUNYA_ZARI_BANTLARI.find((b) => n >= b.alt && n <= b.ust)
    if (aralik) return aralik.ton
  }
  return 'muted'
}

/* ------------------------------------------------------------ JSON denetimi */

/**
 * JSON.parse hata mesajından satır/sütun çıkarır. V8 mesajı bazen
 * "(line 3 column 5)" içerir, bazen yalnızca "position 42" — ikisini de
 * karşılıyoruz, hiçbiri yoksa satır/sütun boş kalır.
 * @param {string} metin
 * @param {Error} hata
 */
function konumBul(metin, hata) {
  const mesaj = String(hata?.message || '')
  const satirSutun = mesaj.match(/line (\d+) column (\d+)/i)
  if (satirSutun) return { satir: Number(satirSutun[1]), sutun: Number(satirSutun[2]) }

  const konum = mesaj.match(/position (\d+)/i)
  if (!konum) return { satir: null, sutun: null }

  const indeks = Math.min(Number(konum[1]), metin.length)
  const oncesi = metin.slice(0, indeks)
  const satir = oncesi.split('\n').length
  const sonSatirBasi = oncesi.lastIndexOf('\n')
  return { satir, sutun: indeks - sonSatirBasi }
}

/** Sık görülen ayrıştırma hatalarının Türkçe karşılığı. */
function hatayiTurkcelestir(mesaj) {
  const m = String(mesaj || '')
  if (/Unexpected end of (JSON )?input|Unterminated/i.test(m)) {
    return 'metin yarım kaldı — bir süslü parantez, köşeli parantez ya da tırnak kapanmamış'
  }
  if (/Expected property name|Unexpected token '?}/i.test(m)) {
    return 'beklenen yerde alan adı yok — fazladan virgül ya da eksik tırnak olabilir'
  }
  if (/Unexpected non-whitespace character after/i.test(m)) {
    return 'JSON bittikten sonra fazladan karakter var — tek bir nesne yaz'
  }
  if (/Bad escaped character|Bad control character/i.test(m)) {
    return 'metin içinde kaçırılmamış bir karakter var (ters bölü ya da satır sonu)'
  }
  if (/Unexpected token/i.test(m)) {
    return 'beklenmeyen karakter — virgül fazlası ya da tırnaksız alan adı olabilir'
  }
  return 'ayrıştırılamadı'
}

/**
 * Serbest yama metnini denetler.
 * @param {string} metin
 * @returns {{gecerli:boolean, bos:boolean, veri:object|null, mesaj:string,
 *   ayrinti:string, satir:number|null, sutun:number|null}}
 */
export function jsonDenetle(metin) {
  const ham = String(metin ?? '').trim()
  const bos = {
    gecerli: false,
    bos: true,
    veri: null,
    mesaj: '',
    ayrinti: '',
    satir: null,
    sutun: null,
  }
  if (!ham) return bos

  let veri
  try {
    veri = JSON.parse(ham)
  } catch (e) {
    const { satir, sutun } = konumBul(ham, e)
    const yer = satir ? ` — satır ${satir}, sütun ${sutun}` : ''
    return {
      gecerli: false,
      bos: false,
      veri: null,
      mesaj: `JSON geçersiz${yer}: ${hatayiTurkcelestir(e.message)}.`,
      ayrinti: String(e?.message || ''),
      satir,
      sutun,
    }
  }

  if (veri === null || typeof veri !== 'object' || Array.isArray(veri)) {
    return {
      gecerli: false,
      bos: false,
      veri: null,
      mesaj: 'Yama bir JSON nesnesi olmalı — süslü parantezle başlayıp bitmeli.',
      ayrinti: '',
      satir: 1,
      sutun: 1,
    }
  }
  if (Object.keys(veri).length === 0) {
    return {
      gecerli: false,
      bos: false,
      veri: null,
      mesaj: 'Yama boş bir nesne — sunucu bunu reddeder.',
      ayrinti: '',
      satir: 1,
      sutun: 1,
    }
  }

  return { gecerli: true, bos: false, veri, mesaj: '', ayrinti: '', satir: null, sutun: null }
}

/** Nesneyi düzenleyiciye yazılacak biçimde metne çevirir. */
export function jsonYaz(nesne) {
  return JSON.stringify(nesne, null, 2)
}
