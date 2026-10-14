"""Tests for skills/team-logbook/scripts/day.py, on synthetic transcripts.

Every test points the home folder at a temp dir, so no real ~/.claude/projects is
ever read, and git and gh are replaced by a fake verifier. Fixtures are made up:
never copy a real transcript here, they hold client and session content.

Run: python3 -I -m unittest discover -s tests -v   (python on Windows)
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "team-logbook" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import day  # noqa: E402

SID = "11111111-2222-4333-8444-555555555555"
SID2 = "66666666-7777-4888-9999-aaaaaaaaaaaa"
DEMO = "/work/demo"


def user(ts, text, cwd=DEMO, branch="fix-guard", sid=SID):
    return {"type": "user", "timestamp": ts, "sessionId": sid, "cwd": cwd, "gitBranch": branch,
            "message": {"role": "user", "content": text}}


def assistant(ts, text, sid=SID):
    return {"type": "assistant", "timestamp": ts, "sessionId": sid,
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def window(date):
    start = day.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=day.WIB)
    return day.sd.Window(since=start, until=start + day.timedelta(days=1), rule="explicit")


# A PR as `gh search prs` and `gh pr view` return it: Ana (ana) opened it the day before, committed
# and commented today; Budi (budi) committed, approved and merged it later the same day.
GUARD_PR = {"repository": {"nameWithOwner": "acme/demo"}, "number": 6, "title": "Guard",
            "url": "https://github.com/acme/demo/pull/6", "state": "MERGED", "author": {"login": "ana"},
            "createdAt": "2026-10-11T09:00:00Z", "updatedAt": "2026-10-12T08:20:00Z"}
GUARD_PR_VIEW = {
    "mergedBy": {"login": "budi"}, "mergedAt": "2026-10-12T08:20:00Z",
    "reviews": [{"author": {"login": "budi"}, "state": "APPROVED", "submittedAt": "2026-10-12T08:00:00Z"}],
    "commits": [{"authors": [{"login": "ana"}], "committedDate": "2026-10-12T03:15:00Z"},
                {"authors": [{"login": "budi"}], "committedDate": "2026-10-12T07:00:00Z"}],
    "comments": [{"author": {"login": "ana"}, "createdAt": "2026-10-12T04:54:00Z"},
                 {"author": {"login": "budi"}, "createdAt": "2026-10-12T07:30:00Z"}],
}


class FakeVerifier(day.sd.NullVerifier):
    """Stands in for git and gh: canned repos, commits and working trees."""

    def __init__(self, repos=None, commits=(), working=(), refs=None):
        super().__init__()
        self.warnings = []
        self.repos = repos or {}
        self._commits = list(commits)
        self._working = {w["path"]: w for w in working}
        self.worktrees = dict.fromkeys(self._working)
        self.refs = refs or {}

    def verify_ref(self, ref):
        return dict(self.refs.get((ref.repo, ref.number)) or super().verify_ref(ref))

    def repo_for(self, cwd):
        return self.repos.get(cwd)

    def commits(self, cwd, window, session_cwd=True):
        return [c for c in self._commits if c["path"] == cwd]

    def working_state(self, toplevel):
        return self._working.get(toplevel)


class DayFixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)

    def transcript(self, records, project="-work-demo", sid=SID, subdir=""):
        folder = self.home / ".claude" / "projects" / project / subdir
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{sid}.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        return path

    def run_day(self, *argv, verifier=None, activity=None):
        buf = io.StringIO()
        with mock.patch.object(Path, "home", return_value=self.home), \
                mock.patch.object(day.sd, "GhVerifier", return_value=verifier or FakeVerifier()), \
                mock.patch.object(day, "github_activity", return_value=activity or []), \
                redirect_stdout(buf):
            code = day.main(list(argv))
        self.assertEqual(code, 0)
        return buf.getvalue()


class DayWindow(DayFixture):
    def test_times_are_shown_in_wib(self):
        self.assertEqual(day.hhmm("2026-10-12T02:35:26.867Z"), "09:35")
        self.assertEqual(day.hhmm("2026-10-12T04:35:00+09:00"), "02:35")
        self.assertEqual(day.hhmm(None), "?")

    def test_the_day_runs_midnight_to_midnight_wib(self):
        # 16:59Z is 23:59 WIB on the 11th; 17:01Z is 00:01 WIB on the 12th.
        self.transcript([user("2026-10-11T16:59:00.000Z", "before midnight"),
                         user("2026-10-11T17:01:00.000Z", "after midnight")])
        out = self.run_day("--date", "2026-10-12")
        self.assertIn("after midnight", out)
        self.assertNotIn("before midnight", out)
        self.assertIn("session 00:01-00:01", out)
        out = self.run_day("--date", "2026-10-11")
        self.assertIn("before midnight", out)
        self.assertNotIn("after midnight", out)

    def test_a_day_with_nothing_says_so(self):
        self.transcript([user("2026-10-01T03:00:00Z", "long ago")])
        self.assertIn("No activity found", self.run_day("--date", "2026-10-12"))

    def test_a_bad_date_is_refused(self):
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            self.assertEqual(day.main(["--date", "12/10/2026"]), 2)


class DayOutput(DayFixture):
    def test_work_is_grouped_by_repo_with_every_time_in_wib(self):
        self.transcript([
            {"type": "ai-title", "aiTitle": "Guard for the AI assistant", "sessionId": SID},
            user("2026-10-12T02:00:00Z", "build the guard, then finish #9"),
            assistant("2026-10-12T02:30:00Z", "The guard blocks pushes to main."),
        ])
        self.transcript([user("2026-10-12T05:00:00Z", "clean up my disk", cwd=str(self.home), sid=SID2)],
                        project="-home", sid=SID2)
        verifier = FakeVerifier(
            repos={DEMO: "acme/demo"},
            commits=[{"sha": "abc1234", "committed_at": "2026-10-12T03:15:00Z", "subject": "Add the guard",
                      "repo": "acme/demo", "path": DEMO}],
            working=[{"path": DEMO, "repo": "acme/demo", "branch": "fix-guard", "dirty_files": 2,
                      "last_commit": {"sha": "abc1234", "committed_at": "2026-10-10T10:49:00Z"}}],
            # "#9" in a prompt is looked up as an issue; it is a PR, merged the next morning.
            refs={("acme/demo", 9): {"verification": "confirmed", "state": "MERGED", "title": "Fixes",
                                      "merged_at": "2026-10-13T02:00:00Z", "closed_at": "2026-10-13T02:00:00Z",
                                      "url": "https://github.com/acme/demo/pull/9"}},
        )
        activity = [day.pr_activity(GUARD_PR, GUARD_PR_VIEW, "ana", window("2026-10-12"))]
        out = self.run_day("--date", "2026-10-12", verifier=verifier, activity=activity)

        demo, outside = out.split("## demo")[1].split("## (outside any repo)")
        self.assertIn(f"from: acme/demo · {DEMO}", demo)
        self.assertIn('session 09:00-09:30 "Guard for the AI assistant" launch=human branches=fix-guard', demo)
        self.assertIn("prompt: build the guard", demo)
        self.assertIn("note: The guard blocks pushes to main.", demo)
        self.assertIn("pr demo#9 state=open (that day; merged later, 2026-10-13 09:00)", demo)
        self.assertIn("commit abc1234 10:15 Add the guard", demo)
        # Your last touch was a comment at 11:54; the later update was a teammate's.
        self.assertIn("github PR #6 (yours) state=MERGED opened=2026-10-11 16:00 your_last_activity=11:54 "
                      "last_update_by_anyone=15:20", demo)
        self.assertIn("approved by budi; merged today 15:20 by budi", demo)
        # A last commit from another day carries its date.
        self.assertIn(f"working tree {DEMO} branch=fix-guard uncommitted_files=2 last_commit=abc1234 2026-10-10 17:49",
                      demo)
        self.assertIn("prompt: clean up my disk", outside)
        self.assertNotIn("clean up my disk", demo)

        only = self.run_day("--date", "2026-10-12", "--repo", "dem", verifier=verifier, activity=activity)
        self.assertIn("## demo", only)
        self.assertNotIn("outside any repo", only)

    def test_your_own_activity_on_a_pr_is_told_apart_from_a_teammates(self):
        # Seen from Budi's side: they approved, committed and merged; Ana's comment is not theirs.
        pr = day.pr_activity(GUARD_PR, GUARD_PR_VIEW, "budi", window("2026-10-12"))
        self.assertEqual((pr["mine"], pr["my_last"], pr["approved_by"]), (False, "15:20", []))
        self.assertEqual(pr["my_reviews"], ["APPROVED 15:00"])
        # The next day nobody touched it, so it is not that day's work at all.
        self.assertIsNone(day.pr_activity(GUARD_PR, GUARD_PR_VIEW, "ana", window("2026-10-13")))

    def test_a_pr_merged_the_next_morning_reads_as_open_on_its_day(self):
        pr = dict(GUARD_PR, number=10, createdAt="2026-10-12T11:37:00Z", updatedAt="2026-10-13T02:00:00Z")
        view = {"mergedBy": {"login": "budi"}, "mergedAt": "2026-10-13T02:00:00Z",
                "reviews": [{"author": {"login": "budi"}, "state": "APPROVED", "submittedAt": "2026-10-13T01:50:00Z"}],
                "commits": [{"authors": [{"login": "ana"}], "committedDate": "2026-10-12T11:36:00Z"}], "comments": []}
        seen = day.pr_activity(pr, view, "ana", window("2026-10-12"))
        self.assertEqual(seen["state"], "open (that day; merged later, 2026-10-13 09:00)")
        self.assertEqual((seen["opened"], seen["my_last"], seen["merged_at"]), ("2026-10-12 18:37", "18:37", None))
        self.assertEqual(seen["approved_by"], [])  # approved only the next day
        self.assertEqual(day.pr_activity(pr, view, "ana", window("2026-10-13"))["state"], "MERGED")

    def test_prompts_lose_harness_wrappers_and_are_trimmed(self):
        long = "word " * 100
        self.transcript([
            user("2026-10-12T02:00:00Z", "<system-reminder>injected</system-reminder>fix the header"),
            user("2026-10-12T02:01:00Z", long),
        ])
        out = self.run_day("--date", "2026-10-12")
        self.assertIn("prompt: fix the header", out)
        self.assertNotIn("injected", out)
        trimmed = next(line for line in out.splitlines() if line.strip().startswith("prompt: word"))
        self.assertTrue(trimmed.endswith("..."))
        self.assertLessEqual(len(trimmed.strip()), len("prompt: ") + day.CHARS)

    def test_a_session_outside_any_repo_is_grouped_by_its_folder(self):
        self.transcript([user("2026-10-12T02:00:00Z", "draft the proposal", cwd="/work/Alpha proposal")],
                        project="-work-Alpha-proposal")
        self.transcript([user("2026-10-12T03:00:00Z", "rename my photos", cwd=str(self.home), sid=SID2)],
                        project="-home", sid=SID2)
        out = self.run_day("--date", "2026-10-12")
        folder, outside = out.split("## Alpha proposal")[1].split("## (outside any repo)")
        self.assertIn("draft the proposal", folder)
        self.assertIn("rename my photos", outside)

    def test_subagent_transcripts_are_left_out(self):
        self.transcript([user("2026-10-12T02:00:00Z", "main session")])
        self.transcript([user("2026-10-12T02:05:00Z", "subagent work")], subdir=f"{SID}/subagents", sid=SID2)
        out = self.run_day("--date", "2026-10-12")
        self.assertIn("main session", out)
        self.assertNotIn("subagent work", out)


class DayCommandLine(DayFixture):
    def test_only_the_given_home_is_read(self):
        self.transcript([user("2026-10-12T02:00:00Z", "fixture prompt")])
        env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home))
        res = subprocess.run([sys.executable, "-I", str(SCRIPTS / "day.py"), "--date", "2026-10-12", "--no-verify"],
                             capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("prompt: fixture prompt", res.stdout)
        self.assertEqual(res.stdout.count("- session "), 1)
        self.assertIn("## demo", res.stdout)  # without git, the folder name still groups it
        self.assertIn("verification skipped", res.stdout)


if __name__ == "__main__":
    unittest.main()
