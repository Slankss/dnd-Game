"""Oyuncu hesapları — kim hangi karakteri oynuyor.

Oyun dışarı açık bir sunucuda çalıştığı için karakterin kime ait olduğu
artık istemcinin söylediği bir şey DEĞİL: her karakter bir kez sahiplenilir,
sahiplenen kendi şifresini belirler ve o karakterin hamlelerini yalnız o
oturum yapabilir.

Bu modül SAF: şifreyi karşılaştırır, defteri sözlüğe çevirir, dosya ya da
HTTP bilmez. Sahiplenme kuralı ve kaba kuvvet frenleri servis katmanında
(services/auth_service).

Şifre özeti werkzeug'un `scrypt` varsayılanıyla üretilir — Flask'ın zaten
getirdiği bir bağımlılık, ayrıca kurulum gerektirmez.
"""

import time

from werkzeug.security import check_password_hash, generate_password_hash

from app.models.text import norm_tr

# Dışarı açık bir sunucuda 4 karakterlik şifre kabul edilemez; 6 hem
# kırılması zor hem de oyun masasında yazılabilir bir alt sınır.
MIN_PASSWORD = 6
# Karakter adı zaten kadrodan geliyor; yine de saçma uzunlukları erken kes.
MAX_PASSWORD = 200


class Account:
    """Bir karakterin sahibi. `player` kadrodaki ADIN AYNISIDIR (sıra ve
    büyük/küçük harf dahil) — eşleştirme `norm_tr` ile yapılır ama kayıt
    kadronun yazdığı biçimi korur."""

    __slots__ = ("player", "hash", "created", "last_login")

    def __init__(self, player: str, hash: str, created=None, last_login=None):
        self.player = player
        self.hash = hash
        self.created = created or time.time()
        self.last_login = last_login

    @classmethod
    def from_dict(cls, data: dict) -> "Account":
        data = data if isinstance(data, dict) else {}
        return cls(player=str(data.get("player") or ""),
                   hash=str(data.get("hash") or ""),
                   created=data.get("created"),
                   last_login=data.get("last_login"))

    def to_dict(self) -> dict:
        return {"player": self.player, "hash": self.hash,
                "created": self.created, "last_login": self.last_login}

    def verify(self, password: str) -> bool:
        if not self.hash or not isinstance(password, str) or not password:
            return False
        return check_password_hash(self.hash, password)

    def set_password(self, password: str) -> None:
        self.hash = generate_password_hash(password)


class AccountBook:
    """Karakter adı → hesap. Anahtar `norm_tr` ile normalleştirilir ki
    "okan" ile "Okan" aynı hesabı bulsun."""

    def __init__(self, accounts=None):
        self.accounts = dict(accounts or {})

    @classmethod
    def from_dict(cls, data: dict) -> "AccountBook":
        data = data if isinstance(data, dict) else {}
        ham = data.get("players")
        ham = ham if isinstance(ham, dict) else {}
        out = {}
        for key, value in ham.items():
            hesap = Account.from_dict(value)
            if hesap.player and hesap.hash:
                out[norm_tr(hesap.player) or norm_tr(key)] = hesap
        return cls(out)

    def to_dict(self) -> dict:
        return {"players": {k: v.to_dict() for k, v in self.accounts.items()}}

    # ------------------------------------------------------------- sorgular
    def find(self, player):
        return self.accounts.get(norm_tr(player))

    def claimed(self, player) -> bool:
        return self.find(player) is not None

    def names(self) -> list:
        """Sahiplenilmiş karakterlerin kadrodaki yazımıyla listesi."""
        return [a.player for a in self.accounts.values()]

    # ----------------------------------------------------------- değişiklik
    def claim(self, player: str, password: str) -> Account:
        """Sahipsiz bir karakteri sahiplendirir. Çağıran ÖNCE karakterin
        kadroda olduğunu ve sahipsiz olduğunu doğrulamalıdır."""
        hesap = Account(player=player, hash="")
        hesap.set_password(password)
        self.accounts[norm_tr(player)] = hesap
        return hesap

    def release(self, player) -> bool:
        """Sahipliği bırakır (anlatıcı bir oyuncunun şifresini sıfırlarken).
        Karakterin kendisine dokunmaz, yalnız hesabı siler."""
        return self.accounts.pop(norm_tr(player), None) is not None

    def touch(self, player) -> None:
        hesap = self.find(player)
        if hesap:
            hesap.last_login = time.time()


def password_problem(password) -> str:
    """Şifre kabul edilebilir mi? Sorun varsa Türkçe mesaj, yoksa ""."""
    if not isinstance(password, str) or not password.strip():
        return "Şifre girin."
    if len(password) < MIN_PASSWORD:
        return f"Şifre en az {MIN_PASSWORD} karakter olmalı."
    if len(password) > MAX_PASSWORD:
        return "Şifre çok uzun."
    return ""
