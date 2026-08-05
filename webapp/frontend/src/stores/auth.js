import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '@/api/client'

/**
 * Kimlik — kim bu ekranda oturuyor.
 *
 * Sunucu kimliği imzalı bir oturum çerezinde tutar; burada onun yansımasını
 * saklarız. Tarayıcıda ŞİFRE ya da PIN saklanmaz: yenilemede `/api/auth/me`
 * sorulur, çerez hâlâ geçerliyse oturum kaldığı yerden sürer.
 *
 * Üç rol:
 *   player — bir karakteri oynar, YALNIZ onu oynar
 *   table  — tek ekran kipi: masadaki cihaz kadronun tamamı adına oynar
 *   gm     — anlatıcı
 */
export const useAuthStore = defineStore('auth', () => {
  /** 'player' | 'table' | 'gm' | null */
  const role = ref(null)
  /** Oyuncu oturumunda oynanan karakter; masa/anlatıcıda null */
  const player = ref(null)
  /** Kadro (hayatta olanlar) — giriş ekranı bunu listeler */
  const roster = ref([])
  /** Henüz sahiplenilmemiş karakterler */
  const available = ref([])
  /** Sahiplenilmiş karakterler */
  const claimed = ref([])
  /** Anlatıcı kadroyu kurdu mu — kurmadıysa oyuncu giriş bile yapamaz */
  const rosterReady = ref(false)
  /** Tek ekran kipi açık mı (giriş ekranında "tek ekran" seçeneği) */
  const singleScreen = ref(false)

  /** İlk `me()` çağrısı tamamlandı mı — bitmeden ekran çizilmez */
  const hazir = ref(false)
  const busy = ref(false)
  const error = ref(null)

  const girisli = computed(() => role.value !== null)
  const anlatici = computed(() => role.value === 'gm')
  /** Hamle yapabilen oturum mu (oyuncu ya da masa) */
  const oynayabilir = computed(() => role.value === 'player' || role.value === 'table')
  /** Tek ekran kipinde tek cihaz herkesi oynar → karakter değiştirici görünür */
  const masaKipi = computed(() => role.value === 'table')

  function benimse(veri) {
    role.value = veri?.role ?? null
    player.value = veri?.player ?? null
    roster.value = veri?.roster ?? []
    available.value = veri?.available ?? []
    claimed.value = veri?.claimed ?? []
    rosterReady.value = !!veri?.roster_ready
    singleScreen.value = !!veri?.single_screen
  }

  /** Sayfa açılışında ve 401 alındığında çağrılır. */
  async function yenile() {
    try {
      benimse(await api.authMe())
      error.value = null
    } catch (e) {
      // Sunucuya ulaşılamıyorsa kimliği DÜŞÜRME: ağ döndüğünde oturum duruyor.
      if (!api.toApiError(e).isNetwork) benimse(null)
      error.value = api.toApiError(e)
    } finally {
      hazir.value = true
    }
  }

  async function giris({ player: ad, password, code = null }) {
    busy.value = true
    error.value = null
    try {
      benimse(await api.authLogin({ player: ad, password, code }))
      return true
    } catch (e) {
      error.value = api.toApiError(e)
      return false
    } finally {
      busy.value = false
    }
  }

  /** Tek ekran: yalnız oyun kodu; masadaki cihaz herkes adına oynar. */
  async function masaGirisi(code) {
    busy.value = true
    error.value = null
    try {
      benimse(await api.authTable(code))
      return true
    } catch (e) {
      error.value = api.toApiError(e)
      return false
    } finally {
      busy.value = false
    }
  }

  async function anlaticiGirisi(pin) {
    busy.value = true
    error.value = null
    try {
      benimse(await api.authGm(pin))
      return true
    } catch (e) {
      error.value = api.toApiError(e)
      return false
    } finally {
      busy.value = false
    }
  }

  async function cikis() {
    busy.value = true
    try {
      benimse(await api.authLogout())
    } catch {
      benimse(null)
    } finally {
      busy.value = false
    }
  }

  /** Bir istek 401 döndüyse oturum düşmüştür: kimliği tazele. */
  function oturumDustu() {
    benimse(null)
  }

  return {
    role, player, roster, available, claimed, rosterReady, singleScreen,
    hazir, busy, error,
    girisli, anlatici, oynayabilir, masaKipi,
    yenile, giris, masaGirisi, anlaticiGirisi, cikis, oturumDustu,
  }
})
