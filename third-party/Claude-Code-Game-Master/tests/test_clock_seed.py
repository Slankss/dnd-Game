"""Tests for threat-clock-seeding: detect time pressure + seed clocks."""

from lib.clock_seed import detect_time_pressure, seed_clocks
from lib.threat_clocks import ThreatClockManager


def test_detects_collapse_day_count():
    plots = {
        "Survive the Iron Tangle": {
            "description": "The floor will collapse in 10 days (half the usual 20).",
            "consequences": "Death by collapse.",
        }
    }
    sugg = detect_time_pressure(plots)
    assert len(sugg) == 1
    assert sugg[0]["segments"] == 10
    assert sugg[0]["linked_plot"] == "Survive the Iron Tangle"
    assert "collapse" in sugg[0]["consequence"].lower()


def test_ignores_day_count_without_pressure_word():
    plots = {"Idle": {"description": "They rested for 3 days in the inn."}}
    assert detect_time_pressure(plots) == []


def test_ignores_pressure_without_day_count():
    plots = {"Vague": {"description": "Everything will collapse eventually."}}
    assert detect_time_pressure(plots) == []


def test_seed_clocks_creates_real_entries_with_metadata(dcc_world):
    mgr = ThreatClockManager(dcc_world)
    seeded = seed_clocks(dcc_world, [{
        "name": "Collapse (10 days)", "segments": 10, "advance_on": "time",
        "consequence": "The floor collapses; everyone dies.", "linked_plot": "Survive the Iron Tangle",
    }])
    assert seeded == 1
    clocks = mgr.get_clocks()
    assert "Collapse (10 days)" in clocks
    c = clocks["Collapse (10 days)"]
    assert c["max"] == 10
    assert c["consequence"].startswith("The floor collapses")
    assert c["linked_plot"] == "Survive the Iron Tangle"


def test_add_clock_backcompat_without_metadata(dcc_world):
    # Existing 2-arg callers must still work.
    mgr = ThreatClockManager(dcc_world)
    entry = mgr.add_clock("Doom", 4)
    assert entry["max"] == 4
    assert "consequence" not in entry
