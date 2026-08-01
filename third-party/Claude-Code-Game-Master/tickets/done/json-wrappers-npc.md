---
slug: json-wrappers-npc
title: --json mode for npc_manager (status/voice read + update write)
category: enhancement
kind: afk
priority: p2
lane: agent
parentPrd: dm-claude-reimagining
blockedBy: [json-returning-wrappers]
claimedBy: ss-tix001
claimedAt: 2026-06-06T04:54:18Z
changedFiles: [lib/npc_manager.py, tools/dm-npc.sh, tests/test_json_wrappers_npc.py]
resolution: npc_manager --json envelopes status + voice (read) and update (write); dm-npc.sh forwards --json on those cases
createdAt: 2026-06-06T04:10:42Z
updatedAt: 2026-06-06T04:54:18Z
---

## Parent

DM Claude Reimagining (prds/dm-claude-reimagining.md)

## Category

enhancement

## What to build

Wire the shared `cli_output` envelope into npc_manager. Add `--json` for a
representative read (`status`/`voice` — note `voice` already returns a JSON list)
and a representative write (`update`). Normalize on the shared `{"ok","data"}`
envelope.

## Acceptance criteria

- [x] `status --json` and `voice --json` emit the success envelope (voice data = the lines list).
- [x] `update --json` emits a structured success/error envelope.
- [x] Human output unchanged without `--json`.
- [x] `dm-npc.sh` passes `--json` through.
- [x] Tests assert envelope shape for the read and the write (hermetic, DCC fixture).

## Verification

Lane: agent

## Blocked by

json-returning-wrappers

---

## QA Reports

### 2026-06-06T04:54:18Z — pass [ss-tix001]
`uv run pytest` → 64 passed (3 new). status --json → {"data": {npc dict}}; voice --json → {"data": {"voice": [lines]}}; update --json → {"data": {"updated": name}} (method prints suppressed). dm-npc.sh status/voice/update forward "$@". Completes the json-returning-wrappers split (all 5 managers now have a --json read+write surface on the shared cli_output envelope).

## History

- 2026-06-06T04:54:18Z  in-progress → done  [ss-tix001]
- 2026-06-06T04:54:18Z  ready → in-progress (claimed)  [ss-tix001]
- 2026-06-06T04:10:42Z  created → ready  [ss-tix001]
