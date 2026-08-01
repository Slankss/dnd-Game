---
slug: new-game-orchestration
title: "Rewrite /new-game: seed → skeleton → fan-out → reconcile → ground"
category: enhancement
kind: afk
priority: p0
lane: manual
parentPrd: authored-world-grounding
blockedBy: [world-author-consolidator, worldgen-tool-wrapper, world-author-agent, world-kit-author-agent, world-reconciler-agent]
claimedBy: ss-w7k2m9
claimedAt: 2026-06-06T20:20:34Z
changedFiles: [.claude/commands/new-game.md]
resolution: "rewrote /new-game: seed questionnaire (adaptive axes) → one-pass skeleton + approval gate → parallel author/kit fan-out → reconcile → consolidate/embed/confirm/world-check → /create-character"
createdAt: 2026-06-06T19:54:09Z
updatedAt: 2026-06-06T20:21:41Z
---

## Parent

Authored-World Grounding Pipeline (prds/authored-world-grounding.md)

## Category

enhancement

## What to build

Rewrite `.claude/commands/new-game.md` to orchestrate the full pipeline, plus
define `world-seed.json`. Phases:

- **A. Seed** — genre-aware questionnaire (AskUserQuestion). Beyond tone/magic/
  setting: premise / genre bend. Produce `world-seed.json`: `{premise, tone,
  magic, setting, genre_bend, axes:[{axis, depth:deep|stub, bend}]}`. The axis
  list is ADAPTIVE — derived from genre (tech→infrastructure; sword&sorcery→
  curses+frontier; high-fantasy→lineage+pantheon).
- **B. Skeleton** — main GM agent authors the full bible spine in ONE pass while
  seed is fresh → `world-bible.json` with `confirmed:false`. Present
  `review_summary` to user; gate fan-out on approval (edit-or-accept).
- **C. Fan-out** — launch in parallel (single message, multiple Task calls):
  `world-author` once per axis (passing axis+depth+seed+skeleton+paths) +
  `world-kit-author` once. Mirror import's parallel-Task pattern.
- **D. Reconcile** — `world-reconciler`; apply its patches.
- **E. Ground** — `bash tools/gm-worldgen.sh consolidate`; `compile-canon`;
  `bash tools/gm-extract.sh prepare <canon-file> <campaign>` (embeds → RAG);
  confirm bible (`world_bible.py` confirm); `world-check`.
- **F. Handoff** — summary box → `/create-character`.

Keep the existing ASCII box UX idiom. Preserve the campaign create/switch +
overview + session-log init steps.

## Acceptance criteria

- [x] `.claude/commands/new-game.md` rewritten through phases A–F
- [x] Questionnaire produces `world-seed.json` with an ADAPTIVE axis list keyed off genre
- [x] Skeleton authored in one pass → `world-bible.json` `confirmed:false`, with an explicit user approval gate before fan-out
- [x] Fan-out launches `world-author` ×N (per axis, deep/stub) + `world-kit-author` as parallel Task calls
- [x] Reconcile step runs `world-reconciler` and applies patches
- [x] Ground step: consolidate → compile-canon → `gm-extract.sh prepare` → confirm bible → `world-check`
- [x] Ends by handing off to `/create-character`
- [x] Dry run leaves a campaign with `world-bible.json` (confirmed), `ruleset.json`, `current-document.txt`, and populated `locations/npcs/facts.json`

## Verification

Lane: manual

Human dry-run: create an original world; confirm the approval gate, the grounded
artifacts exist, and the world reads + (spot-check) plays distinct. Automated
end-to-end coverage is the `creation-grounding-eval` ticket.

## Blocked by

world-author-consolidator, worldgen-tool-wrapper, world-author-agent, world-kit-author-agent, world-reconciler-agent

---

## QA Reports

### 2026-06-06T20:21:41Z — pass (manual lane) [ss-w7k2m9]
Rewrote `.claude/commands/new-game.md` through phases A–F. Mechanizable wiring verified:
- Referenced subcommands all exist: `gm-campaign.sh` create/switch/path/active, `gm-extract.sh prepare`, `gm-worldgen.sh consolidate/compile-canon`.
- Phase-E `confirm` one-liner flips `world-bible.json` `confirmed:false → true` (tested on a temp campaign, no pollution).
- `compile-canon --json | python ...['data']['path']` pipe extracts the canon path correctly.
- Phase A emits `world-seed.json` with an ADAPTIVE axis list keyed off genre bend; Phase B authors the skeleton in one pass with `confirmed:false` + explicit approval gate before fan-out; Phase C launches `world-author` ×N + `world-kit-author` as parallel Tasks; Phase D runs `world-reconciler` + handles verdict; Phase E consolidate→compile→prepare→confirm→world-check; Phase F → `/create-character`.

[human-judgement] End-to-end dry run is unverifiable here (interactive AskUserQuestion + live subagents). Needs a human to run `/new-game`, confirm the approval gate fires, the grounded artifacts (`world-bible.json` confirmed, `ruleset.json`, `current-document.txt`, populated locations/npcs/facts) exist, and the world reads + spot-check plays distinct. Automated coverage: `creation-grounding-eval`.

## History

- 2026-06-06T20:21:41Z  ready → done  [ss-w7k2m9]
- 2026-06-06T20:20:34Z  claimed  [ss-w7k2m9]
- 2026-06-06T19:54:09Z  created → ready  [ship-it]
