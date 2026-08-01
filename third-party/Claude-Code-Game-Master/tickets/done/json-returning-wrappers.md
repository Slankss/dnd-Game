---
slug: json-returning-wrappers
title: Bash wrappers / managers return structured JSON
category: enhancement
kind: afk
priority: p1
lane: agent
parentPrd: dm-claude-reimagining
blockedBy: [test-harness-scaffold]
claimedBy: ss-tix001
claimedAt: 2026-06-06T04:10:42Z
changedFiles: [lib/cli_output.py, lib/search.py, tests/test_cli_output_json.py]
resolution: shared cli_output {"ok","data"|"error"} envelope + wired search.py --json (the search slice); per-manager wiring split into json-wrappers-{session,consequence,player,npc}
createdAt: 2026-06-06T02:24:27Z
updatedAt: 2026-06-06T04:10:42Z
---

## Parent

DM Claude Reimagining (prds/dm-claude-reimagining.md)

## Category

enhancement

## What to build

NARROWED (split decision): this ticket delivers the FOUNDATION — a shared
`cli_output` envelope — plus the **search** slice (which unblocks
scene-context-consolidation). The other four managers are split into their own
ready tickets: json-wrappers-session, json-wrappers-consequence,
json-wrappers-player, json-wrappers-npc.

Kill the stdout-scraping + prefix/typo bug classes without adding a process
(no MCP): a stable `{"ok", "data"|"error"}` envelope managers opt into via
`--json`, human-readable output preserved as default.

## Acceptance criteria

- [x] Shared `cli_output` exposes a stable success/error envelope (`wants_json`, `strip_json_flag`, `emit`, `emit_error`).
- [x] `search.py --json` returns the envelope (the search slice for scene-context-consolidation).
- [x] Error cases return structured `{"ok": false, "error": ...}` instead of bare stderr text.
- [x] Existing human-readable output preserved as default (no regression to interactive use).
- [x] Tests assert JSON shape for the envelope + a representative search read (hermetic).
- [x] Per-manager wiring filed as sub-tickets (session/consequence/player/npc) blocked on this foundation.

## Verification

Lane: agent

## Blocked by

test-harness-scaffold

---

## QA Reports

### 2026-06-06T04:10:42Z — pass [ss-tix001]
`uv run pytest` → 26 passed (6 new in tests/test_cli_output_json.py). Scope narrowed via user split decision.
- New lib/cli_output.py: `wants_json` (flag or DM_JSON=1), `strip_json_flag`, `emit` (success envelope or human message), `emit_error` (returns 1 for `sys.exit(emit_error(...))`).
- Wired search.py `--json`: regular + tag searches emit `{"ok": true, "data": {...}}`; no-query → `{"ok": false, "error": ...}`. Live: `python lib/search.py dragon --json` → valid envelope with keys facts/npcs/locations/consequences/plots/related_plots. Human mode (no flag) unchanged.
- Tests: envelope unit tests (success/human/error/exit-code/flag detection) + hermetic WorldSearcher(dcc_world).search_all read.
- Remaining per-manager wiring intentionally deferred to json-wrappers-{session,consequence,player,npc} (ready/, blocked on this). dm-search.sh full --json merge folds into the search work there; search.py --json (what scene-context-consolidation needs) is done.

## History

- 2026-06-06T04:10:42Z  in-progress → done  [ss-tix001]
- 2026-06-06T04:10:42Z  ready → in-progress (claimed)  [ss-tix001]
- 2026-06-06T02:24:27Z  created → ready  [ship-it]
