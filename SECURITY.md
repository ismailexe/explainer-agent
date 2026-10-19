# Security

## What the explainer reads and sends

The explainer is a Claude Code session, so everything it reads can be sent to
Anthropic as part of its conversation, exactly as in any Claude Code session. It
reads:

- the transcript of the work session it explains, and the first lines of other
  transcripts under Claude Code's projects directory, to find its own earlier chats;
- the repository and its worktrees, the project's memory notes under Claude Code's
  projects directory, and the `CLAUDE.md` files in scope;
- web pages, when it looks up an industry term.

Do not point it at sessions or repositories you would not send to Claude.

## What it can do

Writes are refused at the tool layer (`--allowedTools` in `bin/explainer`): it can
read files and run an allow-list of read-only commands. The only things written are
its glossary and catch-up positions under Claude Code's projects directory, and a
briefing file in your temporary directory.

## Prompt injection

Transcripts and repository files are untrusted input. Text in them can mislead the
explainer's answers, and because web search and fetch are allowed, it could in
principle steer the explainer into fetching a URL. Being read-only, it cannot be made
to change files or run state-changing commands. If web access matters in your
setting, remove `WebSearch` and `WebFetch` from the tool list in `bin/explainer`.

## Reporting a vulnerability

Please report it privately through the repository's **Security** tab ("Report a
vulnerability"), not in a public issue.
