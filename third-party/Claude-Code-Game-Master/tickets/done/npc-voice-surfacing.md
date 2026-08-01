---
slug: npc-voice-surfacing
title: Surface canonical NPC voice at the speaking moment
category: enhancement
kind: afk
priority: p1
lane: agent
parentPrd: dm-claude-reimagining
blockedBy: [story-spine-context]
claimedBy: ss-tix001
claimedAt: 2026-06-06T04:02:06Z
changedFiles: [lib/npc_manager.py, lib/session_manager.py, tools/dm-npc.sh, tests/test_npc_voice.py]
resolution: NPCManager.get_voice + `dm-npc.sh voice <name>` return canonical dialogue; get_full_context surfaces an NPC VOICES block for present NPCs (party + location-tagged), read-only
createdAt: 2026-06-06T02:24:27Z
updatedAt: 2026-06-06T04:02:06Z
---

## Parent

DM Claude Reimagining (prds/dm-claude-reimagining.md)

## Category

enhancement

## What to build

Turn the most magical unused asset into immersion. The NPC `context` field
already stores verbatim book dialogue (e.g. Mordecai's actual lines) but is
loaded by nothing during play. Surface present-NPC voice lines in
`get_full_context`, plus a `dm-npc.sh voice <name>` the DM calls right before an
NPC speaks. PROTECT the canonical-voice extraction — read it, never overwrite it.

## Acceptance criteria

- [x] `dm-npc.sh voice <name>` returns the NPC's canonical voice lines / descriptor (structured JSON per the wrappers ticket if landed, else plain).
- [x] `get_full_context` includes voice snippets for NPCs at the current location.
- [x] No mutation of the existing NPC `context` field.
- [x] Graceful when an NPC has no voice data (empty, no error).
- [x] Test: DCC fixture surfaces a known Mordecai/Donut line when that NPC is present.

## Verification

Lane: agent

## Blocked by

story-spine-context

---

## QA Reports

### 2026-06-06T04:02:06Z — pass [ss-tix001]
`uv run pytest` → 20 passed (4 new in tests/test_npc_voice.py); `bash -n tools/dm-npc.sh` ok.
- NPCManager.get_voice(name): returns the `context` dialogue list (None if NPC missing, [] if no voice); read-only.
- CLI: added `voice` subparser + handler (JSON output) and a `voice)` case + usage line in dm-npc.sh. Live: `dm-npc.sh voice Mordecai` → his canonical lines; missing NPC → "[ERROR] ... not found" + exit 1 (no crash).
- get_full_context: new `_present_npc_voices` helper surfaces an "NPC VOICES" block for present NPCs (party members + NPCs tagged to current location), ≤2 lines each (full=all). Live DCC shows Carl/Donut/Mongo speaking in their own words.
- Read-only guard: test asserts npcs.json byte-identical after get_voice + get_full_context.
- Adversarial: the read-only test would fail if surfacing mutated `context`; the value assertions pull exact source lines the old code never loaded.

## History

- 2026-06-06T04:02:06Z  in-progress → done  [ss-tix001]
- 2026-06-06T04:02:06Z  ready → in-progress (claimed)  [ss-tix001]
- 2026-06-06T02:24:27Z  created → ready  [ship-it]
