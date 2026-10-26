#!/usr/bin/env python3
"""A day in my life: one Markdown note per day of everything a person worked on, across every
project, in a folder of their own that syncs to SharePoint (or any shared storage) for the team.

Layout, inside the person's note folder, which is named after them (for example "Daily Notes/KD"):

  KD-2026-10-23.md    that day's note; only this person's agent writes it

Commands:

  note.py setup --folder PATH --language LANG [--name NAME] [--sources LIST]
        save where your notes go and the language they are written in. --name is your name as
        the notes show it (needed the first time). --sources names the connectors read besides
        this laptop's sessions and GitHub, comma-separated, such as "Google Calendar, Fireflies"
        ("" for none)
  note.py ignore GROUP [--remove]     never put this repo or folder in your notes
  note.py where                       your settings, and whether the folder is there
  note.py list [--from YYYY-MM-DD] [--to YYYY-MM-DD]
                                      days with a note, and weekdays without one (default: the
                                      last 14 days). A note written before its day was over says
                                      when, since work after that time is not in it yet
  note.py show [--date YYYY-MM-DD]    print that day's note (default: today)
  note.py write --file FILE.md [--date YYYY-MM-DD]
                                      save FILE.md as that day's note, replacing the one there,
                                      and remember when it was written
  note.py check-update                say whether a newer version of this skill exists

Settings live in ~/.config/a-day-in-my-life/config.json (A_DAY_IN_MY_LIFE_CONFIG overrides). Days
are WIB (UTC+7) whatever the laptop's time zone. Stdlib only; Python 3.9+, macOS, Linux and Windows.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

WIB = timezone(timedelta(hours=7), "WIB")
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%Y-%m-%d %H:%M"
LIST_DAYS = 14
KEEP_WRITTEN = 62  # days whose write time is remembered
REPO = "KevinDarrell/team-skills"
VERSION_PATH = "skills/a-day-in-my-life/VERSION"


# --------------------------------------------------------------------------
# Settings and files
# --------------------------------------------------------------------------

def config_path() -> Path:
    return Path(os.environ.get("A_DAY_IN_MY_LIFE_CONFIG")
                or Path.home() / ".config" / "a-day-in-my-life" / "config.json")


def load_config() -> dict:
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_atomic(path: Path, text: str) -> None:
    """Write via a temp file and rename; retry while OneDrive holds a lock on Windows."""
    tmp = path.with_name(f".{path.name}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:  # LF on every OS
        fh.write(text)
    for attempt in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(1)


def save_config(cfg: dict) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(path, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    return path


def require_config() -> dict:
    cfg = load_config()
    if not cfg.get("folder") or not cfg.get("name"):
        sys.exit("a-day-in-my-life: not set up yet. Run: note.py setup --folder PATH --language LANG "
                 f"--name NAME  ({config_path()})")
    return cfg


def require_folder(cfg: dict) -> Path:
    folder = Path(cfg["folder"])
    if not folder.is_dir():
        sys.exit(f"a-day-in-my-life: folder not found: {folder} (is OneDrive syncing it?)")
    return folder


def parse_day(text: Optional[str]) -> str:
    """YYYY-MM-DD, default today in WIB; exits on anything else."""
    day = text or datetime.now(WIB).strftime(DATE_FORMAT)
    try:
        datetime.strptime(day, DATE_FORMAT)
    except ValueError:
        sys.exit(f"error: {day!r} is not YYYY-MM-DD")
    return day


def note_path(folder: Path, day: str) -> Path:
    """<folder>/<folder's name>-<day>.md: the folder is named after its person, such as KD."""
    return folder / f"{folder.name}-{day}.md"


# --------------------------------------------------------------------------
# Update check
# --------------------------------------------------------------------------

def local_version() -> str:
    try:
        return (Path(__file__).resolve().parent.parent / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0"


def version_tuple(text: str) -> Tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", text)) or (0,)


def latest_version() -> Optional[str]:
    """The VERSION on the repo's main branch, read through gh; None when it cannot be read."""
    try:
        out = subprocess.run(
            ["gh", "api", "-H", "Accept: application/vnd.github.raw", f"repos/{REPO}/contents/{VERSION_PATH}"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


# --------------------------------------------------------------------------
# Commands: setting up
# --------------------------------------------------------------------------

def cmd_setup(args) -> int:
    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"error: note folder not found: {folder}", file=sys.stderr)
        return 2
    cfg = load_config()
    if args.name:
        cfg["name"] = args.name.strip()
    if not cfg.get("name"):
        print("error: pass --name with your name as the notes show it", file=sys.stderr)
        return 2
    cfg["folder"] = str(folder.resolve())
    cfg["language"] = args.language.strip()
    if args.sources is not None:
        cfg["sources"] = [s.strip() for s in args.sources.split(",") if s.strip()]
    cfg.setdefault("sources", [])
    cfg.setdefault("ignore", [])
    path = save_config(cfg)
    print(f"saved {path}: name={cfg['name']}, folder={cfg['folder']}, language={cfg['language']}, "
          f"sources={', '.join(cfg['sources']) or 'none'}; notes are named {note_path(folder, 'YYYY-MM-DD').name}")
    return 0


def cmd_ignore(args) -> int:
    cfg = require_config()
    rest = [g for g in cfg.get("ignore") or [] if g.lower() != args.group.lower()]
    cfg["ignore"] = rest if args.remove else rest + [args.group]
    save_config(cfg)
    print(f"{args.group}: {'noted again' if args.remove else 'left out of your notes from now on'}")
    return 0


# --------------------------------------------------------------------------
# Commands: reading (these never write)
# --------------------------------------------------------------------------

def cmd_where(_args) -> int:
    cfg = load_config()
    if not cfg.get("folder") or not cfg.get("name"):
        print(f"not set up ({config_path()} has no settings yet)")
        return 1
    folder = Path(cfg["folder"])
    print(f"name: {cfg['name']}\n"
          f"note folder: {folder} ({'ok' if folder.is_dir() else 'NOT FOUND'})\n"
          f"notes are named: {note_path(folder, 'YYYY-MM-DD').name}\n"
          f"language: {cfg.get('language') or '?'}\n"
          f"sources besides sessions and GitHub: {', '.join(cfg.get('sources') or []) or 'none'}\n"
          f"left out: {', '.join(cfg.get('ignore') or []) or 'nothing'}\n"
          f"config: {config_path()}")
    return 0


def cmd_list(args) -> int:
    cfg = require_config()
    folder = require_folder(cfg)
    until = datetime.strptime(parse_day(args.to), DATE_FORMAT)
    since = datetime.strptime(parse_day(args.since), DATE_FORMAT) if args.since else until - timedelta(days=LIST_DAYS - 1)
    if since > until:
        sys.exit("error: --from is after --to")
    written = cfg.get("written") or {}
    day = since
    while day <= until:
        name = day.strftime(DATE_FORMAT)
        if note_path(folder, name).is_file():
            stamp = str(written.get(name) or "")
            early = stamp.startswith(name)  # written before the day was over
            print(f"{name} {day.strftime('%a')}: note"
                  + (f", written {stamp[11:]} that day: work after that is not in it yet" if early else ""))
        elif day.weekday() < 5:
            print(f"{name} {day.strftime('%a')}: no note")
        day += timedelta(days=1)
    return 0


def cmd_show(args) -> int:
    folder = require_folder(require_config())
    day = parse_day(args.date)
    path = note_path(folder, day)
    if not path.is_file():
        print(f"no note for {day} yet ({path})")
        return 0
    print(f"{path}\n")
    print(path.read_text(encoding="utf-8"), end="")
    return 0


def cmd_check_update(_args) -> int:
    mine, latest = local_version(), latest_version()
    if latest is None:
        print(f"version {mine}: could not check for updates (gh unavailable or offline)")
    elif version_tuple(latest) > version_tuple(mine):
        print(f"UPDATE AVAILABLE: installed {mine}, latest {latest}. Ask the person to run "
              "`npx skills update -g a-day-in-my-life` in a terminal (with the -g), then start a new session.")
    else:
        print(f"version {mine}: up to date")
    return 0


# --------------------------------------------------------------------------
# Commands: writing
# --------------------------------------------------------------------------

def cmd_write(args) -> int:
    cfg = require_config()
    folder = require_folder(cfg)
    day = parse_day(args.date)
    if day > datetime.now(WIB).strftime(DATE_FORMAT):
        print(f"error: {day} has not happened yet", file=sys.stderr)
        return 2
    try:
        text = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {args.file}: {exc}", file=sys.stderr)
        return 2
    lines: List[str] = text.replace("\r\n", "\n").replace("\r", "\n").strip().split("\n")
    if not lines[0].startswith("# "):
        print("error: a note starts with its title line, '# <name> — <day>'", file=sys.stderr)
        return 2
    path = note_path(folder, day)
    existed = path.is_file()
    write_atomic(path, "\n".join(lines) + "\n")
    written = dict(cfg.get("written") or {})
    written[day] = datetime.now(WIB).strftime(TIME_FORMAT)
    cfg["written"] = dict(sorted(written.items())[-KEEP_WRITTEN:])
    save_config(cfg)
    print(f"{'replaced' if existed else 'wrote'} {path} ({len(lines)} lines)")
    return 0


def main(argv: List[str]) -> int:
    for stream in (sys.stdout, sys.stderr):  # a Windows pipe would use the ANSI code page
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("setup")
    p.add_argument("--folder", required=True, help="your own note folder, named after you, such as KD")
    p.add_argument("--language", required=True, help="the language notes are written in, such as English")
    p.add_argument("--name", help="your name as the notes show it (needed the first time)")
    p.add_argument("--sources", help="connectors read besides sessions and GitHub, comma-separated")
    p = sub.add_parser("ignore")
    p.add_argument("group")
    p.add_argument("--remove", action="store_true")
    sub.add_parser("where")
    p = sub.add_parser("list")
    p.add_argument("--from", dest="since")
    p.add_argument("--to")
    p = sub.add_parser("show")
    p.add_argument("--date")
    p = sub.add_parser("write")
    p.add_argument("--file", required=True)
    p.add_argument("--date")
    sub.add_parser("check-update")
    args = ap.parse_args(argv)
    return {"setup": cmd_setup, "ignore": cmd_ignore, "where": cmd_where, "list": cmd_list,
            "show": cmd_show, "write": cmd_write, "check-update": cmd_check_update}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
