# Design history

How the explainer came to be shaped the way it is: the problem, what was measured
about Claude Code, the decisions taken and why, and the mistakes that changed the
design. It covers September 2026, when the project was built. What came after the
first month of real use is in [`roadmap.md`](roadmap.md).

Every platform fact below was measured, not assumed. Claude Code versions moved
from 2.1.25x to 2.1.30x over this history; facts that a new version could break
are marked as measured, so they can be measured again.

## The problem

Working with a coding agent, you keep having to stop it and ask what something
meant. That costs twice. The agent drops the work and becomes a teacher, and the
explanation settles into the working conversation's context and stays there. Not
asking is worse: you carry on without understanding, and every decision after that
is made half-blind.

And when you do ask, the answer is often the wrong kind. The case that started this
project: a repository had a table called `ledger`, and the agent explained it by
translating the word. But `ledger` was a name someone on that project had chosen.
Searching for it returns blockchains and accounting software. What the person needed
was the vocabulary of the field:

| layer | the term to search for |
|---|---|
| the problem | `at-least-once delivery` |
| the property | `idempotency` |
| the key | `idempotency key` |
| the table | `deduplication table`, `idempotency store` |
| the state machine | `claim → work → settle` |
| the honest claim | `exactly-once processing`, never `exactly-once delivery` |

So the need is not a definition. It is the concept's searchable name. Plenty of
tools explain a term; none found makes it searchable. That is the core idea, and
everything else is plumbing.

## The idea

A second, read-only agent that the **person** calls, not the main agent. It reads the
main session's live transcript, checks what it is asked about against the code and
the documents, then explains the concept and gives its industry name. Four
properties have to hold together:

1. its own context, so its research never lands in the working conversation;
2. it reads the working conversation as it happens;
3. a person calls it, not the agent at work;
4. its job is to teach the concept, not to review the code.

## How "listening" works

A subagent cannot listen to a conversation; it only receives the prompt it was
started with. But Claude Code writes every session to disk as it happens: one JSON
object per line (JSONL), appended live. The explainer does not listen, but whenever
it is asked, it can read everything up to that moment. In practice there is no
difference.

## Measured platform facts

**Where a transcript lives.** `~/.claude/projects/<slug>/<session-id>.jsonl`. The
slug replaces every character outside `[A-Za-z0-9]` with `-`. The first guess was
"only `/`"; measured against 57 project directories it held for 27 of them, and the
real rule held for 56 (the exception had been renamed).

**Finding the right file.** A subagent's shell inherits `CLAUDE_CODE_SESSION_ID` from
the session that started it, which is the main session: the subagent can find the
conversation without being told. Deriving the slug from the working directory is not
reliable, because IDE workspaces can open a session in a different directory from
the one its transcript is keyed to.

**What a transcript holds.** Entry types include `user`, `assistant`, `system`,
`attachment`, `file-history-snapshot` and several bookkeeping types. Only `user` and
`assistant` carry the conversation; `message.content` is a string or a list of
`text`, `thinking`, `tool_use` and `tool_result` blocks. Subagent chatter
(`isSidechain`), `<system-reminder>` blocks and command wrappers are noise for this
purpose. The last line can be half written while the session runs, so a parse error
is skipped, not raised.

**Where agents and commands live.** `~/.claude/agents/<name>.md` applies to every
project, `<repo>/.claude/agents/<name>.md` to one; `~/.claude/commands/<name>.md`
becomes `/<name>`. A new agent file is picked up without a restart, after a short
delay.

**Memory is keyed differently from transcripts.** A transcript sits under the slug
of the directory the session was opened in; `memory/` sits under the slug of the
working directory. From a worktree, the two differ. Scanning project directories for
the repository's name was ambiguous (two candidates with 2 and 58 memory files), so
the main worktree is resolved exactly with `git rev-parse --path-format=absolute
--git-common-dir`, and the name scan is only a fallback.

**A subagent reports to the main agent, not to the person.** Its answer has to pass
through the main agent's context. That fact ended up deciding the architecture.

## Decisions and their reasons

**Read-only.** The thing that explains must not be able to change what it explains,
and writing to the same files as the main agent would race with it. At first this
was a sentence in the prompt; once the explainer ran as its own process it became
`--allowedTools`, a refusal at the tool layer rather than a request.

**Never paraphrase the main agent.** The person already read what the main agent
said. The explainer has to go to the source, and say so when it cannot verify a
claim instead of filling the gap with something plausible, because the person
cannot check it. (In October this became three verdicts per claim; see the
roadmap, finding G.)

**A second pair of eyes.** If the main agent says something the code does not
support, the explainer says so. The one doing the work and the one judging it are
kept apart, the principle behind critic–actor setups and LLM-as-judge.

**Language of the sentences, language of the terms.** The answer is written in the
person's language, but technical terms stay in English, with a one-phrase gloss on
first use. Translating `ledger` into the local word for "notebook" cuts the person
off from the word they actually need. (The order that decides the sentence language
was settled in October; see finding J.)

**Distribution: a repository, not a plugin.** `install.sh` symlinks the files into
`~/.claude/`, so editing the repository edits the running agent, with no second copy
to drift. The industry name is a symlink or dev-mode install; copying would be
vendoring.

**Zero pollution of the working conversation: its own process.** The first version
ran as a subagent behind `/explain`, and its answer had to pass back through the main
agent, where it stayed. That is not a bug to patch but a consequence of calling it
from inside. So the explainer became its own `claude` process: `bin/explainer`
resolves which conversation to explain before starting (at that instant the newest
transcript is still the work session), then launches
`claude --agent explainer --allowedTools <read-only list>`.

**Claude Code only, with one seam.** Other harnesses have no subagent primitive, so
abstracting over them would buy complexity for a feature that could not exist. The
seam is kept instead: `bin/explainer_layout.py` is the only module that knows Claude
Code's on-disk layout; even the bash launcher asks it for paths.

**The name.** `explainer` was already the agent's name, the command's name and the
name of the per-project briefing file; it also says what the thing does.

**The glossary.** One file per term, so the next question about a term builds on the
earlier answer instead of deriving it again, possibly differently. The explainer is
read-only, yet it must write glossary entries; the answer was not to give it `Write`
but a purpose-built command, which keeps both the letter and the reason of the
read-only rule.

**A chat, not a one-shot answer.** The first build answered one question and exited.
The person stopped it: what they wanted was a conversation kept open beside the work,
to turn to and come back to. That changed three things:

1. The explainer catches up before **every** answer, because the work session keeps
   moving while the chat stays open.
2. `/explain` prints the command that opens the chat instead of opening a window.
   Opening a terminal window from inside a full-screen IDE was measured to start the
   process while the window appeared behind the IDE or on another desktop. An
   invisible success is worse than a failure: it looks like nothing happened.
3. The main agent no longer produces explanations at all.

**The last thing said is the explanation.** In one-shot mode `claude -p` prints only
the final message. In the first real use, the screen showed only "recorded it in the
glossary"; the explanation itself had been thrown away. The same thing had happened
in testing and was missed, because the glossary file had been written and that was
counted as success.

## Bugs found, and what they taught

**Explaining the wrong project's conversation.** Choosing the conversation by "a
session opened in this directory or above it" made every session opened in `$HOME`
a candidate, since `$HOME` is above everything. Explaining an unrelated conversation
in confident detail is worse than an error, so the boundary became the repository,
and an empty pool now fails loudly.

**A worktree's subdirectory could not see its own session.** The boundary had been
the main worktree, which is not a prefix of a linked worktree's path. The real
mistake was answering two questions with one function:

| question | boundary | why |
|---|---|---|
| which sessions are mine | `worktree_root()`, this checkout | a session in another checkout looked at other files |
| which project's memory | `main_worktree()`, the repository | every worktree shares `memory/` |

**The glossary confused with the owner's table.** Asked to record a term, the agent
said it was "already in the glossary" when the glossary was empty: it had read the
local-name table in `EXPLAINER.md`. Both have the same shape. The table belongs to the
project's owner and is only read; the glossary is the explainer's own record and it
alone writes it. The inventory now says so explicitly.

## Prior art

**Claude Code's own output styles.** The Explanatory style adds insight blocks to the
agent's answers; the Learning style leaves parts of the work for the person. Both put
the explanation in the working agent's mouth, which is the problem this project
avoids: they are the opposite design, not a competitor.
([output styles](https://code.claude.com/docs/en/output-styles))

**Transcript readers.** [claude-code-log](https://github.com/daaain/claude-code-log),
[claude-code-trace](https://github.com/delexw/claude-code-trace),
[claude-code-transcripts](https://github.com/simonw/claude-code-transcripts),
claudelogs.com and `ccusage` all read the same files. They are viewers for a person;
none is an agent you can question. Reading transcripts is a solved problem, so it is
not where this project's difference lies.

**Subagent collections.** [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents)
and similar lists group agents by technical role. Searches found no tutor or
explainer type.

No tool combining the four properties was found. That is weak evidence, not proof of
absence: five searches from three angles agreed, and nothing more.

## Background research, and the cost of it

The idea: let the explainer look up unfamiliar names on the web ahead of time, so a
later question costs a lookup.

**Cost, measured rather than guessed.** The first estimate warned that a naive
background watcher would spend over half a million tokens on a quiet day. True, but
the wrong scale. Measured on real usage, Claude Code resends the accumulated context
every turn and almost all of it is cache reads; the binding limit was the five-hour
usage window, not the week; and a naive watcher would have used under one percent of
a typical window. The decision came from the usage screen's own warnings instead:
most usage came from subagent-heavy sessions and from sessions running for eight hours
or more, often in the background. So there is no background watcher, and a research
run starts at most three subagents.

**The most instructive mistake: a chore left to the model.** Research was first
written into the explainer's prompt: after answering, look up the new names. Across
three real questions it fired zero times out of three, and moving the instruction
before the answer did not help. A model with a question in front of it answers the
question and skips the optional chore. Instead of rewording the prompt a fourth time,
the structure changed: **deterministic decisions in code, judgment in the model.**
`bin/explainer-research` decides *when* to run (Python, free);
`agents/explainer-researcher.md` decides *what* is worth researching. On its first
real run it correctly rejected all fifteen candidates as code identifiers, without a
single web search.

**The filter, fixed twice.** Mining every message, tool calls included, of an 80-hour
session gave 897 candidates, topped by the repository's own directory name with 660
mentions. Limiting it to prose gave 1,139, because it still read the whole file.
Limiting it to the last 25 messages gave 12, a usable list. A filter cannot tell a
field name from a concept, and should not be asked to: the filter's job is novelty,
the model's job is judgment.

## Catching up without a clock

A follow-up question used to mean re-reading the recent conversation. Measured on a
session of 240 readable messages: `--turns 25` sent about 5,000 tokens to the model,
`--since HH:MM` about 1,800, and the whole file (about a million tokens) was never
sent at all, since Python scans it for free in a fraction of a second. But `--since`
depended on the model remembering the time of its last look: the same kind of chore
that had just failed zero out of three.

So the position moved into code: `--new` keeps a byte offset per chat and per
transcript, and consumes only whole lines. Measured: about 4,000 tokens for the first
look and about 100 for a follow-up.

**Live streaming was not built.** It would be easy, since the file is append-only,
but reading takes about a tenth of a second while the model takes 10 to 60. Streaming
would optimise a rounding error, at the price of a process running all the time. What
streaming would really open is proactivity: speaking up unasked when the main agent
says something the code contradicts. That is a different feature, and the expensive
one.

## Since then

The first month of real use produced findings A to N, an answer-quality eval suite
and its measured results. They are recorded in [`roadmap.md`](roadmap.md).
