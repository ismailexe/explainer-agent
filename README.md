# explainer

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://github.com/ismailexe/explainer-agent/actions/workflows/test.yml/badge.svg)](https://github.com/ismailexe/explainer-agent/actions/workflows/test.yml)

A read-only second agent for Claude Code. Keep it open beside your work, ask it what
the working agent just said, and get the answer checked against your code — with the
**industry's own name** for the concept, so you can look it up yourself.

## Quickstart

```sh
git clone https://github.com/ismailexe/explainer-agent.git
cd explainer-agent && ./install.sh
explainer      # in a second terminal, inside the checkout you are working in
```

Requires Claude Code and Python 3. `install.sh` symlinks the files into `~/.claude/`
and prints anything left to add to your shell profile. Used day to day on macOS; on Linux
the tests pass, but it has not yet been used there.

## What to ask it

> **what does `ledger` mean here?**
> The repository's name for the table that records which webhooks were already
> forwarded, with the line that writes it — and the terms to search for:
> `idempotency store`, `at-least-once delivery`.

> **why did it switch the queue to Kafka?**
> If no queue was switched, that comes first, with where it looked — not an
> explanation of something that never happened.

> **has it forgotten anything since the compaction?**
> What the compaction summary dropped that still matters now, checked against the
> code, and a note to paste back to the working agent.

## Why

Stopping the working agent to ask what something meant costs twice: it turns into a
teacher, and the explanation settles into its context for good. Not asking is worse.
And the answer you get is often the wrong kind. A table called `ledger` is a name
someone on the project chose; searching for it returns accounting software. What you
need is the field's vocabulary — `idempotency`, `deduplication table`,
`exactly-once processing` — so you can learn the concept, not just this instance of
it.

## How it works

The explainer runs as its own `claude` process. Claude Code writes every session to
disk as it happens, so before each answer the explainer reads what the working
session added since its last look, then checks the claim against the project's
briefing, documents, memory and code. It follows the working agent into other
worktrees and branches, and nothing it says ever enters the working conversation.
Writes are refused at the tool layer; the only file it writes is its own glossary.
More in [`docs/architecture.md`](docs/architecture.md).

## When not to use it

- **Outside Claude Code.** It depends on Claude Code's transcripts and agent support.
- **To change anything.** It is read-only by design; it tells you what to ask the
  working agent instead.
- **For what the transcript does not hold.** It cannot see your browser, your other
  panes or what you said out loud — paste it in.
- **When every token counts.** Each question is a Claude call on your own login,
  typically 10 to 60 seconds.
- **On transcripts you would not send to Claude.** It reads your sessions and project
  files the way any Claude Code session does; see [`SECURITY.md`](SECURITY.md).

## Documentation

- [Usage](docs/usage.md) — the chat, one-shot questions, resuming chats, the
  glossary, language, environment variables
- [`EXPLAINER.md`](docs/explainer-md.md) — teaching it about your project
- [Architecture](docs/architecture.md) — components, principles, the Claude Code
  behaviour it relies on
- [Decisions](docs/decisions/README.md) — why it is built this way
- [Evaluation](docs/evaluation.md) — how the answers are measured, and the results
- [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

## License

[MIT](LICENSE)
