# 2. Read-only, enforced at the tool layer

- Status: accepted
- Date: 2026-09-02

## Context

The explainer explains code that another agent is changing. If it could edit files,
the thing that explains could change what it explains, and two agents writing the
same files would race.

## Considered options

- State "never edit" in the agent's instructions.
- Refuse writes in the tools the process is allowed to use.

## Decision

The launcher starts the agent with `--allowedTools` limited to reading: `Read`,
`Grep`, `Glob`, web lookups, and an allow-list of read-only shell commands. The
instructions explain the rule; the tool list enforces it.

## Consequences

- An instruction is a request; a missing tool is a refusal.
- The glossary still has to be written. That is done through one purpose-built
  command, not a general `Write` (see [0006](0006-glossary-one-file-per-term.md)).
