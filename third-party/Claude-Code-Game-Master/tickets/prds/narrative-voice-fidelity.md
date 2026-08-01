---
slug: narrative-voice-fidelity
title: Narrative Voice Fidelity — GM narrates in the author's voice
status: active
version: 1
supersedes: null
createdAt: 2026-06-06T20:29:20Z
updatedAt: 2026-06-06T20:29:20Z
---

## Problem Statement

The GM does not narrate in the world's authorial voice. Traced in code:
`world-bible.json` carries a `voice` block (`style` / `vocab` / `sample_passages`)
and `WorldBible.voice()` exists, but the ONLY runtime reader is the import-draft
code + `review_summary`. The narration path —
`session_manager.get_full_context` → `scene_context` → `gm-context.sh` (the front
door the GM reads every beat) — has ZERO references to the bible voice (grep
confirms). The GM gets per-NPC canonical lines (NPC VOICES), so NPC *dialogue* is
grounded, but the GM's own *prose* voice is not. The author's voice sits in a JSON
file the narrator never opens.

Two upstream gaps feed this:
- **Imports**: the bible-draft does not reliably capture the author's voice
  (`book_bible.py` has no voice assembly; `sample_passages` often empty).
- **Originals**: `/new-game` captures `genre_bend` but never asks whose voice to
  channel; the skeleton authors a `voice` block with no exemplar to imitate.

Result: a Conan world should read like Robert E. Howard and a Tolkien-flavored
world like Tolkien — instead both default to generic narrator prose.

## Solution

Make the author's voice a first-class, surfaced, and used artifact:

1. **Surface it (load-bearing):** inject a `NARRATIVE VOICE` block (style +
   sample_passages) into `get_full_context`, so every beat the GM reads HOW to
   write, not just what is true. Nothing else matters without this.
2. **Capture — imports:** the import bible-draft populates `voice.style` + real
   `sample_passages` excerpts of the author's prose.
3. **Capture — originals:** `/new-game` asks whose voice to channel (Howard /
   Tolkien / Le Guin / Gibson / Pratchett / free text) → seed `voice_exemplar` →
   the skeleton + culture axis author `style` + imitation `sample_passages`.
4. **Craft:** `gm-craft` points at the `NARRATIVE VOICE` block as the prose target.

## User Stories

1. As a player of an imported book, I want the GM to narrate in that book's prose
   voice, so play feels like being inside the book.
2. As a player of an original world, I want to pick an author whose voice the GM
   channels, so my world has a distinct literary feel instead of generic narration.
3. As the GM at play time, I want the world's voice (style + sample passages) in my
   scene context every beat, so I can actually write in it.

## Implementation Decisions

- `get_full_context` (`lib/session_manager.py`) gains a `--- NARRATIVE VOICE ---`
  block built from `WorldBible().voice()` — `style` line + up to N `sample_passages`
  as imitation targets. Emitted only when a voice exists (no bible / no voice → no
  block). This is the keystone; other tickets feed it.
- Import voice capture lives in the bible-draft step (`.claude/commands/import.md`
  + any `book_bible.py` helper): `voice.style` + 2-3 real source excerpts.
- Original voice capture: `/new-game` seed gains `voice_exemplar`; the skeleton's
  `voice` block + the culture axis author imitation passages.
- `gm-craft` references the block as the narration target.

## Testing Decisions

- **agent**: `get_full_context` includes `NARRATIVE VOICE` with style+passages when
  the bible has a voice, and omits it cleanly when absent (extend the grounding /
  scene-context tests). Seed shape includes `voice_exemplar`. Import draft yields a
  non-empty `voice`.
- **manual**: does the GM actually narrate in voice at play (Howard vs Tolkien
  reads distinct)? Human-judgement at a dry-run.

## Out of Scope

- No change to NPC canonical-line surfacing (already works).
- No automated prose-style scorer (a future guard; not now).
- No new voice storage format — reuse `world-bible.voice`.

## Further Notes

Sibling to `authored-world-grounding`: that PRD grounds *facts/mechanics*; this one
grounds *voice*. #1 (surfacing) changes behavior; 2-4 feed it.
