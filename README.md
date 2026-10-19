# explainer

A read-only second agent that answers *"what did that mean?"* about the Claude Code
conversation you are in the middle of — and answers it with the **word the industry
uses**, so you can go and search for the concept yourself.

## The problem

Working with an agent, you keep having to stop it and ask what something meant. That
costs twice. The agent drops the work and becomes a teacher, and the explanation
settles into the working conversation's context and stays there. Not asking is worse:
you carry on without understanding, and every decision after that is made half-blind.

And when you do ask, you often get the wrong kind of answer. A repository invents its
own names. Ask about a table called `ledger` and a well-meaning agent explains the
ledger — maybe even translates the word for you. But `ledger` is a name somebody on
that project chose. Searching for it returns blockchains and accounting software. What
you actually needed was:

| layer | the term to search for |
|---|---|
| the problem | `at-least-once delivery` |
| the property | `idempotency` |
| the key | `idempotency key` |
| the table | `deduplication table`, `idempotency store` |
| the honest claim | `exactly-once processing` — never `exactly-once delivery` |

Plenty of tools will *explain* a term. This one exists to make it **searchable**.

## How it works

Claude Code appends every session to disk as it happens
(`~/.claude/projects/<slug>/<session-id>.jsonl`). The explainer cannot listen to your
conversation — no agent can — but it can read that file the moment you ask it
something. In practice there is no difference.

It then goes and checks: the project's own briefing, the docs, the accumulated
memory, the notes kept outside the repository, the code, and the web — in that order.
An explanation that only rephrases what the main agent said is worthless, because you
already read that.

It follows the main agent. When the work session moves to another worktree or
branch, the explainer checks claims against the files there, not against its own
directory. It opens with a short briefing built from the project — what it is, its
recent commits, where the work session stands — so it can orient you before it has
read anything. And when the main agent's context has been compacted, ask the
explainer what was lost: it compares each compaction summary with what you said
before it, and gives you a note to paste back.

## Install

```sh
git clone https://github.com/ismailexe/explainer-agent.git
cd explainer-agent
./install.sh
```

`install.sh` symlinks the launcher, its scripts, the two agents and the `/explain`
command into `~/.claude/` (`bin/`, `agents/`, `commands/`), so editing the repository
edits the running agent and there is no second copy to drift. Any regular file it
replaces is kept as `<name>.pre-explainer-agent`.

Put `~/.claude/bin` on your `PATH` to call `explainer` by name.

Requires Claude Code and Python 3 — no packages.

## Use

The explainer is a **chat you keep open beside your work**, in its own window. Not
a command that answers once — a conversation you turn to when the other agent says
something you did not follow, and turn back to an hour later.

Open a second terminal window, go to the same checkout the work session is in, and
run:

```sh
explainer                            # the chat
explainer --resume                   # bring back an earlier chat of this repository
explainer --sessions                 # which conversations it can see from here
explainer "what does ledger mean?"   # one question, printed and gone, if you prefer
```

`--resume` lists the chats opened anywhere in this repository, in any of its
worktrees, and asks which one (`--resume 2` picks directly). The chat comes back
with its history, pointed at the work session you are in now. If that chat is still
open in another window, you get a copy of it instead, because two windows writing
one conversation would interleave.

Quote a one-shot question: zsh reads `?` and `*` as filename patterns and fails with
"no matches found" before `explainer` runs. `alias explainer='noglob explainer'` in
`~/.zshrc` removes the need for `?`. An apostrophe still needs double quotes, and in
an interactive shell `!` needs single quotes, because it triggers history expansion
even inside double quotes. Long questions are easier in the chat.

`/explain`, typed in the working conversation, hands you that command with the
right directory filled in. It deliberately does not open the window for you: a
terminal spawned from inside another program reports success while its window sits
behind a full-screen workspace or on another Space, which looks exactly like
nothing happening.

It runs as its own `claude` process, so nothing it says ever enters the working
conversation. Every time you ask it something it reads what was appended since its
last look — a cursor it keeps itself, not a timestamp anything has to remember —
so it stays current while the other agent keeps working, and a follow-up costs a
fraction of the first question. It reads the
same `CLAUDE.md` files that agent works under, plus the project's memory and docs,
so it knows roughly what the agent knows.

Read-only is enforced at the tool layer, not merely requested in a prompt. And it
cannot talk back into the working conversation: if you want the other agent to
know something, paste it over yourself.

## Teach it about your project

Drop a `.claude/EXPLAINER.md` in your repository. Three things no amount of grepping
recovers: the notes you keep outside the repo, your local-name → industry-term table,
and which source wins when the docs and the code disagree. Format and locations:
[`docs/explainer-md.md`](docs/explainer-md.md).

Check what it can see with:

```sh
transcript-tail.py --sources
```

## The glossary

Once a term has been given its industry name, the answer is kept — one file per term
under `~/.claude/projects/<slug>/glossary/`. Ask about it again and the explainer
builds on what it told you instead of re-deriving it, possibly differently.

```sh
explainer-glossary.py --list
explainer-glossary.py --lookup ledger
```

It fills from two directions. Answering your question writes a `verified` entry —
checked against the repository. And you can get ahead of your own questions:

```sh
explainer-research              # names from the last 25 messages
explainer-research --dry-run    # see the candidates, call no model
```

That finds names nobody has recorded yet and has a cheap Sonnet worker look up
their industry counterparts. A free Python filter runs first, so a run with
nothing new costs nothing at all — and most runs are that. Entries it writes are
marked `provenance: auto` and carry no repo-local meaning, because the worker
never read your code; the explainer says so when it uses one, and upgrades it to
`verified` once it has checked. Skipping most of a candidate list is the normal
outcome: field and function names are not concepts.

The glossary is per-person and never committed. The curated table your team shares
belongs in `EXPLAINER.md`.

## Language

The explainer answers in `EXPLAINER_LANG` when it is set; otherwise in the `language`
of your Claude Code settings, when that is set; otherwise in the language you asked
in. **The terminology stays English regardless**, which is the whole point: the term
is what you have to type into a search box, read in an error message, and recognise
in your own codebase.

## What it will not do

It has no `Edit` and no `Write`, and its `Bash` is restricted to reading. It never
runs builds, tests, servers or migrations, never starts or stops anything, and never
tells the main agent what to do — it can only tell you what to ask. The single thing
it writes is one glossary entry.

Every claim it makes carries one verdict: verified, with the line quoted; verified
absent, with where it looked; or unverified, with why. It never fills a gap with
something plausible, because you cannot check it.

## How good the answers are

`evals/` holds an answer-quality suite: questions about a synthetic work session,
each graded for premises, verdicts, citations, terminology, language and length. The
roadmap records each change and what it did to the scores. In short, the share of
cases passing every check went from 51% to 77% across the first month's fixes, and the
two features with a before-and-after case — following the main agent across
worktrees and the launch briefing — went from 0 of 3 to 3 of 3.

Why it is built the way it is: [`docs/design.md`](docs/design.md). What was found in
real use and done about it: [`docs/roadmap.md`](docs/roadmap.md).

## Limits worth knowing

- **Claude Code only.** The layout knowledge is isolated in `bin/explainer_layout.py`,
  but the design leans on a primitive other harnesses do not have.
- **Start it inside the checkout the work session was opened in** — the same
  directory, or anywhere below it. That is how it finds the conversation: a session
  opened in another worktree is invisible from here, which is what you want when four
  of them are running at once. Once attached, it follows the main agent wherever that
  goes. `explainer --sessions` shows what was found from where you are, and
  `--transcript PATH` names one outright.
- **It reads the transcript, not your mind.** Anything that happened outside the
  session — something you saw in a browser, said out loud, or did in another pane — it
  cannot know about.
