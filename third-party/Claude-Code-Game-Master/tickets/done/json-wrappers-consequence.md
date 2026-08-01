---
slug: json-wrappers-consequence
title: --json mode for consequence_manager (check read + add write)
category: enhancement
kind: afk
priority: p1
lane: agent
parentPrd: dm-claude-reimagining
blockedBy: [json-returning-wrappers]
claimedBy: ss-tix001
claimedAt: 2026-06-06T04:50:44Z
changedFiles: [lib/consequence_manager.py, tools/dm-consequence.sh, tests/test_json_wrappers_consequence.py]
resolution: consequence_manager --json envelopes check (read, {pending}) and add (write, {id}); add's [SUCCESS] print suppressed in json mode; dm-consequence.sh forwards --json
createdAt: 2026-06-06T04:10:42Z
updatedAt: 2026-06-06T04:50:44Z
---

## Parent

DM Claude Reimagining (prds/dm-claude-reimagining.md)

## Category

enhancement

## What to build

Wire the shared `cli_output` envelope into consequence_manager. Add `--json` for
a representative read (`check`/`check_pending`) and write (`add`). Pairs naturally
with the reactivity-engine work, which wants structured fired-consequence data.

## Acceptance criteria

- [x] `consequence_manager.py check --json` emits the pending list in the success envelope.
- [x] `add --json` emits a structured success/error envelope (incl. the new consequence id).
- [x] Human output unchanged without `--json`.
- [x] `dm-consequence.sh` passes `--json` through.
- [x] Tests assert envelope shape for the read and the write (hermetic, DCC fixture).

## Verification

Lane: agent

## Blocked by

json-returning-wrappers

---

## QA Reports

### 2026-06-06T04:50:44Z — pass [ss-tix001]
`uv run pytest` → 59 passed (2 new). check --json → {"ok":true,"data":{"pending":[...]}}; add --json → {"data":{"id":...}}. add's [SUCCESS] stdout print is suppressed (redirect_stdout) in json mode so stdout is pure JSON. dm-consequence.sh check forwards "$@" (add already did). Hermetic CLI subprocess test runs the manager with cwd at the fixture's world-state root.

## History

- 2026-06-06T04:50:44Z  in-progress → done  [ss-tix001]
- 2026-06-06T04:50:44Z  ready → in-progress (claimed)  [ss-tix001]
- 2026-06-06T04:10:42Z  created → ready  [ss-tix001]
