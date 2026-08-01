#!/usr/bin/env python3
"""Seed headline threat clocks from the book at import time.

`threat_clocks` exists as a system but import seeds zero clocks, so the book's
headline pressure (e.g. the 10-day Iron Tangle collapse) lives only as prose inside
a plot description. This scans plots for explicit time/countdown pressure and seeds
real threat-clock entries (segments + full-clock consequence + linked plot).
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# "...collapse in 10 days...", "10 days before...", "countdown of 7 days", etc.
_DAYS_RE = re.compile(r"(\d{1,3})\s*days?", re.IGNORECASE)
_PRESSURE_WORDS = ("collapse", "countdown", "timer", "before the", "runs out",
                   "destroyed", "deadline", "days left", "explode")


def detect_time_pressure(plots: dict):
    """Return a list of suggested clocks from plot descriptions.

    Each: {name, segments, advance_on, consequence, linked_plot}. Only plots whose
    description contains both a day-count and a pressure word produce a clock.
    """
    suggestions = []
    seen = set()
    for pname, plot in (plots or {}).items():
        if not isinstance(plot, dict):
            continue
        desc = (plot.get("description") or "")
        low = desc.lower()
        if not any(w in low for w in _PRESSURE_WORDS):
            continue
        m = _DAYS_RE.search(desc)
        if not m:
            continue
        days = int(m.group(1))
        if days <= 0 or days > 365:
            continue
        # Clock name: derive from the pressure, keep it short + unique.
        base = "Collapse" if "collapse" in low else "Countdown"
        cname = f"{base} ({days} days)"
        if cname in seen:
            continue
        seen.add(cname)
        # consequence: prefer the plot's own stated consequence, else a generic one.
        consequence = plot.get("consequences") or f"The {days}-day timer runs out — catastrophe."
        if isinstance(consequence, list):
            consequence = "; ".join(str(c) for c in consequence)
        suggestions.append({
            "name": cname,
            "segments": days,
            "advance_on": "time",
            "consequence": consequence[:300],
            "linked_plot": pname,
        })
    return suggestions


def seed_clocks(world_state_dir, clocks) -> int:
    """Create the given clocks via ThreatClockManager (active campaign). Returns count."""
    from threat_clocks import ThreatClockManager
    mgr = ThreatClockManager(world_state_dir)
    n = 0
    for c in clocks:
        mgr.add_clock(c["name"], c["segments"], advance_on=c.get("advance_on", "time"),
                      consequence=c.get("consequence"), linked_plot=c.get("linked_plot"))
        n += 1
    return n


def seed_from_campaign(world_state_dir, campaign_dir) -> dict:
    """Detect pressure in the campaign's plots and seed clocks. Returns a report."""
    plots_path = Path(campaign_dir) / "plots.json"
    plots = json.loads(plots_path.read_text()) if plots_path.exists() else {}
    suggestions = detect_time_pressure(plots)
    count = seed_clocks(world_state_dir, suggestions) if suggestions else 0
    return {"seeded": count, "clocks": suggestions}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Seed threat clocks from plots")
    parser.add_argument("campaign_dir")
    parser.add_argument("--world-state", default="world-state")
    args = parser.parse_args()
    report = seed_from_campaign(args.world_state, args.campaign_dir)
    print(f"  seeded {report['seeded']} clock(s)")
    for c in report["clocks"]:
        print(f"    - {c['name']} (linked: {c['linked_plot']})")


if __name__ == "__main__":
    main()
