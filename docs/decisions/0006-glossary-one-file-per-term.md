# 6. A glossary, one file per term, written through its own command

- Status: accepted
- Date: 2026-09-02

## Context

Asked about the same term twice, the explainer derived the answer again from scratch,
which costs a research pass and can come out differently.

## Decision

Keep a glossary per project: one Markdown file per term, under the project's entry in
Claude Code's projects tree. The explainer reads it first and records a term once it
has named its industry counterpart. It writes only through `explainer-glossary.py`,
which refuses to overwrite an entry silently.

## Consequences

- The glossary is personal and never committed. A table a team shares belongs in the
  repository's `EXPLAINER.md`; the two are kept distinct, after the agent once
  mistook one for the other.
- Entries carry a provenance: `verified` against the repository, or `auto` from a
  background web lookup that never read the code.
