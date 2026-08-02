"""Anlatıcı modeliyle konuşan tek nokta: `claude` CLI süreci.

Sunucunun geri kalanı subprocess bilmez; sadece `NarratorClient.ask(...)`
çağırır ve sözlük alır. Hata halinde servis dilindeki istisnalar atılır.
"""

import json
import os
import subprocess
import tempfile

from app import config
from app.errors import NarratorError, NarratorTimeout


class NarratorClient:
    """claude CLI'ı headless (-p) modda çalıştırır; claude.ai OAuth girişini
    kullanır, ayrı bir API anahtarı istemez."""

    def __init__(self, binary: str = None, model: str = None,
                 effort: str = None, timeout: int = None,
                 cwd=None):
        self.binary = binary or config.CLAUDE_BIN
        self.model = model or config.MODEL
        self.effort = effort or config.EFFORT
        self.timeout = timeout or config.CLAUDE_TIMEOUT
        self.cwd = str(cwd or config.BASE_DIR)

    @staticmethod
    def _write_temp(text: str, prefix: str) -> str:
        """Prompt metnini geçici bir UTF-8 dosyaya yazar, yolunu döndürür."""
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text or "")
        return path

    def ask(self, prompt: str, extra_system: str, session_id,
            scenario_text: str = None) -> dict:
        """`session_id` None ise yeni oturum açılır (senaryo sistem promptu
        olarak verilir); değilse mevcut oturum --resume ile sürdürülür.

        Uzun metinler komut satırından DEĞİL, geçici dosyalardan geçer
        (`--system-prompt-file` / `--append-system-prompt-file`). Windows'ta
        CreateProcess'in komut satırı sınırı 32767 karakterdir; senaryo metni
        tek başına 35 000 karaktere yaklaştığı için argüman olarak
        geçirildiğinde her yeni oturum `WinError 206` ile düşüyordu. Dosya
        yolu geçmek bu tavanı tamamen ortadan kaldırır.
        """
        gecici = []
        try:
            append_path = self._write_temp(extra_system, "kc-append-")
            gecici.append(append_path)
            cmd = [
                self.binary,
                "-p", prompt,
                "--tools", "",
                "--output-format", "json",
                "--model", self.model,
                "--effort", self.effort,
                "--append-system-prompt-file", append_path,
            ]
            if session_id is None:
                system_path = self._write_temp(scenario_text or "", "kc-system-")
                gecici.append(system_path)
                cmd += ["--system-prompt-file", system_path]
            else:
                cmd += ["--resume", session_id]

            try:
                result = subprocess.run(
                    cmd,
                    cwd=self.cwd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired:
                raise NarratorTimeout()
        finally:
            for path in gecici:
                try:
                    os.unlink(path)
                except OSError:
                    pass

        if result.returncode != 0:
            raise NarratorError(
                f"claude CLI çıkışı {result.returncode}: {result.stderr.strip()[:500]}"
            )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise NarratorError(f"claude CLI çıktısı JSON değil: {result.stdout[:500]}")

        if payload.get("is_error"):
            raise NarratorError(f"claude hata döndürdü: {payload.get('result')}")
        return payload
