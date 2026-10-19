# Changelog

Notable changes, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions below 1.0 promise
no compatibility: commands, options and file layouts may change in any release.

## [Unreleased]

## [0.1.0] - 2026-10-19

The first public version.

### Added

- `explainer`: a read-only chat beside a Claude Code session, run as its own process,
  that catches up on the working session before every answer and gives the industry
  term for a repository's own names.
- One-shot questions (`explainer "…"`) and `/explain` in the working session.
- Following the working agent across worktrees and branches; project knowledge is
  taken from where it works.
- `explainer --resume`: bring back an earlier chat of the repository, resumed if closed
  and forked if still open elsewhere.
- A briefing built at launch, so the explainer can orient you before reading anything.
- `transcript-tail.py --forgotten`: what a compaction summary dropped, beside what was
  said before it.
- A per-project glossary, filled by answers and by optional background research.
- `.claude/EXPLAINER.md`: a project's local names, notes and source of truth.
- Answers with one verdict per claim — verified, verified absent or unverified.
- Answer language: `EXPLAINER_LANG`, then Claude Code's `language` setting, then the
  language of the question.
- Support for `CLAUDE_CONFIG_DIR`.
- An answer-quality eval suite under `evals/`.

[Unreleased]: https://github.com/ismailexe/explainer-agent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ismailexe/explainer-agent/releases/tag/v0.1.0
