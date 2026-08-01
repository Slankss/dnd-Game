---
slug: import-voice-capture
title: "Import bible-draft captures author style + real sample_passages"
category: enhancement
kind: afk
priority: p1
lane: agent
parentPrd: narrative-voice-fidelity
blockedBy: []
claimedBy: ss-w7k2m9
claimedAt: 2026-06-06T20:34:17Z
changedFiles: [lib/book_bible.py, .claude/commands/import.md, tests/test_import_voice.py]
resolution: "book_bible.draft_voice grounds voice.sample_passages to verbatim source excerpts; import Step 6.7 populates the bible voice block + validates"
createdAt: 2026-06-06T20:29:20Z
updatedAt: 2026-06-06T20:35:35Z
---

## Parent

Narrative Voice Fidelity (prds/narrative-voice-fidelity.md)

## Category

enhancement

## What to build

Ensure an imported book's `world-bible.json` `voice` is actually populated from the
source. In the import bible-draft step (`.claude/commands/import.md`, plus any
helper in `lib/book_bible.py`), the draft must set:
- `voice.style` — a concrete prose fingerprint (sentence rhythm, diction,
  imagery) inferred from the book,
- `voice.sample_passages` — 2-3 SHORT real excerpts of the author's prose pulled
  from the source text (grounding the voice, not invented),
- `voice.vocab` — a few signature in-world terms when present.

This is what `voice-context-surfacing` then feeds to the GM. Keep excerpts short
(fair-use sized) and verbatim from the source.

## Acceptance criteria

- [x] The import bible-draft instructions explicitly require populating `voice.style` + `voice.sample_passages` (real excerpts) + optional `voice.vocab`
- [x] A drafted bible from a sample source has a non-empty `voice` with ≥1 sample passage traceable to the source text
- [x] Drafted bible still passes `world_bible.py validate`
- [x] `sample_passages` are verbatim source excerpts, not paraphrase/invention (documented in the step)

## Verification

Lane: agent

Run the bible-draft against a small fixture text containing a distinctive voice;
assert the resulting `voice` has a `style` and ≥1 `sample_passages` entry that
appears in the source, and the bible validates.

## Blocked by

None.

---

## QA Reports

### 2026-06-06T20:35:35Z — pass [ss-w7k2m9]
Added `book_bible.draft_voice(style, sample_passages, source_text, vocab)` — keeps only passages that appear VERBATIM in the source (drops invented/paraphrased), so an imported voice is the author's real prose. Added import Step 6.7 (REQUIRED): infer `voice.style`, supply verbatim excerpts through `draft_voice`, merge into `world-bible.json`, validate.
`tests/test_import_voice.py` (3 passed): verbatim-only filtering (non-source line dropped), the voice block yields a valid bible (`validate_bible`), and zero invented passages survive when none match. `test_book_bible_import.py` still green (6 passed). Feeds `voice-context-surfacing`.

## History

- 2026-06-06T20:35:35Z  ready → done  [ss-w7k2m9]
- 2026-06-06T20:34:17Z  claimed  [ss-w7k2m9]
- 2026-06-06T19:54:09Z  created → ready  [ship-it]
