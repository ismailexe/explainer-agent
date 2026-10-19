# Explainer agent — briefing for the explainer agent

This repository is the explainer agent itself: a read-only second agent that
answers "what did that mean?" about a live Claude Code conversation without
polluting it. The person invokes it, it reads the main session's transcript from
disk, verifies the answer against the repository, and replies in their language with
English terminology — always giving the *industry* name for a repo-local one, so they
can search for the concept themselves. That last part is the reason the project
exists; everything else is plumbing.

## Documents

- `docs/design.md` — why the project is shaped the way it is: the problem, the
  measured platform facts, the decisions with their reasons, the bugs that changed
  the design, the prior art. **Read it before answering anything about why.**
- `docs/roadmap.md` — findings A to N from real use, what was done about each, and
  the measured eval results.
- `evals/README.md` — the answer-quality suite and how a case is graded.

## Local name → industry term

| Local name | What it is here | Search for |
|---|---|---|
| `transcript` | the JSONL file Claude Code appends every session to | `session log`, `JSONL` (JSON Lines) |
| `slug` | `~/.claude/projects` directory name derived from a path | `path sanitization`, `derived key` |
| `sidechain` | transcript lines belonging to a subagent, not the main thread | `subagent`, `sub-conversation` |
| `sources inventory` | what `--sources` prints: every place worth reading | `bootstrap manifest`, `context discovery` |
| briefing | what the launcher builds in code and appends to the system prompt | `context injection`, `system prompt augmentation` |
| second-eyes role | the agent contradicting the main agent when the code disagrees | `critic-actor`, `LLM-as-judge` |
| verdicts | verified / verified absent / unverified, one per claim | `claim verification`, `FEVER labels` |
| `memory/` | per-project notes holding the *why* behind past decisions | `long-term memory`, `retrieval` |
| `glossary/` | terms already explained here, one file per term | `memoization`, `cache` |
| `install.sh`'s linking | `~/.claude` pointing into this repo instead of holding copies | `symlink install`, `dev-mode install` (the copying alternative is `vendoring`) |
| `--resolve-target` | picking which conversation to explain, before claude starts | — |
| `work_dir()` | where the main agent is working now; project knowledge follows it | — |
| `--resume` | bringing an earlier chat back, or forking it when still open | `session resume`, `fork` |
| `--forgotten` | each compaction summary beside the user's words from before it | `context compaction`, `context rot` |
| `--candidates` | the free Python filter in front of the researcher | `gate`, `early exit`, `speculative prefetch` |
| `--new` / cursor | reading only what was appended since the last look | `cursor`, `high-water mark`, `incremental read` |
| `provenance` | whether an entry was checked against the repo or only web-searched | `provenance`, `data lineage` |
| `run mode` (`chat`/`once`) | open session vs one printed answer | — |

## Conflict rule

`docs/design.md` and `docs/roadmap.md` state the intent and the decisions; the code
states what actually happens. When they disagree the **code wins on behaviour** and
the documents win on **intent** — and say out loud that they diverge, because a
stale document is the failure mode this project is most exposed to.

## Traps

- The files under `~/.claude/` are symlinks into this repo, created by
  `install.sh`. Editing either path edits the same file; there is no second copy
  to keep in sync.
- `bin/explainer_layout.py` is the only module that knows Claude Code's on-disk
  layout. Do not build a `~/.claude/...` path anywhere else — ask it, including
  from bash (`explainer_layout.py project-dir`).
- Session scoping bit twice. There are two boundaries and they are not the same:
  `worktree_root()` answers "which sessions are mine" (per checkout),
  `main_worktree()` answers "which project's memory" (shared by every worktree).
  `SessionScope` and `WorktreeSessionScope` in the test file lock both.
- Explainer transcripts are recognised by their own `agentSetting`. There is no
  registry of explainer sessions any more; do not add one back.
- A transcript is written while the session runs, so its last line can be half
  flushed. Any JSON parse error is skipped silently on purpose.
- Catching up is a **cursor** (`--new`), not a timestamp the model passes:
  `--since` worked but made catching up something the model could forget.
- Background research is a **command** (`explainer-research`), not something the
  explainer does while answering. In the prompt it fired zero times out of three.
  Deciding *when* is deterministic and belongs in a script; only deciding *what*
  needs a model.
- Examples in `agents/explainer.md` must not be the eval's cases, or the eval
  measures recall of the prompt instead of behaviour.
