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
# style, CLAUDE.md and auto memory cannot decide a result.
NEUTRAL_SETTINGS = {
    "language": "",
    "outputStyle": "default",
    "claudeMdExcludes": [str(Path.home() / ".claude" / "CLAUDE.md")],
    "autoMemoryEnabled": False,
}

FIXED_DATE = "2026-10-18T07:10:00Z"


def build_world():
    world = Path(tempfile.mkdtemp(prefix="explainer-eval-")).resolve()
    repo = world / "repo"
    shutil.copytree(FIXTURE / "repo", repo)
    git_env = {**os.environ, "GIT_AUTHOR_DATE": FIXED_DATE, "GIT_COMMITTER_DATE": FIXED_DATE}
    for args in (["init", "-q", "-b", "main"], ["add", "-A"],
                 ["-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
                  "commit", "-q", "-m", "relay: forward shop webhooks to the helpdesk"]):
        subprocess.run(["git", *args], cwd=repo, env=git_env, check=True, capture_output=True)

    projects = world / "projects"
    entry = projects / slug(repo)
    shutil.copytree(FIXTURE / "memory", entry / "memory")
    transcript = entry / f"{session.SESSION_ID}.jsonl"
    session.write(transcript, str(repo))
    return world, repo, projects, transcript


def call_api(prompt, options, context):
    world, repo, projects, transcript = build_world()
    # A case can play a user who has set a Claude Code `language`.
    language = (context.get("vars") or {}).get("settings_language") or ""
    env = {
        **os.environ,
        "EXPLAINER_PROJECTS_DIR": str(projects),
        "EXPLAINER_SETTINGS": json.dumps({**NEUTRAL_SETTINGS, "language": language}),
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    }
    env.pop("EXPLAINER_LANG", None)
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
