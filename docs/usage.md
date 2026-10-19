# Using the explainer

The explainer is a chat you keep open in a second terminal, beside the Claude Code
session you are working in. You turn to it when the working agent says something you
did not follow, and back again an hour later.

## Open it

In a second terminal, go to the checkout the work session was opened in — the same
directory or anywhere below it — and run:

```sh
explainer
```

That is how it finds the conversation to explain. `explainer --sessions` shows which
conversations it can see from where you are, and `explainer --transcript PATH` names
one outright.

Typing `/explain` in the working conversation prints that command with the right
directory filled in. It deliberately does not open the window for you: a terminal
spawned from inside another program can report success while its window sits behind
a full-screen IDE, which looks exactly like nothing happening.

## Ask

Ask in the chat whatever you did not follow: a name, a decision, an error, a
screenshot you paste. Before every answer it reads what was added to the work
session since its last look, so it stays current while the other agent keeps
working.

Each claim in an answer carries one verdict: **verified**, with the line quoted;
**verified absent**, with where it looked; or **unverified**, with why. When a
repository name has a counterpart in the industry's vocabulary, it gives you that
term and the phrase to search for.

It cannot write into the working conversation. When it has something the other agent
should hear, it gives you a sentence to paste there yourself.

### One question, no chat

```sh
explainer "what does ledger mean?"
```

prints one answer and exits. Quote the question: zsh reads `?` and `*` as filename
patterns and fails with "no matches found" before `explainer` even runs. With
`alias explainer='noglob explainer'` in `~/.zshrc` a `?` needs no quotes, but an
apostrophe still needs double quotes, and in an interactive shell `!` needs single
quotes, because it triggers history expansion even inside double quotes. Long
questions are easier in the chat.

An option the launcher does not know is an error, not a question. A question that
really starts with `-` goes after `--`.

## Bring back an earlier chat

```sh
explainer --resume        # pick from a list
explainer --resume 2      # or by number, or by the start of its session id
```

The list covers chats opened anywhere in the repository, in any of its worktrees,
with their first question, when they were last active and whether they are still
open. The chat you pick comes back with its history, pointed at the work session you
are in now. If it is still open in another window you get a copy of it instead,
because two windows writing one conversation would interleave.

## When the work session moves

If the working agent moves to another worktree or branch, the explainer follows it:
every read names the checkout and branch the agent is in now, and claims are checked
against the files there. The project's `EXPLAINER.md`, memory and glossary are taken
from the repository the agent is working in.

## After a compaction

When the working agent's context fills up, Claude Code compacts it into a summary.
Ask the explainer what was lost. It compares each compaction summary with what you
said before it, reports only what the summary dropped and still matters for the
current work, checks it against the code, and gives you a note to paste back to the
working agent.

## Teach it about your project

A `.claude/EXPLAINER.md` in your repository tells the explainer the three things no
search recovers: notes kept outside the repository, your local-name → industry-term
table, and which source wins when the docs and the code disagree. See
[`explainer-md.md`](explainer-md.md). To see everything it can find from where you
are:

```sh
transcript-tail.py --sources
```

## The glossary

Once a term has been given its industry name, the answer is kept — one file per term
under `~/.claude/projects/<slug>/glossary/` — and the next question about it builds on
the earlier answer instead of deriving it again.

```sh
explainer-glossary.py --list
explainer-glossary.py --lookup ledger
```

You can also get ahead of your own questions:

```sh
explainer-research              # names from the last 25 messages
explainer-research --dry-run    # see the candidates, call no model
```

A free filter runs first, so a run with nothing new costs nothing. Names that pass go
to a small worker that looks up their industry terms on the web. Its entries are
marked `provenance: auto`: the worker never read your code, so the explainer says so
when it uses one, and marks it `verified` once it has checked. The glossary is
personal and never committed; a table your team shares belongs in `EXPLAINER.md`.

## Language

The explainer answers in, in this order:

1. `EXPLAINER_LANG`, when it is set;
2. the `language` in your Claude Code settings, when it is set;
3. the language you asked in.

Technical terms stay in English in every language, because the term is what you have
to search for, read in error messages and find in your own codebase.

## Environment variables

| Variable | Effect |
|---|---|
| `EXPLAINER_LANG` | Pins the answer language. |
| `EXPLAINER_PROJECTS_DIR` | Reads Claude Code's projects tree from another directory. The eval suite uses it to isolate each case. |
| `EXPLAINER_SETTINGS` | JSON, or a path to it, layered over your user settings with `--settings`. |
| `CLAUDE_CONFIG_DIR` | Honoured as Claude Code honours it. |
