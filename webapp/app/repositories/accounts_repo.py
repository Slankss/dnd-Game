"""Oyuncu hesapları — `data/accounts.json`.

Hesaplar oyunun DURUMU DEĞİLDİR: `/api/reset` oyunu sıfırlasa bile insanlar
aynı insanlardır, şifrelerini yeniden kurmaları saçma olurdu. Bu yüzden ayrı
bir dosyada dururlar ve state.json ile birlikte silinmezler.

Dosya şifre ÖZETLERİ taşır (düz şifre değil) ama yine de depoya girmez —
.gitignore'da. Yazma atomiktir: yarım kalan bir yazma kimseyi oyunun dışında
bırakmasın.
"""

import json
import os
from pathlib import Path

from ..models.accounts import AccountBook

BASE_DIR = Path(__file__).resolve().parents[2]
ACCOUNTS_FILE = BASE_DIR / "data" / "accounts.json"


class AccountsRepository:
    def __init__(self, accounts_file=None):
        self.accounts_file = Path(accounts_file) if accounts_file else ACCOUNTS_FILE

    def load(self) -> AccountBook:
        """Bozuk dosya oyunu düşürmez ama SESSİZCE de geçilemez: hesaplar
        okunamazsa kimse giremez, bu yüzden boş defter dönüp çağıranın
        (auth_service) yeniden sahiplenmeye izin vermesi gerekir."""
        if not self.accounts_file.exists():
            return AccountBook()
        try:
            data = json.loads(self.accounts_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return AccountBook()
        return AccountBook.from_dict(data if isinstance(data, dict) else {})

    def save(self, book: AccountBook) -> None:
        self.accounts_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.accounts_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(book.to_dict(), ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, self.accounts_file)
        # Şifre özetleri dünyaya okunur olmasın (Windows'ta sessizce geçer).
        try:
            os.chmod(self.accounts_file, 0o600)
        except OSError:
            pass
