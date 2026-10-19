# 13. Resume a closed chat, fork an open one

- Status: accepted
- Date: 2026-10-19

## Context

When the work moves to a new session, the explainer chat that knew its history was
lost. Claude Code can resume a session from any directory, but two processes
resuming the same session interleave their messages into one transcript.

## Considered options

- Always fork.
- Let the person choose between resuming and forking.
- Decide by whether the chat is open, using a lock file or the process table.

## Decision

`explainer --resume` lists the repository's chats, found by the `agentSetting` their
own transcripts record. A closed chat is resumed and pointed at the current work
session; one still open elsewhere is forked into a new session whose id is set in
advance. Open or closed is read from the process table, not from a `flock` lock:
macOS has no `flock` command, and the process table leaves nothing on disk to go stale
after a crash. Both paths rebuild the system prompt, since a resumed session otherwise
reuses the one recorded when it began.

## Consequences

The registry of launched sessions is gone; a transcript identifies itself.
