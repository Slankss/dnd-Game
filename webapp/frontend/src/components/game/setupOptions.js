/**
 * Kurulum ekranındaki hazır seçenekler.
 *
 * Bir dayatma değil, hızlı seçim içindir: her alanda "Kendim yazayım" ile
 * serbest metne geçilebilir. Başlangıç eşyası önerileri sunucudan
 * (`startItemSuggestions`) gelir, burada tekrarlanmaz.
 */

export const OZEL_SECENEK = '__kendim__'

export const MESLEKLER = {
  Sağlık: ['Doktor', 'Hemşire', 'Paramedik', 'Eczacı', 'Veteriner', 'Psikolog'],
  Teknik: [
    'Tamirci',
    'Elektrikçi',
    'Marangoz',
    'Kaynakçı',
    'Mühendis',
    'Yazılımcı',
    'Kimyager',
    'Telsiz operatörü',
  ],
  Güvenlik: [
    'Polis',
    'Asker',
    'İtfaiyeci',
    'Güvenlik görevlisi',
    'Avcı',
    'Dövüş hocası',
    'Korucu',
  ],
  Saha: [
    'Kamyon şoförü',
    'Çiftçi',
    'Dağ rehberi',
    'Denizci',
    'Madenci',
    'İnşaat işçisi',
    'Balıkçı',
  ],
  Diğer: [
    'Öğretmen',
    'Aşçı',
    'Gazeteci',
    'Hırsız',
    'Öğrenci',
    'Din görevlisi',
    'Avukat',
    'Berber',
    'Müzisyen',
  ],
}

export const GUCLU_YANLAR = {
  Beden: [
    'Güçlü ve dayanıklı',
    'Hızlı koşar',
    'Tırmanma ve parkur',
    'Açlığa dayanıklı',
    'Uzun süre uyanık kalabilir',
  ],
  Savaş: [
    'İyi nişancı',
    'Bıçak ustası',
    'Soğukkanlı',
    'Sessiz hareket eder',
    'Soğukkanlı sürücü',
  ],
  Zihin: [
    'Pratik zekalı',
    'Her şeyi tamir eder',
    'Yara sarmayı bilir',
    'Kilit açar',
    'Yön duygusu kuvvetli',
    'Keskin göz ve kulak',
  ],
  Sosyal: [
    'Doğal lider',
    'İyi bir yalancı',
    'İnsanları okur',
    'İyi pazarlıkçı',
    'Hayvanlarla arası iyi',
  ],
}

export const ZAYIF_YANLAR = {
  Bedensel: [
    'Astım',
    'Kalp rahatsızlığı',
    'Diyabet (insülin gerekli)',
    'Bir bacağı sakat',
    'Gözlüksüz göremiyor',
    'Bir kulağı sağır',
    'Zayıf ve çelimsiz',
  ],
  Ruhsal: [
    'Panik atak',
    'Kan görünce donuyor',
    'Karanlıktan korkuyor',
    'Yüksekten korkar',
    'Kapalı alan korkusu',
    'Kabuslar yüzünden uyuyamıyor',
  ],
  Karakter: [
    'Çabuk sinirlenir',
    'Kimseye güvenemiyor',
    'Fazla güveniyor',
    'Ağzından laf kaçırır',
    'Riske tapıyor',
    'İnatçı, emir dinlemez',
  ],
  Beceri: ['Silah kullanamıyor', 'Bağımlılık (ilaç/alkol)', 'Uykusuz kalamıyor', 'Yüzme bilmiyor'],
}

/**
 * Karakter refleksi — baskı altındaki İLK tepki (düşünülmüş karar değil).
 * Anlatıcı bunu Felaket/Kritik zar bantlarında ve gerilim yükseldiğinde
 * fiilen oynatır; küfür dozu ayarlardan gelir.
 */
export const REFLEKSLER = {
  Saldırgan: [
    'Küfreder ve üstüne yürür',
    'Önce vurur, sonra sorar',
    'Bağırarak emir yağdırır',
    'Eline ne geçerse fırlatır',
  ],
  Kaçıngan: [
    'Donakalır, sesi çıkmaz',
    'İçgüdüsel olarak kaçar',
    'Siper alır ve bekler',
    'Geri çekilip başkasını çeker',
  ],
  Soğukkanlı: [
    'Sessizleşir ve hesaplar',
    'Önce yaralıya bakar',
    'Kara mizahla dalga geçer',
    'Yüksek sesle plan söyler',
  ],
  Dağınık: [
    'Panikleyip konuşmaya başlar',
    'Elindekini düşürür',
    'Aynı şeyi tekrar tekrar dener',
    'Sövüp sayarak kendini suçlar',
  ],
}

/** Sunucu 1-8 karakter kabul eder (bkz. /api/setup-characters). */
export const EN_AZ_KARAKTER = 1
export const EN_COK_KARAKTER = 8

/** Boş bir künye satırı. */
export function bosKunye(isim = '') {
  return {
    anahtar: `k-${Math.random().toString(36).slice(2, 9)}`,
    name: isim,
    profession: '',
    age: '',
    strength: '',
    weakness: '',
    reflex: '',
    secret: '',
    item: '',
  }
}
