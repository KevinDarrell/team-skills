"""Tests for skills/a-day-in-my-life/scripts/note.py, the daily note.

Run: python3 -I -m unittest discover -s tests -v   (python on Windows)
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "a-day-in-my-life" / "scripts"
WIB = timezone(timedelta(hours=7))

NOTE = """# Ana — Monday, 12 October 2026

**Summary:** Built the guard for the AI assistant.

## Project Alpha

### AI assistant guard · Done
09:00–11:30 · Coding · PR #6
- Built a guard so the assistant can't upload client documents
"""


class NoteFixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.notes = self.root / "Daily Notes" / "AN"
        self.notes.mkdir(parents=True)
        self.env = dict(os.environ, A_DAY_IN_MY_LIFE_CONFIG=str(self.root / "config.json"))

    def note(self, *args):
        return subprocess.run([sys.executable, "-I", str(SCRIPTS / "note.py"), *args],
                              capture_output=True, text=True, encoding="utf-8", env=self.env)

    def config(self):
        return json.loads((self.root / "config.json").read_text(encoding="utf-8"))

    def draft(self, text):
        path = self.root / "draft.md"
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return str(path)


class NoteSetup(NoteFixture):
    def test_setup_needs_a_name_the_first_time(self):
        self.assertNotEqual(self.note("setup", "--folder", str(self.notes), "--language", "English").returncode, 0)
        res = self.note("setup", "--folder", str(self.notes), "--language", "Indonesian", "--name", "Ana",
                        "--sources", "Google Calendar, Fireflies")
        self.assertEqual(res.returncode, 0, res.stderr)
        where = self.note("where").stdout
        self.assertIn("name: Ana", where)
        self.assertIn(f"note folder: {self.notes.resolve()} (ok)", where)
        self.assertIn("notes are named: AN-YYYY-MM-DD.md", where)
        self.assertIn("language: Indonesian", where)
        self.assertIn("sources besides sessions and GitHub: Google Calendar, Fireflies", where)
        # Setting up again keeps the name and the sources not passed.
        self.assertEqual(self.note("setup", "--folder", str(self.notes), "--language", "English").returncode, 0)
        self.assertEqual((self.config()["name"], self.config()["sources"]), ("Ana", ["Google Calendar", "Fireflies"]))

    def test_groups_can_be_left_out_and_let_back_in(self):
        self.note("setup", "--folder", str(self.notes), "--language", "English", "--name", "Ana")
        self.assertEqual(self.note("ignore", "dotfiles").returncode, 0)
        self.assertEqual(self.config()["ignore"], ["dotfiles"])
        self.assertIn("left out: dotfiles", self.note("where").stdout)
        self.note("ignore", "DOTFILES", "--remove")
        self.assertEqual(self.config()["ignore"], [])

    def test_nothing_runs_before_setup(self):
        self.assertEqual(self.note("where").returncode, 1)
        res = self.note("write", "--file", self.draft(NOTE), "--date", "2026-10-12")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("not set up", res.stderr)


class NoteWriting(NoteFixture):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.note("setup", "--folder", str(self.notes), "--language", "English",
                                   "--name", "Ana").returncode, 0)

    def test_a_note_is_one_file_per_day_named_after_its_person(self):
        res = self.note("write", "--file", self.draft(NOTE.replace("\n", "\r\n")), "--date", "2026-10-12")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("wrote", res.stdout)
        self.assertEqual([p.name for p in self.notes.iterdir()], ["AN-2026-10-12.md"])
        written = (self.notes / "AN-2026-10-12.md").read_bytes()
        self.assertNotIn(b"\r", written)
        self.assertEqual(written.decode("utf-8"), NOTE)
        self.assertIn("AI assistant guard", self.note("show", "--date", "2026-10-12").stdout)
        res = self.note("write", "--file", self.draft(NOTE), "--date", "2026-10-12")
        self.assertIn("replaced", res.stdout)
        self.assertEqual(len(list(self.notes.iterdir())), 1)

    def test_a_draft_without_a_title_or_for_a_future_day_is_refused(self):
        res = self.note("write", "--file", self.draft("- just a bullet\n"), "--date", "2026-10-12")
        self.assertEqual(res.returncode, 2)
        self.assertIn("title line", res.stderr)
        later = (datetime.now(WIB) + timedelta(days=2)).strftime("%Y-%m-%d")
        self.assertEqual(self.note("write", "--file", self.draft(NOTE), "--date", later).returncode, 2)
        self.assertEqual(self.note("write", "--file", self.draft(NOTE), "--date", "12/10/2026").returncode, 1)
        self.assertEqual(list(self.notes.iterdir()), [])

    def test_show_says_when_a_day_has_no_note(self):
        self.assertIn("no note for 2026-10-13 yet", self.note("show", "--date", "2026-10-13").stdout)

    def test_list_shows_notes_and_the_weekdays_without_one(self):
        self.note("write", "--file", self.draft(NOTE), "--date", "2026-10-12")
        out = self.note("list", "--from", "2026-10-09", "--to", "2026-10-13").stdout
        self.assertEqual(out.splitlines(), [
            "2026-10-09 Fri: no note",  # the weekend without notes is left out
            "2026-10-12 Mon: note",
            "2026-10-13 Tue: no note",
        ])

    def test_a_note_written_before_its_day_was_over_says_so(self):
        today = datetime.now(WIB).strftime("%Y-%m-%d")
        self.note("write", "--file", self.draft(NOTE), "--date", today)
        self.note("write", "--file", self.draft(NOTE), "--date", "2026-10-12")
        line = self.note("list", "--from", today).stdout.splitlines()[-1]
        self.assertTrue(line.startswith(today))
        self.assertIn("that day: work after that is not in it yet", line)
        self.assertEqual(self.note("list", "--from", "2026-10-12", "--to", "2026-10-12").stdout.strip(),
                         "2026-10-12 Mon: note")  # written days later, so the whole day is in it
        self.assertEqual(sorted(self.config()["written"]), ["2026-10-12", today])

    def test_a_missing_folder_is_reported(self):
        self.notes.rmdir()
        res = self.note("show")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("folder not found", res.stderr)


if __name__ == "__main__":
    unittest.main()
