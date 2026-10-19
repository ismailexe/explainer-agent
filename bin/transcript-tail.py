#!/usr/bin/env python3
"""Print the readable part of a Claude Code session transcript.

Claude Code appends every session to ~/.claude/projects/<slug>/<session-id>.jsonl
as it happens. This script strips that file down to what a human said and what
the assistant answered, so the `explainer` agent can see the conversation it is
being asked about without loading raw JSON into its context.

  transcript-tail.py                      last 14 messages of the current session
  transcript-tail.py --turns 40           more history
  transcript-tail.py --grep ledger        every mention of a term, with context
  transcript-tail.py --tool-results       include (truncated) tool output
  transcript-tail.py --file PATH          a specific transcript
  transcript-tail.py --nth 2              second-newest session for this cwd
  transcript-tail.py --sources            inventory of everything worth reading
  transcript-tail.py --new                only what has been said since you last looked
  transcript-tail.py --since 14:05        only what was said after that time today
  transcript-tail.py --since "10-17 14:05"  the same, on another day
  transcript-tail.py --candidates         names worth researching that are not recorded yet
  transcript-tail.py --resolve-target     path of the session to explain, for `explainer`
  transcript-tail.py --list-sessions      every candidate session, newest first

The explainer is a conversation someone comes back to over hours, so the useful
question is usually not "what happened" but "what happened since I last looked".
That is --new.
"""

import argparse
import datetime as dt
import functools
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explainer_layout import (  # noqa: E402
    HOME,
    PROJECTS,
    SKIPPED_FILE,
    read_cursor,
    answer_language,
    run_mode,
    branch_of,
    first_cwd,
    is_explainer,
    glossary_dir,
    main_agent_cwd,
    main_worktree,
    pick_file,
    project_dir,
    sessions_for_cwd,
    target_transcript,
    work_dir,
    worktree_root,
    write_cursor,
)

# Conversation noise Claude Code injects into the transcript: it is addressed to
# the model, never typed by anyone, and reprinting it would drown the dialogue.
NOISE = re.compile(
    r"<system-reminder>.*?</system-reminder>"
    r"|<local-command-[^>]*>.*?</local-command-[^>]*>"
    r"|<command-(name|message|args)>.*?</command-(name|message|args)>",
    re.S,
)



# --------------------------------------------------------------------------
# Reading a transcript
# --------------------------------------------------------------------------


def clean(text):
    return NOISE.sub("", text or "").strip()


def clock(entry):
    """MM-DD HH:MM, local time. The date is always there: sessions run for days, and
    a bare 20:05 sent the reader to the wrong one."""
    stamp = entry.get("timestamp")
    if not stamp:
        return "--- --:--"
    try:
        moment = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        return moment.astimezone().strftime("%m-%d %H:%M")
    except ValueError:
        return "--- --:--"


@functools.lru_cache(maxsize=64)
def checkout(cwd):
    """The checkout a directory belongs to, so a move into a subdirectory is not
    mistaken for a move to another worktree."""
    if not cwd:
        return None
    root = worktree_root(cwd) if Path(cwd).is_dir() else None
    return str(root or Path(cwd))


def location_line(path):
    """Where the main agent is working now, for the top of every read."""
    cwd = main_agent_cwd(path)
    if not cwd:
        return None
    place = checkout(str(cwd))
    branch = branch_of(place) if Path(place).is_dir() else None
    line = f"# main agent is working in: {place}" + (f" · branch {branch}" if branch else "")
    if place != checkout(os.getcwd()):
        line += "\n# that is not your directory — check its claims against files there"
    return line


def render(entry, args, home=None):
    """Turn one transcript entry into printable lines, or None if it carries nothing.

    With `home`, the checkout the session started in, an entry written from any
    other checkout is marked with where it was: what it says is about the files
    there, not here.
    """
    if entry.get("type") not in ("user", "assistant"):
        return None
    if entry.get("isSidechain") and not args.include_sidechain:
        return None

    message = entry.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    if not isinstance(content, list):
        return None

    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text":
            body = clean(block.get("text"))
            if body:
                parts.append(body[: args.max_chars])
        elif kind == "thinking" and args.thinking:
            body = clean(block.get("thinking"))
            if body:
                parts.append("(thinking) " + body[: args.max_chars])
        elif kind == "tool_use":
            payload = json.dumps(block.get("input"), ensure_ascii=False)
            parts.append(f"  · tool: {block.get('name')} {payload[:220]}")
        elif kind == "tool_result" and args.tool_results:
            raw = block.get("content")
            if isinstance(raw, list):
                raw = " ".join(b.get("text", "") for b in raw if isinstance(b, dict))
            body = clean(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False))
            if body:
                parts.append("  · result: " + body[:600].replace("\n", " "))

    if not parts:
        return None
    if entry.get("isCompactSummary"):
        # Stored as a user entry, but Claude Code wrote it when the context ran
        # out; shown as USER, it reads as something the person said.
        who = "COMPACTION SUMMARY (written by Claude Code, not the user)"
    elif entry.get("type") == "user":
        who = "USER"
    else:
        who = "MAIN AGENT"
    place = checkout(entry.get("cwd")) if home is not None else None
    if place and place != home:
        who += f" · in {place}"
    return f"[{clock(entry)}] {who}\n" + "\n".join(parts)


def moment(entry):
    """The entry's wall-clock time, or None when it carries no timestamp."""
    stamp = entry.get("timestamp")
    if not stamp:
        return None
    try:
        return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def parse_since(text):
    """Accept the shapes a person actually types for "since when".

    MM-DD HH:MM is what this script prints next to every message, so it reads
    back as-is; HH:MM alone means today, and a full ISO timestamp works too.
    """
    text = text.strip()
    try:
        return dt.datetime.fromisoformat(text).astimezone()
    except ValueError:
        pass
    today = dt.date.today()
    for shape in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            # The year is supplied before parsing so 02-29 is a valid date.
            when = dt.datetime.strptime(f"{today.year}-{text}", shape)
        except ValueError:
            continue
        if when.date() > today:          # 12-31 typed in January means last year
            when = when.replace(year=today.year - 1)
        return when.astimezone()
    for shape in ("%H:%M", "%H:%M:%S"):
        try:
            clock_only = dt.datetime.strptime(text, shape).time()
        except ValueError:
            continue
        return dt.datetime.combine(today, clock_only).astimezone()
    sys.exit(f'--since: cannot read "{text}" — use HH:MM, "MM-DD HH:MM" or a full ISO timestamp')


def load_since_cursor(path, args):
    """Everything appended since this chat last read, and the new high-water mark.

    A byte offset rather than a clock time, because the offset is exact and, more
    to the point, because nothing has to remember it. Asking the model to pass
    `--since HH:MM` on every follow-up made catching up a thing it could forget —
    and in this project a chore left to the model's discretion has a measured
    record of not happening. Only whole lines are consumed: the final line of a
    live transcript is often half flushed, and re-reading it next time is correct.
    """
    start = read_cursor(path)
    if start is None:                    # first look in this chat
        messages = load(path, args)[-args.turns:]
        write_cursor(path, path.stat().st_size)
        return messages, "first"

    home = checkout(first_cwd(path))
    size = path.stat().st_size
    if size < start:                     # the file was replaced under us
        start = 0
    out, consumed = [], start
    with path.open("rb") as fh:
        fh.seek(start)
        blob = fh.read()
    text = blob.decode("utf-8", errors="replace")
    for line in text.splitlines(keepends=True):
        if not line.endswith("\n"):
            break                        # a partial tail; leave it for next time
        consumed += len(line.encode("utf-8", errors="replace"))
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        block = render(entry, args, home)
        if block:
            out.append(block)
    write_cursor(path, consumed)
    return out, "incremental"


def load(path, args):
    cutoff = parse_since(args.since) if getattr(args, "since", None) else None
    home = checkout(first_cwd(path))
    out = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue  # a partially flushed final line while the session is live
            if cutoff:
                when = moment(entry)
                if when is None or when < cutoff:
                    continue
            block = render(entry, args, home)
            if block:
                out.append(block)
    return out


# --------------------------------------------------------------------------
# --candidates: the free gate in front of the model
#
# Background research costs a model call per poll if the model is the one
# deciding whether there is anything to research. Almost always there is not:
# ordinary work adds paragraphs of prose and no new names. This finds the names
# with a regex, subtracts everything already recorded or already rejected, and
# says nothing when nothing is new - so the model is only woken when it has
# something to judge.
#
# It deliberately does not decide whether a name is *worth* recording. That
# needs to know the project, and it is what the model is for.
# --------------------------------------------------------------------------

IDENTIFIER = re.compile(
    r"`([^`\n]{2,60})`"                              # anything the writer backticked
    r"|\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b"           # snake_case
    r"|\b([a-z]+(?:-[a-z]+){1,3})\b"                  # kebab-case
    r"|\b([a-z][a-z0-9]*[A-Z][A-Za-z0-9]*)\b"         # camelCase
)

# Words that are structure, not vocabulary: they carry no concept to look up, so
# proposing them wastes a model call. Kept short on purpose - deciding what he
# already knows is not this filter's job.
NOISE_WORDS = frozenset("""
true false null nil none void int str bool float list dict array object string number
if else for while return break continue import export from const let var func def class
this self new async await try catch finally throw yield lambda print echo cat ls cd rm
mkdir touch grep sed awk head tail wc git npm bun pip go run test build make sudo chmod
all any each none both same other every some most many few more less than then when
must should would could will shall might may does did has have was were been being
add commit push pull merge diff show log status branch checkout clone fetch rebase stash
get set put post delete patch http https url uri json yaml yml toml csv txt md sh py js
ts tsx jsx rs java rb php css html sql env config file files dir path line lines code
error errors warning info debug logs message messages result results data value values
name names type types item items user users id ids key keys todo fixme note ok yes done
next prev first last one two three
""".split())

EXTENSIONS = (".md", ".py", ".go", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml",
              ".sh", ".txt", ".sql", ".toml", ".css", ".html", ".rs", ".java", ".rb", ".lock")


def looks_like_a_term(word):
    """Reject the shapes that are addresses rather than concepts."""
    if not 3 <= len(word) <= 60:
        return False
    if "/" in word or word.startswith(("-", ".", "$", "#")):
        return False           # a path, a flag, a variable - not a name to look up
    if word.lower().endswith(EXTENSIONS):
        return False           # a filename
    if not any(ch.isalpha() for ch in word):
        return False
    if word.count(" ") > 3:
        return False           # a sentence someone backticked
    parts = [part for part in re.split(r"[\s_-]+", word.lower()) if part]
    return not all(part in NOISE_WORDS for part in parts)


def recorded_terms(project):
    """Everything already answered or already judged not worth answering."""
    gloss = glossary_dir(project)
    if not gloss or not gloss.is_dir():
        return set()
    known = set()
    for entry in gloss.glob("*.md"):
        known.add(entry.stem)
        known.add(entry.stem.replace("-", " "))
    try:
        known |= {line.strip() for line in (gloss / SKIPPED_FILE).read_text().splitlines() if line.strip()}
    except OSError:
        pass
    return {term.lower() for term in known}


CODE_FENCE = re.compile(r"```.*?```", re.S)
PATH_RUN = re.compile(r"[~./]?(?:[\w.@+-]+/){1,}[\w.@+-]*")
COMMAND_LINE = re.compile(r"^\s*(?:[$>]|\d+x?\s|\s*·)", re.M)


def prose_only(path, args, cutoff=None, tail=None):
    """What was actually said recently, with the machinery stripped out.

    Two mistakes the first version made, both found by running it on a real
    80-hour session. It mined tool calls and code, so its top "concepts" were the
    repository's own directory name (660 mentions) and a Python method from a
    pasted snippet. And it read the whole transcript, so it proposed 1139 names —
    a list no one, model or person, can act on.

    Concepts appear in sentences, and "new" means recent. Both are narrowed here
    rather than filtered afterwards, because a filter cannot tell a field name
    from a concept and should not be asked to.
    """
    said = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") not in ("user", "assistant"):
                continue
            if entry.get("isSidechain") and not args.include_sidechain:
                continue
            if cutoff:
                when = moment(entry)
                if when is None or when < cutoff:
                    continue
            content = (entry.get("message") or {}).get("content")
            chunk = []
            if isinstance(content, str):
                chunk.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        chunk.append(block.get("text") or "")
            if chunk:
                said.append("\n".join(chunk))

    if tail and not cutoff:
        said = said[-tail:]
    text = clean("\n".join(said))
    text = CODE_FENCE.sub(" ", text)          # code is not vocabulary
    text = PATH_RUN.sub(" ", text)            # a path segment is an address
    text = COMMAND_LINE.sub(" ", text)
    return text


def local_noise(cwd, repo):
    """Names of the directories we are standing in: addresses, not concepts."""
    words = set()
    for base in (cwd, repo):
        if not base:
            continue
        for part in Path(base).parts:
            for piece in re.split(r"[^A-Za-z0-9]+", part):
                if piece:
                    words.add(piece.lower())
            words.add(re.sub(r"[^A-Za-z0-9-]+", "-", part).lower())
    return words


def print_candidates(args):
    cwd = work_dir()
    repo = main_worktree(cwd)
    project = project_dir(cwd, repo)
    known = recorded_terms(project) | local_noise(cwd, repo)

    path = Path(args.file).expanduser() if args.file else pick_file(args.nth)
    cutoff = parse_since(args.since) if args.since else None
    text = prose_only(path, args, cutoff=cutoff, tail=args.turns)

    counts = {}
    for groups in IDENTIFIER.findall(text):
        for word in groups:
            word = word.strip()
            if not word or not looks_like_a_term(word):
                continue
            flat = word.lower()
            if flat in known or flat.replace("-", " ") in known:
                continue
            counts[word] = counts.get(word, 0) + 1

    if not counts:
        print("nothing new - every name in this stretch of conversation is already")
        print("recorded or already judged not worth recording. Do not research anything.")
        sys.exit(1)

    # A name repeated dozens of times across a working session is the furniture of
    # the project, not something he stumbled over once and needs named.
    ranked = sorted(
        ((word, hits) for word, hits in counts.items() if hits <= args.candidate_ceiling),
        key=lambda pair: (-pair[1], pair[0]),
    )
    if not ranked:
        print("nothing new worth a look — the only unrecorded names appear so often")
        print("they are this project's furniture. Do not research anything.")
        sys.exit(1)
    window = f"since {args.since}" if args.since else f"the last {args.turns} messages"
    print(f"# {len(ranked)} unrecorded names in {window}, most mentioned first")
    print("# most of these are field and function names, not concepts. Research only a")
    print("# name whose industry counterpart would teach him something; --skip the rest")
    print("# so they stop coming back. Skipping most of a list is the normal outcome.\n")
    for word, hits in ranked[:15]:
        print(f"{hits:>3}x  {word}")
    if len(ranked) > 15:
        print(f"\n({len(ranked) - 15} more, not shown — if none of the above is a concept,")
        print("--skip them and stop rather than digging further down the list.)")


# --------------------------------------------------------------------------
# --sources: the inventory of what this project knows
# --------------------------------------------------------------------------

INLINE_LIMIT = 20000

# Advisory only: catches stale paths mentioned in EXPLAINER.md. The file's own
# text is the contract; this scan just flags entries that no longer exist.
PATHLIKE = re.compile(r"`([~./A-Za-z0-9][^`\s]*(?:/[^`\s]*|\.(?:md|txt|json|ya?ml)))`")


def show(label, path, limit=INLINE_LIMIT):
    """Print one file's contents inline, or say plainly that it is not there."""
    if not path or not Path(path).is_file():
        print(f"[missing] {label}: {path}")
        return None
    body = Path(path).read_text(encoding="utf-8", errors="replace")
    print(f"[found] {label}: {path}  ({len(body)} chars)")
    print("--------8<--------")
    print(body[:limit].rstrip())
    if len(body) > limit:
        print(f"... truncated, {len(body) - limit} more chars — read the file directly")
    print("-------->8--------\n")
    return body


# --------------------------------------------------------------------------
# --briefing: what the explainer knows before its first tool call
# --------------------------------------------------------------------------

BRIEFING_LIMIT = 6000


def text_of(entry):
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, list):
        content = " ".join(b.get("text", "") for b in content
                           if isinstance(b, dict) and b.get("type") == "text")
    return " ".join(clean(str(content or "")).split())


def last_exchange(path, chunk=262144):
    """The latest request the user typed and the latest thing the main agent said."""
    user = agent = None
    try:
        with Path(path).open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - chunk))
            lines = fh.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None, None
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("isSidechain") or entry.get("isMeta") or entry.get("isCompactSummary"):
            continue
        text = text_of(entry)
        if not text:
            continue
        if entry.get("type") == "user" and user is None:
            user = text
        elif entry.get("type") == "assistant" and agent is None:
            agent = text
        if user and agent:
            break
    return user, agent


def git_lines(where, *args):
    try:
        out = subprocess.run(["git", *args], cwd=where, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []
    return out.stdout.splitlines() if out.returncode == 0 else []


def briefing():
    """A short orientation for the explainer's system prompt, built at launch.

    Everything in it is read from disk by code, so the explainer knows what the
    project is and what the work session is doing before it runs a single tool.
    It ages as the session moves; --new and --sources stay the current truth.
    """
    work = work_dir()
    repo = main_worktree(work) or worktree_root(work) or work
    parts = [f"# Briefing, built when this chat was launched ({dt.datetime.now():%m-%d %H:%M})",
             "It ages as the session moves. What transcript-tail.py prints is current; "
             "check claims there and in the files, not here."]

    readme = next((repo / name for name in ("README.md", "readme.md", "README") if (repo / name).is_file()), None)
    if readme:
        body = readme.read_text(encoding="utf-8", errors="replace").strip()
        parts += ["", "## What the project says it is", body[:1500] + (" …" if len(body) > 1500 else "")]

    docs = sorted((repo / "docs").glob("*.md"))[:15] if (repo / "docs").is_dir() else []
    if docs:
        parts += ["", "## Its documents"]
        for doc in docs:
            heading = next((l.lstrip("# ").strip() for l in doc.read_text(encoding="utf-8", errors="replace").splitlines()
                            if l.startswith("#")), "")
            parts.append(f"- {doc.relative_to(repo)}" + (f" — {heading}" if heading else ""))

    if (repo / ".claude" / "EXPLAINER.md").is_file():
        parts += ["", "This project briefs you in .claude/EXPLAINER.md; transcript-tail.py --sources prints it."]

    log = git_lines(work, "log", "--oneline", "-8")
    if log:
        parts += ["", "## Recent commits where the main agent works"] + log
    trees = git_lines(work, "worktree", "list")
    if len(trees) > 1:
        parts += ["", "## Checkouts of this repository"] + trees

    try:
        transcript = pick_file(1)
    except SystemExit:
        transcript = None
    if transcript:
        parts += ["", "## The work session right now"]
        where = location_line(transcript)
        if where:
            parts.append(where.splitlines()[0].lstrip("# "))
        user, agent = last_exchange(transcript)
        if user:
            parts.append(f"last request from the user: {user[:400]}")
        if agent:
            parts.append(f"last thing the main agent said: {agent[:400]}")

    text = "\n".join(parts)
    return text if len(text) <= BRIEFING_LIMIT else text[:BRIEFING_LIMIT] + "\n… (cut)"


def print_sources(args):
    # Project knowledge follows the main agent: when it works in another
    # worktree, that checkout's EXPLAINER.md and its repository's memory apply.
    cwd = work_dir()
    repo = main_worktree(cwd)
    project = project_dir(cwd, repo)

    print("# sources inventory")
    print("# read in this order; an earlier source outranks a later one on conflict\n")

    print("## 0 · where you are")
    own = Path(os.getcwd())
    if checkout(str(own)) != checkout(str(cwd)):
        print(f"you        : {own}")
        print(f"main agent : {cwd}   (everything below is resolved from here)")
    branch = branch_of(cwd) if repo else None
    print(f"cwd        : {cwd}" + (f"   (branch {branch})" if branch else ""))
    if repo and repo != cwd:
        print(f"repo       : {repo}   (cwd is a linked worktree of it)")
    elif repo:
        print(f"repo       : {repo}")
    else:
        print("repo       : (not a git repository)")
    print(f"project dir: {project if project else f'(none found under {PROJECTS})'}")

    try:
        transcript = Path(args.file).expanduser() if args.file else pick_file(args.nth)
        count = sum(1 for _ in transcript.open(encoding="utf-8", errors="replace"))
        print(f"transcript : {transcript}  ({count} raw lines)")
    except SystemExit as exc:
        print(f"transcript : unavailable — {exc}")
    print("read it with: transcript-tail.py --turns 20\n")

    print("## 1 · EXPLAINER.md — what this project wants you to know")
    print("# the private copy wins where the two disagree\n")
    explainers = []
    if repo and repo != cwd:
        explainers.append(("repo (shared, committed)", repo / ".claude" / "EXPLAINER.md"))
        explainers.append(("worktree (shared, committed)", cwd / ".claude" / "EXPLAINER.md"))
    else:
        explainers.append(("repo (shared, committed)", cwd / ".claude" / "EXPLAINER.md"))
    if project:
        explainers.append(("private (never committed)", project / "EXPLAINER.md"))

    referenced, found_any = [], False
    for label, path in explainers:
        body = show(label, path)
        if body:
            found_any = True
            referenced.extend(PATHLIKE.findall(body))
    if not found_any:
        print("no EXPLAINER.md anywhere — this project has not briefed you.")
        print("say so in your answer if it costs you an explanation you could not verify.\n")

    print("## 2 · memory — why past decisions were made")
    print("# a memory records what was true when it was written; it can be STALE.")
    print("# verify any file, flag or command it names before you rely on it.\n")
    if project and (project / "memory").is_dir():
        memory = project / "memory"
        files = sorted(memory.glob("*.md"))
        print(f"dir: {memory}  ({len(files)} files)")
        print("read one with: cat '<dir>/<name>.md'\n")
        show("MEMORY.md (the index)", memory / "MEMORY.md")
    else:
        print(f"[missing] memory dir under {project if project else '(unknown project dir)'}\n")

    print("## 3 · glossary — terms YOU have already explained here")
    print("# not the same thing as the table in EXPLAINER.md above: that one is written")
    print("# by the project owner and you only read it. This one is yours to append to,")
    print("# and only the terms listed below are in it.\n")
    gloss = glossary_dir(project)
    if gloss and gloss.is_dir():
        terms = sorted(entry.stem for entry in gloss.glob("*.md"))
        if terms:
            print(f"dir: {gloss}  ({len(terms)} terms)")
            print("read one with : explainer-glossary.py --lookup '<term>'")
            print("add a new one : explainer-glossary.py --add '<term>' --local '<repo name>' ...")
            print("\nknown: " + ", ".join(terms) + "\n")
        else:
            print(f"dir: {gloss}")
            print("EMPTY — nothing has been recorded here yet, whatever EXPLAINER.md lists.\n")
    else:
        print("EMPTY — no glossary yet, whatever EXPLAINER.md lists; the first --add creates it.")
        print(f"it will live at: {glossary_dir(project) if project else '(unknown project dir)'}\n")

    print("## 4 · how to answer")
    pinned = answer_language()
    if pinned:
        print(f"answer language: {pinned}   (pinned by EXPLAINER_LANG)")
    else:
        print("answer language: not pinned — use the response language your system prompt")
        print("                 sets, if it sets one; otherwise the language of his question")
    print("technical terms stay in English regardless of the answer language.")
    mode = run_mode()
    print(f"run mode       : {mode}")
    if mode == "once":
        print("# one printed answer, then the process exits. Only your FINAL message is")
        print("# shown, so it must be the explanation — and there is no after, so do not")
        print("# start background research.")
    else:
        print("# an open session he returns to. After the answer is written you may do")
        print("# housekeeping in the same turn; he sees everything.")
    print()

    print("## 5 · CLAUDE.md in scope")
    seen = set()
    for path in [HOME / ".claude" / "CLAUDE.md", (repo or cwd) / "CLAUDE.md", cwd / "CLAUDE.md"]:
        if path in seen:
            continue
        seen.add(path)
        mark = "[found]  " if path.is_file() else "[missing]"
        size = f"  ({path.stat().st_size} bytes)" if path.is_file() else ""
        print(f"{mark} {path}{size}")
    print("# not inlined — cat the ones you need.\n")

    if referenced:
        print("## 6 · paths named in EXPLAINER.md")
        print("# advisory: a missing one means the briefing has gone stale\n")
        for raw in dict.fromkeys(referenced):
            target = Path(raw).expanduser()
            if not target.is_absolute():
                target = (repo or cwd) / raw
            print(f"{'ok     ' if target.exists() else 'MISSING'}  {raw}")
        print()


# --------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--turns", type=int, default=14, help="how many trailing messages to print")
    ap.add_argument("--grep", help="print only messages mentioning this term, with neighbours")
    ap.add_argument("--file", help="explicit transcript path")
    ap.add_argument("--nth", type=int, default=1, help="1 = newest session for this directory")
    ap.add_argument("--tool-results", action="store_true", help="include truncated tool output")
    ap.add_argument("--thinking", action="store_true", help="include the assistant's thinking blocks")
    ap.add_argument("--include-sidechain", action="store_true", help="include subagent chatter")
    ap.add_argument("--max-chars", type=int, default=2500, help="per-message truncation")
    ap.add_argument("--since", metavar="TIME", help='only messages after this time: HH:MM (today), "MM-DD HH:MM" or ISO timestamp')
    ap.add_argument("--sources", action="store_true", help="inventory of everything worth reading, instead of the transcript")
    ap.add_argument("--briefing", action="store_true", help="the short orientation `explainer` puts in the system prompt at launch")
    ap.add_argument("--resolve-target", action="store_true", help="print the path of the session to explain, excluding this one")
    ap.add_argument("--list-sessions", action="store_true", help="every candidate session for this directory, newest first")
    ap.add_argument("--new", action="store_true", help="only what was appended since this chat last read; the position is remembered for you")
    ap.add_argument("--candidates", action="store_true", help="unrecorded names in the conversation; exits 1 when there are none")
    ap.add_argument("--candidate-ceiling", type=int, default=12, help="ignore names mentioned more often than this: they are the project's furniture")
    args = ap.parse_args()

    if args.candidates:
        print_candidates(args)
        return

    if args.resolve_target:
        print(target_transcript(args.nth))
        return

    if args.list_sessions:
        own = os.environ.get("CLAUDE_CODE_SESSION_ID")
        pool = sessions_for_cwd()
        if not pool:
            sys.exit("no sessions found for this directory")
        for i, path in enumerate(pool, 1):
            if path.stem == own:
                tag = "this process"
            elif is_explainer(path):
                tag = "an explainer session"
            else:
                tag = "candidate"
            stamp = dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"{i:>2}. {stamp}  {tag:<20} {path.name}")
        return

    if args.sources:
        print_sources(args)
        return

    if args.briefing:
        print(briefing())
        return

    if args.new:
        path = Path(args.file).expanduser() if args.file else pick_file(args.nth)
        messages, kind = load_since_cursor(path, args)
        print(f"# transcript: {path}")
        where = location_line(path)
        if where:
            print(where)
        if kind == "first":
            print(f"# first look in this chat — the last {args.turns} messages\n")
        elif not messages:
            print("# nothing new since you last looked. His question is about something")
            print("# you have already read; do not read the whole conversation again.")
            return
        else:
            print(f"# {len(messages)} new message(s) since you last looked\n")
        for message in messages:
            print(message, "\n")
        return

    path = Path(args.file).expanduser() if args.file else pick_file(args.nth)
    messages = load(path, args)
    print(f"# transcript: {path}")
    where = location_line(path)
    if where:
        print(where)
    print(f"# {len(messages)} readable messages\n")

    if args.grep:
        needle = args.grep.lower()
        hits = [i for i, m in enumerate(messages) if needle in m.lower()]
        if not hits:
            print(f'no mention of "{args.grep}" in this transcript')
            return
        shown = set()
        for i in hits:
            for j in range(max(0, i - 1), min(len(messages), i + 2)):
                if j not in shown:
                    shown.add(j)
                    print(messages[j], "\n")
        return

    shown = messages if args.since else messages[-args.turns :]
    for message in shown:
        print(message, "\n")


if __name__ == "__main__":
    main()
