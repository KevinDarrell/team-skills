"""Tests for skills/team-logbook/scripts/teamlog.py.

Run: python3 -I -m unittest discover -s tests -v   (python on Windows)
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "team-logbook" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import teamlog  # noqa: E402


def row(ts, item, status="In progress", project="client-alpha", description="did a thing", reference=""):
    return {"timestamp": ts, "project": project, "item": item, "description": description,
            "status": status, "reference": reference}


class Cli:
    """Runs teamlog.py as a person would, with its own config and a shared folder."""

    def __init__(self, folder: Path, home: Path, pic: str, own: str, personal: Optional[Path] = None):
        # Without a personal config of its own, `add` would rebuild the real personal logbooks.
        self.env = dict(os.environ, TEAM_LOGBOOK_CONFIG=str(home / f"{pic}.json"),
                        PERSONAL_LOGBOOK_CONFIG=str(personal or home / "no-personal-logbook.json"))
        self.folder, self.pic, self.own = folder, pic, own
        assert self.run("setup", "--pic", pic, "--folder", str(folder), "--own-folder", own).returncode == 0

    def run(self, *args):
        return subprocess.run([sys.executable, "-I", str(SCRIPTS / "teamlog.py"), *args],
                              capture_output=True, text=True, env=self.env)

    def add(self, rows):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(rows, fh)
        try:
            return self.run("add", "--rows", fh.name)
        finally:
            os.unlink(fh.name)


class TeamLogbook(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.folder = self.root / "04 Working Folders"
        (self.folder / "AN").mkdir(parents=True)
        (self.folder / "BD").mkdir()
        self.ana = Cli(self.folder, self.root, "Ana", "AN")
        self.budi = Cli(self.folder, self.root, "Budi", "BD")

    def logbook_rows(self):
        return teamlog.parse_table((self.folder / teamlog.LOGBOOK).read_text(encoding="utf-8"))

    def test_rows_from_both_people_are_merged_in_time_order_and_numbered(self):
        self.assertEqual(self.ana.add([row("2026-10-12 12:00", "Pengaman asisten AI")]).returncode, 0)
        # Budi's agent writes later, but their work happened earlier in the day.
        self.assertEqual(self.budi.add([row("2026-10-12 10:00", "Templat kunci jawaban")]).returncode, 0)
        rows = self.logbook_rows()
        self.assertEqual([r[0] for r in rows], ["1", "2"])
        self.assertEqual([r[2] for r in rows], ["Budi", "Ana"])
        self.assertEqual([r[1] for r in rows], ["2026-10-12 10:00", "2026-10-12 12:00"])

    def test_each_agent_writes_only_its_own_file_and_pic(self):
        r = row("2026-10-12 09:00", "Sesuatu")
        r["pic"] = "Budi"  # a PIC in the input is ignored
        self.ana.add([r])
        self.assertTrue((self.folder / "AN" / "logbook-entries.md").exists())
        self.assertFalse((self.folder / "BD" / "logbook-entries.md").exists())
        self.assertEqual(self.logbook_rows()[0][2], "Ana")
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["AN", "BD", "logbook.md"])

    def test_same_item_same_day_updates_next_day_appends(self):
        self.ana.add([row("2026-10-12 11:00", "Pengaman asisten AI")])
        self.ana.add([row("2026-10-12 15:20", "Pengaman asisten AI", status="In review")])
        self.assertEqual(len(self.logbook_rows()), 1)
        self.assertEqual(self.logbook_rows()[0][6], "In review")
        self.ana.add([row("2026-10-13 10:05", "pengaman asisten ai", status="Done")])
        rows = self.logbook_rows()
        self.assertEqual([r[6] for r in rows], ["In review", "Done"])

    def test_a_row_can_be_renamed_or_deleted_without_touching_the_file(self):
        self.ana.add([row("2026-10-12 09:00", "Build back-end"), row("2026-10-12 10:00", "Typo row"),
                        row("2026-10-13 09:00", "Build back-end")])
        renamed = row("2026-10-12 09:30", "Build back-end: Parser", status="Done")
        renamed["was"] = "build back-end"
        res = self.ana.add([renamed, {"timestamp": "2026-10-12", "item": "Typo row", "delete": True}])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("0 added, 0 updated, 1 renamed, 1 deleted", res.stdout)
        items = [(r[1], r[4], r[6]) for r in self.logbook_rows()]
        self.assertEqual(items, [("2026-10-12 09:30", "Build back-end: Parser", "Done"),
                                 ("2026-10-13 09:00", "Build back-end", "In progress")])  # the 13th untouched

    def test_a_rename_or_delete_of_a_row_that_is_not_there_writes_nothing(self):
        self.ana.add([row("2026-10-12 09:00", "Guard")])
        before = (self.folder / "AN" / "logbook-entries.md").read_bytes()
        ghost = row("2026-10-12 10:00", "New name")
        ghost["was"] = "Never logged"
        res = self.ana.add([ghost, {"timestamp": "2026-10-11 09:00", "item": "Guard", "delete": True}])
        self.assertEqual(res.returncode, 2)
        self.assertIn("no row of yours on 2026-10-12 with Item 'Never logged' to rename", res.stderr)
        self.assertIn("no row of yours on 2026-10-11 with Item 'Guard' to delete", res.stderr)
        self.assertEqual((self.folder / "AN" / "logbook-entries.md").read_bytes(), before)

    def test_invalid_rows_write_nothing(self):
        res = self.ana.add([row("12/10/2026 9am", "x"), row("2026-10-12 09:00", "y", status="Finished")])
        self.assertEqual(res.returncode, 2)
        self.assertIn("timestamp", res.stderr)
        self.assertIn("status", res.stderr)
        self.assertFalse((self.folder / teamlog.LOGBOOK).exists())

    def test_pipes_and_newlines_survive_a_round_trip(self):
        self.ana.add([row("2026-10-12 09:00", "A | B", description="line one\nline | two")])
        rows = teamlog.read_entries(self.folder / "AN" / "logbook-entries.md")
        self.assertEqual(rows[0]["item"], "A | B")
        self.assertEqual(rows[0]["description"], "line one line | two")

    def test_conflict_copy_is_merged_once_and_reported(self):
        self.ana.add([row("2026-10-12 09:00", "Pengaman")])
        original = self.folder / "AN" / "logbook-entries.md"
        (self.folder / "AN" / "logbook-entries-Anas-MacBook.md").write_text(
            original.read_text(encoding="utf-8"), encoding="utf-8")
        res = self.ana.run("rebuild")
        self.assertIn("conflict copy", res.stdout)
        self.assertEqual(len(self.logbook_rows()), 1)

    def test_show_lists_one_persons_rows_for_a_day(self):
        self.ana.add([row("2026-10-12 09:00", "Ana item")])
        self.budi.add([row("2026-10-12 10:00", "Budi item")])
        out = self.ana.run("show", "--date", "2026-10-12", "--pic", "Budi").stdout
        self.assertIn("Budi item", out)
        self.assertNotIn("Ana item", out)

    def test_attach_copies_the_file_and_prints_a_sharepoint_link(self):
        web = "https://example.sharepoint.com/sites/X/Shared%20Documents/04%20Working%20Folders"
        self.assertEqual(self.ana.run("setup", "--pic", "Ana", "--folder", str(self.folder),
                                        "--own-folder", "AN", "--web-url", web + "/").returncode, 0)
        shot = self.root / "layar login.png"
        shot.write_bytes(b"\x89PNG fake")
        first = self.ana.run("attach", str(shot), "--date", "2026-10-12").stdout.strip()
        second = self.ana.run("attach", str(shot), "--date", "2026-10-12").stdout.strip()
        self.assertEqual(first, f"[layar login.png]({web}/AN/logbook-attachments/2026-10-12/layar%20login.png)")
        self.assertIn("layar%20login-2.png", second)  # never overwrites
        self.assertTrue((self.folder / "AN" / "logbook-attachments" / "2026-10-12" / "layar login.png").is_file())

    def test_attach_without_web_url_gives_a_relative_link(self):
        f = self.root / "notes.txt"
        f.write_text("x", encoding="utf-8")
        out = self.budi.run("attach", str(f), "--date", "2026-10-12").stdout.strip()
        self.assertEqual(out, "[notes.txt](BD/logbook-attachments/2026-10-12/notes.txt)")

    def test_setup_rejects_a_path_as_own_folder(self):
        res = self.ana.run("setup", "--pic", "Ana", "--folder", str(self.folder), "--own-folder", "AN/sub")
        self.assertEqual(res.returncode, 2)

    def test_where_reports_missing_setup(self):
        env = dict(os.environ, TEAM_LOGBOOK_CONFIG=str(self.root / "nobody.json"))
        res = subprocess.run([sys.executable, "-I", str(SCRIPTS / "teamlog.py"), "where"],
                             capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 1)
        self.assertIn("not set up", res.stdout)


class Projects(unittest.TestCase):
    """One logbook per project: settings, routing and a person on two projects."""

    WEB = "https://example.sharepoint.com/sites/Alpha/Shared%20Documents/04%20Working%20Folders"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.alpha = self.root / "Alpha - 04 Working Folders"
        self.beta = self.root / "Beta shared"
        for f in (self.alpha, self.beta):
            f.mkdir()
        self.ana = Cli(self.alpha, self.root, "Ana", "AN")
        self.budi = Cli(self.alpha, self.root, "Budi", "BD")

    def setup_project(self, cli, folder, own, project, *extra):
        res = cli.run("setup", "--pic", cli.pic, "--folder", str(folder), "--own-folder", own,
                      "--project", project, *extra)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res

    def snapshot(self):
        files = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file())
        return files, [(self.root / f).read_bytes() for f in files]

    def test_a_config_from_0_5_0_reads_as_one_logbook_and_is_left_alone(self):
        old = self.root / "old.json"
        old.write_text(json.dumps({"pic": "Ana", "folder": str(self.alpha), "own": "AN", "web_url": self.WEB}),
                       encoding="utf-8")
        cli = Cli.__new__(Cli)
        cli.env, cli.pic = dict(os.environ, TEAM_LOGBOOK_CONFIG=str(old)), "Ana"
        before = old.read_bytes()
        self.assertIn("(ok)", cli.run("where").stdout)
        self.assertEqual(cli.add([row("2026-10-12 09:00", "Guard")]).returncode, 0)
        shot = self.root / "a.png"
        shot.write_bytes(b"x")
        self.assertTrue(cli.run("attach", str(shot), "--date", "2026-10-12").stdout.startswith(f"[a.png]({self.WEB}/AN/"))
        self.assertEqual(old.read_bytes(), before)
        self.assertEqual(len(teamlog.parse_table((self.alpha / teamlog.LOGBOOK).read_text(encoding="utf-8"))), 1)

    def test_project_settings_are_created_once_and_shared(self):
        self.setup_project(self.ana, self.alpha, "AN", "Alpha", "--web-url", self.WEB + "/")
        again = self.setup_project(self.budi, self.alpha, "BD", "Something else")
        self.assertIn("kept the project settings", again.stdout)
        settings = json.loads((self.alpha / teamlog.SETTINGS).read_text(encoding="utf-8"))
        self.assertEqual(settings, {"project": "Alpha", "language": "English", "web_url": self.WEB})
        # Budi never gave the SharePoint address; the project's settings carry it.
        f = self.root / "notes.txt"
        f.write_text("x", encoding="utf-8")
        link = self.budi.run("attach", str(f), "--date", "2026-10-12").stdout.strip()
        self.assertEqual(link, f"[notes.txt]({self.WEB}/BD/logbook-attachments/2026-10-12/notes.txt)")
        self.assertEqual(self.ana.run("settings", "--language", "Bahasa Indonesia").returncode, 0)
        self.assertIn("rows are written in Bahasa Indonesia", self.budi.run("names").stdout)

    def test_a_sharepoint_view_address_becomes_the_folders_address(self):
        folder = ("https://acme.sharepoint.com/sites/Alpha/Shared%20Documents/Project%20Data-Alpha/"
                  "2026%20-%20Build/04%20Working%20Folders")
        view = ("https://acme.sharepoint.com/sites/Alpha/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2FAlpha"
                "%2FShared%20Documents%2FProject%20Data%2DAlpha%2F2026%20%2D%20Build%2F04%20Working%20Folders"
                "&viewid=1234abcd%2D0000")
        self.assertEqual(teamlog.folder_address(view), (folder, None))
        self.assertEqual(teamlog.folder_address(folder + "/"), (folder, None))
        for bad in ("https://acme.sharepoint.com/sites/Alpha/Shared%20Documents/Forms/AllItems.aspx",
                    "acme.sharepoint.com/sites/Alpha"):
            self.assertIn("not a folder's address", teamlog.folder_address(bad)[1])
        self.setup_project(self.ana, self.alpha, "AN", "Alpha", "--web-url", view)
        self.assertEqual(json.loads((self.alpha / teamlog.SETTINGS).read_text(encoding="utf-8"))["web_url"], folder)
        self.assertEqual(self.ana.run("settings", "--web-url", "https://acme.sharepoint.com/x/a.aspx").returncode, 2)

    def test_a_renamed_project_still_answers_to_its_folders_name(self):
        res = self.ana.run("settings", "--name", "Alpha One")
        self.assertIn("now called 'Alpha One'", res.stdout)
        self.assertIn('"project": "Alpha One"', res.stdout)
        self.assertEqual(self.ana.run("names", "--logbook", self.alpha.name).returncode, 0)
        self.assertIn("alpha-app -> Alpha One, Project 'Alpha One'",
                      self.ana.run("map", "alpha-app", "--label", "unused").stdout)

    def test_a_person_on_two_projects_writes_each_row_to_its_own_logbook(self):
        self.setup_project(self.ana, self.alpha, "AN", "Alpha")
        self.setup_project(self.ana, self.beta, "AN", "Beta")
        res = self.ana.add([row("2026-10-12 09:00", "Alpha thing")])
        self.assertEqual(res.returncode, 2)
        self.assertIn("no logbook", res.stderr)
        alpha, beta = row("2026-10-12 09:00", "Alpha thing"), row("2026-10-12 10:00", "Beta thing")
        alpha["logbook"], beta["logbook"] = "alpha", "Beta"
        res = self.ana.add([alpha, beta])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual([r[4] for r in teamlog.parse_table((self.alpha / teamlog.LOGBOOK).read_text(encoding="utf-8"))],
                         ["Alpha thing"])
        self.assertEqual([r[4] for r in teamlog.parse_table((self.beta / teamlog.LOGBOOK).read_text(encoding="utf-8"))],
                         ["Beta thing"])
        bad = row("2026-10-12 11:00", "x")
        bad["logbook"] = "Gamma"
        self.assertIn("'Gamma' is not one of", self.ana.add([bad]).stderr)
        out = self.ana.run("show", "--date", "2026-10-12").stdout
        self.assertIn("## Alpha", out)
        self.assertIn("## Beta", out)

    def test_routing_learns_once_for_the_whole_team(self):
        self.setup_project(self.ana, self.alpha, "AN", "Alpha")
        self.setup_project(self.ana, self.beta, "AN", "Beta")
        self.ana.run("settings", "--logbook", "Alpha", "--project-column", "label")
        self.ana.add([dict(row("2026-10-12 09:00", "Old work", project="alpha-app"), logbook="Alpha")])
        self.assertEqual(self.ana.run("map", "alpha-mockup", "--logbook", "Alpha", "--label", "Mockup").returncode, 0)
        self.assertEqual(self.ana.run("ignore", "home-scripts").returncode, 0)
        out = self.ana.run("route", "alpha-app", "alpha-mockup", "home-scripts", "new-thing").stdout.splitlines()
        self.assertEqual(out, [
            "alpha-app -> Alpha, Project 'alpha-app' (from earlier rows)",
            "alpha-mockup -> Alpha, Project 'Mockup' (mapped by AN)",
            "home-scripts -> ignored",
            "new-thing -> unknown: ask which logbook it belongs to, then map or ignore it",
        ])
        # Budi's agent learns Ana's answer without asking, but not Ana's personal ignore.
        budi = self.budi.run("route", "alpha-mockup", "home-scripts").stdout.splitlines()
        self.assertEqual(budi, ["alpha-mockup -> Alpha, Project 'Mockup' (mapped by AN)",
                                 "home-scripts -> unknown: ask which logbook it belongs to, then map or ignore it"])
        # Their own answer wins for them; Ana sees a warning-free route of his own.
        self.budi.run("map", "alpha-mockup", "--label", "Prototype")
        self.assertIn("'Prototype' (mapped by BD)", self.budi.run("route", "alpha-mockup").stdout)
        self.assertIn("'Mockup' (mapped by AN)", self.ana.run("route", "alpha-mockup").stdout)
        self.ana.run("map", "shared-lib", "--logbook", "Beta")
        self.budi.run("map", "shared-lib")
        self.assertIn("ambiguous", self.ana.run("route", "shared-lib").stdout)
        self.assertEqual(self.ana.run("unmap", "shared-lib", "--logbook", "Beta").returncode, 0)
        self.assertIn("(mapped by BD)", self.ana.run("route", "shared-lib").stdout)
        self.assertEqual(sorted(p.name for p in (self.alpha / "AN").iterdir()), ["logbook-entries.md", teamlog.SOURCES])

    def test_each_project_shapes_its_own_rows(self):
        # Alpha: Project is the project's name, Items come from a tracker, Description is titled Details.
        self.setup_project(self.ana, self.alpha, "AN", "Alpha")
        tracker = "https://www.notion.so/example/Tracker-0123456789abcdef?v=42"
        res = self.ana.run("settings", "--column", "Description=Details", "--tracker", tracker + "&source=copy_link",
                             "--item-format", "{Initiative} - {Activity}")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.ana.run("settings", "--column", "Colour=Blue").returncode, 2)
        self.ana.run("map", "alpha-app", "--label", "App")
        self.assertIn("alpha-app -> Alpha, Project 'Alpha' (mapped by AN)", self.ana.run("route", "alpha-app").stdout)
        self.ana.add([row("2026-10-12 09:00", "Initiative 1: Extractor - Build back-end", project="App")])
        table_text = (self.alpha / teamlog.LOGBOOK).read_text(encoding="utf-8")
        self.assertIn("| No | Timestamp (WIB) | PIC | Project | Item | Details | Status | Reference |", table_text)
        self.assertEqual(teamlog.parse_table(table_text)[0][3:5], ["Alpha", "Initiative 1: Extractor - Build back-end"])
        rules = self.budi.run("names").stdout
        self.assertIn("Project is always 'Alpha'", rules)
        self.assertIn(f"Item comes from the tracker {tracker}, written as '{{Initiative}} - {{Activity}}'", rules)
        self.assertIn("the format has no {part}", rules)
        self.ana.run("settings", "--item-format", "{Initiative} - {Activity}: {part}")
        self.assertIn("{part} is the piece of the activity", self.budi.run("names").stdout)
        self.assertIn("Description is titled 'Details'", rules)
        # Beta, another team's project, keeps the plain shape.
        self.setup_project(self.ana, self.beta, "AN", "Beta")
        self.ana.run("settings", "--logbook", "Beta", "--project-column", "label")
        self.ana.add([dict(row("2026-10-12 10:00", "Screens", project="beta-app"), logbook="Beta")])
        beta = (self.beta / teamlog.LOGBOOK).read_text(encoding="utf-8")
        self.assertIn("| Description |", beta)
        self.assertEqual(teamlog.parse_table(beta)[0][3], "beta-app")
        # Restoring a title and removing the tracker.
        self.ana.run("settings", "--logbook", "Alpha", "--column", "Description=", "--tracker", "")
        self.assertEqual(json.loads((self.alpha / teamlog.SETTINGS).read_text(encoding="utf-8")),
                         {"project": "Alpha", "language": "English"})

    def test_names_lists_what_the_logbook_already_uses(self):
        self.ana.add([row("2026-10-12 09:00", "Design UI/UX", project="Initiative 1", status="In progress"),
                        row("2026-10-13 09:00", "Design UI/UX", project="Initiative 1", status="Done"),
                        row("2026-10-12 10:00", "Build back-end", project="Initiative 1")])
        self.budi.add([row("2026-10-11 10:00", "UAT", project="Initiative 2", status="Planned")])
        names = teamlog.parse_table(self.ana.run("names").stdout)
        self.assertEqual([r[:4] for r in names], [
            ["Initiative 1", "Design UI/UX", "2026-10-13 09:00", "Done"],
            ["Initiative 1", "Build back-end", "2026-10-12 10:00", "In progress"],
            ["Initiative 2", "UAT", "2026-10-11 10:00", "Planned"],
        ])

    def test_reading_commands_never_write(self):
        self.setup_project(self.ana, self.alpha, "AN", "Alpha")
        self.ana.add([row("2026-10-12 09:00", "Guard")])
        self.ana.run("map", "alpha-app")
        before = self.snapshot()
        for args in (["where"], ["route", "alpha-app", "x"], ["names"], ["show", "--date", "2026-10-12"],
                     ["settings"]):
            self.assertEqual(self.ana.run(*args).returncode, 0, args)
        self.assertEqual(self.snapshot(), before)


class UpdateReminder(unittest.TestCase):
    def test_version_file_is_valid(self):
        v = teamlog.local_version()
        self.assertRegex(v, r"^\d+\.\d+\.\d+$")

    def test_versions_compare_as_numbers(self):
        self.assertGreater(teamlog.version_tuple("0.10.0"), teamlog.version_tuple("0.9.1"))
        self.assertEqual(teamlog.version_tuple("1.2.3"), (1, 2, 3))

    def test_reminder_wording(self):
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        for latest, expect in (("9.0.0", "UPDATE AVAILABLE"), (teamlog.local_version(), "up to date"),
                               (None, "could not check")):
            with mock.patch.object(teamlog, "latest_version", return_value=latest):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    teamlog.cmd_check_update(None)
                self.assertIn(expect, buf.getvalue())


if __name__ == "__main__":
    unittest.main()
