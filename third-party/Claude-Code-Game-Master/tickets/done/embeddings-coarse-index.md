---
slug: embeddings-coarse-index
title: Demote embeddings to a coarse chapter index; pluggable embedder
category: enhancement
kind: afk
priority: p2
lane: agent
parentPrd: dm-claude-reimagining
blockedBy: [import-longcontext-read]
claimedBy: ss-tix001
claimedAt: 2026-06-06T05:13:48Z
changedFiles: [lib/rag/coarse_index.py, tests/test_coarse_index.py]
resolution: CoarseIndex indexes at chapter granularity and returns POINTERS into the retained text (load_chapter resolves them); embedder pluggable via config (keyword default = no heavy deps; model name loads lazily); query templates branch literary vs game-module
createdAt: 2026-06-06T02:24:27Z
updatedAt: 2026-06-06T05:13:48Z
---

## Parent

DM Claude Reimagining (prds/dm-claude-reimagining.md)

## Category

enhancement

## What to build

Stop routing fidelity through weak MiniLM 3000-char chunks. Demote embeddings to
a COARSE chapter index whose job is only to point INTO the retained text (which
long-context reading then consumes). Make the embedder pluggable and branch query
templates by content type (literary vs game-module) so importing a novel stops
dragging retrieval toward D&D stat-block vocabulary.

## Acceptance criteria

- [x] Embedding store indexes at chapter/section granularity pointing into the kept text, not fidelity-bearing 3000-char chunks.
- [x] Embedder is pluggable via config (swap model without code changes).
- [x] Query templates branch by content type (literary vs game-module).
- [x] Retrieval returns chapter pointers that the long-context reader can load.
- [x] Test: index a sample text → query → returns the right chapter pointer.

## Verification

Lane: agent

## Blocked by

import-longcontext-read

---

## QA Reports

### 2026-06-06T05:13:48Z — pass [ss-tix001]
`uv run pytest` → 113 passed (5 new in tests/test_coarse_index.py).
- lib/rag/coarse_index.py CoarseIndex.build segments via book_bible (chapter spans); query() returns {index,title,score} POINTERS, not text; load_chapter() resolves a pointer to the full chapter the long-context reader loads.
- Embedder pluggable: "keyword" default (no sentence-transformers needed), a model name loads lazily (kept out of tests). _template branches game-module (rules/mechanics vocab) vs literary (scene/atmosphere) so novel imports stop pulling toward stat-block vocab.
- Tests: query returns the right chapter; pointers not blobs (but resolve to full text); template branching; no-match → [].

## History

- 2026-06-06T05:13:48Z  in-progress → done  [ss-tix001]
- 2026-06-06T05:13:48Z  ready → in-progress (claimed)  [ss-tix001]
- 2026-06-06T02:24:27Z  created → ready  [ship-it]
