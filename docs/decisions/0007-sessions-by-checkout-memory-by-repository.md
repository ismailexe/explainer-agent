# 7. Sessions are scoped by checkout, memory by repository

- Status: accepted
- Date: 2026-09-02

## Context

Two bugs shaped this. Choosing "a session opened in this directory or above it" made
every session ever opened in `$HOME` a candidate, so an unrelated project's
conversation could be explained in confident detail. Fixing that by bounding at the
main worktree then hid a linked worktree's own session from its subdirectories, since
the main worktree's path is not a prefix of the linked one's. One boundary was being
used to answer two different questions.

## Decision

- Which sessions are mine: the current checkout, `worktree_root()`.
- Which project's memory: the repository, `main_worktree()`, resolved exactly with
  `git rev-parse --git-common-dir`, since every worktree shares it.

When no session is in scope, the launcher fails loudly instead of guessing.

## Consequences

Four worktrees can run four work sessions at once without seeing one another, while
all of them share one memory. Both boundaries are locked by tests.
