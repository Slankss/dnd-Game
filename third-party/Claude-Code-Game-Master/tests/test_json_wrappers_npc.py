"""Tests for json-wrappers-npc: --json envelope over status/voice (read) + update (write)."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(dcc_world, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / "lib" / "npc_manager.py"), *args],
        capture_output=True, text=True, cwd=str(Path(dcc_world).parent), env={**os.environ},
    )


def test_status_read_envelope(dcc_world):
    r = _run(dcc_world, "status", "Mordecai", "--json")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["ok"] is True and isinstance(d["data"], dict)


def test_voice_read_envelope(dcc_world):
    r = _run(dcc_world, "voice", "Mordecai", "--json")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["ok"] is True and isinstance(d["data"]["voice"], list) and d["data"]["voice"]


def test_update_write_envelope(dcc_world):
    r = _run(dcc_world, "update", "Mordecai", "tested an event", "--json")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["ok"] is True and d["data"]["updated"] == "Mordecai"
