# 11. One verdict per claim

- Status: accepted
- Date: 2026-10-19

## Context

The instructions allowed two states: verified, or "could not verify". Asked about
something that never happened, the explainer said in one answer that it had not
happened and that it could not verify that — and suggested a question for the working
agent that repeated the false premise. It also labelled claims unverified that one
read would have settled.

## Considered options

- Add a rule for questions about past events.
- Three verdicts, taken from fact-checking work (FEVER) and from Claude Code's own
  review prompt, plus a premise check before answering.

## Decision

Each claim gets exactly one verdict, stated first: verified with the line quoted,
verified absent with where it looked, or unverified with why. A question is restated
neutrally and its assumption checked before it is answered; a false premise is
corrected in the first sentence and never carried into a suggested question. A claim
one or two reads can settle is read. A decision's recorded reason counts as verified
once the record is read.

## Consequences

The last rule was added after the stricter verdicts made the explainer doubt a
documented reason — an over-correction the eval caught.
