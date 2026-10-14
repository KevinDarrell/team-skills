#!/usr/bin/env python3
"""Claude Code PreToolUse hook for Bash commands in this repo.

Reads the hook JSON on stdin and exits 2, with the reasons on stderr, to block:

  - git commit on main, or git push to main: every change reaches main through a
    pull request, and GitHub cannot protect main on this repo's plan
  - git push or gh pr create when a skill under skills/ changed but its VERSION is
    not above the one on origin/main: the update reminder compares the two, so a
    change without a new version reaches nobody
  - git commit or gh pr create while the tests fail
  - this repo's own teamlog.py writing (add, rebuild, setup, attach, settings, map,
    unmap, ignore) without
    TEAM_LOGBOOK_CONFIG on the command line: the saved config points at the
    team's live logbook on SharePoint. The installed copy under ~/.claude/skills
    or ~/.agents/skills is left alone, so /team-logbook works from here as usual.

A safety net against slips, not a sandbox: it reads the command text. Anything it
cannot work out (no git, no origin/main, bad input) lets the command through.
Stdlib only; Python 3.9+, macOS, Linux and Windows (Git Bash).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

GIT = r"\bgit(?:\s+-[Cc]\s+\S+)*\s+"
COMMIT = re.compile(GIT + r"commit\b")
PUSH = re.compile(GIT + r"push\b([^;&|\n]*)")
PR_CREATE = re.compile(r"\bgh\s+pr\s+create\b")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?^\s*\2\s*$", re.S | re.M)
QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
TEAMLOG_WRITE = re.compile(
    r"\bpy(?:thon[\d.]*)?(?:\.exe)?\s+(?:-\S+\s+)*(\"[^\"]*\"|'[^']*'|\S+)\s+(add|rebuild|setup|attach|settings|map|unmap|ignore)\b")
SCRATCH_CONFIG = re.compile(r"\bTEAM_LOGBOOK_CONFIG=[^\s;&|]")
INSTALLED = ("/.claude/skills/", "/.agents/skills/")
TESTS_TIMEOUT = 150


def git(top: str, *args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", "-C", top, *args], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.decode("utf-8", errors="ignore").strip()


def version_tuple(text: str) -> Tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", text)) or (0,)


def strip_text(command: str) -> str:
    """The command without heredoc bodies and quoted strings, so a message that
    mentions `git push origin main` is not read as a push."""
    return QUOTED.sub("''", HEREDOC.sub("", command))


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def teamlog_problems(command: str) -> List[str]:
    if SCRATCH_CONFIG.search(command):
        return []
    text = HEREDOC.sub("", command)
    for m in TEAMLOG_WRITE.finditer(text):
        script = m.group(1).strip("'\"").replace("\\", "/")
        rest = text[m.end():].split("&&")[0].split(";")[0].split("|")[0].split()
        if "-h" in rest or "--help" in rest:
            continue
        if script.endswith("teamlog.py") and not any(i in script for i in INSTALLED):
            return [f"teamlog.py {m.group(2)} from this repo without TEAM_LOGBOOK_CONFIG writes to the team's "
                    "live logbook. Put TEAM_LOGBOOK_CONFIG=<temp folder>/config.json in front of the command, "
                    "and run setup against a temp shared folder first"]
    return []


def pushes_main(args: str, branch: str) -> bool:
    """Whether `git push <args>` run on `branch` updates main."""
    words = [w for w in args.split() if not w.startswith("-")]
    targets = [r.lstrip("+").split(":")[-1] for r in words[1:]] or [branch]
    return any((branch if t in ("HEAD", "@") else t).replace("refs/heads/", "") == "main" for t in targets)


def unbumped_skills(top: str) -> List[str]:
    """Skills changed on this branch whose VERSION is not above origin/main's."""
    base = git(top, "merge-base", "HEAD", "origin/main")
    changed = git(top, "diff", "--name-only", base, "HEAD") if base else None
    if changed is None:
        return []
    names = sorted({p.split("/")[1] for p in changed.splitlines() if p.startswith("skills/") and p.count("/") >= 2})
    problems = []
    for name in names:
        on_main = git(top, "show", f"origin/main:skills/{name}/VERSION")
        mine = git(top, "show", f"HEAD:skills/{name}/VERSION")
        if on_main is None or mine is None:  # a new or a removed skill
            continue
        if version_tuple(mine) <= version_tuple(on_main):
            problems.append(f"skills/{name} changed but its committed VERSION ({mine}) is not above origin/main's "
                            f"({on_main}). Raise skills/{name}/VERSION and commit it; if main moved, "
                            "git fetch first")
    return problems


def failing_tests(top: str) -> List[str]:
    if not (Path(top) / "tests").is_dir():
        return []
    try:
        res = subprocess.run([sys.executable, "-I", "-m", "unittest", "discover", "-s", "tests"], cwd=top,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=TESTS_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return []
    if res.returncode == 0:
        return []
    tail = "\n".join(res.stdout.decode("utf-8", errors="ignore").splitlines()[-30:])
    return [f"tests fail (python -I -m unittest discover -s tests). Fix them first:\n{tail}"]


def check(command: str, cwd: str) -> List[str]:
    reasons = teamlog_problems(command)
    plain = strip_text(command)
    commit, push, pr = COMMIT.search(plain), PUSH.search(plain), PR_CREATE.search(plain)
    if not (commit or push or pr):
        return reasons
    top = git(cwd, "rev-parse", "--show-toplevel")
    if not top:
        return reasons
    branch = git(top, "symbolic-ref", "--short", "-q", "HEAD") or ""
    if commit and branch == "main":
        reasons.append("git commit on main. Start a branch from origin/main first: every change goes through a PR")
    if push and pushes_main(push.group(1), branch):
        reasons.append("git push to main. Push your own branch and open a pull request")
    if push or pr:
        reasons += unbumped_skills(top)
    if (commit or pr) and not reasons:
        reasons += failing_tests(top)
    return reasons


# --------------------------------------------------------------------------
# Hook
# --------------------------------------------------------------------------

def main() -> int:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    command = (data.get("tool_input") or {}).get("command") or ""
    reasons = check(command, data.get("cwd") or os.getcwd())
    if not reasons:
        return 0
    print("BLOCKED by .claude/hooks/gate.py:", file=sys.stderr)
    for r in dict.fromkeys(reasons):
        print(f"- {r}", file=sys.stderr)
    print("If this is genuinely needed, ask the person to run it in their own terminal.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # fail open: one odd case must not stop every Bash command
        print(f"gate: hook error, command not checked: {exc!r}", file=sys.stderr)
        sys.exit(1)
