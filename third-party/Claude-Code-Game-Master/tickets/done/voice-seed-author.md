---
slug: voice-seed-author
title: "/new-game seed asks author to channel; skeleton authors voice"
category: enhancement
kind: afk
priority: p1
lane: agent
parentPrd: narrative-voice-fidelity
blockedBy: []
claimedBy: ss-w7k2m9
claimedAt: 2026-06-06T20:32:43Z
changedFiles: [.claude/commands/new-game.md]
resolution: "/new-game Phase A asks voice_exemplar (genre-adaptive authors); Phase B authors the bible voice block (style + original imitation passages) from it"
createdAt: 2026-06-06T20:29:20Z
updatedAt: 2026-06-06T20:33:32Z
---

## Parent

Narrative Voice Fidelity (prds/narrative-voice-fidelity.md)

## Category

enhancement

## What to build

Give original worlds an explicit authorial voice to channel. In `/new-game`
(`.claude/commands/new-game.md`):
- Phase A questionnaire gains a **voice** question — "Whose voice should this world
  channel?" with genre-appropriate suggestions (Howard / Tolkien / Le Guin /
  Gibson / Pratchett / free text). Store as `voice_exemplar` in `world-seed.json`.
- Phase B skeleton authoring is instructed to write the bible `voice` block from
  the exemplar: a `style` fingerprint that imitates that author + 2-3 original
  `sample_passages` written in that voice (NOT copied from the author).
- The `culture` axis (when present) deepens `voice.vocab` / additional passages.

Pairs with `voice-context-surfacing`, which surfaces this block at play.

## Acceptance criteria

- [x] Phase A asks the voice/author question and records `voice_exemplar` in the `world-seed.json` shape
- [x] Phase B instructs authoring `voice.style` (imitating the exemplar) + 2-3 original `sample_passages` in that voice
- [x] Suggested exemplars are genre-adaptive (tied to the chosen bend), free-text allowed
- [x] `sample_passages` for originals are explicitly original imitation, not the author's real text (avoids copying)
- [x] The `world-seed.json` example in the command shows `voice_exemplar`

## Verification

Lane: agent

Inspect the rewritten command: assert the voice question + `voice_exemplar` seed
field + Phase-B voice-authoring instructions are present and coherent. (Live feel
is judged in the manual dry-run alongside new-game-orchestration.)

## Blocked by

None.

---

## QA Reports

### 2026-06-06T20:33:32Z — pass [ss-w7k2m9]
Extended `.claude/commands/new-game.md`: Phase A adds the "Whose voice should this world be narrated in?" question with genre-adaptive exemplars (Howard / Tolkien / Le Guin / Gibson / Pratchett + free text) → `voice_exemplar` in the `world-seed.json` example; Phase B authors the bible `voice` block from it — concrete `style` fingerprint imitating the exemplar + 2-3 SHORT original imitation `sample_passages` (explicitly NOT copied from the real author) + `vocab`, with culture axis deepening. Structural grep checks all green; seed example shows `voice_exemplar`. (Feeds `voice-context-surfacing`, which surfaces the block at play.)

## History

- 2026-06-06T20:33:32Z  ready → done  [ss-w7k2m9]
- 2026-06-06T20:32:43Z  claimed  [ss-w7k2m9]
- 2026-06-06T20:29:20Z  created → ready  [ship-it]
