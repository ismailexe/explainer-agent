# 3. Run as a separate `claude` process, not a subagent

- Status: accepted
- Date: 2026-09-02

## Context

The first version ran as a subagent behind `/explain`. A subagent's report returns to
the agent that started it, so every explanation travelled back through the working
agent and stayed in its context — the pollution the project exists to avoid. The
person also wanted a conversation kept open beside the work, not one answer at a time.

## Considered options

- A subagent whose answer the working agent is told to relay verbatim.
- An independent `claude` process in a second terminal, reading the work session's
  transcript from disk.

## Decision

`bin/explainer` starts its own `claude --agent explainer` process. It resolves which
conversation to explain before starting, while the work session is still the newest
transcript in that directory. `/explain` only prints the command to run; it does not
open a window, because a window spawned from inside a full-screen IDE was seen to
open out of sight while reporting success.

## Consequences

- Nothing the explainer says ever enters the working conversation.
- It cannot talk back either: anything the working agent should hear is pasted over
  by the person.
- The explainer must catch up before every answer, because the work session keeps
  moving while the chat is open.
