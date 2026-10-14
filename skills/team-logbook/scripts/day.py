#!/usr/bin/env python3
"""Print one person's work for one day, grouped by repo or folder, with every time in WIB.

  day.py [--date YYYY-MM-DD] [--repo NAME] [--no-verify]

Reads this laptop's Claude Code and Codex sessions through the vendored
standup_digest extractor (see ../SOURCE.md) and prints, per repo: each session
with its times, prompts and closing notes (trimmed), pull requests and issues
with their state as checked on GitHub, your GitHub activity that day (PRs you
opened, reviewed or merged, including work done on github.com), commits, and
uncommitted work. A session outside any GitHub repo is grouped by the name of the
folder it ran in; only sessions in the home folder itself are "(outside any repo)".
Each group starts with where it came from (owner/repo, folder), so a person can tell
it apart. Each PR shows when it was opened, your own last activity on it that day
(commit, comment, review or merge) apart from anyone's last update, and who approved it.
The day runs midnight to midnight WIB (UTC+7) and every time printed is WIB, whatever
this laptop's time zone; a time from another day carries its date. It writes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import standup_digest as sd  # noqa: E402

WIB = timezone(timedelta(hours=7), "WIB")
OUTSIDE = "(outside any repo)"
MAX_PROMPTS, MAX_NOTES, CHARS = 20, 8, 300


def repo_name(repo: str | None, path: str | None = None) -> str | None:
    """Short repo name from owner/name, else the folder name of a path."""
    if repo:
        return repo.split("/")[-1]
    return Path(path).name if path else None


def work_folder(session: dict) -> str | None:
    """The folder a session ran in, unless that is the home folder itself."""
    cwds = session.get("cwds") or []
    return cwds[0] if cwds and Path(cwds[0]) != Path.home() else None


def trim(text: str, limit: int = CHARS) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def wib(stamp: str | None) -> datetime | None:
    """An ISO timestamp (with an offset or a trailing Z) as WIB."""
    if not stamp:
        return None
    try:
        moment = datetime.fromisoformat(stamp[:-1] + "+00:00" if stamp.endswith("Z") else stamp)
    except ValueError:
        return None
    return moment.astimezone(WIB) if moment.tzinfo else None


def hhmm(stamp: str | None) -> str:
    moment = wib(stamp)
    return moment.strftime("%H:%M") if moment else "?"


def at(stamp: str | None, day: str) -> str:
    """HH:MM in WIB, with the date in front when the moment is not on `day`."""
    moment = wib(stamp)
    if not moment:
        return "?"
    return moment.strftime("%H:%M" if moment.strftime("%Y-%m-%d") == day else "%Y-%m-%d %H:%M")


def _login(who: dict | None) -> str:
    return (who or {}).get("login") or ""


def state_that_day(state: str | None, merged_at: str | None, closed_at: str | None,
                   window: sd.Window) -> str:
    """A PR's or issue's state as it stood at the end of the window, not as it stands now."""
    for verb, stamp in (("merged", merged_at), ("closed", closed_at)):
        moment = wib(stamp)
        if moment is not None and moment >= window.until:
            return f"open (that day; {verb} later, {moment.strftime('%Y-%m-%d %H:%M')})"
    return state or "?"


def pr_activity(p: dict, d: dict, me: str, window: sd.Window) -> dict | None:
    """One PR as day.py prints it, or None when nothing happened on it in the window. `p` is a
    `gh search prs` result, `d` the PR's `gh pr view`. `my_last` is your own last activity on it in
    the window (opening it, a commit, comment, review or merge); `updated_at` is anyone's, a
    teammate's included. `state` is the state at the end of the window."""
    def in_window(t: datetime | None) -> bool:
        return t is not None and window.since <= t < window.until

    reviews = d.get("reviews") or []
    opened = wib(p.get("createdAt"))
    merged_at = wib(d.get("mergedAt"))
    merged_by = _login(d.get("mergedBy"))
    author = _login(p.get("author"))
    events = [(opened, author), (merged_at, merged_by)]
    events += [(wib(c.get("committedDate")), _login((c.get("authors") or [{}])[0])) for c in d.get("commits") or []]
    events += [(wib(c.get("createdAt")), _login(c.get("author"))) for c in d.get("comments") or []]
    events += [(wib(r.get("submittedAt")), _login(r.get("author"))) for r in reviews]
    events += [(wib(c.get("committedDate")), me) for c in d.get("commits") or []
               if any(_login(a) == me for a in (c.get("authors") or [])[1:])]  # a co-author
    that_day = sorted((t, who) for t, who in events if in_window(t))
    if not that_day:
        return None
    mine = [t for t, who in that_day if who == me]
    return {
        "repo": p["repository"]["nameWithOwner"], "number": p["number"], "title": p["title"], "url": p["url"],
        "state": state_that_day(p.get("state"), d.get("mergedAt"), d.get("closedAt"), window),
        "author": author, "mine": author == me,
        "opened": opened.strftime("%Y-%m-%d %H:%M") if opened else "?",
        "merged_by": merged_by if in_window(merged_at) else None,
        "merged_at": merged_at.strftime("%H:%M") if in_window(merged_at) else None,
        "my_reviews": [f"{r.get('state')} {wib(r.get('submittedAt')).strftime('%H:%M')}" for r in reviews
                       if _login(r.get("author")) == me and in_window(wib(r.get("submittedAt")))],
        "my_last": mine[-1].strftime("%H:%M") if mine else None,
        "approved_by": sorted({_login(r.get("author")) for r in reviews
                               if r.get("state") == "APPROVED" and _login(r.get("author")) not in ("", me)
                               and wib(r.get("submittedAt")) is not None and wib(r.get("submittedAt")) < window.until}),
        "updated_at": that_day[-1][0].strftime("%H:%M"),
    }


SEARCH_LIMIT = 100


def github_activity(window: sd.Window, warnings: list[str] | None = None) -> list[dict] | None:
    """PRs involving you that something happened on during the window: opened, committed to,
    commented on, reviewed, merged. None without gh. The search asks for PRs updated since the
    window began, because a PR touched again later (the next morning) no longer shows an update
    inside the window."""
    since = window.since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = sd._run(["gh", "search", "prs", "--involves=@me", "--updated", f">={since}", "--limit", str(SEARCH_LIMIT),
                   "--json", "repository,number,title,state,url,author,updatedAt,createdAt"], timeout=30)
    me = (sd._run(["gh", "api", "user", "--jq", ".login"]) or "").strip()
    if out is None or not me:
        return None
    found = json.loads(out)
    if len(found) >= SEARCH_LIMIT and warnings is not None:
        warnings.append(f"GitHub returned the maximum of {SEARCH_LIMIT} PRs updated since that day; "
                        "some of that day's PRs may be missing")
    activity = []
    for p in found:
        created = wib(p.get("createdAt"))
        if created is not None and created >= window.until:
            continue  # opened after the day
        d = json.loads(sd._run(["gh", "pr", "view", str(p["number"]), "--repo", p["repository"]["nameWithOwner"],
                                "--json", "mergedBy,mergedAt,closedAt,reviews,commits,comments"]) or "{}")
        pr = pr_activity(p, d, me, window)
        if pr is not None:
            activity.append(pr)
    return activity


def origin(g: dict[str, list]) -> str:
    """Where a group's work came from: its GitHub repos and its folders, so a person can tell it apart."""
    home = str(Path.home())
    repos = [s.get("repo") for s in g["sessions"]] + [c.get("repo") for c in g["commits"]]
    repos += [w.get("repo") for w in g["working"]] + [a["repo"] for a in g["github"]]
    folders = [(s.get("cwds") or [None])[0] for s in g["sessions"]] + [c.get("path") for c in g["commits"]]
    folders += [w.get("path") for w in g["working"]]
    folders = ["~" + f[len(home):] if f.startswith(home + os.sep) or f.startswith(home + "/") else f
               for f in dict.fromkeys(f for f in folders if f)]
    return " · ".join(list(dict.fromkeys(r for r in repos if r)) + folders)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", help="YYYY-MM-DD, default today in WIB")
    ap.add_argument("--repo", help="only repos whose name contains this text")
    ap.add_argument("--no-verify", action="store_true", help="skip git and gh (offline)")
    args = ap.parse_args(argv)

    day = args.date or datetime.now(WIB).strftime("%Y-%m-%d")
    try:
        start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=WIB)
    except ValueError:
        print(f"error: --date {day!r} is not YYYY-MM-DD", file=sys.stderr)
        return 2
    window = sd.Window(since=start, until=start + timedelta(days=1), rule="explicit")
    verifier = sd.NullVerifier() if args.no_verify else sd.GhVerifier()
    roots = [Path.home() / ".claude" / "projects", Path.home() / ".codex" / "sessions"]
    digest = sd.build_digest(roots, window, verifier)

    groups: dict[str, dict[str, list]] = {}

    def group(key: str | None) -> dict[str, list]:
        return groups.setdefault(key or OUTSIDE, {"sessions": [], "commits": [], "working": [], "github": []})

    for s in digest["sessions"]:
        group(repo_name(s.get("repo"), work_folder(s)))["sessions"].append(s)
    for c in digest["commits"]:
        group(repo_name(c.get("repo"), c.get("path")))["commits"].append(c)
    for w in digest["working_state"]:
        group(repo_name(w.get("repo"), w.get("path")))["working"].append(w)
    warnings = list(digest["warnings"])
    activity = None if args.no_verify else github_activity(window, warnings)
    for a in activity or []:
        group(repo_name(a["repo"]))["github"].append(a)

    print(f"DAY: {day} (midnight to midnight WIB; all times below are WIB)")
    if activity is None and not args.no_verify:
        warnings.append("GitHub activity unavailable (gh search failed)")
    if warnings:
        print("WARNINGS (say the entries may be incomplete): " + "; ".join(warnings))

    names = sorted(k for k in groups if k != OUTSIDE) + ([OUTSIDE] if OUTSIDE in groups else [])
    if args.repo:
        names = [n for n in names if args.repo.lower() in n.lower()]
    if not names:
        print("No activity found for that day" + (f" in repos matching {args.repo!r}" if args.repo else "") + ".")
        return 0

    for name in names:
        g = groups[name]
        print(f"\n## {name}")
        if name != OUTSIDE and origin(g):
            print(f"  from: {origin(g)}")
        for s in sorted(g["sessions"], key=lambda x: x.get("started_at") or ""):
            print(f"- session {hhmm(s.get('started_at'))}-{hhmm(s.get('ended_at'))} "
                  f"\"{trim(s.get('title') or '', 80)}\" launch={s.get('launch')} "
                  f"branches={', '.join(s.get('branches') or []) or '-'}")
            prompts = s.get("prompts") or []
            for p in prompts[:MAX_PROMPTS]:
                print(f"    prompt: {trim(p)}")
            if len(prompts) > MAX_PROMPTS:
                print(f"    (+{len(prompts) - MAX_PROMPTS} more prompts)")
            for n in (s.get("assistant_notes") or [])[:MAX_NOTES]:
                print(f"    note: {trim(n)}")
            for r in s.get("refs") or []:
                # A bare "#5" is looked up as an issue; GitHub's answer says when it is a PR.
                kind = "pr" if "/pull/" in (r.get("url") or "") else r.get("kind")
                where = (r.get("repo") or "").split("/")[-1]
                state = state_that_day(r.get("state"), r.get("merged_at"), r.get("closed_at"), window)
                print(f"    {kind} {where}#{r.get('number')} state={state} "
                      f"verification={r.get('verification')} \"{trim(r.get('title') or '', 90)}\" {r.get('url') or ''}")
        for c in sorted(g["commits"], key=lambda x: x.get("committed_at") or ""):
            print(f"- commit {c.get('sha')} {hhmm(c.get('committed_at'))} {trim(c.get('subject') or '', 120)}")
        for a in sorted(g["github"], key=lambda x: x["number"]):
            who = "yours" if a["mine"] else f"by {a['author']}"
            extra = []
            if a.get("approved_by"):
                extra.append("approved by " + ", ".join(a["approved_by"]))
            if a["merged_at"]:
                extra.append(f"merged today {a['merged_at']} by {a['merged_by']}")
            if a["my_reviews"]:
                extra.append("your reviews today: " + ", ".join(a["my_reviews"]))
            print(f"- github PR #{a['number']} ({who}) state={a['state']} opened={a.get('opened', '?')} "
                  f"your_last_activity={a.get('my_last') or 'none today'} last_update_by_anyone={a['updated_at']} "
                  f"\"{trim(a['title'], 90)}\" {'; '.join(extra)} {a['url']}")
        for w in g["working"]:
            last = w.get("last_commit") or {}
            print(f"- working tree {w.get('path')} branch={w.get('branch')} uncommitted_files={w.get('dirty_files')} "
                  f"last_commit={last.get('sha')} {at(last.get('committed_at'), day)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
