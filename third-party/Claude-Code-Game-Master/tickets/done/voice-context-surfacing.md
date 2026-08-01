---
slug: voice-context-surfacing
title: "Inject NARRATIVE VOICE block into get_full_context"
category: enhancement
kind: afk
priority: p0
lane: agent
parentPrd: narrative-voice-fidelity
blockedBy: []
claimedBy: ss-w7k2m9
claimedAt: 2026-06-06T20:30:58Z
changedFiles: [lib/session_manager.py, tests/test_voice_surfacing.py]
resolution: "get_full_context emits a NARRATIVE VOICE block (style+vocab+sample passages) from world-bible voice; omitted when no/empty voice"
createdAt: 2026-06-06T20:29:20Z
updatedAt: 2026-06-06T20:31:43Z
---

## Parent

Narrative Voice Fidelity (prds/narrative-voice-fidelity.md)

## Category

enhancement

## What to build

The load-bearing fix: make the world's authorial voice reach the GM every beat.
Add a `--- NARRATIVE VOICE ---` block to `SessionManager.get_full_context`
(`lib/session_manager.py`), built from `WorldBible().voice()`:
- a `Style:` line from `voice.style`,
- up to 3 `sample_passages` as labelled imitation targets ("write in this voice"),
- optionally `vocab` as in-world terms to favor.

Emit the block ONLY when a voice exists (no `world-bible.json`, or empty
`voice`/`style` and no passages → emit nothing, no empty header). Place it near the
top of the narration context (with the other `--- ... ---` blocks, e.g. after the
session header / before CHARACTER) so it frames how the GM writes. Read the bible
via `WorldBible` pointed at the same world-state the session manager uses (respect
its `world_state_dir`).

## Acceptance criteria

- [x] `get_full_context` includes a `--- NARRATIVE VOICE ---` block with the style line + sample passages when the active bible has a non-empty `voice`
- [x] No block (and no stray header) is emitted when there is no bible or the voice is empty
- [x] Passages are presented as imitation targets the GM should write in, not as facts/lore
- [x] Respects the session manager's `world_state_dir` (works against a hermetic test world-state)
- [x] Existing get_full_context content/tests still pass

## Verification

Lane: agent

Pytest with the hermetic world-state pattern: (a) a campaign whose bible has a
voice → assert the block + style + a sample passage appear in `get_full_context`;
(b) a campaign with no bible / empty voice → assert the block is absent.

## Blocked by

None.

---

## QA Reports

### 2026-06-06T20:31:43Z — pass [ss-w7k2m9]
Added the `--- NARRATIVE VOICE ---` block to `get_full_context` (read from `world-bible.json` via the session manager's own `json_ops`, so it respects `world_state_dir`). Block frames passages as a prose target ("narrate in this voice; NOT lore"), shows Style + favored vocab + up to 3 sample passages.
`tests/test_voice_surfacing.py` (3 passed): (a) voice present → block + style + passage + vocab + "NOT lore" present; (b) no bible → no block, no stray header; (c) empty voice → no block. Regression: `test_get_full_context` / `test_scene_context` / `test_story_spine` still green (14 passed).

## History

- 2026-06-06T20:31:43Z  ready → done  [ss-w7k2m9]
- 2026-06-06T20:30:58Z  claimed  [ss-w7k2m9]
- 2026-06-06T20:29:20Z  created → ready  [ship-it]
