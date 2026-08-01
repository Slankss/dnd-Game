---
slug: untruncate-campaign-rules
title: Stop truncating campaign_rules in session context
category: enhancement
kind: afk
priority: p0
lane: agent
parentPrd: dm-claude-reimagining
blockedBy: [test-harness-scaffold]
claimedBy: ss-tix001
claimedAt: 2026-06-06T02:44:35Z
changedFiles: [lib/session_manager.py, tests/test_untruncate_rules.py]
resolution: render campaign_rules in full under a "YOUR WORLD'S RULES (follow exactly)" block — removed the 220-char truncation, nested systems pretty-printed, opt-in token observability via DM_DEBUG_CONTEXT
createdAt: 2026-06-06T02:24:27Z
updatedAt: 2026-06-06T02:44:35Z
---

## Parent

DM Claude Reimagining (prds/dm-claude-reimagining.md)

## Category

enhancement

## What to build

Highest-ROI fix in the roadmap. `get_full_context` truncates every
`campaign_rules` value to 220 chars (near `session_manager.py:468`), so the DM is
told "follow your world's rules exactly" while shown only half of them
(`dm_checklist`, `achievement_checks`, `opening_ceremony`, `reaction_types` are
cut). Render the full `campaign_rules` as a distinct, clearly-labeled
"YOUR WORLD'S RULES — follow exactly" block with NO truncation. Soft token
target is guidance only; never a silent cutoff.

## Acceptance criteria

- [x] `campaign_rules` values are emitted in full (no 220-char cut) in `get_full_context`.
- [x] Rules render as their own labeled block, visually separate from the NPC/consequence summaries.
- [x] Running `bash tools/dm-session.sh context` on DCC shows the full `loot_box_system`, `audience_system`, `interview_system` text with no trailing `...`.
- [x] Optional token count of the context block is logged/observable (no enforced ceiling).
- [x] Characterization snapshot from `test-harness-scaffold` updated intentionally; new test asserts a known full-rule substring is present.

## Verification

Lane: agent

## Blocked by

test-harness-scaffold

---

## QA Reports

### 2026-06-06T02:44:35Z — pass [ss-tix001]
`uv run pytest` → 11 passed (3 new in tests/test_untruncate_rules.py). Evidence:
- Replaced the `self._truncate(str(val), 220, full)` calls in the Campaign Rules block with full rendering under a new "YOUR WORLD'S RULES (follow exactly)" label; nested dict/list systems pretty-printed via json.dumps(indent=2).
- Live check: `bash tools/dm-session.sh context` on DCC now shows the full loot_box_system incl. achievement_checks / opening_ceremony / dm_checklist (all previously starved at 220 chars); no "use --full" rule marker.
- Token observability: opt-in `DM_DEBUG_CONTEXT=1` prints `[context] ~N tokens` to stderr — guidance only, no hard cut.
- Adversarial: test_deep_rule_content_survives_no_truncation asserts content (dm_checklist, Celestial Quest Box) that lives well past char 220 — fails against the pre-fix truncating code, not a mirror of the impl.

## History

- 2026-06-06T02:44:35Z  in-progress → done  [ss-tix001]
- 2026-06-06T02:44:35Z  ready → in-progress (claimed)  [ss-tix001]
- 2026-06-06T02:24:27Z  created → ready  [ship-it]
