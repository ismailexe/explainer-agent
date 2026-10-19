# The `EXPLAINER.md` contract

A project drops one file to tell the explainer agent what it cannot work out on
its own. Without it the agent still works — it reads the transcript, greps the
code, searches the web. The file exists for the three things no amount of
grepping recovers:

1. **Notes that live outside the repository.** Handover files, status reports and
   task lists kept in `.tmp/` or `backup/` are usually where a project's real
   reasoning is. They are gitignored, so `grep` over the tree never finds them
   and the agent does not know to look.
2. **Local names.** A repo invents `ledger`, `probe flow`, `edge algebra`. Those
   words teach the reader nothing when typed into a search box. Mapping each one
   to its industry term is the whole point of the agent, and only someone who
   knows the project can write that mapping down.
3. **Which source wins.** In one project the docs are the specification and the
   code is behind them; in another the docs are stale. The agent cannot guess.

## Where it goes

| Path | Visibility |
|---|---|
| `<repo>/.claude/EXPLAINER.md` | committed, shared with the team |
| `~/.claude/projects/<slug>/EXPLAINER.md` | private to this machine, never committed |

Both are read; the private copy wins where the two disagree. `<slug>` is the
project path with every character outside `[A-Za-z0-9]` replaced by `-` —
`transcript-tail.py --sources` prints the resolved path, so there is no need to
build it by hand.

**Worktree trap:** an uncommitted `<repo>/.claude/EXPLAINER.md` is visible only
inside the worktree holding it. Commit it, or put it in the private location, or
the agent will find it in one worktree and not the next.

## What goes in it

There is no schema — the file is read by a language model, not a parser. Free-form
Markdown, in English, under roughly 150 lines. What earns its place:

- **One paragraph on what the project is.** Not a feature list; what problem it
  solves and for whom.
- **Notes outside the repo**, as a list of backtick-quoted paths with one line
  each on what the file holds. `--sources` existence-checks these and flags the
  ones that have gone missing, so a stale list shows up as a warning rather than
  as a silently wrong answer.
- **A local-name → industry-term table.** The highest-value section. One row per
  invented name, with the term to search for.
- **The conflict rule.** Which source the agent should believe when the docs, the
  code and its own reasoning disagree.
- **Traps.** Things a reader gets wrong on first contact.

What does not belong: anything the agent can read off the code, build and test
commands (it never runs them), or instructions about how to answer — that lives in
the agent definition and applies to every project.
