---
slug: threat-clock-seeding
title: Seed headline threat clocks from the book at import
category: enhancement
kind: afk
priority: p1
lane: agent
parentPrd: import-pipeline-hardening
blockedBy: []
claimedBy: ss-7q3w9z
claimedAt: 2026-06-06T17:12:00Z
changedFiles: [lib/clock_seed.py, lib/threat_clocks.py, tools/dm-extract.sh, .claude/commands/import.md, tests/test_clock_seed.py]
resolution: dm-extract.sh seed-clocks detects "N days" + pressure-word in plots and seeds real threat_clocks entries (segments + consequence + linked_plot); add_clock extended with optional consequence/linked_plot; live seeded the 10-day Iron Tangle collapse clock
createdAt: 2026-06-06T16:47:47Z
updatedAt: 2026-06-06T17:14:57Z
---

## Parent

prds/import-pipeline-hardening.md

## Category

enhancement

## What to build

`lib/threat_clocks.py` exists as a system (named pressure; full clock = beat due) but
import seeds ZERO clocks. The book's headline pressure (DCC: the 10-day floor
collapse) lives only as prose inside a plot description, not as an actual clock that
drives the world. Add an import step that extracts the book's primary time/pressure
threats and creates real threat-clock entries (name, size/segments, what a full clock
triggers, link to the driving plot). At minimum seed the dominant clock; capture
secondary clocks where the source is explicit.

## Acceptance criteria

- [x] Import creates ≥1 threat-clock entry from the source's headline pressure.
- [x] DCC import seeds the 10-day Iron Tangle collapse clock with sensible segments + a full-clock consequence.
- [x] Each seeded clock links to its driving plot/location where applicable.
- [x] Clocks are real `threat_clocks` entries (queryable via the existing tooling), not prose.
- [x] Seeding is reported to the user during import.

## Verification

Lane: agent

## Blocked by

None.

---

## QA Reports

### 2026-06-06T17:14:57Z — pass [ss-7q3w9z]
5 unit tests in tests/test_clock_seed.py pass: detects "collapse in 10 days" → segments 10
linked to plot; ignores day-count w/o pressure word; ignores pressure w/o day-count; seed
creates real entry with consequence+linked_plot; add_clock back-compat (7 test_threat_clocks
regression tests still pass). Live smoke: seed-clocks on anarchists-cookbook created
"Collapse (10 days)" (max 10, advance_on time, consequence from the plot, linked to "Survive
and Escape the Iron Tangle (Fourth Floor)") in threat-clocks.json. import seeds after the
integrity gate.

## History

- 2026-06-06T16:47:47Z  created → ready  [ship-it]
- 2026-06-06T17:12:00Z  claimed  [ss-7q3w9z]
- 2026-06-06T17:14:57Z  done  [ss-7q3w9z]
