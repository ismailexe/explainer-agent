#!/usr/bin/env python3
"""Where Claude Code keeps things, and how this project names them.

The only module that knows Claude Code's on-disk layout. Everything else in
`bin/` asks this module instead of building paths of its own, so the layout is
recorded once and a second harness would replace this file rather than being
threaded through the others.

Nothing here reads a transcript or answers a question; it resolves paths.
"""

import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path


HOME = Path.home()


def projects_dir(env=None):
    """Where Claude Code keeps per-project transcripts and memory.

    Claude Code moves its whole configuration directory when CLAUDE_CONFIG_DIR is
    set, so a fixed ~/.claude would read a stale tree on those machines.
    EXPLAINER_PROJECTS_DIR points the explainer alone somewhere else — the eval
    suite uses it to give every case an empty world of its own.
    """
    env = os.environ if env is None else env
    override = env.get("EXPLAINER_PROJECTS_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    config = env.get("CLAUDE_CONFIG_DIR", "").strip()
    return (Path(config).expanduser() if config else HOME / ".claude") / "projects"


PROJECTS = projects_dir()

# Measured against all 57 project directories on this machine: every character
# outside [A-Za-z0-9] becomes "-", not just "/". Paths carrying "_" or "." (macOS
# temp dirs, dotted folder names) break under a slash-only rule.
SLUG_CHARS = re.compile(r"[^A-Za-z0-9]")

def slug(path):
    """The ~/.claude/projects directory name Claude Code derives from a path."""
    return SLUG_CHARS.sub("-", str(path))


def main_worktree(start):
    """Absolute path of the repository's main worktree, or None outside git.

    A linked worktree has its own path but shares the main repo's git directory,
    and Claude Code keys memory/ off the directory the session was opened in.
    --git-common-dir points at the main repo from anywhere inside the tree, which
    is what lets a worktree session find the main project's notes.
    """
    for argv in (
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        ["git", "rev-parse", "--git-common-dir"],  # older git: may return ".git"
    ):
        try:
            out = subprocess.run(
                argv, cwd=start, capture_output=True, text=True, timeout=5
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if out.returncode == 0 and out.stdout.strip():
            common = (Path(start) / out.stdout.strip()).resolve()
            return common.parent
    return None


# This project's own agents. Their transcripts are never the conversation to
# explain, and the explainer's chats are the ones `--resume` brings back.
EXPLAINER_AGENTS = ("explainer", "explainer-researcher")


def transcript_meta(path, lines=40):
    """(agentSetting, entrypoint) from the head of a transcript.

    Measured on Claude Code 2.1.303: the agent-setting entry is the first or
    second line, a fork keeps it, and a `claude -p` run is entrypoint "sdk-cli"
    where an interactive chat is "cli".
    """
    agent = entry_point = None
    try:
        with Path(path).open(encoding="utf-8", errors="replace") as fh:
            for _ in range(lines):
                line = fh.readline()
                if not line:
                    break
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                agent = agent or entry.get("agentSetting")
                entry_point = entry_point or entry.get("entrypoint")
                if agent and entry_point:
                    break
    except OSError:
        pass
    return agent, entry_point


def is_explainer(path):
    """Whether a transcript belongs to one of this project's agents.

    The transcript says so itself, so no record has to be kept. The record this
    replaced had to be written at launch, and a forked chat it never heard of
    would have been taken for the conversation to explain.
    """
    return transcript_meta(path)[0] in EXPLAINER_AGENTS


def worktree_root(start):
    """The checkout we are standing in, or None outside git.

    Not the same question as main_worktree(). Memory is shared by every worktree
    of a repository, so it keys off the main one; sessions are not — a session
    opened in a different checkout was looking at different files. This is the
    boundary for "which conversations are mine".
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode == 0 and out.stdout.strip():
        return Path(out.stdout.strip()).resolve()
    return None


def candidate_files():
    files = list(PROJECTS.glob("*/*.jsonl"))
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def first_cwd(path):
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for _ in range(80):
                line = fh.readline()
                if not line:
                    return None
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if entry.get("cwd"):
                    return entry["cwd"]
    except OSError:
        return None
    return None


def sessions_for_cwd(skip=frozenset()):
    """Transcripts plausibly belonging to this directory, best match first.

    A session is a candidate only if it was opened here or in a directory above
    here, and ancestors are ranked deepest-first so a session opened in the repo
    beats one opened in $HOME. Sessions from unrelated directories are dropped
    rather than kept as a fallback: explaining a conversation that belongs to a
    different project, confidently and in detail, is worse than saying nothing.
    """
    here = os.getcwd()
    # The checkout is the boundary. Two failures it stands between:
    # $HOME is an ancestor of every path, so without a boundary any session ever
    # opened there became a candidate — an unrelated conversation, explained in
    # confident detail. And using the *main* worktree here instead broke the
    # ordinary worktree case: the main repo's path is not a prefix of a linked
    # worktree's, so a session opened at the worktree root stopped being visible
    # from a subdirectory of that same worktree.
    boundary = str(worktree_root(here) or here).rstrip("/")
    ranked = []
    for path in candidate_files()[:60]:
        if path.stem in skip:
            continue
        cwd = first_cwd(path)
        if not cwd:
            continue
        cwd = cwd.rstrip("/")
        if cwd == here:
            depth = len(here) + 1  # exact beats every ancestor
        elif here.startswith(cwd + "/") and (cwd == boundary or cwd.startswith(boundary + "/")):
            depth = len(cwd)  # an ancestor, but only inside this project
        else:
            continue
        ranked.append((depth, path))
    # candidate_files() is already newest-first, and sort is stable, so within one
    # specificity the most recent session stays ahead.
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [path for _, path in ranked]


def target_transcript(nth=1):
    """The conversation to explain, seen from a session that is not it.

    `explainer` runs as its own claude process, so the session id in the
    environment is its own — useless here. What is wanted is the newest session
    for this directory that is neither this process nor a previous explainer.
    """
    own = os.environ.get("CLAUDE_CODE_SESSION_ID")
    pool = [path for path in sessions_for_cwd({own} if own else frozenset())
            if not is_explainer(path)]
    if not pool:
        sys.exit(
            "no other session found for this directory.\n"
            "open the work session here first, or name its transcript with --file "
            "(transcript-tail.py --list-sessions shows what was found)"
        )
    if nth > len(pool):
        sys.exit(f"only {len(pool)} candidate session(s) for this directory")
    return pool[nth - 1]


def locate_transcript(path):
    """The transcript at `path`, or wherever Claude Code has moved it since.

    `/cd` moves a session's transcript into the new directory's project storage.
    The file name — the session id — survives the move, so that is what binds
    the explainer to its conversation; the path is only where it was last seen.
    """
    path = Path(path)
    if path.is_file():
        return path
    moved = sorted(PROJECTS.glob(f"*/{path.name}"), key=lambda p: p.stat().st_mtime, reverse=True)
    return moved[0] if moved else None


def main_agent_cwd(path, chunk=262144):
    """The directory the main agent's latest message was written from.

    Every transcript entry records its cwd, so a session that moved to another
    worktree says so on its own. Only the tail is read: the answer is the last
    entry, and a long session's file runs to megabytes.
    """
    try:
        with Path(path).open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - chunk))
            blob = fh.read()
    except OSError:
        return None
    for line in reversed(blob.decode("utf-8", errors="replace").splitlines()):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if (entry.get("type") in ("user", "assistant") and not entry.get("isSidechain")
                and entry.get("cwd")):
            return Path(entry["cwd"])
    first = first_cwd(Path(path))
    return Path(first) if first else None


def work_dir():
    """Where the main agent is working now — the files its claims are about.

    Project knowledge (EXPLAINER.md, memory, glossary) follows it there. The
    explainer's own bookkeeping does not: cursors and its session record stay
    keyed to the directory it was opened in. Without a transcript to ask, or when
    the directory is gone, this is simply the explainer's own directory.
    """
    forced = os.environ.get("EXPLAINER_TRANSCRIPT")
    if forced:
        path = locate_transcript(Path(forced).expanduser())
        cwd = main_agent_cwd(path) if path else None
        if cwd and cwd.is_dir():
            return cwd
    return Path(os.getcwd())


def branch_of(directory):
    """The branch checked out in `directory` right now, read from git.

    Not from the transcript: its gitBranch field was measured reporting HEAD on
    a checkout that was on main.
    """
    def git(*args):
        try:
            out = subprocess.run(["git", *args], cwd=directory,
                                 capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return ""
        return out.stdout.strip() if out.returncode == 0 else ""

    name = git("rev-parse", "--abbrev-ref", "HEAD")
    if name == "HEAD":
        sha = git("rev-parse", "--short", "HEAD")
        return f"detached at {sha}" if sha else None
    return name or None


def pick_file(nth):
    """The transcript to read, in falling order of certainty.

    1. --file, said outright.
    2. EXPLAINER_TRANSCRIPT, resolved by the `explainer` wrapper before it
       launched claude — at that moment the work session was still the newest
       transcript here, which is why the wrapper resolves it and not us.
    3. CLAUDE_CODE_SESSION_ID, which a subagent inherits from the session that
       spawned it: for /explain that is exactly the conversation to read.
    4. The newest session for this directory.
    """
    forced = os.environ.get("EXPLAINER_TRANSCRIPT")
    if forced and nth == 1:
        path = locate_transcript(Path(forced).expanduser())
        if path:
            return path

    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if session and nth == 1 and not forced:
        for path in PROJECTS.glob(f"*/{session}.jsonl"):
            return path

    pool = sessions_for_cwd()
    if not pool:
        sys.exit(
            f"no transcript found for this directory under {PROJECTS} — "
            "name one with --file"
        )
    if nth > len(pool):
        sys.exit(f"only {len(pool)} transcript(s) available for this directory")
    return pool[nth - 1]


def project_dir(cwd, repo):
    """The ~/.claude/projects entry holding this project's memory/ and notes.

    Claude Code keys this directory off the path the session was opened in, which
    for a worktree session is not the path memory/ was written under. Resolving
    the main worktree first is exact; the name scan below is a fallback for repos
    whose project directory was created under a since-renamed path.
    """
    seen, ordered = set(), []
    for base in (repo, cwd):
        if not base:
            continue
        candidate = PROJECTS / slug(base)
        if candidate.is_dir() and candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)

    if repo:
        tail = "-" + slug(Path(repo).name)
        by_size = []
        for entry in PROJECTS.iterdir():
            if not entry.is_dir() or entry in seen or not entry.name.endswith(tail):
                continue
            memory = entry / "memory"
            by_size.append((len(list(memory.glob("*.md"))) if memory.is_dir() else 0, entry))
        by_size.sort(key=lambda pair: pair[0], reverse=True)
        ordered.extend(entry for _, entry in by_size)

    populated = [d for d in ordered if (d / "memory").is_dir() and any((d / "memory").glob("*.md"))]
    return (populated or ordered or [None])[0]




CURSOR_DIR = "explainer-cursors"


def cursor_key(transcript):
    """One cursor per (chat, transcript) pair.

    Keyed by the explainer's own session id so two chats open on the same
    conversation do not consume each other's progress.
    """
    return f"{os.environ.get('CLAUDE_CODE_SESSION_ID', 'anon')}--{Path(transcript).stem}"


def cursor_path(transcript, cwd=None):
    """The one file holding this pair's position.

    A file per pair, not one shared file: two chats saving at the same moment
    each read, edited and rewrote the shared file, and the later write erased
    the other's update — a lost update. With nothing shared, nothing races.
    """
    return PROJECTS / slug(cwd or os.getcwd()) / CURSOR_DIR / f"{cursor_key(transcript)}.offset"


def read_cursor(transcript, cwd=None):
    """Byte offset already consumed for this transcript, or None on a first read."""
    try:
        text = cursor_path(transcript, cwd).read_text().strip()
    except OSError:
        return None
    return int(text) if text.isdigit() else None


def write_cursor(transcript, offset, cwd=None):
    """Record the offset atomically: a reader sees the old value or the new, never half.

    Written to a temporary file beside it and renamed over it, because a rename
    within one directory replaces the file in a single step.
    """
    path = cursor_path(transcript, cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        temp.write_text(f"{offset}\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


SKIPPED_FILE = ".skipped"


def glossary_dir(project):
    """Terms this project has already had explained, one file per term.

    Kept beside memory/ rather than in the repo on purpose: it accumulates from
    one person's questions, while the curated repo-local name table that a team
    shares belongs in EXPLAINER.md.
    """
    return (project / "glossary") if project else None


def run_mode():
    """`chat` for the session he comes back to, `once` for a single printed answer.

    The distinction is not cosmetic. In `once` mode the process prints only the
    final message and exits, so there is no "after the answer" — housekeeping put
    there would either never run or replace the explanation on screen.
    """
    return "once" if os.environ.get("EXPLAINER_MODE") == "once" else "chat"


def answer_language():
    """The language the explainer answers in.

    Turkish is the default because the project exists to teach English technical
    vocabulary inside Turkish sentences. EXPLAINER_LANG overrides it, and it is
    the single point of variation — no per-project copy of the language rule.
    """
    return os.environ.get("EXPLAINER_LANG", "").strip() or "Turkish"


def resolve_project(cwd=None):
    """This project's ~/.claude/projects entry — by default the project the main
    agent is working in now, which is the one whose glossary a term belongs to."""
    here = Path(cwd) if cwd else work_dir()
    return project_dir(here, main_worktree(here))


def worktree_paths(start):
    """Every checkout of the repository `start` is in, or [] outside git."""
    try:
        out = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=start,
                             capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    return [Path(line[len("worktree "):]) for line in out.stdout.splitlines()
            if line.startswith("worktree ")]


def explainer_chats(start=None):
    """Explainer chats opened anywhere in this repository, newest first.

    Chats only: a one-shot `explainer "question"` printed its answer and left
    nothing to come back to, as Claude Code's own picker leaves `-p` runs out.
    """
    here = Path(start or os.getcwd())
    roots = [str(p) for p in worktree_paths(here)] or [str(worktree_root(here) or here)]
    chats = []
    for path in candidate_files():
        agent, entry_point = transcript_meta(path)
        if agent != "explainer" or entry_point == "sdk-cli":
            continue
        cwd = (first_cwd(path) or "").rstrip("/")
        if any(cwd == root or cwd.startswith(root + "/") for root in roots):
            chats.append(path)
    return chats


def first_question(path, width=60):
    """The first thing typed into a chat — its label, since these chats get no title."""
    try:
        with Path(path).open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if (entry.get("type") != "user" or entry.get("isMeta")
                        or entry.get("isCompactSummary")):
                    continue
                content = (entry.get("message") or {}).get("content")
                if isinstance(content, list):
                    content = " ".join(b.get("text", "") for b in content
                                       if isinstance(b, dict) and b.get("type") == "text")
                text = " ".join(str(content or "").split())
                if text and not text.startswith("<"):
                    return text if len(text) <= width else text[: width - 1] + "…"
    except OSError:
        pass
    return "(no question yet)"


def sessions_held(ps_lines):
    """Session ids that running processes have open, from `ps` argument lines.

    A process holds the id after --session-id, and the id after --resume unless
    it is forking that session into a new one. Read from the process table, so a
    chat that crashed is closed at once — nothing on disk can go stale.
    """
    held = set()
    for line in ps_lines:
        args = line.split()
        forking = "--fork-session" in args
        for flag, value in zip(args, args[1:]):
            if flag == "--session-id" or (flag in ("--resume", "-r") and not forking):
                held.add(value)
    return held


def open_sessions():
    try:
        out = subprocess.run(["ps", "-axo", "args="], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return set()
    return sessions_held(out.stdout.splitlines())


def pick_chat(selector=None):
    """Choose an earlier chat and how to bring it back: "resume <id>" or "fork <id>".

    A closed chat is resumed — the same conversation, pointed at the current
    work session. One still open in another window is forked instead, because
    two processes resuming one session interleave into a single transcript. The
    person never has to know the difference.
    """
    chats = explainer_chats()[:20]
    if not chats:
        sys.exit("no earlier explainer chat in this repository")
    held = open_sessions()
    rows = []
    for i, path in enumerate(chats, 1):
        state = "open" if path.stem in held else "closed"
        stamp = dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%m-%d %H:%M")
        where = Path(first_cwd(path) or "?").name
        rows.append((path, state))
        print(f"{i:>2}. {stamp}  {state:<6}  {where:<18.18}  {first_question(path)}",
              file=sys.stderr)

    if selector is None:
        try:
            with open("/dev/tty") as tty:
                print("Which chat? [number, Enter to cancel]: ", end="", file=sys.stderr, flush=True)
                selector = tty.readline().strip()
        except OSError:
            sys.exit("no terminal to ask on: pass a number, as in explainer --resume 2")
    if not selector:
        sys.exit(1)

    if selector.isdigit() and 1 <= int(selector) <= len(rows):
        chosen = [rows[int(selector) - 1]]
    else:
        chosen = [row for row in rows if row[0].stem.startswith(selector)]
    if len(chosen) != 1:
        sys.exit(f"no single chat matches {selector!r}")
    path, state = chosen[0]
    return f"{'fork' if state == 'open' else 'resume'} {path.stem}"


def _cli():
    """A path oracle for the shell.

    The `explainer` wrapper needs the same paths this module resolves. Asking
    for them here keeps the layout recorded once instead of being reimplemented
    in bash, where it would drift the first time Claude Code moves a directory.
    """
    if len(sys.argv) < 2:
        sys.exit("usage: explainer_layout.py <project-dir|glossary-dir|answer-language|pick-chat [N|ID]>")
    what = sys.argv[1]
    if what == "pick-chat":
        print(pick_chat(sys.argv[2] if len(sys.argv) > 2 else None))
        return
    if what == "answer-language":
        print(answer_language())
        return
    project = resolve_project()
    if what == "project-dir":
        print(project if project else "")
        return
    if what == "glossary-dir":
        print(glossary_dir(project) if project else "")
        return
    sys.exit(f"unknown query: {what}")


if __name__ == "__main__":
    _cli()
