# 5. Claude Code only, with one module that knows its layout

- Status: accepted
- Date: 2026-09-02

## Context

The explainer depends on Claude Code's on-disk layout — where transcripts and memory
live, how directories are named — and on a subagent primitive that other harnesses do
not have. That layout is internal to Claude Code and can change.

## Considered options

- Abstract over several harnesses now.
- Support Claude Code only, but keep its layout in one place.

## Decision

Claude Code only. `bin/explainer_layout.py` is the single module that knows the
layout; every other script, the bash launcher included, asks it for paths.

## Consequences

- A layout change in Claude Code is fixed in one file.
- Supporting another harness would mean replacing that module, not threading changes
  through the rest.
