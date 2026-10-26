"""Tests for .claude/hooks/gate.py, the Claude Code hook for this repo.

Run: python3 -I -m unittest discover -s tests -v   (python on Windows)
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "gate.py"
sys.path.insert(0, str(HOOK.parent))

import gate  # noqa: E402

REPO_TEAMLOG = "python3 -I skills/team-logbook/scripts/teamlog.py"
REPO_NOTE = "python3 -I skills/a-day-in-my-life/scripts/note.py"
GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")


class TeamlogWrites(unittest.TestCase):
    def test_repo_copy_writing_without_a_scratch_config_is_blocked(self):
        for sub in ("add --rows r.json", "rebuild", "setup --pic K --folder x --own-folder AN", "attach a.png",
                    "settings --name X", "map demo --logbook X", "unmap demo", "ignore home"):
            self.assertTrue(gate.teamlog_problems(f"{REPO_TEAMLOG} {sub}"), sub)
        self.assertTrue(gate.teamlog_problems(
            'cd skills/team-logbook && python -I "scripts/teamlog.py" add --rows r.json'))

    def test_scratch_config_reads_and_the_installed_copy_pass(self):
        for cmd in (
            f"TEAM_LOGBOOK_CONFIG=/tmp/x/config.json {REPO_TEAMLOG} add --rows r.json",
            f"{REPO_TEAMLOG} show --date 2026-10-12",
            f"{REPO_TEAMLOG} where",
            f"{REPO_TEAMLOG} settings --help",
            f"{REPO_TEAMLOG} route client-alpha",
            f"{REPO_TEAMLOG} names --logbook X",
            "python3 -I ~/.claude/skills/team-logbook/scripts/teamlog.py add --rows r.json",
            "python3 -I /Users/k/.agents/skills/team-logbook/scripts/teamlog.py rebuild",
            r"python -I %USERPROFILE%\.claude\skills\team-logbook\scripts\teamlog.py add --rows r.json",
            "python3 -I -m unittest discover -s tests -v",
        ):
            self.assertEqual(gate.teamlog_problems(cmd), [], cmd)

    def test_an_empty_config_variable_falls_back_to_the_real_one(self):
        self.assertTrue(gate.teamlog_problems(f"TEAM_LOGBOOK_CONFIG= {REPO_TEAMLOG} add --rows r.json"))

    def test_repo_note_writing_without_a_scratch_config_is_blocked(self):
        for sub in ("write --file n.md --date 2026-10-12", "setup --folder x --language English", "ignore home"):
            self.assertTrue(gate.teamlog_problems(f"{REPO_NOTE} {sub}"), sub)
        for cmd in (
            f"A_DAY_IN_MY_LIFE_CONFIG=/tmp/x/config.json {REPO_NOTE} write --file n.md",
            f"{REPO_NOTE} where",
            f"{REPO_NOTE} show --date 2026-10-12",
            f"{REPO_NOTE} list",
            f"{REPO_NOTE} check-update",
            f"{REPO_NOTE} write --help",
            "python3 -I ~/.claude/skills/a-day-in-my-life/scripts/note.py write --file n.md",
            "python3 -I skills/a-day-in-my-life/scripts/day.py --date 2026-10-12 --detail",
        ):
            self.assertEqual(gate.teamlog_problems(cmd), [], cmd)
        # Each script needs its own variable: the logbook's does not cover the notes, nor the other way round.
        self.assertTrue(gate.teamlog_problems(f"TEAM_LOGBOOK_CONFIG=/tmp/x/config.json {REPO_NOTE} write --file n.md"))
        self.assertTrue(gate.teamlog_problems(f"A_DAY_IN_MY_LIFE_CONFIG=/tmp/x/c.json {REPO_TEAMLOG} add --rows r.json"))


class PersonalLogbookWrites(unittest.TestCase):
    def test_worklog_writes_need_their_own_scratch_config(self):
        repo = "python3 -I skills/personal-logbook/scripts/worklog.py"
        for sub in ("setup --folder x", "person Ana --folder AN", "project ../Alpha", "build"):
            self.assertTrue(gate.teamlog_problems(f"{repo} {sub}"), sub)
        for cmd in (f"PERSONAL_LOGBOOK_CONFIG=/tmp/x/p.json {repo} build", f"{repo} where", f"{repo} show --person Ana",
                    "python3 -I ~/.claude/skills/personal-logbook/scripts/worklog.py build"):
            self.assertEqual(gate.teamlog_problems(cmd), [], cmd)

    def test_teamlog_add_needs_both_when_personal_logbooks_are_set_up(self):
        add = f"TEAM_LOGBOOK_CONFIG=/tmp/x/c.json {REPO_TEAMLOG} add --rows r.json"
        with mock.patch.object(gate, "personal_setup", return_value=False):
            self.assertEqual(gate.teamlog_problems(add), [])
        with mock.patch.object(gate, "personal_setup", return_value=True):
            self.assertTrue(gate.teamlog_problems(add))
            self.assertEqual(gate.teamlog_problems(f"PERSONAL_LOGBOOK_CONFIG=/tmp/x/p.json {add}"), [])
            self.assertEqual(gate.teamlog_problems(f"TEAM_LOGBOOK_CONFIG=/tmp/x/c.json {REPO_TEAMLOG} where"), [])


class PushTargets(unittest.TestCase):
    def test_which_pushes_reach_main(self):
        cases = [
            ("", "main", True), (" origin", "main", True), (" -u origin HEAD", "main", True),
            (" origin main", "fix", True), (" origin fix:main", "fix", True), (" origin +HEAD:refs/heads/main", "x", True),
            ("", "fix", False), (" -u origin fix", "fix", False), (" origin fix", "main", False), (" 2>", "fix", False),
        ]
        for args, branch, expected in cases:
            self.assertEqual(gate.pushes_main(args, branch), expected, (args, branch))

    def test_a_commit_message_that_mentions_a_push_is_not_a_push(self):
        cmd = "git commit -m \"$(cat <<'EOF'\nblock git push origin main\nEOF\n)\""
        plain = gate.strip_text(cmd)
        self.assertIsNotNone(gate.COMMIT.search(plain))
        self.assertIsNone(gate.PUSH.search(plain))
        self.assertIsNone(gate.PUSH.search(gate.strip_text('git log --grep "git push origin main"')))


class InARepo(unittest.TestCase):
    """A throwaway repo with a skill, an origin/main and a feature branch."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.top = tmp.name
        self.git("init", "-q", "-b", "main")
        self.write("skills/demo/VERSION", "0.5.0\n")
        self.write("skills/demo/SKILL.md", "v1\n")
        self.commit("start")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("switch", "-q", "-c", "fix")

    def git(self, *args):
        subprocess.run(["git", "-C", self.top, "-c", "commit.gpgsign=false", *args],
                       check=True, capture_output=True, env=GIT_ENV)

    def write(self, rel, text):
        path = Path(self.top) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def test_a_skill_change_needs_a_higher_version(self):
        self.write("skills/demo/SKILL.md", "v2\n")
        self.commit("change")
        self.assertIn("0.5.0", " ".join(gate.unbumped_skills(self.top)))
        self.assertTrue(gate.check("gh pr create --fill", self.top))
        self.write("skills/demo/VERSION", "0.6.0\n")
        self.commit("bump")
        self.assertEqual(gate.unbumped_skills(self.top), [])

    def test_changes_outside_skills_need_no_version(self):
        self.write("README.md", "docs\n")
        self.commit("docs")
        self.assertEqual(gate.unbumped_skills(self.top), [])
        self.assertEqual(gate.check("git push -u origin fix", self.top), [])

    def test_commit_on_main_is_blocked(self):
        self.git("switch", "-q", "main")
        self.assertIn("main", " ".join(gate.check("git add a && git commit -m x", self.top)))

    def test_hook_reads_json_and_exits_2_to_block(self):
        payload = {"tool_name": "Bash", "cwd": self.top, "tool_input": {"command": "git push origin main"}}
        res = subprocess.run([sys.executable, "-I", str(HOOK)], input=json.dumps(payload),
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)
        self.assertIn("BLOCKED", res.stderr)
        payload["tool_input"]["command"] = "ls"
        res = subprocess.run([sys.executable, "-I", str(HOOK)], input=json.dumps(payload),
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
