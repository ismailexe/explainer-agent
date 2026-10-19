# Evals

An answer-quality suite for the explainer, run with
[promptfoo](https://www.promptfoo.dev). Every case asks the real explainer one
question about a synthetic work session, and grades the answer.

```sh
./install.sh                                   # once: the suite runs the installed agent
evals/run.sh                                   # every case
evals/run.sh --filter-pattern "false premise"  # cases whose description matches
npx promptfoo@0.124.1 view                     # browse the last results
```

It needs Claude Code (signed in), Python 3, and Node for `npx`. There is no API key:
the explainer and the judges both run through `claude -p` on your own login, so a
full run spends that login's usage.

## What it runs against

- `fixture/repo/`: a small relay service with a `ledger`, a `routes.yaml` checked at
  build time, a dashboard, and a `docs/DECISIONS.md`.
- `fixture/session.py`: the work session being explained. It spans two days and was
  compacted once. Three things are planted in it: a request that only exists before
  the compaction, a timeout the main agent claims but never wrote, and no mention of
  Redis at all.
- `fixture/memory/`: the project's memory notes.

`provider.py` gives every case a world of its own: a fresh git checkout, a private
projects directory (`EXPLAINER_PROJECTS_DIR`) and neutral settings
(`EXPLAINER_SETTINGS`), so the machine owner's language, output style, `CLAUDE.md`
and auto memory cannot change a result. Afterwards it removes the explainer's own
session with `claude purge`.

## How a case is graded

- **In code:** length in words, answer language, and whether every cited `file:line`
  exists (`assert_citations.py`).
- **By a judge:** one pass/fail rubric per criterion, through `judge.py`. Each rubric
  carries the ground truth the judge needs, because the judge never sees the
  repository.

Rubrics are a draft until a judge agrees with a person's own pass/fail on the same
answers. Where they disagree, fix the rubric, not the person.
