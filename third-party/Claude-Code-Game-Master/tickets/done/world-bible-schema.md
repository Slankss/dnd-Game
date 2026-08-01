---
slug: world-bible-schema
title: Define world-bible.json (voice/factions/themes/geography/systems)
category: enhancement
kind: afk
priority: p1
lane: agent
parentPrd: dm-claude-reimagining
blockedBy: [world-kit-schema]
claimedBy: ss-tix001
claimedAt: 2026-06-06T05:09:55Z
changedFiles: [lib/world_bible.py, tests/test_world_bible.py, tests/fixtures/world-state/campaigns/dungeon-crawler-carl/world-bible.json, docs/schema-reference.md]
resolution: world-bible.json schema (voice/tone/themes/factions-graph/geography-graph/timeline/signature_systems) + WorldBible loader + validator; hand-authored DCC bible ships + validates; documented
createdAt: 2026-06-06T02:24:27Z
updatedAt: 2026-06-06T05:09:55Z
---

## Parent

DM Claude Reimagining (prds/dm-claude-reimagining.md)

## Category

enhancement

## What to build

The structured fidelity spine for a world. Define `world-bible.json`: VOICE
(prose style, rhythm, signature vocab, sample passages), TONE, THEMES, FACTIONS
as a graph (allegiances/conflicts/territory), GEOGRAPHY as a place-graph with
real adjacency, TIMELINE, and the book's SIGNATURE SYSTEMS. This is what
auto-drafts the bespoke ruleset + `campaign_rules`. Hand-author one for DCC first
to validate the schema (DCC's `campaign_rules` was hand-written — codify what
made it good).

## Acceptance criteria

- [x] `world-bible.json` schema defined + documented (voice, tone, themes, factions-graph, geography-graph, timeline, signature systems).
- [x] A hand-authored DCC `world-bible.json` validates against the schema.
- [x] Schema maps cleanly onto `ruleset.json` + `campaign_rules` (the auto-draft target in the next ticket). (signature_systems → campaign_rules; the bible drives import-longcontext-read's auto-draft)
- [x] Loadable as the canonical spine at session start (read path defined). (WorldBible loader)
- [x] Test: DCC world-bible loads + the factions/geography graphs parse.

## Verification

Lane: agent

## Blocked by

world-kit-schema

---

## QA Reports

### 2026-06-06T05:09:55Z — pass [ss-tix001]
`uv run pytest` → 102 passed (4 new in tests/test_world_bible.py).
- lib/world_bible.py: validate_bible (requires name/voice/tone/themes/factions-graph/geography-graph/signature_systems; graphs = {nodes,edges}) + WorldBible loader (voice/factions/geography/signature_systems accessors) + CLI validate/show.
- Hand-authored DCC world-bible.json (fixture + live) validates; factions graph (crawlers/system/showrunners + relations) and geography graph (floor1→floor4 stairwell adjacency) parse; voice.style + signature_systems (loot boxes, viewers, Odette interviews, floor-collapse clock) present.
- Validator rejects a non-graph factions block. Schema documented in docs/schema-reference.md.

## History

- 2026-06-06T05:09:55Z  in-progress → done  [ss-tix001]
- 2026-06-06T05:09:55Z  ready → in-progress (claimed)  [ss-tix001]
- 2026-06-06T02:24:27Z  created → ready  [ship-it]
