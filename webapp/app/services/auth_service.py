"""Kimlik — kim hangi karakteri oynuyor, kim anlatıcı.

Oyun dışarı açık bir sunucuda çalışıyor. Bu yüzden "ben Okan'ım" iddiası
artık istemciden gelen bir alan DEĞİL, sunucudaki oturumun taşıdığı bir
gerçek. API katmanı oturumu kurar/okur (Flask `session`), buradaki kod Flask
bilmez: kimlik sözlüğü döndürür, kararı verir.

Akış:
  1. Anlatıcı bir OYUN KODU paylaşır (config.GAME_CODE).
  2. Oyuncu ilk girişte kodu + karakterini + kendi belirlediği şifreyi yazar;
     karakter o an SAHİPLENİLİR.
  3. Sonraki girişlerde kod gerekmez — karakter adı + şifre yeter.
  4. Sahiplenilmiş bir karakteri başkası alamaz; anlatıcı `release` ile
     sahipliği bırakırsa yeniden sahiplenilebilir.

Kaba kuvvet freni bellekte tutulur: tek süreçli bir oyun sunucusu için
yeterli, yeniden başlatınca sıfırlanır (kilitlenip kalan kimse olmaz).
"""

import hmac
import time

from app import config
from app.errors import AuthError, LoginRequired, ValidationError
from app.models.accounts import password_problem
from app.models.text import norm_tr

try:  # senaryo modülü kök dizinde
    from scenario import GROUP_LABEL
except ImportError:  # pragma: no cover — senaryo yoksa grup kararı da yok
    GROUP_LABEL = ""

from app.repositories.accounts_repo import AccountsRepository
from app.repositories.state_repo import LOCK, StateRepository

ROL_OYUNCU = "player"
ROL_ANLATICI = "gm"
# TEK EKRAN: herkes aynı masada, tek cihazın başında. Bu oturum bir karaktere
# bağlı değildir, kadronun TAMAMI adına oynar. Yalnız ayarlarda tek ekran kipi
# açıkken kurulabilir ve kip kapanırsa kendiliğinden geçersizleşir.
ROL_MASA = "table"

# Kaba kuvvet freni: aynı anahtar (IP + hedef) için art arda kaç deneme, ve
# aşıldığında ne kadar beklenir. Oyun masası için cömert, saldırgan için değil.
MAX_DENEME = 8
KILIT_SANIYE = 300
# Deneme sayacı bu kadar sessizlikten sonra kendiliğinden unutulur.
UNUTMA_SANIYE = 900


class AuthService:
    """`/api/auth/*` — giriş, sahiplenme, çıkış, kimlik sorgusu."""

    def __init__(self, accounts_repo=None, state_repo=None, game_code=None,
                 gm_pin=None):
        self.accounts = accounts_repo or AccountsRepository()
        self.state_repo = state_repo or StateRepository()
        self._game_code = game_code
        self._gm_pin = gm_pin
        # {anahtar: [deneme_sayısı, son_deneme_ts]}
        self._denemeler = {}

    # ------------------------------------------------------------ ayarlar
    @property
    def game_code(self) -> str:
        return self._game_code if self._game_code is not None else config.GAME_CODE

    @property
    def gm_pin(self) -> str:
        return self._gm_pin if self._gm_pin is not None else config.GM_PIN

    # --------------------------------------------------------- kaba kuvvet
    def _fren(self, anahtar: str) -> None:
        """Kilitliyse hata atar. Çağrı BAŞARISIZ olursa `_yanlis` çağrılır."""
        kayit = self._denemeler.get(anahtar)
        if not kayit:
            return
        sayi, son = kayit
        if time.time() - son > UNUTMA_SANIYE:
            self._denemeler.pop(anahtar, None)
            return
        if sayi >= MAX_DENEME:
            kalan = int(KILIT_SANIYE - (time.time() - son))
            if kalan > 0:
                raise AuthError(
                    f"Çok fazla hatalı deneme. {max(1, kalan // 60) } dakika sonra "
                    "tekrar deneyin."
                )
            self._denemeler.pop(anahtar, None)

    def _yanlis(self, anahtar: str) -> None:
        sayi, _ = self._denemeler.get(anahtar, (0, 0))
        self._denemeler[anahtar] = (sayi + 1, time.time())

    def _dogru(self, anahtar: str) -> None:
        self._denemeler.pop(anahtar, None)

    # ------------------------------------------------------------- kadro
    def _roster(self) -> list:
        """Kadrodaki HAYATTA karakterler (state.json'daki sırayla)."""
        with LOCK:
            state = self.state_repo.load()
            world = StateRepository.world_of(state)
        return [ad for ad, kisi in (world.characters or {}).items()
                if kisi.is_alive]

    def single_screen(self) -> bool:
        """Tek ekran kipi açık mı (ayarlardan okunur, canlı değişir)."""
        with LOCK:
            state = self.state_repo.load()
            return bool(StateRepository.settings_of(state).get("single_screen"))

    def _kadroda(self, player):
        """Girilen adı kadrodaki YAZIMIYLA döndürür, yoksa None."""
        hedef = norm_tr(player)
        if not hedef:
            return None
        return next((ad for ad in self._roster() if norm_tr(ad) == hedef), None)

    # -------------------------------------------------------------- sorgu
    def me(self, kimlik: dict) -> dict:
        """Oturumun kim olduğunu ve giriş ekranının neye ihtiyacı olduğunu
        söyler. Kimlik doğrulanmamışken de çağrılabilir."""
        kimlik = kimlik if isinstance(kimlik, dict) else {}
        rol = kimlik.get("role")
        defter = self.accounts.load()
        kadro = self._roster()
        oyuncu = kimlik.get("player")
        tek_ekran = self.single_screen()
        # Karakter silinmiş/ölmüşse oturum artık geçerli değil.
        if rol == ROL_OYUNCU and not self._kadroda(oyuncu):
            rol, oyuncu = None, None
        # Kip kapandıysa masa oturumu da düşer — giriş ekranı yeniden gelir.
        if rol == ROL_MASA and not tek_ekran:
            rol, oyuncu = None, None
        return {
            "role": rol,
            "player": oyuncu if rol == ROL_OYUNCU else None,
            "roster": kadro,
            # Hangi karakterler hâlâ sahipsiz — giriş ekranı bunu listeler.
            "available": [ad for ad in kadro if not defter.claimed(ad)],
            "claimed": [ad for ad in kadro if defter.claimed(ad)],
            # Kadro yoksa oyun daha kurulmamıştır: oyuncu bekler, anlatıcı kurar.
            "roster_ready": bool(kadro),
            # Giriş ekranı "tek ekran" seçeneğini ancak kip açıkken gösterir.
            "single_screen": tek_ekran,
        }

    # ------------------------------------------------------------- giriş
    def login(self, player, password, code=None, ip="?") -> dict:
        """Karakter sahipliyse şifreyle girer, sahipsizse OYUN KODUYLA
        sahiplenir. İki yolu tek uca toplamak giriş ekranını da tekleştirir.

        Dönen sözlük API katmanının oturuma yazacağı kimliktir."""
        kadro_adi = self._kadroda(player)
        if not kadro_adi:
            if not self._roster():
                raise ValidationError(
                    "Kadro henüz kurulmadı — anlatıcı oyunu hazırlayana kadar bekleyin."
                )
            raise ValidationError("Böyle bir karakter yok.")

        anahtar = f"{ip}:{norm_tr(kadro_adi)}"
        self._fren(anahtar)

        defter = self.accounts.load()
        hesap = defter.find(kadro_adi)

        if hesap is None:
            # İLK GİRİŞ — sahiplenme. Oyun kodu burada sorulur.
            if not self._kod_dogru(code):
                self._yanlis(anahtar)
                raise AuthError("Oyun kodu yanlış.")
            sorun = password_problem(password)
            if sorun:
                raise ValidationError(sorun)
            defter.claim(kadro_adi, password)
            defter.touch(kadro_adi)
            self.accounts.save(defter)
            self._dogru(anahtar)
            return {"role": ROL_OYUNCU, "player": kadro_adi, "claimed": True}

        if not hesap.verify(password or ""):
            self._yanlis(anahtar)
            raise AuthError("Karakter adı ya da şifre yanlış.")
        defter.touch(kadro_adi)
        self.accounts.save(defter)
        self._dogru(anahtar)
        return {"role": ROL_OYUNCU, "player": kadro_adi, "claimed": False}

    def table_login(self, code, ip="?") -> dict:
        """TEK EKRAN girişi: karakter yok, şifre yok — yalnız oyun kodu.

        Masadaki tek cihaz kadronun tamamı adına oynar. Kip kapalıyken bu
        kapı hiç açılmaz; açık bir masa oturumu da kip kapanınca ilk hamlede
        reddedilir (bkz. `acting_player`)."""
        if not self.single_screen():
            raise ValidationError(
                "Tek ekran kipi kapalı — anlatıcı ayarlardan açabilir."
            )
        anahtar = f"{ip}:__masa__"
        self._fren(anahtar)
        if not self._kod_dogru(code):
            self._yanlis(anahtar)
            raise AuthError("Oyun kodu yanlış.")
        self._dogru(anahtar)
        return {"role": ROL_MASA, "player": None}

    def acting_player(self, kimlik: dict, istenen=None) -> str:
        """Bu istekte KİM adına hamle yapılıyor?

        - Oyuncu oturumu: her zaman kendi karakteri. Gövdedeki ad dikkate
          ALINMAZ — dışarı açık bir sunucuda istemcinin sözü kimlik değildir.
        - Masa oturumu: gövdedeki karakter, ama yalnız kip hâlâ açıkken ve
          karakter kadrodaysa.
        - Anlatıcı: hamle yapmaz; sahneyi o yazar.
        """
        kimlik = kimlik if isinstance(kimlik, dict) else {}
        rol = kimlik.get("role")
        # ORTAK KARAR grubun sözüdür, bir karakterin değil: her oyuncu
        # gönderebilir. Kimlik yine de gerekli — girişsiz kimse yazamaz.
        if (GROUP_LABEL and rol in (ROL_OYUNCU, ROL_MASA)
                and norm_tr(istenen) == norm_tr(GROUP_LABEL)):
            return GROUP_LABEL
        if rol == ROL_OYUNCU:
            ad = self._kadroda(kimlik.get("player"))
            if not ad:
                raise AuthError("Karakteriniz kadroda değil — yeniden giriş yapın.")
            return ad
        if rol == ROL_MASA:
            if not self.single_screen():
                raise AuthError(
                    "Tek ekran kipi kapandı — karakterinizle giriş yapın."
                )
            ad = self._kadroda(istenen)
            if not ad:
                raise ValidationError("Karakter seçilmedi.")
            return ad
        raise LoginRequired("Bu işlem için karakterinizle giriş yapın.")

    def gm_login(self, pin, ip="?") -> dict:
        anahtar = f"{ip}:__gm__"
        self._fren(anahtar)
        if not self._sabit_esit(str(pin or ""), str(self.gm_pin)):
            self._yanlis(anahtar)
            raise AuthError("Yanlış PIN.")
        self._dogru(anahtar)
        return {"role": ROL_ANLATICI, "player": None}

    # ----------------------------------------------------- anlatıcı işlemi
    def release(self, player) -> dict:
        """Bir karakterin sahipliğini bırakır — oyuncu şifresini unuttuğunda
        anlatıcı bunu yapar, oyuncu yeniden sahiplenir."""
        kadro_adi = self._kadroda(player) or str(player or "").strip()
        if not kadro_adi:
            raise ValidationError("Karakter seçilmedi.")
        defter = self.accounts.load()
        if not defter.release(kadro_adi):
            raise ValidationError(f"{kadro_adi} zaten sahipsiz.")
        self.accounts.save(defter)
        return {"ok": True, "player": kadro_adi}

    def accounts_overview(self) -> dict:
        """Anlatıcı ekranı için: kim girmiş, kim hiç girmemiş."""
        defter = self.accounts.load()
        satirlar = []
        for ad in self._roster():
            hesap = defter.find(ad)
            satirlar.append({
                "player": ad,
                "claimed": hesap is not None,
                "last_login": hesap.last_login if hesap else None,
            })
        return {"accounts": satirlar, "game_code": self.game_code}

    # ---------------------------------------------------------- yardımcı
    def _kod_dogru(self, code) -> bool:
        return self._sabit_esit(str(code or "").strip(), str(self.game_code).strip())

    @staticmethod
    def _sabit_esit(a: str, b: str) -> bool:
        """Sabit süreli karşılaştırma: yanıt süresinden karakter karakter
        kod/PIN okunamasın."""
        return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
