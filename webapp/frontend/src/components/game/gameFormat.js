/**
 * Oyuncu ekranı biçimlendirme yardımcıları.
 *
 * Kural: buradaki hiçbir fonksiyon renk KODU döndürmez — yalnızca tasarım
 * sistemindeki ton adlarını ('ok' | 'warn' | 'danger' | 'accent' | 'muted')
 * ve Material Symbols ikon adlarını döndürür (docs/tasarim-sistemi.md §3, §5).
 *
 * Sunucu tarafındaki veri biçimleri savunmacı ele alınır: `challenges` kimi
 * kayıtlarda sözlük kimi kayıtlarda dizi, `resources` kalemi kimi zaman düz
 * sayı kimi zaman `{qty, unit, notes}` olabiliyor.
 */

/* ------------------------------------------------------------------ vitals */

/** Hayatta kalma göstergeleri: 0 = gayet iyi, 100 = dayanılmaz. */
export const VITAL_ALANLARI = [
  { anahtar: 'fatigue', etiket: 'Yorgunluk', kisa: 'yorgun', ikon: 'bedtime' },
  { anahtar: 'hunger', etiket: 'Açlık', kisa: 'aç', ikon: 'restaurant' },
  { anahtar: 'thirst', etiket: 'Susuzluk', kisa: 'susuz', ikon: 'local_drink' },
  { anahtar: 'stress', etiket: 'Stres', kisa: 'stres', ikon: 'psychology' },
]

/** 0-100 aralığına kırpılmış sayı. */
export function olcuyeAl(deger) {
  const n = Number(deger)
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(100, Math.round(n)))
}

/** Gösterge değeri → durum tonu. Eşikler eski arayüzle aynı. */
export function vitalTonu(deger) {
  const v = olcuyeAl(deger)
  if (v >= 65) return 'danger'
  if (v >= 40) return 'warn'
  return 'ok'
}

/** Kartta yalnızca dikkat çeken (>=40) göstergeler gösterilir. */
export function dikkatCekenVitals(vitals) {
  if (!vitals || typeof vitals !== 'object') return []
  return VITAL_ALANLARI.map((alan) => ({ ...alan, deger: olcuyeAl(vitals[alan.anahtar]) })).filter(
    (a) => a.deger >= 40,
  )
}

/* ------------------------------------------------------------------ yaralar */

/** Yara şiddeti → ton. */
export function yaraTonu(siddet) {
  const s = String(siddet || 'orta').toLocaleLowerCase('tr-TR')
  if (s.includes('kritik')) return 'danger'
  if (s.includes('ağır') || s.includes('agir')) return 'danger'
  if (s.includes('orta')) return 'warn'
  return 'ok'
}

/** Enfeksiyon riski → ton. */
export function enfeksiyonTonu(risk) {
  const r = olcuyeAl(risk)
  if (r >= 60) return 'danger'
  if (r >= 35) return 'warn'
  return 'ok'
}

/** Yalnızca açıklaması olan yaralar sayılır (boş kayıtlar sızabiliyor). */
export function yaralariDiziye(wounds) {
  if (!Array.isArray(wounds)) return []
  return wounds.filter((y) => y && typeof y === 'object' && y.desc)
}

/** Kadro kartındaki tek satırlık yara özeti için en kötü enfeksiyon riski. */
export function enKotuEnfeksiyon(wounds) {
  const liste = yaralariDiziye(wounds)
  if (!liste.length) return 0
  return liste.reduce((enKotu, y) => Math.max(enKotu, olcuyeAl(y.infection_risk)), 0)
}

/* ------------------------------------------------------- sahne katılımı */

/**
 * `presence.state` → rozet bilgisi. "sahnede" için rozet YOK: normal hal
 * sessiz kalır, yalnızca sapma göze çarpar.
 */
export const KATILIM_HALLERI = {
  uyuyor: { etiket: 'uyuyor', ikon: 'bedtime', ton: 'muted' },
  uzakta: { etiket: 'sahne dışında', ikon: 'directions_walk', ton: 'muted' },
  baygın: { etiket: 'baygın', ikon: 'blur_on', ton: 'warn' },
  esir: { etiket: 'esir', ikon: 'lock', ton: 'danger' },
}

/** @returns {{etiket:string, ikon:string, ton:string, not:string}|null} */
export function katilimBilgisi(bilgi) {
  const presence = bilgi?.presence
  const hal = presence && typeof presence === 'object' ? presence.state : presence
  const kayit = KATILIM_HALLERI[hal]
  if (!kayit) return null
  return { ...kayit, not: (presence && presence.note) || '' }
}

/* ------------------------------------------------------------------ durum */

/** Serbest metin sağlık durumu → ton (anlatıcı burayı düz yazıyor). */
export function saglikTonu(status) {
  const s = String(status || '').toLocaleLowerCase('tr-TR')
  if (!s) return 'muted'
  if (s.includes('öldü') || s.includes('ölü')) return 'danger'
  if (s.includes('ağır') || s.includes('enfekte') || s.includes('kritik')) return 'danger'
  if (s.includes('yaralı') || s.includes('bitkin') || s.includes('hasta') || s.includes('zayıf'))
    return 'warn'
  return 'ok'
}

/* -------------------------------------------------------------------- zar */

/** Zar bandı → ton. Bant adları sunucudaki DICE_BANDS ile birebir. */
export const ZAR_BANT_TONU = {
  Felaket: 'danger',
  Başarısız: 'danger',
  'Kısmi Başarı': 'warn',
  Başarı: 'ok',
  'Güçlü Başarı': 'ok',
  Kritik: 'accent',
}

export function zarTonu(bant) {
  return ZAR_BANT_TONU[bant] || 'neutral'
}

/* --------------------------------------------------------------- zorluklar */

const KAPALI_DURUMLAR = ['çözüldü', 'başarısız']

/** Zorluk şiddeti → ton. */
export function zorlukTonu(siddet) {
  const s = String(siddet || 'orta').toLocaleLowerCase('tr-TR')
  if (s.includes('kritik') || s.includes('yüksek')) return 'danger'
  if (s.includes('orta')) return 'warn'
  return 'ok'
}

export function zorlukKapali(durum) {
  return KAPALI_DURUMLAR.includes(String(durum || '').toLocaleLowerCase('tr-TR'))
}

/**
 * Zorlukları tek tip diziye çevirir; kapananlar sona iner (oyuncular ne
 * başardıklarını görsün ama listenin başını tıkamasın).
 * @param {object|Array} ham
 */
export function zorluklariDiziye(ham) {
  let liste = []
  if (Array.isArray(ham)) {
    liste = ham
      .filter((z) => z && typeof z === 'object')
      .map((z, i) => ({ ad: z.name || z.ad || `Zorluk ${i + 1}`, ...z }))
  } else if (ham && typeof ham === 'object') {
    liste = Object.entries(ham).map(([ad, bilgi]) => ({ ad, ...(bilgi || {}) }))
  }
  return liste.sort((a, b) => Number(zorlukKapali(a.status)) - Number(zorlukKapali(b.status)))
}

/* ---------------------------------------------------------------- kaynaklar */

/**
 * Ortak stok: `{kategori: {kalem: 5 | {qty, unit, notes}}}` → düz liste.
 * @returns {Array<{kategori:string, kalemler:Array<object>}>}
 */
export function kaynaklariDiziye(resources) {
  if (!resources || typeof resources !== 'object') return []
  return Object.entries(resources)
    .map(([kategori, kalemler]) => ({
      kategori,
      kalemler: Object.entries(kalemler || {}).map(([ad, bilgi]) => {
        const nesne = bilgi && typeof bilgi === 'object'
        const miktar = nesne ? bilgi.qty : bilgi
        const sayi = Number(miktar)
        return {
          ad,
          miktar: Number.isFinite(sayi) ? sayi : miktar,
          sayisal: Number.isFinite(sayi) ? sayi : null,
          birim: (nesne ? bilgi.unit : '') || '',
          not: (nesne ? bilgi.notes : '') || '',
        }
      }),
    }))
    .filter((k) => k.kalemler.length > 0)
}

/** Kalem miktarı → ton (bitti / azaldı / normal). */
export function kaynakTonu(kalem) {
  if (kalem.sayisal === null) return 'neutral'
  if (kalem.sayisal <= 0) return 'danger'
  if (kalem.sayisal <= 5) return 'warn'
  return 'neutral'
}

/** Ortada gerçekten stok var mı? (boş kategoriler sayılmaz) */
export function stokVarMi(resources) {
  return kaynaklariDiziye(resources).length > 0
}

/* ------------------------------------------------------------ dünya künyesi */

/** Hava metninden ikon seç (docs §5 hava satırı). */
export function havaIkonu(hava) {
  const h = String(hava || '').toLocaleLowerCase('tr-TR')
  if (!h) return 'cloud'
  if (h.includes('kar') || h.includes('tipi')) return 'weather_snowy'
  if (h.includes('yağmur') || h.includes('sağanak') || h.includes('çisel')) return 'rainy'
  if (h.includes('sis') || h.includes('pus')) return 'foggy'
  if (h.includes('güneş') || h.includes('açık')) return 'wb_sunny'
  if (h.includes('don') || h.includes('buz')) return 'ac_unit'
  return 'cloud'
}

/**
 * Sıcaklık gösterimi. Sunucu kimi kayıtta "7°C" (metin) kimi kayıtta 7 (sayı)
 * yazıyor — birimi iki kez yazmamak için burada tek noktadan çözülür.
 */
export function sicaklikMetni(deger) {
  if (deger === null || deger === undefined || deger === '') return ''
  const metin = String(deger).trim()
  return /[°]/.test(metin) ? metin : `${metin}°C`
}

/** "Gün 98 · 21:40 gece · yağmurlu 7°C · konum" (ekran okuyucu / ipucu için) */
export function dunyaSaatiMetni(saat) {
  if (!saat) return ''
  const zaman = [saat.clock, saat.timeOfDay].filter(Boolean).join(' ')
  const gokyuzu = [saat.weather, sicaklikMetni(saat.temperature)].filter(Boolean).join(', ')
  return [saat.day != null ? `Gün ${saat.day}` : '', zaman, gokyuzu, saat.location]
    .filter(Boolean)
    .join(' · ')
}

/** Gerilim düzeyi → ton. Severity renkleri yalnızca durum bildirir (docs §3). */
export function gerilimTonu(gerilim) {
  const g = String(gerilim || '').toLocaleLowerCase('tr-TR')
  if (g.includes('yüksek') || g.includes('kritik')) return 'danger'
  if (g.includes('orta')) return 'warn'
  return 'ok'
}

/* ------------------------------------------------------------------ metin */

/**
 * Emoji temizliği — sunucu bazı sistem girdilerini emojiyle yazıyor
 * ("💀 Okan öldü…"), arayüzde emoji kullanılmıyor (docs §5).
 */
export function emojiTemizle(metin) {
  return String(metin ?? '')
    .replace(/[\p{Extended_Pictographic}️‍]/gu, '')
    .replace(/[ \t]{2,}/g, ' ')
    .trim()
}

/** "2026-08-02 21:40:03" → "21:40" (uzun damga akışta yer kaplıyor). */
export function saatMetni(ts) {
  const m = /(\d{2}:\d{2})(?::\d{2})?$/.exec(String(ts || ''))
  return m ? m[1] : ''
}

/** Karakter künyesinin tek satırlık özeti: "34 yaşında · Tamirci" */
export function kunyeOzeti(bilgi) {
  if (!bilgi) return ''
  const yas = bilgi.age ? `${bilgi.age} yaşında` : ''
  return [yas, bilgi.profession].filter(Boolean).join(' · ')
}
