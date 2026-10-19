# Architecture

The explainer is a second Claude Code process that reads the working session's
transcript from disk. It never shares a context with the working agent and never
writes into its conversation; the only thing the two have in common is a file that
Claude Code is already writing.

```
 terminal 1                         terminal 2
 ┌───────────────────────┐          ┌──────────────────────────────┐
 │ claude (working agent)│          │ explainer  (bin/explainer)   │
 └──────────┬────────────┘          │   └─ claude --agent explainer│
            │ appends               └──────────────┬───────────────┘
            ▼                                      │ reads, never writes
 ~/.claude/projects/<slug>/<session>.jsonl ◄───────┤
 ~/.claude/projects/<slug>/memory/         ◄───────┤
 the repository and its worktrees          ◄───────┘
```

## Components

| Path | Role |
|---|---|
| `bin/explainer` | The launcher. Picks the conversation to explain, builds the briefing, hands over directories and starts `claude --agent explainer` with a read-only tool list. |
| `bin/explainer_layout.py` | The only module that knows Claude Code's on-disk layout: project directories, transcripts, memory, cursors, which chats exist. Everything else, the bash launcher included, asks it. |
| `bin/transcript-tail.py` | Reads a transcript for the agent: catch-up (`--new`), the sources inventory (`--sources`), the launch briefing (`--briefing`), compactions (`--forgotten`) and research candidates (`--candidates`). |
| `bin/explainer-glossary.py` | Reads and writes the per-project glossary; the agent's only way to write anything. |
| `bin/explainer-research` + `agents/explainer-researcher.md` | Optional background research: a free filter decides whether anything is new, a small worker looks the new names up. |
| `agents/explainer.md` | The agent's instructions: what to read, how to verify, how an answer looks. |
| `commands/explain.md` | `/explain` in the working session: prints the command that opens the chat. |

## A chat, from launch to answer

**Launch** (`bin/explainer`):

1. Resolve the conversation to explain: the newest session opened in this checkout
   that is not itself an explainer. This happens before `claude` starts, while the
   work session is still the newest transcript.
2. Hand over every other worktree of the repository, and the project's entry under
   Claude Code's projects tree, with `--add-dir`.
3. Build the briefing and append it to the system prompt.
4. Start `claude --agent explainer --allowedTools <read-only list> --setting-sources user`.

**Every answer** (the agent, following `agents/explainer.md`):

1. Catch up: `transcript-tail.py --new` returns only what was appended since the last
   look, headed by where the working agent is now.
2. Check what the question assumes, then go to the sources: the glossary,
   `EXPLAINER.md`, `docs/`, memory, notes outside the repository, the code, the web.
3. Answer with one verdict per claim and the industry term where one applies; record
   the term in the glossary.

## Principles

- **Deterministic work in code, judgment in the model.** Whatever must always happen —
  catching up, deciding whether research is worth starting, building the briefing —
  is done by a script. The prompt holds only what needs judgment.
- **Read-only at the tool layer.** `--allowedTools` refuses writes; the prompt only
  explains why.
- **The working agent never learns the explainer exists.** Anything it should hear
  goes through the person, as text it can check for itself.
- **Claude Code's transcript format is internal.** All parsing lives in two modules,
  ignores unknown fields and skips a half-written last line.

## Following the working agent

The target is bound by session id, and its path is resolved again on every read, so
a transcript moved by `/cd` is still found. Every transcript entry records the
directory it was written from; the last one says where the working agent is now.
The branch is read from git at that moment. Each read opens with that location, and
entries written from another checkout are marked with it.

Project knowledge — `EXPLAINER.md`, memory, glossary — follows the working agent to
the repository it is in. The explainer's own bookkeeping stays with the directory it
was opened in.

## Catching up

The position in each transcript is a byte offset, kept per chat and per transcript in
a small file of its own, written atomically. Only whole lines are consumed, because
the last line of a live transcript is often half written. A first look costs about
4,000 tokens and a follow-up about 100; the full transcript is scanned in Python and
never sent to the model.

## Earlier chats

An explainer chat is recognised by the `agentSetting` its own transcript records, so
no registry is kept. `--resume` lists the repository's chats and tells open from
closed by the process table: a running process holds a session id after
`--session-id`, or after `--resume` unless it is forking. A closed chat is resumed;
an open one is forked into a new session.

## The briefing

At launch, `transcript-tail.py --briefing` collects the README's opening, the
documents' headings, recent commits, the worktrees, and where the work session stands
— its checkout, branch, last request and last reply — capped at 6,000 characters. It
lets the agent orient the person before it has run a tool. It is a snapshot; the
reads that follow are the current truth.

## Compactions

`transcript-tail.py --forgotten` prints each compaction summary beside the person's
own words from before it, keeping the start and the end of a long stretch. Choosing
what the summary lost that still matters is left to the agent, which checks each item
against the code before reporting it.

## Where state lives

| What | Where | Lifetime |
|---|---|---|
| Glossary | `<projects>/<repo slug>/glossary/` | kept; personal, never committed |
| Catch-up positions | `<projects>/<checkout slug>/explainer-cursors/` | one small file per chat and transcript |
| Briefing | a temporary file in `$TMPDIR` | read by `claude` at start; cleared by the OS |
| The chat itself | Claude Code's own transcript | as Claude Code keeps sessions |

`<projects>` is `EXPLAINER_PROJECTS_DIR`, or `$CLAUDE_CONFIG_DIR/projects`, or
`~/.claude/projects`.

## Claude Code behaviour this relies on

Measured on Claude Code 2.1.303. The transcript format is internal to Claude Code and
can change in any release; each fact here is covered by a test or was measured, and
is worth measuring again after an upgrade.

- A transcript is `<projects>/<slug>/<session-id>.jsonl`, where the slug replaces
  every character outside `[A-Za-z0-9]` with `-`.
- Every `user` and `assistant` entry records `cwd`. The `gitBranch` field is not
  reliable: it was seen reading `HEAD` on a branch checkout.
- A compaction summary is a `user` entry with `isCompactSummary: true`; the messages
  before it stay in the file.
- A session started with `--agent` records `agentSetting` on its first or second
  line, and a fork keeps it. A `claude -p` run is marked `entrypoint: "sdk-cli"`.
- `claude --resume <id>` finds a session started in another directory;
  `--fork-session --session-id <uuid>` sets the fork's id in advance.
- On resume and fork the system prompt recorded at the first request is reused
  unless `--system-prompt-snapshot off` is passed.
- `Read` and `grep` reach files outside the working directory; `cat` does not, unless
  the directory is added with `--add-dir`.
- `/cd` moves a session's transcript to the new directory's project storage.

## Related work

- **Claude Code's Explanatory and Learning output styles** put explanations in the
  working agent's own answers. The explainer exists to keep them out of that context.
  ([output styles](https://code.claude.com/docs/en/output-styles))
- **Transcript viewers** — [claude-code-log](https://github.com/daaain/claude-code-log),
  [claude-code-trace](https://github.com/delexw/claude-code-trace),
  [claude-code-transcripts](https://github.com/simonw/claude-code-transcripts) — read
  the same files for a person to browse; none is an agent you can question.
- **Subagent collections** such as
  [awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents)
  group agents by technical role; none teaches the vocabulary behind the work.
