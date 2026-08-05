"""Yetki bekçileri — hangi ucu kim çağırabilir.

Kural TEK yerde: uçlar `@player_required` / `@gm_required` ile işaretlenir,
kimliğin kendisi Flask oturumundan okunur. İstemcinin gövdede gönderdiği
"player" alanı ARTIK KİMLİK DEĞİL — kimin oynadığını sunucu bilir, yoksa
dışarı açık bir sunucuda herkes herkesin yerine hamle yapabilirdi.

Üç rol var:
  * `player` — bir karakteri oynar, yalnız onu oynar
  * `table`  — TEK EKRAN kipi: masadaki tek cihaz, kadronun tamamı adına oynar
  * `gm`     — anlatıcı: kurar, ayarlar, sahneyi yazar; hamle yapmaz

Oturum çerezi imzalıdır (Flask `session`), HttpOnly'dir ve SameSite=Lax ile
gelir; ayarları `create_app` kurar.
"""

from functools import wraps

from flask import request, session

from app import services
from app.errors import AuthError, LoginRequired
from app.services.auth_service import ROL_ANLATICI, ROL_MASA, ROL_OYUNCU

# Oturumda tuttuğumuz alanlar.
ROL = "role"
OYUNCU = "player"


def kimlik() -> dict:
    """Oturumdaki ham kimlik ({role, player}); giriş yoksa boş sözlük."""
    rol = session.get(ROL)
    if rol not in (ROL_OYUNCU, ROL_ANLATICI, ROL_MASA):
        return {}
    return {"role": rol, "player": session.get(OYUNCU)}


def giris_yap(veri: dict) -> None:
    """Oturumu kurar. Oturum sabitlemeye karşı önce eskisi temizlenir."""
    session.clear()
    session[ROL] = veri.get("role")
    if veri.get("player"):
        session[OYUNCU] = veri["player"]
    session.permanent = True


def cikis_yap() -> None:
    session.clear()


def is_gm() -> bool:
    return session.get(ROL) == ROL_ANLATICI


def current_player():
    """Oturumun oynadığı karakter; masa/anlatıcı/girişsiz ise None."""
    return session.get(OYUNCU) if session.get(ROL) == ROL_OYUNCU else None


def acting_player(istenen=None) -> str:
    """Bu istekte kim adına hamle yapılıyor — kararı servis verir.

    Oyuncu oturumunda gövdedeki ad yok sayılır; masa oturumunda (tek ekran)
    gövdedeki ad kullanılır ama kip hâlâ açık olmalıdır."""
    return services.auth.acting_player(kimlik(), istenen)


def login_required(view):
    """Oyuncu, masa ya da anlatıcı — sahneyi görmek için giriş şart."""
    @wraps(view)
    def sarmal(*args, **kwargs):
        if not kimlik():
            raise LoginRequired()
        return view(*args, **kwargs)
    return sarmal


def player_required(view):
    """Hamle yapabilen oturumlar: oyuncu ve tek ekran masası.

    Anlatıcı hamle YAPMAZ — sahneyi o yazar; karıştırmak "kim oynadı"
    sorusunu belirsizleştirirdi. Hangi karakter adına oynandığını uç
    `acting_player()` ile sorar."""
    @wraps(view)
    def sarmal(*args, **kwargs):
        rol = session.get(ROL)
        if rol not in (ROL_OYUNCU, ROL_MASA):
            if not kimlik():
                raise LoginRequired()
            raise AuthError("Bu işlem için karakterinizle giriş yapın.")
        return view(*args, **kwargs)
    return sarmal


def gm_required(view):
    """Yalnız anlatıcı: kurulum, ayarlar, sıfırlama, senaryo ve /secrets."""
    @wraps(view)
    def sarmal(*args, **kwargs):
        if not is_gm():
            if not kimlik():
                raise LoginRequired()
            raise AuthError("Bu işlem anlatıcıya ait.")
        return view(*args, **kwargs)
    return sarmal


def govde() -> dict:
    """JSON gövdesi (boş olabilir) — uçlar tekrar tekrar yazmasın."""
    return request.get_json(silent=True) or {}
