"""Tests for json-wrappers-consequence: --json envelope over check (read) + add (write)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run_cli(dcc_world, *args):
    """Run consequence_manager CLI against the fixture campaign via DM_JSON + env."""
    env = {
        **__import__("os").environ,
        "VIRTUAL_ENV": "",
    }
    # Point the manager at the fixture by running from a cwd whose world-state is the fixture.
    return subprocess.run(
        [sys.executable, str(ROOT / "lib" / "consequence_manager.py"), *args],
        capture_output=True, text=True, cwd=dcc_world_root(dcc_world), env=env,
    )


def dcc_world_root(dcc_world):
    # dcc_world is <tmp>/world-state; the manager expects to find world-state under cwd.
    return str(Path(dcc_world).parent)


def test_check_json_envelope(dcc_world):
    r = _run_cli(dcc_world, "check", "--json")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["ok"] is True and "pending" in d["data"]
    assert isinstance(d["data"]["pending"], list)


def test_add_json_envelope_returns_id(dcc_world):
    r = _run_cli(dcc_world, "add", "A new omen", "next dawn", "--json")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["ok"] is True and d["data"]["id"]
