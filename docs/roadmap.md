# Roadmap

Status as of 2026-10-19. The findings come from a dogfooding session on a real, private
work repository (TypeScript on Cloudflare Workers; the work session it explained had
3,037 messages and two compactions), and from measurements against Claude Code 2.1.303.

## Principles

- **Deterministic work in code, judgment in the model.** If a step must always happen,
  the launcher or a script does it; the prompt only holds what needs judgment.
- **Measure before changing the prompt.** Every answer-quality change is checked against
  the eval suite, starting from a baseline of the current agent.
- **The main agent never learns the explainer exists.** Anything the explainer wants the
  main agent to know goes through the user, as text the main agent can verify on its
  own. An automatic channel would carry the explainer's mistakes straight into the main
  agent's reasoning.
- **The transcript format is internal to Claude Code** and changes between releases.
  All parsing stays in one module, ignores unknown fields, and is tested against
  recorded samples.

## Decisions (2026-10-19)

- **Eval harness: promptfoo.** It is a development-only Node dependency; installing the
  explainer still needs nothing but Claude Code and Python 3.
- **Answer language, in order:** `EXPLAINER_LANG` when set; otherwise the `language`
  in the user's Claude Code settings, when set; otherwise the language of the
  question. Terminology stays English in every language.
- **Explainer chats are listed from their transcripts** (`agentSetting: "explainer"`),
  not from a registry. `explainer-sessions.txt` goes away.
- **Bringing an explainer back:** a closed chat is resumed; a chat still open in another
  window is forked. The user never chooses between the two.

## Measured facts

Claude Code 2.1.303, measured in throwaway directories unless marked as documented.

- `claude --resume <id>` finds a session started in another directory. New turns are
  appended to the original project directory's transcript, and each new message records
  the new `cwd`.
- `--resume <id> --fork-session` writes the fork into the current directory's project
  directory. Passing `--session-id <uuid>` as well fixes the fork's id in advance.
- A fork keeps `agentSetting`, even when `--agent` is not passed again.
- On resume and on fork, the system prompt recorded at the conversation's first request
  is reused, and a new `--append-system-prompt` is ignored.
  `--system-prompt-snapshot off` makes the new text apply.
- Every transcript message carries `cwd`. `gitBranch` is unreliable: it read `HEAD` while
  the checkout was on `main`.
- Raw messages from before a compaction stay in the transcript. The explainer quoted a
  message written a day before two compactions, which the main agent only holds as a
  summary.
- Documented: `/cd` moves a session's transcript into the new directory's project
  storage.
- Documented: resuming one session in two terminals without forking interleaves both
  into one transcript.

## Findings and plan

### A · Cold-start knowledge
On first open the explainer knows only the auto-loaded `CLAUDE.md`, the memory index and
git status. It does not know what the project is, or what the main agent is doing.

**Plan.** At every launch the launcher builds a project briefing in code: a README
summary, the headings under `docs/`, `EXPLAINER.md`, recent commits, the worktree list,
and the work session's current directory, branch and last request. It passes the
briefing with `--append-system-prompt-file`. On resume and fork it also passes
`--system-prompt-snapshot off`, so the briefing is fresh.

### B · Bringing back a previous explainer
When the main agent's session moves elsewhere, today's only option is a new explainer,
and the old chat is lost.

**Plan.** `explainer --resume` lists the repository's explainer chats across all
worktrees, derived from transcripts. Each row shows the title or first question, last
activity, worktree and branch, and whether the chat is open. One-shot (`-p`) chats are
left out, as Claude Code's own picker does. A closed chat is resumed and re-targeted. An
open one is forked with a pre-assigned id. To tell open from closed, each running chat
holds a lock file with `flock` for its whole lifetime, so a crashed process never leaves
a stale record behind.

### C · Following the main agent across worktrees and branches
Today the target is bound by path at launch, and claims are verified against the
explainer's own checkout. If the main agent moves to another worktree mid-session, the
explainer keeps checking the wrong files.

**Plan.**
- Bind the target by session id and resolve its path on every read, which also survives
  `/cd`.
- Read `cwd` per message and verify in the main agent's current worktree.
- Read the branch from git at read time, not from `gitBranch`.
- Give the other worktrees to the explainer with `--add-dir`.
- Cover a mid-session worktree hop with a test.

### D · Cursor lost update
`write_cursor` (`bin/explainer_layout.py`) reads a shared file, edits it and rewrites it
without a lock. Two chats saving at the same moment lose one update, and that chat
re-reads recent messages.

**Plan.** One cursor file per (chat, transcript) pair, written atomically: write to a
temporary file, then `os.replace`. With no shared file, there is nothing to race on.

### E · An unknown flag becomes a question
`explainer --resume`, typed before the flag existed, ran as a one-shot question and spent
a model call.

**Plan.** An unknown `--` option fails and prints the usage.

### F · `?` breaks one-shot questions in zsh
Questions naturally end in `?`. zsh treats it as a glob and fails with "no matches
found" before the explainer runs.

**Done.** `install.sh` prints `alias explainer='noglob explainer'` for zsh users and
leaves the profile to them, as it already does for `PATH`. The README and
`explainer --help` say what still needs quotes: an apostrophe needs double quotes,
and `!` needs single ones, because it triggers history expansion even inside double
quotes.

### G · False premises
Asked why the main agent had set a Redis TTL that was never added, the explainer said in
one answer both that Redis was not added and that it could not verify this. It then
suggested a follow-up question for the main agent that carried the false premise
forward. The cause is that the agent prompt knows only two verdicts: verified, and could
not verify.

**Plan.**
- Rewrite the question neutrally before answering.
- Give one verdict per claim, stated first:
  - **verified**, with a quote;
  - **verified absent**, with the scope searched;
  - **unverified**, with what would settle it.
- When a premise is false, correct it in the first sentence, and build follow-up
  questions from the corrected version.

### H · Term precision
The explainer reaches for popular but inexact terms:
- "GitOps", twice, for a configuration file read at build time;
- `stale-while-revalidate` where `stale-if-error` is exact;
- `denormalization` offered as the exact counterpart of single source of truth.

**Plan.** Use a term only when the thing meets the term's defining criteria. Otherwise
give the plain descriptive name.

### I · Unnecessary "could not verify"
It marks claims as unverified when one read would settle them: a plugin file, twice,
and a dependency that `package.json` lists and the file imports.

**Plan.** If verifying costs one or two reads, verify.

### J · Answer language
A question asked in English got a Turkish answer. Two things decide it today: the
agent definition defaults to Turkish, and the user's own Claude Code `language`
setting and `CLAUDE.md` load into the explainer like into any session.

**Plan.** Apply the order in Decisions: `EXPLAINER_LANG`, then the settings
`language`, then the question's language. The eval covers both sides: a case with a
`language` setting, and cases without one.

### K · Citation drift
One `file:line` citation was a line off. Every other citation checked in testing was
exact.

**Plan.** Quote the cited line in the answer, and add citation accuracy as an eval
dimension.

### L · Compaction summaries print as the user
A compaction summary is stored as a `user` entry with `isCompactSummary: true`, and
`transcript-tail.py` prints it under `USER`. The explainer is shown Claude Code's
automatic summary as if the user had written it. The baseline run passed the
attribution case anyway, so the cost is a risk rather than an observed failure.

**Plan.** Render it under its own label, such as `COMPACTION SUMMARY`.

### M · Times without dates
Messages print as `[HH:MM]`, and `--since HH:MM` assumes today. A session that spans
several days becomes ambiguous; the real session behind these findings ran across
three days.

**Plan.** Print the date whenever the transcript spans more than one day, and accept a
date in `--since`.

### Length
Answers ran 18 to 25 lines where about 12 is the target. The eval measures words
rather than lines: a terminal wraps a long paragraph, so a line count lets padding
through.

**Plan.** Put 3 to 5 example answers written at the target length into the agent
prompt. The eval checks length in code.

## Features

- **Forgotten context, on demand.** The user asks what the main agent has lost. The
  explainer compares decisions from before compaction with the current work, and writes
  a self-contained note for the user to paste. The note points at evidence the main
  agent can check for itself. A proactive version is a separate feature: it needs
  background watching, and it is out of scope for now.
- **Screenshot and error explanation.** In testing, a pasted UI banner was traced to its
  component, i18n key and data hook. This is a core use case and belongs in the eval
  suite.
- *Idea, not planned:* a Socratic mode, with glossary terms brought back by spaced
  repetition.

## Evaluation

- promptfoo runs the explainer agent itself, in one-shot mode, against a **synthetic**
  fixture repository and transcript. The suite ships with this repository, so it can
  never contain a real work session.
- 20–30 seed cases come from the findings above. Every case has a should and a
  should-not side, for example a true premise and a false premise.
- Each dimension gets one pass/fail judge: premise handling, verdict consistency, term
  precision, citation accuracy, answer language. Length is checked in code and is never
  graded by a judge.
- Judges are calibrated against the maintainer's own pass/fail critiques, until they
  agree more than 90% of the time.
- Scoring penalizes a wrong claim more than an honest "unverified".
- The current agent is baselined before any prompt change.

## Order

0. First commit of the current state.
1. This roadmap.
2. Eval suite and baseline.
3. Code fixes: E, F, D, L, M, C, B, A (all done 2026-10-19).
   A's eval case — "without reading anything, what is this project and what was
   the main agent doing?" — passed 3 of 3 runs with the briefing and 0 of 3 with
   it switched off.
   B tells open from closed through the process table rather than a `flock`
   lock: macOS has no `flock` command, and the process table leaves nothing on
   disk to go stale after a crash.
   C's eval case — the main agent adds retry jitter from a second worktree without
   naming it — passed 3 of 3 runs after the fix and 0 of 3 before it. Before the
   fix, the explainer checked its own checkout, found no jitter, and reported that
   the main agent had claimed work it never did.
4. Answer contract: G, H, I, J, K and length, each measured against the baseline.
5. Forgotten context.
6. Publication:
   - the design history, rewritten in English as `docs/design.md`;
   - remove personal names and paths;
   - fill in the README install placeholder;
   - add a LICENSE and a demo recording.

## References

- Verdict model: FEVER, <https://arxiv.org/abs/1803.05355>; Claude Code's review verifier
  states, <https://github.com/Piebald-AI/claude-code-system-prompts>
- Premise handling: Ask Don't Tell, <https://arxiv.org/abs/2602.23971>; AbstentionBench,
  <https://arxiv.org/abs/2506.09038>
- Length and style: Anthropic prompting best practices,
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices>;
  Verbosity ≠ Veracity, <https://arxiv.org/abs/2411.07858>
- Term precision: Semantic Diffusion,
  <https://martinfowler.com/bliki/SemanticDiffusion.html>; OpenGitOps principles,
  <https://opengitops.dev>; RFC 5861, <https://www.rfc-editor.org/rfc/rfc5861>
- Evaluation: Demystifying evals for AI agents,
  <https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents>; Using
  LLM-as-a-Judge, <https://hamel.dev/blog/posts/llm-judge/>; Length-Controlled
  AlpacaEval, <https://arxiv.org/abs/2404.04475>; Why Language Models Hallucinate,
  <https://arxiv.org/abs/2509.04664>; promptfoo Claude Agent SDK provider,
  <https://www.promptfoo.dev/docs/providers/claude-agent-sdk/>
- Later, if the eval calls for it: Chain-of-Verification,
  <https://arxiv.org/abs/2309.11495>
- Sessions: <https://code.claude.com/docs/en/sessions>,
  <https://code.claude.com/docs/en/cli-reference>
