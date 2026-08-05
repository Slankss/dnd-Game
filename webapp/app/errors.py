"""Servis katmanının hata dili.

Servisler Flask bilmez: doğrulama ya da dış süreç hatasında bu istisnaları
atarlar, API katmanı da bunları `{"error": ...}` + HTTP koduna çevirir.
Mesajlar Türkçe ve doğrudan kullanıcıya gösterilebilir olmalı.
"""


class GameError(Exception):
    """Kullanıcıya gösterilebilir hata. `status` HTTP kodudur."""

    status = 400

    def __init__(self, message: str, status: int = None):
        super().__init__(message)
        self.message = message
        if status is not None:
            self.status = status


class ValidationError(GameError):
    """Eksik/geçersiz istek gövdesi, kurallara aykırı işlem."""
    status = 400


class AuthError(GameError):
    """Kimlik doğru ama yetki yok: yanlış PIN/şifre/kod, ya da bu işlem
    bu role ait değil."""
    status = 403

    def __init__(self, message: str = "Yanlış PIN."):
        super().__init__(message)


class LoginRequired(AuthError):
    """Ortada oturum YOK. 403'ten ayrı tutulur: arayüz 401'i görünce giriş
    ekranını açar, 403'te ise 'senin yetkin yok' der."""
    status = 401

    def __init__(self, message: str = "Giriş yapın."):
        super().__init__(message)


class NarratorError(GameError):
    """claude CLI hata döndürdü ya da çıktısı okunamadı."""
    status = 502


class NarratorTimeout(GameError):
    """claude CLI zaman aşımına uğradı."""
    status = 504

    def __init__(self, message: str = "claude CLI zaman aşımına uğradı."):
        super().__init__(message)
