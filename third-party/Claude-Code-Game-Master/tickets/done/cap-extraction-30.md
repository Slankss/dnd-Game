---
slug: cap-extraction-30
title: Cap extraction to top-30 per type, importance-ranked
category: enhancement
kind: afk
priority: p1
lane: agent
parentPrd: import-pipeline-hardening
blockedBy: []
claimedBy: ss-7q3w9z
claimedAt: 2026-06-06T16:54:00Z
changedFiles: [lib/extraction_cap.py, tools/dm-extract.sh, .claude/commands/import.md, tests/test_extraction_cap.py]
resolution: dm-extract.sh cap caps each type to top-N (default 30) by mention-frequency + plot-reference/party boost; main cast survives because main plots reference them; dropped counts reported; import Step 6 runs it before enhancement
createdAt: 2026-06-06T16:37:48Z
updatedAt: 2026-06-06T16:56:22Z
---

## Parent

prds/import-pipeline-hardening.md

## Category

enhancement

## What to build

Cap each extracted type (npcs, locations, items, plots) at 30 entities, keeping the
30 MOST PLAYABLE. Selection = importance ranking, not naive first-30 or raw agent
dump. Ranking signal: source mention-frequency + main-cast / load-bearing priority
(protagonist party, recurring antagonists, hub locations, signature items, main
plotlines). Apply as a post-extraction filter (deterministic, in
`lib/agent_extractor.py` / a normalize step) so it is independent of agent judgment.
Log how many of each type were dropped.

## Acceptance criteria

- [x] Each of npcs/locations/items/plots written to campaign root has ≤30 entries.
- [x] Kept set chosen by importance score (mention-frequency + main-cast/load-bearing weight), not file order.
- [x] Main cast / protagonist party never dropped (e.g. for a DCC import: Carl, Donut, Mordecai, Katia, Mongo present if extracted).
- [x] Dropped count per type is logged/reported to the user during import.
- [x] Cap is configurable (constant or flag), defaulting to 30.

## Verification

Lane: agent

## Blocked by

None.

---

## QA Reports

### 2026-06-06T16:56:22Z — pass [ss-7q3w9z]
7 unit tests in tests/test_extraction_cap.py pass: plot-referenced entity survives over
high-mention noise; party member survives; no cap under limit; plots rank main>optional;
exactly-limit kept; plot-ref names normalized; cap_campaign writes capped file + report.
Smoke on a COPY of the real anarchists-cookbook data: npcs 65→30 with Carl/Donut/Mordecai/
Katia/Mongo all retained; items 37→30; locations(29)/plots(23) under cap untouched; dropped
counts printed. Live campaign not mutated.

## History

- 2026-06-06T16:37:48Z  created → ready  [ship-it]
- 2026-06-06T16:54:00Z  claimed  [ss-7q3w9z]
- 2026-06-06T16:56:22Z  done  [ss-7q3w9z]
