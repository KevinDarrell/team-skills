"""Tests for skills/team-logbook/scripts/note.py, the daily note.

Run: python3 -I -m unittest discover -s tests -v   (python on Windows)
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "team-logbook" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import teamlog  # noqa: E402

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
        self.env = dict(os.environ, TEAM_LOGBOOK_CONFIG=str(self.root / "config.json"))

    def run_script(self, script, *args):
        return subprocess.run([sys.executable, "-I", str(SCRIPTS / script), *args],
                              capture_output=True, text=True, encoding="utf-8", env=self.env)

    def note(self, *args):
        return self.run_script("note.py", *args)

    def config(self):
        return json.loads((self.root / "config.json").read_text(encoding="utf-8"))

    def draft(self, text):
        path = self.root / "draft.md"
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return str(path)


class NoteSetup(NoteFixture):
    def test_someone_without_a_logbook_can_set_up_a_note(self):
        self.assertNotEqual(self.note("setup", "--folder", str(self.notes), "--language", "English").returncode, 0)
        res = self.note("setup", "--folder", str(self.notes), "--language", "Indonesian", "--pic", "Ana",
                        "--sources", "Google Calendar, Fireflies")
        self.assertEqual(res.returncode, 0, res.stderr)
        where = self.note("where").stdout
        self.assertIn("name: Ana", where)
        self.assertIn(f"note folder: {self.notes.resolve()} (ok)", where)
        self.assertIn("language: Indonesian", where)
        self.assertIn("sources besides sessions and GitHub: Google Calendar, Fireflies", where)

    def test_the_logbooks_own_commands_keep_the_note_settings(self):
        shared = self.root / "04 Working Folders"
        shared.mkdir()
        self.assertEqual(self.run_script("teamlog.py", "setup", "--pic", "Ana", "--folder", str(shared),
                                         "--own-folder", "AN").returncode, 0)
        self.assertEqual(self.note("setup", "--folder", str(self.notes), "--language", "English").returncode, 0)
        self.assertEqual(self.run_script("teamlog.py", "ignore", "dotfiles").returncode, 0)
        self.assertEqual(self.run_script("teamlog.py", "setup", "--pic", "Ana", "--folder", str(shared),
                                         "--own-folder", "AN").returncode, 0)
        cfg = self.config()
        self.assertEqual(cfg["pic"], "Ana")  # taken from the logbook
        self.assertEqual(cfg["note"]["folder"], str(self.notes.resolve()))
        self.assertEqual(len(cfg["logbooks"]), 1)

    def test_the_notes_ignore_list_is_its_own(self):
        self.note("setup", "--folder", str(self.notes), "--language", "English", "--pic", "Ana")
        self.assertEqual(self.note("ignore", "dotfiles").returncode, 0)
        self.assertEqual(self.config()["note"]["ignore"], ["dotfiles"])
        self.assertEqual(self.config()["ignore"], [])
        self.note("ignore", "DOTFILES", "--remove")
        self.assertEqual(self.config()["note"]["ignore"], [])

    def test_nothing_runs_before_setup(self):
        self.assertEqual(self.note("where").returncode, 1)
        res = self.note("write", "--file", self.draft(NOTE), "--date", "2026-10-12")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("not set up", res.stderr)


class NoteWriting(NoteFixture):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.note("setup", "--folder", str(self.notes), "--language", "English",
                                   "--pic", "Ana").returncode, 0)

    def test_a_note_is_one_file_per_day_with_lf_endings(self):
        res = self.note("write", "--file", self.draft(NOTE.replace("\n", "\r\n")), "--date", "2026-10-12")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("wrote", res.stdout)
        written = (self.notes / "2026-10-12.md").read_bytes()
        self.assertNotIn(b"\r", written)
        self.assertEqual(written.decode("utf-8"), NOTE)
        self.assertIn("AI assistant guard", self.note("show", "--date", "2026-10-12").stdout)
        res = self.note("write", "--file", self.draft(NOTE), "--date", "2026-10-12")
        self.assertIn("replaced", res.stdout)

    def test_a_draft_without_a_title_or_for_a_future_day_is_refused(self):
        res = self.note("write", "--file", self.draft("- just a bullet\n"), "--date", "2026-10-12")
        self.assertEqual(res.returncode, 2)
        tomorrow = (datetime.now(teamlog.WIB) + timedelta(days=2)).strftime("%Y-%m-%d")
        self.assertEqual(self.note("write", "--file", self.draft(NOTE), "--date", tomorrow).returncode, 2)
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
        today = datetime.now(teamlog.WIB)
        self.note("write", "--file", self.draft(NOTE), "--date", today.strftime("%Y-%m-%d"))
        self.note("write", "--file", self.draft(NOTE), "--date", "2026-10-12")
        since = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        line = self.note("list", "--from", since).stdout.splitlines()[-1]
        self.assertTrue(line.startswith(today.strftime("%Y-%m-%d")))
        self.assertIn("that day: work after that is not in it yet", line)
        self.assertEqual(self.note("list", "--from", "2026-10-12", "--to", "2026-10-12").stdout.strip(),
                         "2026-10-12 Mon: note")  # written days later, so the whole day is in it
        self.assertEqual(sorted(self.config()["note"]["written"]), ["2026-10-12", today.strftime("%Y-%m-%d")])

    def test_a_missing_folder_is_reported(self):
        self.notes.rmdir()
        res = self.note("show")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("folder not found", res.stderr)


if __name__ == "__main__":
    unittest.main()
