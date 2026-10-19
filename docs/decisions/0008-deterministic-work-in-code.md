# 8. Deterministic work in code, judgment in the model

- Status: accepted
- Date: 2026-09-02

## Context

Background research was first written into the explainer's instructions: after
answering, look up the new names. Across three real questions it ran zero times, and
moving the instruction before the answer did not help. With a question in front of
it, a model answers the question and skips the optional chore.

## Decision

Whatever must always happen is done by code; the model is given only what needs
judgment. `bin/explainer-research` decides *when* research is worth starting, with a
free filter; the researcher agent decides *what* is worth looking up.

## Consequences

The same rule placed several later pieces in code: the catch-up position
([0009](0009-catch-up-by-byte-offset.md)), the launch briefing, the compaction view,
and the decision to resume or fork a chat ([0013](0013-resume-closed-fork-open.md)).
