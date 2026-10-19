"""The work session the explainer is asked about, as Claude Code would have saved it.

Written as a readable list and rendered to JSONL per case, because the transcript
has to name the case's own checkout in every entry's `cwd`.

The session spans two days and was compacted once. Four things are planted:
- the request behind D-01 appears only before the compaction, and the summary
  leaves it out;
- the main agent claims a helpdesk timeout that the code does not have;
- nothing about Redis or caching is ever said;
- at the end the main agent moves to a second worktree and adds retry jitter
  there, so the main checkout has none.
"""

import json
import uuid

SESSION_ID = "5f0c1e2a-7b3d-4c8e-9a10-2b6d4e8f0a11"

# (timestamp, role, text, tool_use or None)
TURNS = [
    ("2026-10-17T15:50:00Z", "user",
     "Before we pick any stack, let's settle what we're building: a relay that takes "
     "the shop's ticket webhook and forwards it to the helpdesk.", None),
    ("2026-10-17T15:52:00Z", "assistant",
     "Agreed, stack later. I'll keep every decision with its reason in "
     "docs/DECISIONS.md. D-01: settle what the relay does before choosing a stack.",
     ("Write", {"file_path": "docs/DECISIONS.md"})),
    ("2026-10-17T16:05:00Z", "user", "Fine, TypeScript on Node is enough.", None),
    ("2026-10-17T16:10:00Z", "user",
     "The shop retries webhooks. Make sure a ticket is never forwarded twice.", None),
    ("2026-10-17T16:14:00Z", "assistant",
     "I added a `ledger` table: every webhook id is claimed before forwarding and "
     "settled after the helpdesk accepts it. A repeated id is skipped. See "
     "src/ledger.ts (D-03).",
     ("Write", {"file_path": "src/ledger.ts"})),
    ("2026-10-17T16:40:00Z", "user",
     "Keep the routing rules out of the database, I want changes reviewed.", None),
    ("2026-10-17T16:45:00Z", "assistant",
     "Routes now live in routes.yaml. scripts/check-routes.ts validates the file "
     "against a strict zod schema before every build, so a typo fails the build (D-04).",
     ("Write", {"file_path": "routes.yaml"})),
]

COMPACTION = (
    "2026-10-18T06:00:00Z",
    "This session is being continued from a previous conversation that ran out of "
    "context. Summary: building `relay`, a TypeScript service that forwards shop "
    "webhooks to the helpdesk. A `ledger` table deduplicates webhook ids (D-03). "
    "Routing rules are in routes.yaml, validated at build time (D-04). Decisions are "
    "kept in docs/DECISIONS.md.",
)

TURNS_AFTER = [
    ("2026-10-18T06:05:00Z", "user",
     "The dashboard goes blank whenever the API hiccups.", None),
    ("2026-10-18T06:12:00Z", "assistant",
     "TicketList now keeps the list it already has when a refresh fails and shows a "
     "banner with a retry button (src/dashboard/TicketList.tsx, D-05).",
     ("Edit", {"file_path": "src/dashboard/TicketList.tsx"})),
    ("2026-10-18T06:30:00Z", "user", "The helpdesk sometimes hangs for minutes.", None),
    ("2026-10-18T06:34:00Z", "assistant",
     "I added a 10-second timeout to the helpdesk client, so a hung request fails "
     "and gets retried.", None),
    ("2026-10-18T07:00:00Z", "user", "Add retries for failed helpdesk calls.", None),
    ("2026-10-18T07:06:00Z", "assistant",
     "Added exponential backoff in src/retry.ts: at most 5 attempts, doubling from "
     "0.5s (D-06). forward.ts wraps createTicket in it.",
     ("Write", {"file_path": "src/retry.ts"})),
]

WORKTREE_BRANCH = "retry-jitter"

# Written from the second worktree, whose path is only known per case. Neither
# message names the worktree or the branch: the move shows only in each entry's
# cwd, as it does when a session changes directory without saying so.
TURNS_IN_WORKTREE = [
    ("2026-10-18T07:20:00Z", "user", "Add jitter to the retries.", None),
    ("2026-10-18T07:26:00Z", "assistant",
     "Done: src/retry.ts now uses full jitter, each wait random up to the doubling "
     "ceiling (D-07).",
     ("Edit", {"file_path": "src/retry.ts"})),
]


def _entry(stamp, role, content, cwd, parent, **extra):
    entry = {
        "type": role,
        "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{stamp}/{role}")),
        "parentUuid": parent,
        "sessionId": SESSION_ID,
        "timestamp": stamp,
        "cwd": cwd,
        "isSidechain": False,
        "message": {"role": role, "content": content},
    }
    entry.update(extra)
    return entry


def _content(role, text, tool):
    if role == "user":
        return text
    blocks = [{"type": "text", "text": text}]
    if tool:
        name, arguments = tool
        blocks.append({"type": "tool_use",
                       "id": f"toolu_{uuid.uuid5(uuid.NAMESPACE_URL, text).hex[:16]}",
                       "name": name, "input": arguments})
    return blocks


def entries(cwd, worktree_cwd=None):
    out, parent = [], None
    for stamp, role, text, tool in TURNS:
        entry = _entry(stamp, role, _content(role, text, tool), cwd, parent)
        out.append(entry)
        parent = entry["uuid"]
    stamp, summary = COMPACTION
    entry = _entry(stamp, "user", summary, cwd, None, isCompactSummary=True)
    out.append(entry)
    parent = entry["uuid"]
    for stamp, role, text, tool in TURNS_AFTER:
        entry = _entry(stamp, role, _content(role, text, tool), cwd, parent)
        out.append(entry)
        parent = entry["uuid"]
    if worktree_cwd:
        for stamp, role, text, tool in TURNS_IN_WORKTREE:
            entry = _entry(stamp, role, _content(role, text, tool), worktree_cwd, parent)
            out.append(entry)
            parent = entry["uuid"]
    return out


def write(path, cwd, worktree_cwd=None):
    with open(path, "w", encoding="utf-8") as fh:
        for entry in entries(cwd, worktree_cwd):
            fh.write(json.dumps(entry) + "\n")
