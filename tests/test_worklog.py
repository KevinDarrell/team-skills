"""Tests for skills/personal-logbook/scripts/worklog.py, driven through teamlog.py as people would.

Run: python3 -I -m unittest discover -s tests -v   (python on Windows)
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_teamlog import Cli, row  # noqa: E402

WORKLOG = Path(__file__).resolve().parents[1] / "skills" / "personal-logbook" / "scripts" / "worklog.py"
sys.path.insert(0, str(WORKLOG.parent))

import worklog  # noqa: E402


def entry(ts, item, logbook):
    """A row for a person with several logbooks, which names the one it goes to."""
    return dict(row(ts, item), logbook=logbook)


class PersonalLogbook(unittest.TestCase):
    """Two projects synced side by side with a work log folder, as OneDrive lays out libraries."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        org = self.root / "Org"
        self.alpha = org / "Alpha - Documents" / "04 Working Folders"
        self.beta = org / "Beta - Documents" / "Working"
        self.worklog = org / "Work Log"
        for d in (self.alpha / "AN", self.alpha / "BD", self.beta / "AN", self.worklog):
            d.mkdir(parents=True)
        self.personal = self.root / "personal.json"
        self.env = dict(os.environ, TEAM_LOGBOOK_CONFIG=str(self.root / "Ana.json"),
                        PERSONAL_LOGBOOK_CONFIG=str(self.personal))
        self.assertEqual(self.run_wl("setup", "--folder", str(self.worklog)).returncode, 0)
        self.assertEqual(self.run_wl("person", "Ana Putri", "--folder", "AN").returncode, 0)
        self.assertEqual(self.run_wl("person", "Ana", "--folder", "AN").returncode, 0)
        self.assertEqual(self.run_wl("person", "Budi", "--folder", "BD").returncode, 0)
        # Ana logs to both projects from one laptop; Budi only to Alpha, from another.
        self.ana_alpha = Cli(self.alpha, self.root, "Ana", "AN", self.personal)
        self.ana_beta = Cli(self.beta, self.root, "Ana", "AN", self.personal)
        for folder, name in ((self.alpha, "Alpha"), (self.beta, "Beta")):
            res = self.ana_alpha.run("settings", "--logbook", str(folder), "--name", name)
            self.assertEqual(res.returncode, 0, res.stderr)
        # Budi's laptop has no personal logbooks set up, so his writes build nothing.
        self.budi = Cli(self.alpha, self.root / "budi-laptop", "Budi", "BD", self.root / "budi-personal.json")

    def run_wl(self, *args, env=None):
        return subprocess.run([sys.executable, "-I", str(WORKLOG), *args],
                              capture_output=True, text=True, encoding="utf-8", env=env or self.env)

    def table(self, own):
        return worklog.parse_table((self.worklog / own / worklog.LOGBOOK).read_text(encoding="utf-8"))

    def test_team_logbook_add_builds_each_persons_table_across_projects(self):
        self.budi.add([row("2026-10-12 09:00", "Answer key")])
        self.ana_beta.add([entry("2026-10-12 11:00", "Back-end", logbook="Beta")])
        res = self.ana_alpha.add([entry("2026-10-12 10:00", "AI guard", logbook="Alpha")])
        self.assertIn("personal logbooks: Ana Putri: AN/logbook.md written, 2 rows", res.stdout)
        self.assertEqual([(r[0], r[1], r[2], r[3]) for r in self.table("AN")],
                         [("1", "2026-10-12 10:00", "Alpha", "AI guard"),
                          ("2", "2026-10-12 11:00", "Beta", "Back-end")])
        self.assertEqual([r[3] for r in self.table("BD")], ["Answer key"])
        self.assertTrue((self.worklog / "AN" / "logbook.md").read_text(encoding="utf-8")
                        .startswith("# Logbook: Ana Putri\n"))

    def test_project_logbooks_are_only_read(self):
        self.ana_alpha.add([entry("2026-10-12 10:00", "AI guard", logbook="Alpha")])
        before = {p: p.read_bytes() for p in self.alpha.rglob("*") if p.is_file()}
        self.assertEqual(self.run_wl("build").returncode, 0)
        self.assertEqual({p: p.read_bytes() for p in self.alpha.rglob("*") if p.is_file()}, before)

    def test_projects_are_stored_beside_the_work_log_so_every_laptop_finds_them(self):
        self.ana_alpha.add([entry("2026-10-12 10:00", "AI guard", logbook="Alpha")])
        paths = [p["path"] for p in json.loads((self.worklog / worklog.SETTINGS).read_text(encoding="utf-8"))["projects"]]
        self.assertEqual(sorted(paths), ["Alpha - Documents/04 Working Folders", "Beta - Documents/Working"])

    def test_a_second_build_with_nothing_new_leaves_the_files_alone(self):
        self.ana_alpha.add([entry("2026-10-12 10:00", "AI guard", logbook="Alpha")])
        before = (self.worklog / "AN" / "logbook.md").read_bytes()
        res = self.run_wl("build")
        self.assertIn("Ana Putri: AN/logbook.md unchanged, 1 rows", res.stdout)
        self.assertEqual((self.worklog / "AN" / "logbook.md").read_bytes(), before)

    def test_a_project_this_laptop_does_not_sync_keeps_its_rows(self):
        self.ana_beta.add([entry("2026-10-12 11:00", "Back-end", logbook="Beta")])
        self.ana_alpha.add([entry("2026-10-12 10:00", "AI guard", logbook="Alpha")])
        hidden = self.beta.parent.with_name("Beta elsewhere")
        self.beta.parent.rename(hidden)
        res = self.run_wl("build")
        self.assertIn("project logbook not found on this laptop", res.stdout)
        self.assertEqual([r[3] for r in self.table("AN")], ["AI guard", "Back-end"])

    def test_a_pic_with_no_folder_is_reported(self):
        stranger = Cli(self.alpha, self.root / "budi-laptop", "Citra", "CT", self.root / "citra-personal.json")
        stranger.add([row("2026-10-12 08:00", "Something")])
        res = self.run_wl("build")
        self.assertIn("1 rows by 'Citra' have no folder here", res.stdout)

    def test_show_filters_by_person_and_days(self):
        self.budi.add([row("2026-10-11 09:00", "Old"), row("2026-10-12 09:00", "Answer key")])
        self.ana_alpha.add([entry("2026-10-12 10:00", "AI guard", logbook="Alpha")])
        res = self.run_wl("show", "--person", "BD", "--since", "2026-10-12")
        self.assertIn("Answer key", res.stdout)
        self.assertNotIn("Old", res.stdout)
        self.assertNotIn("AI guard", res.stdout)

    def test_build_log_goes_to_a_file(self):
        self.ana_alpha.add([entry("2026-10-12 10:00", "AI guard", logbook="Alpha")])
        log = self.root / "logs" / "build.log"
        res = self.run_wl("build", "--log", str(log))
        self.assertEqual((res.returncode, res.stdout), (0, ""))
        self.assertIn("Ana Putri: AN/logbook.md unchanged", log.read_text(encoding="utf-8"))

    def test_team_logbook_without_personal_setup_prints_nothing_extra(self):
        res = Cli(self.alpha, self.root / "budi-laptop", "Budi", "BD", self.root / "nobody.json") \
            .add([row("2026-10-12 09:00", "Answer key")])
        self.assertNotIn("personal logbooks", res.stdout)


if __name__ == "__main__":
    unittest.main()
