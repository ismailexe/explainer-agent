# Evaluation

How the explainer's answers are measured, what the measurements show, and what they
cannot show. To run the suite, see [`evals/README.md`](../evals/README.md).

## Method

Every case asks the real explainer one question, through `bin/explainer`, about a
synthetic work session: a small service that relays support tickets, a two-day
transcript that was compacted once, and a few memory notes. Planted in it are a
request that exists only before the compaction, a rule the summary dropped and the
working agent later broke, a timeout the agent claimed but never wrote, a move to a
second worktree that no message mentions, and no mention of Redis at all.

Each case runs in a world of its own: a fresh git checkout, a private projects
directory and neutral settings, so the machine owner's language, output style,
`CLAUDE.md`, hooks and auto memory cannot change a result.

An answer is graded on separate criteria, each pass/fail:

| Criterion | Graded by | What it checks |
|---|---|---|
| Length | code | word count against a limit |
| Language | code | the answer is in the expected language |
| Citations | code | every `file:line` exists, and points at the line about the subject |
| Premise | judge | a false or leading premise is corrected first, not carried on |
| Verdict | judge | each claim gets one consistent verdict, and cheap checks are made |
| Terms | judge | an industry term is used only when the thing meets its definition |
| Memory | judge | what happened before a compaction, and on which day |
| Scope | judge | it refuses work it must not do, and does not invent what it cannot see |
| Follow | judge | it checks claims in the worktree the working agent moved to |
| Briefing | judge | it knows the project before reading anything |
| Forgotten | judge | it finds what a compaction dropped and writes a self-contained note |

A judge is a separate `claude -p` call in safe mode, with no tools, given the
criterion and the ground truth it needs; it never sees the repository.

## Results

Recorded 2026-10-19 · Claude Code 2.1.303 · explainer on `sonnet` · judges on `sonnet`
· promptfoo 0.124.1 · 3 runs per case. Counts are runs passed out of runs made.

| Criterion | Before (commit `adf2da1`) | After (commit `df4f815`) |
|---|---|---|
| Every criterion of a case | 26 / 51 | 44 / 57 |
| Length | 30 / 51 | 49 / 57 |
| Language | 3 / 9 | 9 / 9 |
| Premise | 12 / 15 | 14 / 15 |
| Verdict | 20 / 21 | 21 / 21 |
| Terms | 11 / 15 | 11 / 15 |
| Citations | 6 / 6 | 6 / 6 |
| Memory | 9 / 9 | 9 / 9 |
| Scope | 6 / 6 | 6 / 6 |
| Follow | — | 3 / 3 |
| Briefing | — | 3 / 3 |

"Before" had 17 cases; the two later cases test features that did not exist yet.

### Features measured with the change switched off

Same case, same day, three runs each:

| Change | Without | With |
|---|---|---|
| Following the working agent into another worktree | 0 / 3 | 3 / 3 |
| Launch briefing, asked to answer without reading anything | 0 / 3 | 3 / 3 |
| Compaction view: a self-contained note for the working agent | 1 / 3 | 3 / 3 |

Without the first change, the explainer checked its own checkout, found no jitter
there, and reported that the working agent had claimed work it never did. For the
compaction view, the rule itself was found 3 of 3 times either way, because the
fixture is short enough to read in full; see the limitations.

## Limitations

- **The fixture is synthetic and small.** Twenty-odd messages can be read in full, so
  it cannot show what the compaction view gains on a real session of thousands of
  lines. On one such session, 13,467 lines came down to 14 KB.
- **The judges are language models.** The citation and length rules were checked
  against the maintainer's reading of real answers. The rubric judges have not yet
  been measured against a person's verdicts on the same answers.
- **The instructions were tuned against this suite.** Their worked examples are kept
  on topics the suite does not ask about, so that a pass reflects behaviour rather
  than recall, but tuning against the test is still tuning against the test.
- **The length limit was set after reading answers.** The maintainer judged answers
  of 110 to 179 words acceptable, and the limit became 180 (120 for a plain
  definition). Both columns above use that limit. With the earlier 130-word limit,
  whole cases went from 9 / 51 to 28 / 57.
- **Three runs per case is a small sample.** A difference of one run is within noise:
  over four rounds with no change aimed at it, the Terms criterion moved between
  11 / 15 and 14 / 15.

## Known weak spots

- Answers are often longer than the 120 words the instructions aim for, though
  within the calibrated limit.
- One term keeps being misnamed: serving data loaded earlier after a failed refresh
  is called `stale-while-revalidate`, where `stale-if-error` is exact.
