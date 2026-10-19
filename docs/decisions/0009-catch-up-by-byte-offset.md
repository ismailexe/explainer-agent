# 9. Catch up by byte offset, not by clock time

- Status: accepted
- Date: 2026-09-09

## Context

A follow-up question needs only what the work session added since the last look.
`--since HH:MM` worked, at about 1,800 tokens instead of 5,000 for re-reading recent
turns, but only if the model remembered the time of its last look — a chore of the
kind [0008](0008-deterministic-work-in-code.md) moved out of the prompt.

## Considered options

- The model passes the time of its last look.
- The script keeps the position itself.
- Stream the transcript live.

## Decision

`transcript-tail.py --new` keeps a byte offset per chat and per transcript and
consumes only whole lines. Each position is a file of its own, written atomically, so
two chats saving at once cannot erase each other's update.

## Consequences

- About 4,000 tokens for a first look and about 100 for a follow-up.
- No live streaming: reading takes a tenth of a second while the model takes ten
  seconds or more, and streaming would need a process running all the time.
