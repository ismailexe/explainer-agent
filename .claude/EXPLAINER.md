# Explainer agent — briefing for the explainer agent

This repository is the explainer agent itself: a read-only second agent that
answers "what did that mean?" about a live Claude Code conversation without
polluting it. The user invokes it, it reads the main session's transcript from
disk, verifies the answer against the repo, and replies in Turkish with English
terminology — always giving the *industry* name for a repo-local one, so the
user can search for the concept himself. That last part is the reason the project
exists; everything else is plumbing.

## Notes outside the repo

- `EXPLAINER-AGENT-BRIEF.md` — in the repo, but written in Turkish as a handover
  note rather than as a repo artifact. It holds the problem statement, the
  measured platform facts, the design decisions with their reasons, the prior-art
  survey, and the open questions. **Read it before answering anything about why
  this project is shaped the way it is.** Two of its measurements are now known to
  be wrong; see the traps below.

## Local name → industry term

| Local name | What it is here | Search for |
|---|---|---|
| `transcript` | the JSONL file Claude Code appends every session to | `session log`, `JSONL` (JSON Lines) |
| `slug` | `~/.claude/projects` directory name derived from a path | `path sanitization`, `derived key` |
| `sidechain` | transcript lines belonging to a subagent, not the main thread | `subagent`, `sub-conversation` |
| `sources inventory` | what `--sources` prints: every place worth reading | `bootstrap manifest`, `context discovery` |
| second-eyes role | the agent contradicting the main agent when the code disagrees | `critic-actor`, `LLM-as-judge` |
| `memory/` | per-project notes holding the *why* behind past decisions | `long-term memory`, `retrieval` |
| `glossary/` | terms already explained here, one file per term | `memoization`, `cache` |
| `install.sh`'s linking | `~/.claude` pointing into this repo instead of holding copies | `symlink install`, `dev-mode install` (the copying alternative is `vendoring`) |
| `--resolve-target` | picking which conversation to explain, before claude starts | — |
| `--candidates` | the free Python filter in front of the researcher | `gate`, `early exit`, `speculative prefetch` |
| `--new` / cursor | reading only what was appended since the last look | `cursor`, `high-water mark`, `incremental read` |
| `provenance` | whether an entry was checked against the repo or only web-searched | `provenance`, `data lineage` |
| `run mode` (`chat`/`once`) | open session vs one printed answer | — |

## Conflict rule

`EXPLAINER-AGENT-BRIEF.md` states the intent and the design decisions; the code
states what actually happens. When they disagree the **code wins on behaviour**
and the brief wins on **intent** — and say out loud that they diverge, because a
stale brief is the failure mode this project is most exposed to.

## Traps

- The brief's §4.1 says the slug replaces `/` with `-`. Measured against all 57
  project directories on this machine, that rule holds for 27 of them. The real
  rule is every character outside `[A-Za-z0-9]`, which is what
  `bin/transcript-tail.py` implements.
- The brief's §4.5 suggests finding the memory directory by scanning for project
  slugs containing the repo name. That is ambiguous here — two slugs contain
  `order-service`, with 2 and 58 memory files. The code resolves the main
  worktree path exactly via `git rev-parse --path-format=absolute
  --git-common-dir` and only falls back to a name scan.
- The files under `~/.claude/` are symlinks into this repo, created by
  `install.sh`. Editing either path edits the same file; there is no second copy
  to keep in sync.
- `bin/explainer_layout.py` is the only module that knows Claude Code's on-disk
  layout. Do not build a `~/.claude/...` path anywhere else — ask it, including
  from bash (`explainer_layout.py project-dir`).
- Session scoping bit twice. First, `$HOME` is an ancestor of every path, so a
  session opened there was resolved as the conversation to explain. Then the fix
  for that used the *main* worktree as the boundary, which hid a worktree's own
  session from every subdirectory of that worktree. There are two boundaries and
  they are not the same: `worktree_root()` answers "which sessions are mine"
  (per checkout), `main_worktree()` answers "which project's memory" (shared by
  every worktree). `SessionScope` and `WorktreeSessionScope` in the test file
  lock both.
- A transcript is written while the session runs, so its last line can be half
  flushed. Any JSON parse error is skipped silently on purpose.
- Catching up is a **cursor** (`--new`), not a timestamp the model passes. Same
  reason as below: `--since HH:MM` worked but made catching up something the model
  could forget. Byte offsets, keyed by chat, only whole lines consumed.
- Background research is a **command** (`explainer-research`), not something the
  explainer does while answering. It was written into the explainer's prompt
  first; measured across three real questions it fired zero times out of three.
  Do not move it back into the prompt — deciding *when* is deterministic and
  belongs in a script; only deciding *what* needs a model.
- `--candidates` looks only at prose in a recent window. Both narrowings were
  forced by measurement: mining tool calls put the repo's own directory name at
  the top with 660 mentions, and reading the whole transcript produced 1139
  candidates. A filter cannot tell a field name from a concept — that is the
  researcher's job, and skipping most of a list is the correct outcome.
