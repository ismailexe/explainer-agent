# 4. Install by symlink, not as a plugin

- Status: accepted
- Date: 2026-09-02

## Context

The explainer is a launcher, a few scripts, two agent definitions and a slash command,
installed into `~/.claude/`. The main entry point is a shell command, `explainer`,
which has to be on the user's `PATH`.

## Considered options

- A Claude Code plugin from a marketplace.
- A repository whose `install.sh` symlinks its files into `~/.claude/`.
- A repository whose `install.sh` copies them.

## Decision

Symlink. Editing the repository edits the running agent, with no second copy to drift,
and a file the installer would replace is kept as `<name>.pre-explainer-agent`.

## Consequences

- No one-command install from a marketplace.
- `install.sh` never edits the user's shell profile; it prints the lines to add, for
  `PATH` and, under zsh, a `noglob` alias.
