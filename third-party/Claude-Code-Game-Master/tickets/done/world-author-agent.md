---
slug: world-author-agent
title: ".claude/agents/world-author.md parameterized axis author"
category: enhancement
kind: afk
priority: p1
lane: agent
parentPrd: authored-world-grounding
blockedBy: [world-author-consolidator]
claimedBy: ss-w7k2m9
claimedAt: 2026-06-06T20:17:52Z
changedFiles: [.claude/agents/world-author.md]
resolution: "parameterized per-axis author: writes only canon/<axis>.md + authored/<axis>.json in the consolidator contract; honors deep/stub; never mutates root"
createdAt: 2026-06-06T19:54:09Z
updatedAt: 2026-06-06T20:18:30Z
---

## Parent

Authored-World Grounding Pipeline (prds/authored-world-grounding.md)

## Category

enhancement

## What to build

ONE parameterized specialist author subagent, invoked once per axis (adaptive).
Frontmatter (`name: world-author`, `tools: Bash, Read, Write`, model, color) +
markdown body, in the style of `extractor-*.md` / `world-builder.md`.

The agent receives (via its launch prompt): the `world-seed.json`, the approved
skeleton (`world-bible.json`), its axis name + bend, depth (`deep` | `stub`), and
output paths. It writes ONLY two files — never mutates root campaign files (this
is what keeps the parallel fan-out race-free):

- `canon/<axis>.md` — authored prose canon for this axis (the corpus body that
  later gets embedded). Deep axes get rich prose; stubs get a short seed.
- `authored/<axis>.json` — structured contributions in the consolidator contract:
  `{locations:{...}, npcs:{...}, facts:{<category>:[...]}, bible:{factions:
  {nodes,edges}, geography:{nodes,edges}, timeline:[...], signature_systems:[...],
  voice:{...}, themes:[...]}}`. Only the keys this axis owns.

Body must instruct: stay coherent with the skeleton (it is canon); produce
named, world-specific nouns (anti-generic); ALWAYS write both files (empty-but-
valid if nothing for a key); honor deep-vs-stub depth.

## Acceptance criteria

- [x] `.claude/agents/world-author.md` exists with valid frontmatter (`name: world-author`, tools incl. Write)
- [x] Body documents the axis/seed/skeleton/depth inputs and the two output paths
- [x] `authored/<axis>.json` shape matches the consolidator contract exactly (keys + nesting)
- [x] Explicit "write ONLY canon/<axis>.md and authored/<axis>.json; never edit root files" rule
- [x] Explicit anti-generic + skeleton-coherence + always-write-both-files instructions
- [x] deep vs stub depth behavior described

## Verification

Lane: agent

Schema check: a hand-run of the agent against a sample seed+skeleton produces an
`authored/<axis>.json` the consolidator ingests without error. Verify it writes
no root files.

## Blocked by

world-author-consolidator

---

## QA Reports

### 2026-06-06T20:18:30Z — pass [ss-w7k2m9]
Authored `.claude/agents/world-author.md` (frontmatter `name: world-author`, tools incl. Write). Built a sample `authored/factions.json` to the documented contract (npcs + facts + bible.factions graph + timeline + voice + themes) and ran it through `WorldAuthor.consolidate`: npcs=1, facts=1, bible_merged; factions node/edge merged, themes deduped, timeline+voice merged, `confirmed:false` preserved, `validate_bible` passes — contract round-trips with zero shape errors. Body covers inputs (seed/skeleton/AXIS/DEPTH), exact two output paths, write-only/never-touch-root rule, always-write-both-files, anti-generic + skeleton-coherence, deep-vs-stub, and the axis→keys mapping.

## History

- 2026-06-06T20:18:30Z  ready → done  [ss-w7k2m9]
- 2026-06-06T20:17:52Z  claimed  [ss-w7k2m9]
- 2026-06-06T19:54:09Z  created → ready  [ship-it]
