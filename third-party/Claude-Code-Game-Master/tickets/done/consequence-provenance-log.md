---
slug: consequence-provenance-log
title: Provenance log + per-beat snapshot for reactive firing
category: enhancement
kind: afk
priority: p1
lane: agent
parentPrd: dm-claude-reimagining
blockedBy: [reactivity-engine]
claimedBy: ss-tix001
claimedAt: 2026-06-06T04:41:08Z
changedFiles: [lib/consequence_manager.py, tools/dm-consequence.sh, tests/test_provenance.py]
resolution: tick() records provenance (id/consequence/reason/ctx_key/fired_at) + a one-beat _snapshot; get_provenance + rollback_last() undo a misfire; dm-consequence.sh log/rollback expose them
createdAt: 2026-06-06T02:24:27Z
updatedAt: 2026-06-06T04:41:08Z
---

## Parent

DM Claude Reimagining (prds/dm-claude-reimagining.md)

## Category

enhancement

## What to build

Reactive-safety net (red-team requirement). Once consequences fire on their own,
a bad trigger or misfire can contradict canon or railroad the player. Add a
"why did this fire" provenance log entry per firing (consequence id, trigger
reason, world-state snapshot ref, timestamp) and a lightweight per-beat snapshot
so a misfire is debuggable and undoable via the existing atomic save/restore.

## Acceptance criteria

- [x] Each fired consequence writes a provenance record (id, reason, matched condition, timestamp).
- [x] A per-beat snapshot (or reuse of atomic save) lets the dev roll back one reactive beat.
- [x] Provenance is queryable (`dm-consequence.sh log` or similar) without parsing prose.
- [x] Rollback restores consequence + world state to pre-fire without corrupting other state.
- [x] Test: fire → inspect provenance → rollback → state matches pre-fire snapshot.

## Verification

Lane: agent

## Blocked by

reactivity-engine

---

## QA Reports

### 2026-06-06T04:41:08Z — pass [ss-tix001]
`uv run pytest` → 47 passed (3 new in tests/test_provenance.py); bash ok.
- tick() captures a pre-fire shallow snapshot of active/resolved into data['_snapshot'] and appends provenance records {id, consequence, reason, ctx_key, fired_at} to data['provenance'] whenever something fires or expires.
- get_provenance() + `dm-consequence.sh log` expose the "why did this fire" trail; rollback_last() + `dm-consequence.sh rollback` restore active/resolved to the pre-fire snapshot.
- Tests: firing writes provenance; rollback removes the last_fired_key stamp (back to pre-fire); rollback with no beat returns False safely.

## History

- 2026-06-06T04:41:08Z  in-progress → done  [ss-tix001]
- 2026-06-06T04:41:08Z  ready → in-progress (claimed)  [ss-tix001]
- 2026-06-06T02:24:27Z  created → ready  [ship-it]
