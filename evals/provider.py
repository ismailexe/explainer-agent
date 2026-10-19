"""promptfoo provider: ask the real explainer one question about the fixture session.

Every call gets a world of its own — a fresh git checkout of fixture/repo, a
private projects directory holding the fixture's memory and transcript — so no
case can see a glossary entry or a cursor another case left behind. The
explainer is launched through bin/explainer, the same path a user takes.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EVALS = Path(__file__).resolve().parent
REPO = EVALS.parent
FIXTURE = EVALS / "fixture"

sys.path.insert(0, str(REPO / "bin"))
sys.path.insert(0, str(FIXTURE))
from explainer_layout import slug  # noqa: E402
import session  # noqa: E402

# Layered over the machine owner's user settings, so their own language, output
# style, CLAUDE.md, auto memory and hooks cannot decide a result. Hooks matter
# twice: they can change what the agent does, and an IDE's status hooks would
# report every case as a finished session of whatever workspace launched the run.
NEUTRAL_SETTINGS = {
    "language": "",
    "outputStyle": "default",
    "claudeMdExcludes": [str(Path.home() / ".claude" / "CLAUDE.md")],
    "autoMemoryEnabled": False,
    "disableAllHooks": True,
}

# Variables an IDE sets so the sessions it launches can report back to it. A
# case inherits them from whoever ran the suite, and must not.
IDE_PREFIXES = ("ORCA_",)


def clean_env(extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(IDE_PREFIXES)}
    env.pop("EXPLAINER_LANG", None)
    return {**env, **extra}

FIXED_DATE = "2026-10-18T07:10:00Z"


def build_world():
    world = Path(tempfile.mkdtemp(prefix="explainer-eval-")).resolve()
    repo = world / "repo"
    shutil.copytree(FIXTURE / "repo", repo)
    git_env = {**os.environ, "GIT_AUTHOR_DATE": FIXED_DATE, "GIT_COMMITTER_DATE": FIXED_DATE}
    identity = ["-c", "user.name=fixture", "-c", "user.email=fixture@example.com"]

    def git(where, *args):
        subprocess.run(["git", *args], cwd=where, env=git_env, check=True, capture_output=True)

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, *identity, "commit", "-q", "-m", "relay: forward shop webhooks to the helpdesk")

    # The second worktree the main agent moves into at the end of the session.
    worktree = world / "relay-jitter"
    git(repo, "worktree", "add", "-q", "-b", session.WORKTREE_BRANCH, str(worktree))
    shutil.copytree(FIXTURE / "worktree", worktree, dirs_exist_ok=True)
    git(worktree, "add", "-A")
    git(worktree, *identity, "commit", "-q", "-m", "retry: full jitter (D-07)")

    projects = world / "projects"
    entry = projects / slug(repo)
    shutil.copytree(FIXTURE / "memory", entry / "memory")
    transcript = entry / f"{session.SESSION_ID}.jsonl"
    session.write(transcript, str(repo), str(worktree))
    return world, repo, projects, transcript


def call_api(prompt, options, context):
    world, repo, projects, transcript = build_world()
    # A case can play a user who has set a Claude Code `language`.
    language = (context.get("vars") or {}).get("settings_language") or ""
    env = clean_env({
        "TMPDIR": str(world),       # the launcher's briefing file goes with the world
        "EXPLAINER_PROJECTS_DIR": str(projects),
        "EXPLAINER_SETTINGS": json.dumps({**NEUTRAL_SETTINGS, "language": language}),
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    })
    try:
        run = subprocess.run(
            [str(REPO / "bin" / "explainer"), "--transcript", str(transcript), prompt],
            cwd=repo, env=env, capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {"error": "explainer did not answer within 600s"}
    finally:
        # The explainer's own session lands in Claude Code's real projects
        # directory, keyed by this checkout. Claude Code's purge removes it.
        subprocess.run(["claude", "purge", str(repo), "-y"], capture_output=True)
        shutil.rmtree(world, ignore_errors=True)

    if run.returncode != 0:
        return {"error": f"explainer exited {run.returncode}: {run.stderr.strip()[-500:]}"}
    return {"output": run.stdout.strip()}
