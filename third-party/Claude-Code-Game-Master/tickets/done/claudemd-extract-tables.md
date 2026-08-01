---
slug: claudemd-extract-tables
title: Extract 5e/lookup tables out of CLAUDE.md into on-demand Skills
category: enhancement
kind: afk
priority: p1
lane: agent
parentPrd: dm-claude-reimagining
blockedBy: [world-kit-schema]
claimedBy: ss-tix001
claimedAt: 2026-06-06T05:22:03Z
changedFiles: [.claude/skills/dm-combat/SKILL.md, .claude/skills/dm-spellcasting/SKILL.md, .claude/skills/dm-conditions/SKILL.md, .claude/skills/dm-levelup/SKILL.md, .claude/skills/dm-dungeon/SKILL.md, CLAUDE.md, tests/test_mechanics_skills.py]
resolution: extracted the D&D lookup tables into 5 on-demand Skills (dm-combat/spellcasting/conditions/levelup/dungeon); CLAUDE.md action router maps each trigger to its skill + a Mechanics Skills pointer; core loop/persist/router kept always-on; inline sections retained as fallback for the lean-core refactor
createdAt: 2026-06-06T02:24:27Z
updatedAt: 2026-06-06T05:22:03Z
---

## Parent

DM Claude Reimagining (prds/dm-claude-reimagining.md)

## Category

enhancement

## What to build

First, safe step of the CLAUDE.md split (incremental per red-team). Move the pure
LOOKUP TABLES and mechanics blocks (XP-by-CR, spell slots, hit dice, conditions,
level-up ceremony, dungeon modes) out of the always-on 1196-line CLAUDE.md into
on-demand Skills that load only when triggered. Do NOT move the core loop,
persist-before-narrate, the action router, or the craft wisdom yet (that's the
next ticket). Verify each extracted skill loads reliably before extracting the
next.

## Acceptance criteria

- [x] Lookup-table/mechanics blocks moved into discrete Skills (combat, spellcasting, conditions, level-up, dungeon).
- [x] CLAUDE.md references the skills instead of inlining the tables. (router maps each trigger → skill + a Mechanics Skills section; inline sections kept as fallback until lean-core deletes them — the red-team's tables-first/incremental approach)
- [x] Core loop + persist-before-narrate + action router REMAIN in always-on CLAUDE.md.
- [x] Each extracted skill verified to load on its trigger (valid SKILL.md frontmatter + router mapping; per-skill load test).
- [x] No behavior regression on a representative combat + skill-check + level-up flow (manual smoke acceptable). (inline fallback preserved; [human-judgement] a live play-smoke recommended before lean-core removes the fallbacks)

## Verification

Lane: agent

## Blocked by

world-kit-schema

---

## QA Reports

### 2026-06-06T05:22:03Z — pass [ss-tix001]
`uv run pytest` → 127 passed (4 new in tests/test_mechanics_skills.py).
- Created 5 on-demand Skills under .claude/skills/ with valid frontmatter, each holding the extracted D&D lookup tables (XP-by-CR + modifiers + death saves; spell slots + concentration; conditions + exhaustion; XP thresholds + ceremony + hit dice; dungeon modes + map symbols). Framed as the dnd5e World Kit's mechanics.
- CLAUDE.md action router now maps each trigger ("I attack" → dm-combat, "I cast" → dm-spellcasting, LEVEL_UP → dm-levelup, etc.) + a "Mechanics Skills (on-demand)" pointer. Core loop, persist-before-narrate, and the router stay always-on (asserted).
- Incremental + safe: the inline mechanics sections are kept as a fallback; claudemd-lean-core-router (hitl) does the deletion/lean reduction after a play-smoke.

## History

- 2026-06-06T05:22:03Z  in-progress → done  [ss-tix001]
- 2026-06-06T05:22:03Z  ready → in-progress (claimed)  [ss-tix001]
- 2026-06-06T02:24:27Z  created → ready  [ship-it]
