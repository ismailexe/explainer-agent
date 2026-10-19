# 14. promptfoo, with judges running on Claude Code

- Status: accepted
- Date: 2026-10-19

## Context

Every change to the instructions was a guess until the answers could be measured.
The suite has to run the real launcher, isolate every case from the machine it runs
on, and grade answers without an API key.

## Considered options

- A small harness of our own in Python.
- promptfoo, with a Python provider and a Python grading provider.

## Decision

promptfoo, as a development-only dependency run through `npx` with a pinned version.
The provider builds a fresh world per case and removes the explainer's session with
`claude purge`; judges run through `claude -p` in safe mode on the user's own login.
Length, language and citations are checked in code, everything else by one pass/fail
judge per criterion.

## Consequences

- Installing the explainer still needs only Claude Code and Python 3.
- A full run spends the user's own usage, about eight minutes for three runs a case.
