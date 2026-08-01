---
slug: world-reconciler-agent
title: ".claude/agents/world-reconciler.md critic + agreement + crosslink"
category: enhancement
kind: afk
priority: p1
lane: manual
parentPrd: authored-world-grounding
blockedBy: [world-author-agent, world-kit-author-agent]
claimedBy: ss-w7k2m9
claimedAt: 2026-06-06T20:19:17Z
changedFiles: [.claude/agents/world-reconciler.md]
resolution: "reconciler agent: genericness critic + kit↔flavor agreement + cross-link, emits reconcile-report.json with verdict"
createdAt: 2026-06-06T19:54:09Z
updatedAt: 2026-06-06T20:19:51Z
---

## Parent

Authored-World Grounding Pipeline (prds/authored-world-grounding.md)

## Category

enhancement

## What to build

The anti-drift pass. Subagent that runs after fan-out, before consolidate. Reads
seed + skeleton + all `authored/*.json` + `canon/*.md` + `ruleset.json`. Performs
three checks and emits a patch report (`reconcile-report.json` or applied edits
to the authored files):

1. **Genericness critic** — flag any content that could appear in any generic
   fantasy world (no world-specific noun, no genre bend). Kick back / rewrite to
   the seed's distinct commitments.
2. **Kit↔flavor agreement** — verify `ruleset.json` actually encodes the magic /
   tech the lore describes (e.g. lore says blood-priced curses but kit still has
   Vancian slots → flag). The world must PLAY distinct, not just READ distinct.
3. **Graph cross-link** — connect faction/geography/npc graphs across axes:
   NPCs → factions, faction edges → geography, dangling references resolved.

Frontmatter + body like the other agents.

## Acceptance criteria

- [x] `.claude/agents/world-reconciler.md` exists with valid frontmatter
- [x] Body specifies the three checks (genericness, kit↔flavor, cross-link) with concrete kick-back criteria
- [x] Emits a machine-readable report (or applies edits) the orchestration can act on
- [x] Cross-link rules connect NPCs↔factions↔geography across separate `authored/*.json`
- [x] Genericness criterion is concrete enough to catch a generic NPC/location (manual judgement note)

## Verification

Lane: manual

Human judgement: run against a deliberately-generic authored set and a distinct
one; confirm the critic flags the generic and passes the distinct, and that
kit↔flavor disagreement is caught. Log as human-judgement note.

## Blocked by

world-author-agent, world-kit-author-agent

---

## QA Reports

### 2026-06-06T20:19:51Z — pass (manual lane) [ss-w7k2m9]
Authored `.claude/agents/world-reconciler.md`. Structural self-check: valid frontmatter (`name: world-reconciler`, tools incl. Write); all three checks present with concrete fail criteria (genericness, kit↔flavor, cross-link); embedded `reconcile-report.json` schema parses as valid JSON and carries `verdict`; cross-link rules connect NPC→faction / faction→geo across separate `authored/*.json`; explicit "NEVER edit world-bible/locations/npcs/facts.json" rule (consolidation owns those).

[human-judgement] The genericness-critic EFFICACY is unverifiable without a live run: needs a human to run the agent against (a) a deliberately-generic authored set and (b) a distinct one, and confirm it flags the generic, passes the distinct, and catches a planted kit↔flavor disagreement. Logged for manual review at orchestration dry-run time (new-game-orchestration / creation-grounding-eval).

## History

- 2026-06-06T20:19:51Z  ready → done  [ss-w7k2m9]
- 2026-06-06T20:19:17Z  claimed  [ss-w7k2m9]
- 2026-06-06T19:54:09Z  created → ready  [ship-it]
