---
slug: identity-onboarding-schema-drift
title: identity_onboarding builds nested identity.* but schema is now flat
category: bug
kind: afk
priority: p2
lane: agent
parentPrd: null
blockedBy: []
claimedBy: null
claimedAt: null
changedFiles: []
resolution: null
createdAt: 2026-06-07T21:50:00Z
updatedAt: 2026-06-07T21:50:00Z
---

## Category

bug

## What to build

Found incidentally during the canvas work (full pytest run): one pre-existing
failure unrelated to the canvas.

`tests/test_identity_onboarding.py::test_build_dispatches_and_saves` fails with
`KeyError: 'identity'`. The test expects `char["identity"]["name"]`, but the
character schema was flattened to a top-level `name` in commit efd1cb7 ("Refactor
character schema handling"). Either `lib/identity_onboarding.py` still emits a
nested `identity.*` block that no longer matches the runtime schema, or the test
is stale. Decide which is canonical (the live `character.json` is flat — `name`,
`race`, `class` at top level) and reconcile.

## Acceptance criteria

- [ ] Decide canonical shape (flat top-level fields, matching live character.json).
- [ ] `lib/identity_onboarding.py` output matches the canonical schema.
- [ ] `tests/test_identity_onboarding.py::test_build_dispatches_and_saves` passes.
- [ ] Full pytest suite green (no regressions elsewhere).

## Verification

Lane: agent

## Blocked by

None.

---

## QA Reports

<!-- newest first -->

## History

- 2026-06-07T21:50:00Z  created → needs-triage  [ss-cnvs01]
