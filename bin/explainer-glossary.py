#!/usr/bin/env python3
"""The terms this project has already had explained.

The explainer derives a term's industry name from scratch every time it is
asked, which costs a full research pass and, worse, can come back slightly
different on the second telling. This is where an answer is kept once it has
been given, so the third time a word comes up the agent builds on what it said
before instead of rediscovering it.

  explainer-glossary.py --list
  explainer-glossary.py --lookup ledger
  explainer-glossary.py --skip parse_args     # not a concept; stop proposing it
  explainer-glossary.py --add ledger \
      --local "delivery table in internal/ledger" \
      --industry "deduplication table, idempotency store" \
      --search "at-least-once delivery, idempotency key" \
      --note "claim -> work -> settle state machine"

One file per term, so two answers written at once cannot corrupt each other and
the entries stay readable and editable by hand.

Every entry records where it came from. An entry written while answering a real
question was checked against this repository; one written by a background search
knows the industry term and nothing about how this project uses it. They must not
look alike six months later, which is what --provenance is for.
"""

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explainer_layout import PROJECTS, SKIPPED_FILE, glossary_dir, resolve_project  # noqa: E402

FILENAME_CHARS = re.compile(r"[^a-z0-9]+")
FIELDS = ("local", "industry", "search")
PROVENANCE = ("verified", "auto")


def filename_for(term):
    stem = FILENAME_CHARS.sub("-", term.strip().lower()).strip("-")
    if not stem:
        sys.exit("a term needs at least one letter or digit")
    return stem + ".md"


def directory(create=False):
    project = resolve_project()
    target = glossary_dir(project)
    if not target:
        sys.exit(
            f"cannot locate this project's directory under {PROJECTS} — "
            "run transcript-tail.py --sources to see what was resolved"
        )
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target


def render(term, args):
    lines = [f"# {term.strip()}", ""]
    for field in FIELDS:
        value = getattr(args, field)
        if value:
            lines.append(f"- {field}: {value.strip()}")
    lines.append(f"- provenance: {args.provenance}")
    if args.provenance == "auto":
        lines.append("- NOT checked against this repository — verify the local half before"
                     " relying on it, and re-record as verified once you have")
    lines.append(f"- first explained: {dt.date.today().isoformat()}")
    if args.note:
        lines += ["", args.note.strip()]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true", help="every term already recorded")
    mode.add_argument("--lookup", metavar="TERM", help="print one entry, exit 1 if unknown")
    mode.add_argument("--add", metavar="TERM", help="record a term just explained")
    mode.add_argument("--skip", metavar="TERM", help="record that this name is not a concept, so --candidates stops proposing it")
    ap.add_argument("--local", help="what the name means inside this repo")
    ap.add_argument("--industry", help="what the industry calls it — the point of the entry")
    ap.add_argument("--search", help="the phrase to type into a search box")
    ap.add_argument("--note", help="anything else worth not re-deriving")
    ap.add_argument("--provenance", choices=PROVENANCE, default="verified",
                    help="verified = checked against this repo while answering; auto = background web research only")
    ap.add_argument("--update", action="store_true", help="overwrite an entry that already exists")
    args = ap.parse_args()

    if args.list:
        target = directory()
        if not target.is_dir():
            print("no glossary yet")
            return
        entries = sorted(target.glob("*.md"))
        if not entries:
            print("no glossary yet")
            return
        print(f"# {len(entries)} terms in {target}\n")
        for entry in entries:
            head = entry.read_text(encoding="utf-8", errors="replace").splitlines()
            title = head[0].lstrip("# ").strip() if head else entry.stem
            def field(label):
                prefix = f"- {label}:"
                return next((l[len(prefix):].strip() for l in head if l.startswith(prefix)), "")
            mark = "?" if field("provenance") == "auto" else " "
            print(f"{mark} {title:<28} {field('industry')}")
        if any(f'- provenance: auto' in e.read_text(errors='replace') for e in entries):
            print("\n? = background research only, the repo-local half is unverified")
        return

    if args.lookup:
        path = directory() / filename_for(args.lookup)
        if not path.is_file():
            print(f'"{args.lookup}" is not in the glossary yet')
            sys.exit(1)
        print(path.read_text(encoding="utf-8", errors="replace").rstrip())
        return

    if args.skip:
        target = directory(create=True)
        path = target / SKIPPED_FILE
        already = set()
        try:
            already = {l.strip().lower() for l in path.read_text().splitlines() if l.strip()}
        except OSError:
            pass
        if args.skip.strip().lower() in already:
            print(f'"{args.skip}" was already skipped')
            return
        with path.open("a", encoding="utf-8") as fh:
            fh.write(args.skip.strip() + "\n")
        print(f'skipped: "{args.skip}" will not be proposed again')
        return

    term = args.add
    if not (args.industry or args.local or args.note):
        sys.exit("--add needs at least one of --industry, --local or --note")
    path = directory(create=True) / filename_for(term)
    if path.is_file() and not args.update:
        print(f'"{term}" is already recorded — read it, build on it, or pass --update:\n')
        print(path.read_text(encoding="utf-8", errors="replace").rstrip())
        sys.exit(1)
    path.write_text(render(term, args), encoding="utf-8")
    print(f"recorded: {path}")


if __name__ == "__main__":
    main()
