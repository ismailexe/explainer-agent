#!/usr/bin/env python3
"""Where Claude Code keeps things, and how this project names them.

The only module that knows Claude Code's on-disk layout. Everything else in
`bin/` asks this module instead of building paths of its own, so the layout is
recorded once and a second harness would replace this file rather than being
threaded through the others.

Nothing here reads a transcript or answers a question; it resolves paths.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


HOME = Path.home()
PROJECTS = HOME / ".claude" / "projects"

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


STATE_FILE = "explainer-sessions.txt"


def state_path(cwd=None):
    """Where `explainer` records the session ids it has launched.

    Without this record the explainer would, on its second run, resolve the
    first explainer session as the conversation to explain — it is the newest
    transcript for this directory by then.
    """
    return PROJECTS / slug(cwd or os.getcwd()) / STATE_FILE


def explainer_sessions(cwd=None):
    path = state_path(cwd)
    try:
        return {line.strip() for line in path.read_text().splitlines() if line.strip()}
    except OSError:
        return set()


def remember_explainer_session(session_id, cwd=None):
    path = state_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(session_id + "\n")


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
    skip = set(explainer_sessions())
    own = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if own:
        skip.add(own)
    pool = sessions_for_cwd(skip)
    if not pool:
        sys.exit(
            "no other session found for this directory.\n"
            "open the work session here first, or name its transcript with --file "
            "(transcript-tail.py --list-sessions shows what was found)"
        )
    if nth > len(pool):
        sys.exit(f"only {len(pool)} candidate session(s) for this directory")
    return pool[nth - 1]


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
        path = Path(forced).expanduser()
        if path.is_file():
            return path

    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if session and nth == 1 and not forced:
        for path in PROJECTS.glob(f"*/{session}.jsonl"):
            return path

    pool = sessions_for_cwd()
    if not pool:
        sys.exit(
            "no transcript found for this directory under ~/.claude/projects — "
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




CURSOR_FILE = "explainer-cursors.txt"


def cursor_path(cwd=None):
    """Where each explainer chat records how far it has read."""
    return PROJECTS / slug(cwd or os.getcwd()) / CURSOR_FILE


def cursor_key(transcript):
    """One cursor per (chat, transcript) pair.

    Keyed by the explainer's own session id so two chats open on the same
    conversation do not consume each other's progress.
    """
    return f"{os.environ.get('CLAUDE_CODE_SESSION_ID', 'anon')}:{Path(transcript).stem}"


def read_cursor(transcript, cwd=None):
    """Byte offset already consumed for this transcript, or None on a first read."""
    key = cursor_key(transcript)
    try:
        for line in cursor_path(cwd).read_text().splitlines():
            saved_key, _, offset = line.partition(" ")
            if saved_key == key and offset.strip().isdigit():
                return int(offset)
    except OSError:
        pass
    return None


def write_cursor(transcript, offset, cwd=None):
    """Record the offset, replacing any previous entry for the same pair."""
    key = cursor_key(transcript)
    path = cursor_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    try:
        kept = [l for l in path.read_text().splitlines()
                if l.strip() and not l.startswith(key + " ")]
    except OSError:
        pass
    kept.append(f"{key} {offset}")
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


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
    """This project's ~/.claude/projects entry, from a directory."""
    here = Path(cwd or os.getcwd())
    return project_dir(here, main_worktree(here))


def _cli():
    """A path oracle for the shell.

    The `explainer` wrapper needs the same paths this module resolves. Asking
    for them here keeps the layout recorded once instead of being reimplemented
    in bash, where it would drift the first time Claude Code moves a directory.
    """
    if len(sys.argv) < 2:
        sys.exit("usage: explainer_layout.py <project-dir|glossary-dir|state-path|answer-language|remember-session UUID>")
    what = sys.argv[1]
    if what == "remember-session":
        if len(sys.argv) != 3:
            sys.exit("remember-session needs exactly one session id")
        remember_explainer_session(sys.argv[2])
        return
    if what == "answer-language":
        print(answer_language())
        return
    if what == "state-path":
        print(state_path())
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
