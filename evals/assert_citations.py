"""promptfoo assertion: every `file:line` the answer cites exists in the fixture.

A citation counts when its path, or a trailing part of it, names a fixture file
and the line is inside that file. With the `cite_must_contain` var set, a
citation into a file that contains that text must point at a line holding it —
a citation of the right file but the wrong line is the drift this is here to
catch. Citations into other files, such as a caller, only have to exist.

The match ignores case, spaces and punctuation, so a comment explaining the code
("Strict objects: ...") counts for `strictObject`. That rule was agreed after
reading real answers: citing the explanation is right, an unrelated line is not.
"""

import re
from pathlib import Path

FIXTURE_REPO = Path(__file__).resolve().parent / "fixture" / "repo"
CITATION = re.compile(r"([\w./-]+\.(?:ts|tsx|js|json|yaml|yml|md|py)):(\d+)")


def squash(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def resolve(cited):
    cited = cited.lstrip("./")
    matches = [p for p in FIXTURE_REPO.rglob("*")
               if p.is_file() and str(p.relative_to(FIXTURE_REPO)).endswith(cited)]
    return matches[0] if len(matches) == 1 else None


def get_assert(output, context):
    must_contain = squash((context.get("vars") or {}).get("cite_must_contain") or "")
    citations = CITATION.findall(output)
    if not citations:
        return {"pass": False, "score": 0, "reason": "no file:line citation in the answer"}

    bad = []
    for cited, line in citations:
        path = resolve(cited)
        if path is None:
            bad.append(f"{cited}:{line} (no such fixture file)")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        number = int(line)
        if not 1 <= number <= len(lines):
            bad.append(f"{cited}:{line} (file has {len(lines)} lines)")
        elif (must_contain and any(must_contain in squash(text) for text in lines)
              and must_contain not in squash(lines[number - 1])):
            bad.append(f"{cited}:{line} (line does not contain {must_contain!r})")

    good = len(citations) - len(bad)
    return {
        "pass": not bad,
        "score": good / len(citations),
        "reason": "all citations check out" if not bad else "bad: " + "; ".join(bad),
    }
