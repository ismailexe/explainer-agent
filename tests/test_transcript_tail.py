#!/usr/bin/env python3
"""Hermetic tests for the parts of transcript-tail.py everything else stands on.

Run: python3 tests/test_transcript_tail.py
No dependencies, and no reliance on this machine's real ~/.claude — every test
builds its own directories under a temporary root.
"""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bin"))
import explainer_layout as layout  # noqa: E402

spec = importlib.util.spec_from_file_location("tt", REPO / "bin" / "transcript-tail.py")
tt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tt)

spec = importlib.util.spec_from_file_location("gl", REPO / "bin" / "explainer-glossary.py")
gl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gl)


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class Slug(unittest.TestCase):
    def test_replaces_every_non_alphanumeric_character(self):
        # Measured rule: "/" is not special — "_" and "." collapse to "-" too.
        # A slash-only rule matched 27 of this machine's 57 project directories.
        self.assertEqual(
            layout.slug("/private/var/folders/m1/nm2z33c50bdf70187s4_zvfc0000gn/T/guard-e2e.EZtXmC/s13352"),
            "-private-var-folders-m1-nm2z33c50bdf70187s4-zvfc0000gn-T-guard-e2e-EZtXmC-s13352",
        )

    def test_keeps_digits_and_case(self):
        self.assertEqual(layout.slug("/Users/dev/Desktop/work/order-service"),
                         "-Users-dev-Desktop-work-order-service")


class ProjectsDir(unittest.TestCase):
    """Where the per-project tree lives, before anything is resolved inside it."""

    def test_defaults_to_the_home_claude_directory(self):
        self.assertEqual(layout.projects_dir({}), layout.HOME / ".claude" / "projects")

    def test_follows_claude_config_dir(self):
        # Claude Code relocates everything under CLAUDE_CONFIG_DIR; reading
        # ~/.claude there would explain a conversation that is not the live one.
        self.assertEqual(
            layout.projects_dir({"CLAUDE_CONFIG_DIR": "/srv/claude"}),
            Path("/srv/claude/projects"),
        )

    def test_explainer_override_wins_over_both(self):
        self.assertEqual(
            layout.projects_dir({"EXPLAINER_PROJECTS_DIR": "/tmp/case-7/projects",
                                 "CLAUDE_CONFIG_DIR": "/srv/claude"}),
            Path("/tmp/case-7/projects"),
        )

    def test_blank_values_are_ignored(self):
        self.assertEqual(
            layout.projects_dir({"EXPLAINER_PROJECTS_DIR": " ", "CLAUDE_CONFIG_DIR": ""}),
            layout.HOME / ".claude" / "projects",
        )


class MainWorktree(unittest.TestCase):
    """A worktree session must resolve to the main repo, or it reads no memory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.main = root / "project"
        self.main.mkdir()
        git("init", "-q", "-b", "main", cwd=self.main)
        git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
            "--allow-empty", "-m", "init", cwd=self.main)
        self.linked = root / "elsewhere" / "feature"
        git("worktree", "add", "-q", "-b", "feature", str(self.linked), cwd=self.main)

    def tearDown(self):
        self.tmp.cleanup()

    def test_from_the_main_worktree(self):
        self.assertEqual(layout.main_worktree(self.main), self.main.resolve())

    def test_from_a_linked_worktree(self):
        # The trap this exists for: cwd is `.../elsewhere/feature`, but memory/
        # was written under the main repo's path.
        self.assertEqual(layout.main_worktree(self.linked), self.main.resolve())

    def test_outside_git_returns_none(self):
        plain = Path(self.tmp.name) / "not-a-repo"
        plain.mkdir()
        self.assertIsNone(layout.main_worktree(plain))


class ProjectDir(unittest.TestCase):
    """Which ~/.claude/projects entry holds this project's memory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.projects = Path(self.tmp.name) / "projects"
        self.projects.mkdir()
        self.saved = layout.PROJECTS
        layout.PROJECTS = self.projects

    def tearDown(self):
        layout.PROJECTS = self.saved
        self.tmp.cleanup()

    def make(self, name, memories=0):
        entry = self.projects / name
        (entry / "memory").mkdir(parents=True)
        for i in range(memories):
            (entry / "memory" / f"m{i}.md").write_text("x")
        return entry

    def test_prefers_the_repo_path_over_the_worktree_path(self):
        repo = "/Users/x/work/engine"
        cwd = "/Users/x/worktrees/engine/feature"
        wanted = self.make(layout.slug(repo), memories=58)
        self.make(layout.slug(cwd), memories=3)
        self.assertEqual(layout.project_dir(Path(cwd), Path(repo)), wanted)

    def test_falls_back_to_the_cwd_entry_outside_git(self):
        cwd = "/Users/x/Desktop/thing"
        wanted = self.make(layout.slug(cwd))
        self.assertEqual(layout.project_dir(Path(cwd), None), wanted)

    def test_name_scan_breaks_the_tie_by_memory_count(self):
        # Two directories end in "-engine"; the brief's name-scan rule alone is
        # ambiguous, so the richer one wins and the exact path wins over both.
        repo = "/Users/x/gone/engine"          # no directory for this path
        self.make("-Users-x-Desktop-engine", memories=2)
        wanted = self.make("-Users-x-Desktop-work-engine", memories=58)
        self.assertEqual(layout.project_dir(Path("/Users/x/gone/engine"), Path(repo)), wanted)

    def test_returns_none_when_nothing_matches(self):
        self.assertIsNone(layout.project_dir(Path("/nowhere"), None))


class SessionScope(unittest.TestCase):
    """Which conversations count as "this project's"."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.projects = root / "projects"
        self.projects.mkdir()
        self.saved_projects, layout.PROJECTS = layout.PROJECTS, self.projects

        self.repo = root / "work" / "repo"
        self.repo.mkdir(parents=True)
        git("init", "-q", "-b", "main", cwd=self.repo)
        git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
            "--allow-empty", "-m", "init", cwd=self.repo)
        self.outside = root / "work"          # the repo's parent
        self.saved_cwd = os.getcwd()
        os.chdir(self.repo)
        self.saved_env = os.environ.pop("CLAUDE_CODE_SESSION_ID", None)

    def tearDown(self):
        os.chdir(self.saved_cwd)
        layout.PROJECTS = self.saved_projects
        if self.saved_env is not None:
            os.environ["CLAUDE_CODE_SESSION_ID"] = self.saved_env
        self.tmp.cleanup()

    def transcript(self, session_id, cwd):
        entry = self.projects / layout.slug(cwd)
        entry.mkdir(parents=True, exist_ok=True)
        path = entry / f"{session_id}.jsonl"
        path.write_text(json.dumps({"type": "user", "cwd": str(cwd),
                                    "message": {"content": "hi"}}) + "\n")
        return path

    def test_a_session_from_outside_the_repo_is_not_a_candidate(self):
        # The bug this locks: $HOME is an ancestor of every path, so a session
        # opened there was resolved as the conversation to explain — a different
        # project's conversation, explained in confident detail.
        self.transcript("aaaaaaaa-0000-0000-0000-000000000001", self.outside)
        self.assertEqual(layout.sessions_for_cwd(), [])

    def test_the_session_opened_here_is_the_candidate(self):
        wanted = self.transcript("aaaaaaaa-0000-0000-0000-000000000002", self.repo)
        self.assertEqual(layout.sessions_for_cwd(), [wanted])

    def test_an_ancestor_inside_the_repo_still_counts(self):
        nested = self.repo / "web" / "src"
        nested.mkdir(parents=True)
        os.chdir(nested)
        wanted = self.transcript("aaaaaaaa-0000-0000-0000-000000000003", self.repo)
        self.assertEqual(layout.sessions_for_cwd(), [wanted])

    def test_target_skips_this_process_and_earlier_explainer_sessions(self):
        work = self.transcript("aaaaaaaa-0000-0000-0000-00000000000a", self.repo)
        mine = self.transcript("aaaaaaaa-0000-0000-0000-00000000000b", self.repo)
        past = self.transcript("aaaaaaaa-0000-0000-0000-00000000000c", self.repo)
        os.environ["CLAUDE_CODE_SESSION_ID"] = mine.stem
        layout.remember_explainer_session(past.stem)
        self.assertEqual(layout.target_transcript(), work)

    def test_target_fails_rather_than_guessing(self):
        self.transcript("aaaaaaaa-0000-0000-0000-00000000000d", self.outside)
        with self.assertRaises(SystemExit) as caught:
            layout.target_transcript()
        self.assertIn("no other session found", str(caught.exception))


class WorktreeSessionScope(unittest.TestCase):
    """Sessions seen from a linked worktree.

    Two boundaries are easy to confuse and were confused once: memory is shared
    by every worktree of a repository, so it keys off the main one, while a
    session belongs to the checkout it was opened in. Using the main worktree as
    the session boundary hid a session opened at the worktree root from every
    subdirectory of that same worktree.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.projects = root / "projects"
        self.projects.mkdir()
        self.saved_projects, layout.PROJECTS = layout.PROJECTS, self.projects

        self.main = root / "main" / "repo"
        self.main.mkdir(parents=True)
        git("init", "-q", "-b", "main", cwd=self.main)
        git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
            "--allow-empty", "-m", "init", cwd=self.main)
        self.worktree = root / "worktrees" / "feature"
        git("worktree", "add", "-q", "-b", "feature", str(self.worktree), cwd=self.main)

        self.saved_cwd = os.getcwd()
        self.saved_env = os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        self.work = self.transcript("bbbbbbbb-0000-0000-0000-000000000001", self.worktree)
        self.elsewhere = self.transcript("bbbbbbbb-0000-0000-0000-000000000002", self.main)

    def tearDown(self):
        os.chdir(self.saved_cwd)
        layout.PROJECTS = self.saved_projects
        if self.saved_env is not None:
            os.environ["CLAUDE_CODE_SESSION_ID"] = self.saved_env
        self.tmp.cleanup()

    def transcript(self, session_id, cwd):
        entry = self.projects / layout.slug(cwd)
        entry.mkdir(parents=True, exist_ok=True)
        path = entry / f"{session_id}.jsonl"
        path.write_text(json.dumps({"type": "user", "cwd": str(cwd),
                                    "message": {"content": "hi"}}) + "\n")
        return path

    def test_a_second_terminal_in_the_same_worktree_finds_the_session(self):
        os.chdir(self.worktree)
        self.assertEqual(layout.sessions_for_cwd(), [self.work])

    def test_a_subdirectory_of_that_worktree_finds_it_too(self):
        nested = self.worktree / "web" / "src"
        nested.mkdir(parents=True)
        os.chdir(nested)
        self.assertEqual(layout.sessions_for_cwd(), [self.work])

    def test_the_main_repo_session_does_not_leak_into_the_worktree(self):
        os.chdir(self.worktree)
        self.assertNotIn(self.elsewhere, layout.sessions_for_cwd())

    def test_and_the_worktree_session_does_not_leak_into_the_main_repo(self):
        os.chdir(self.main)
        self.assertEqual(layout.sessions_for_cwd(), [self.elsewhere])

    def test_memory_still_resolves_to_the_main_repo(self):
        # The distinction this class is about: sessions are per checkout, memory
        # is per repository. Narrowing the session boundary must not narrow this.
        self.assertEqual(layout.main_worktree(self.worktree), self.main)


class Glossary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "glossary"
        # The script talks to a person on stdout; keep it out of the test report
        # so a real failure is the only thing printed.
        self.quiet = contextlib.redirect_stdout(io.StringIO())
        self.quiet.__enter__()
        self.addCleanup(lambda: self.quiet.__exit__(None, None, None))
        self.saved = gl.directory
        gl.directory = lambda create=False: (self.dir.mkdir(parents=True, exist_ok=True)
                                             if create else None) or self.dir

    def tearDown(self):
        gl.directory = self.saved
        self.tmp.cleanup()

    def test_a_term_becomes_one_predictable_filename(self):
        self.assertEqual(gl.filename_for("  At-Least-Once Delivery "), "at-least-once-delivery.md")
        self.assertEqual(gl.filename_for("LEDGER"), "ledger.md")

    def test_a_term_with_no_letters_is_refused(self):
        with self.assertRaises(SystemExit):
            gl.filename_for("///")

    def test_add_then_lookup_is_case_insensitive(self):
        sys.argv = ["gl", "--add", "Ledger", "--industry", "deduplication table"]
        gl.main()
        sys.argv = ["gl", "--lookup", "LEDGER"]
        gl.main()  # exits nonzero if it cannot find the entry
        self.assertTrue((self.dir / "ledger.md").is_file())

    def test_an_existing_term_is_not_silently_overwritten(self):
        sys.argv = ["gl", "--add", "ledger", "--industry", "first"]
        gl.main()
        sys.argv = ["gl", "--add", "ledger", "--industry", "second"]
        with self.assertRaises(SystemExit) as caught:
            gl.main()
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("first", (self.dir / "ledger.md").read_text())
        sys.argv = ["gl", "--add", "ledger", "--industry", "second", "--update"]
        gl.main()
        self.assertIn("second", (self.dir / "ledger.md").read_text())

    def test_add_needs_something_worth_recording(self):
        sys.argv = ["gl", "--add", "ledger"]
        with self.assertRaises(SystemExit):
            gl.main()


class Cursor(unittest.TestCase):
    """Catching up must not depend on anything remembering where it was.

    The `--since HH:MM` form worked but put the bookkeeping in the model's hands,
    and in this project a chore left to the model's discretion has a measured
    record of not happening. These lock the behaviour that replaced it.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.projects = root / "projects"
        self.projects.mkdir()
        self.saved_projects, layout.PROJECTS = layout.PROJECTS, self.projects
        self.saved_cwd = os.getcwd()
        self.work = root / "work"
        self.work.mkdir()
        os.chdir(self.work)
        self.saved_env = os.environ.get("CLAUDE_CODE_SESSION_ID")
        os.environ["CLAUDE_CODE_SESSION_ID"] = "chat-one"
        self.path = root / "live.jsonl"
        self.path.write_text("")

    def tearDown(self):
        os.chdir(self.saved_cwd)
        layout.PROJECTS = self.saved_projects
        if self.saved_env is None:
            os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        else:
            os.environ["CLAUDE_CODE_SESSION_ID"] = self.saved_env
        self.tmp.cleanup()

    def append(self, text, partial=False):
        line = json.dumps({"type": "user", "timestamp": "2026-09-09T03:00:00Z",
                           "message": {"content": text}})
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line if partial else line + "\n")

    def test_first_look_returns_the_tail_and_marks_the_position(self):
        for i in range(5):
            self.append(f"mesaj {i}")
        messages, kind = tt.load_since_cursor(self.path, default_args(turns=2))
        self.assertEqual(kind, "first")
        self.assertEqual(len(messages), 2)
        self.assertIn("mesaj 4", messages[-1])

    def test_second_look_returns_only_what_was_appended(self):
        self.append("eski")
        tt.load_since_cursor(self.path, default_args(turns=10))
        self.append("yeni bir sey")
        messages, kind = tt.load_since_cursor(self.path, default_args())
        self.assertEqual(kind, "incremental")
        self.assertEqual(len(messages), 1)
        self.assertIn("yeni bir sey", messages[0])
        self.assertNotIn("eski", messages[0])

    def test_a_look_with_nothing_new_returns_nothing(self):
        self.append("eski")
        tt.load_since_cursor(self.path, default_args())
        messages, kind = tt.load_since_cursor(self.path, default_args())
        self.assertEqual((messages, kind), ([], "incremental"))

    def test_a_half_written_final_line_is_left_for_next_time(self):
        # The transcript is appended to live, so the last line is often truncated
        # mid-flush. Consuming it would lose the message once it completes.
        self.append("tam")
        tt.load_since_cursor(self.path, default_args())
        self.append("yarim kalan", partial=True)
        messages, _ = tt.load_since_cursor(self.path, default_args())
        self.assertEqual(messages, [])
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write("\n")
        messages, _ = tt.load_since_cursor(self.path, default_args())
        self.assertEqual(len(messages), 1)
        self.assertIn("yarim kalan", messages[0])

    def test_two_chats_keep_separate_positions(self):
        self.append("bir")
        tt.load_since_cursor(self.path, default_args())
        os.environ["CLAUDE_CODE_SESSION_ID"] = "chat-two"
        messages, kind = tt.load_since_cursor(self.path, default_args(turns=10))
        self.assertEqual(kind, "first")          # the second chat has its own cursor
        self.assertEqual(len(messages), 1)

    def test_a_replaced_file_is_read_from_the_start(self):
        for i in range(3):
            self.append(f"mesaj {i}")
        tt.load_since_cursor(self.path, default_args())
        self.path.write_text("")                 # truncated / rotated under us
        self.append("yeniden")
        messages, _ = tt.load_since_cursor(self.path, default_args())
        self.assertEqual(len(messages), 1)
        self.assertIn("yeniden", messages[0])


class Gate(unittest.TestCase):
    """The free filter that decides whether the model is worth waking."""

    def test_rejects_addresses_and_keeps_concepts(self):
        for word in ("ledger", "at-least-once delivery", "backpressure", "autocompact",
                     "idempotency_key", "camelCaseThing"):
            self.assertTrue(tt.looks_like_a_term(word), word)
        for word in ("docs/OBSERVABILITY.md", "ledger.go", "--since", "$HOME", "a",
                     "return", "git commit", "one two three four five"):
            self.assertFalse(tt.looks_like_a_term(word), word)

    def test_ignores_paths_and_code_and_stays_recent(self):
        # Both failures this locks were found on a real 80-hour session: mining
        # tool calls and code put the repo's own directory name at the top with
        # 660 mentions, and reading the whole file produced 1139 candidates.
        import argparse, json as _json, tempfile as _tf, os as _os
        lines = []
        for i, text in enumerate([
            "eski konu: `stale term` burada geciyordu",
            "yolu /Users/x/order-service/internal/ledger.go icinde",
            "```\nread_text() and parse_args()\n```",
            "burada bir `deduplication table` var",
        ]):
            lines.append(_json.dumps({
                "type": "assistant", "timestamp": f"2026-09-02T1{i}:00:00Z",
                "message": {"content": [{"type": "text", "text": text}]},
            }))
        with _tf.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
            fh.write("\n".join(lines) + "\n")
            path = Path(fh.name)
        try:
            args = default_args()
            whole = tt.prose_only(path, args)
            self.assertIn("deduplication table", whole)
            self.assertNotIn("order-service", whole)   # a path segment
            self.assertNotIn("read_text", whole)               # fenced code
            recent = tt.prose_only(path, args, tail=1)
            self.assertIn("deduplication table", recent)
            self.assertNotIn("stale term", recent)             # outside the window
        finally:
            _os.unlink(path)

    def test_finds_backticked_and_cased_names(self):
        text = "the `deduplication table` uses idempotency_key and a fooBar helper"
        found = {w.strip() for groups in tt.IDENTIFIER.findall(text) for w in groups if w.strip()}
        self.assertIn("deduplication table", found)
        self.assertIn("idempotency_key", found)
        self.assertIn("fooBar", found)


class GlossaryProvenance(unittest.TestCase):
    """An entry written from a web search must not look like one checked here."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "glossary"
        self.quiet = contextlib.redirect_stdout(io.StringIO())
        self.quiet.__enter__()
        self.addCleanup(lambda: self.quiet.__exit__(None, None, None))
        self.saved = gl.directory
        gl.directory = lambda create=False: (self.dir.mkdir(parents=True, exist_ok=True)
                                             if create else None) or self.dir

    def tearDown(self):
        gl.directory = self.saved
        self.tmp.cleanup()

    def add(self, *argv):
        sys.argv = ["gl", *argv]
        gl.main()

    def test_verified_is_the_default(self):
        self.add("--add", "ledger", "--industry", "deduplication table")
        self.assertIn("- provenance: verified", (self.dir / "ledger.md").read_text())

    def test_auto_entries_carry_their_own_warning(self):
        self.add("--add", "ledger", "--industry", "deduplication table", "--provenance", "auto")
        body = (self.dir / "ledger.md").read_text()
        self.assertIn("- provenance: auto", body)
        self.assertIn("NOT checked against this repository", body)

    def test_a_skipped_name_is_recorded_once(self):
        self.add("--skip", "parse_args")
        self.add("--skip", "PARSE_ARGS")
        lines = [l for l in (self.dir / layout.SKIPPED_FILE).read_text().splitlines() if l.strip()]
        self.assertEqual(lines, ["parse_args"])

    def test_the_gate_subtracts_both_recorded_and_skipped(self):
        self.add("--add", "ledger", "--industry", "deduplication table")
        self.add("--skip", "parse_args")
        saved = tt.glossary_dir
        tt.glossary_dir = lambda project: self.dir
        try:
            known = tt.recorded_terms(object())
        finally:
            tt.glossary_dir = saved
        self.assertIn("ledger", known)
        self.assertIn("parse_args", known)


def default_args(**overrides):
    args = argparse.Namespace(
        turns=14, grep=None, file=None, nth=1, tool_results=False,
        thinking=False, include_sidechain=False, max_chars=2500, sources=False,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


class Render(unittest.TestCase):
    def entry(self, kind, content, **extra):
        return {"type": kind, "message": {"content": content},
                "timestamp": "2026-09-02T10:30:00Z", **extra}

    def test_strips_system_reminders_and_command_wrappers(self):
        text = "asil soru<system-reminder>gurultu</system-reminder><command-name>/explain</command-name>"
        out = tt.render(self.entry("user", text), default_args())
        self.assertIn("asil soru", out)
        self.assertNotIn("gurultu", out)
        self.assertNotIn("/explain", out)

    def test_drops_subagent_chatter_unless_asked(self):
        entry = self.entry("assistant", "sidechain noise", isSidechain=True)
        self.assertIsNone(tt.render(entry, default_args()))
        self.assertIsNotNone(tt.render(entry, default_args(include_sidechain=True)))

    def test_hides_thinking_and_tool_results_by_default(self):
        blocks = [
            {"type": "text", "text": "cevap"},
            {"type": "thinking", "thinking": "ic ses"},
            {"type": "tool_result", "content": "cikti"},
        ]
        plain = tt.render(self.entry("assistant", blocks), default_args())
        self.assertNotIn("ic ses", plain)
        self.assertNotIn("cikti", plain)
        loud = tt.render(self.entry("assistant", blocks),
                         default_args(thinking=True, tool_results=True))
        self.assertIn("ic ses", loud)
        self.assertIn("cikti", loud)

    def test_ignores_line_types_that_are_not_conversation(self):
        for kind in ("system", "file-history-snapshot", "ai-title", "permission-mode"):
            self.assertIsNone(tt.render(self.entry(kind, "x"), default_args()))

    def test_an_entry_with_nothing_readable_is_dropped(self):
        self.assertIsNone(tt.render(self.entry("user", "   "), default_args()))


class Load(unittest.TestCase):
    def test_skips_the_half_written_final_line(self):
        # The transcript is appended to while the session runs, so the last line
        # can be truncated mid-flush. That must not take the whole read down.
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
            fh.write(json.dumps({"type": "user", "message": {"content": "tam satir"},
                                 "timestamp": "2026-09-02T10:00:00Z"}) + "\n")
            fh.write('{"type": "assistant", "message": {"cont')
            path = Path(fh.name)
        try:
            messages = tt.load(path, default_args())
            self.assertEqual(len(messages), 1)
            self.assertIn("tam satir", messages[0])
        finally:
            os.unlink(path)


class ReferencedPaths(unittest.TestCase):
    """--sources flags paths an EXPLAINER.md names that no longer exist."""

    def test_picks_up_backticked_paths(self):
        found = tt.PATHLIKE.findall(
            "See `backup/HANDOVER.md` and `.tmp/TASKS.md`, plus `~/notes/x.md`."
        )
        self.assertEqual(found, ["backup/HANDOVER.md", ".tmp/TASKS.md", "~/notes/x.md"])

    def test_ignores_plain_identifiers(self):
        self.assertEqual(tt.PATHLIKE.findall("`ledger` and `idempotency`"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
