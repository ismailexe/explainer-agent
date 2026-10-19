"""promptfoo grading provider: one pass/fail judgment through `claude -p`.

Safe mode, no tools and a replaced system prompt keep a judgment to about a
thousand tokens, and it runs on the same Claude Code login as the explainer, so
the suite needs no API key.
"""

import json
import os
import subprocess

SYSTEM = (
    "You grade one answer against one criterion. The criterion states the ground "
    "truth you need; judge only what it asks. Reply with exactly the JSON object "
    "the instructions request and nothing else."
)


def call_api(prompt, options, context):
    run = subprocess.run(
        ["claude", "-p", "--safe-mode", "--model", "sonnet", "--tools", "",
         "--no-session-persistence", "--settings", json.dumps({"language": ""}),
         "--system-prompt", SYSTEM, prompt],
        capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
        # Safe mode already skips hooks; dropping an IDE's variables keeps a
        # judgment from reaching that IDE by any other route.
        env={k: v for k, v in os.environ.items() if not k.startswith("ORCA_")},
    )
    if run.returncode != 0:
        return {"error": f"judge exited {run.returncode}: {run.stderr.strip()[-300:]}"}
    return {"output": run.stdout.strip()}
