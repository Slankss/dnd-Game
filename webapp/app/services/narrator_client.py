"""Anlatıcı modeliyle konuşan tek nokta: `claude` CLI süreci.

Sunucunun geri kalanı subprocess bilmez; sadece `NarratorClient.ask(...)`
çağırır ve sözlük alır. Hata halinde servis dilindeki istisnalar atılır.
"""

import json
import subprocess

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

    def ask(self, prompt: str, extra_system: str, session_id,
            scenario_text: str = None) -> dict:
        """`session_id` None ise yeni oturum açılır (senaryo sistem promptu
        olarak verilir); değilse mevcut oturum --resume ile sürdürülür."""
        cmd = [
            self.binary,
            "-p", prompt,
            "--tools", "",
            "--output-format", "json",
            "--model", self.model,
            "--effort", self.effort,
            "--append-system-prompt", extra_system,
        ]
        if session_id is None:
            cmd += ["--system-prompt", scenario_text or ""]
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
