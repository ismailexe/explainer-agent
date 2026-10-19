# 10. Follow the working agent across worktrees

- Status: accepted
- Date: 2026-10-19

## Context

The working agent can move to another worktree or branch in the middle of a session,
often without saying so. The explainer checked claims against its own checkout, so it
reported correct work as missing: in the eval case for this, it said the working agent
had claimed changes it never made, 3 runs out of 3.

## Decision

- Bind the conversation by session id and find its file again on every read, since
  `/cd` moves a transcript.
- Take the working agent's location from the `cwd` of the latest transcript entry, and
  the branch from git at that moment rather than from the transcript.
- Head every read with that location, mark entries written from another checkout, and
  hand all worktrees to the process with `--add-dir`.
- Resolve project knowledge — `EXPLAINER.md`, memory, glossary — from where the working
  agent is; keep the explainer's own bookkeeping where it was opened.

## Consequences

The eval case passes 3 of 3. A worktree created after launch is still readable with
`Read` and `grep`, but not with `cat`.
