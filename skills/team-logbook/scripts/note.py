#!/usr/bin/env python3
"""A person's daily note: one Markdown file per day of everything they worked on, across every
project, in a folder of their own that syncs to SharePoint (or any shared storage) for the team.

Layout, inside the person's note folder (for example "Daily Notes/AN"):

  2026-10-23.md     that day's note; only this person's agent writes it

Commands:

  note.py setup --folder PATH --language LANG [--pic NAME] [--sources LIST]
        save where your notes go and the language they are written in. --sources names the
        connectors read besides this laptop's sessions and GitHub, comma-separated, such as
        "Google Calendar, Fireflies" ("" for none). --pic is your name; it defaults to the one the
        logbook already has
  note.py ignore GROUP [--remove]     never put this repo or folder in your notes (yours only; the
                                      logbook's own ignore list is separate)
  note.py where                       your note settings, and whether the folder is there
  note.py list [--from YYYY-MM-DD] [--to YYYY-MM-DD]
                                      days with a note, and weekdays without one (default: the
                                      last 14 days). A note written before its day was over says
                                      when, since work after that time is not in it yet
  note.py show [--date YYYY-MM-DD]    print that day's note (default: today)
  note.py write --file FILE.md [--date YYYY-MM-DD]
                                      save FILE.md as that day's note, replacing the one there,
                                      and remember when it was written

Settings live in the logbook's config file (~/.config/team-logbook/config.json, or
TEAM_LOGBOOK_CONFIG), under "note". Days are WIB (UTC+7) whatever the laptop's time zone.
Stdlib only; Python 3.9+, macOS, Linux and Windows.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from teamlog import WIB, config_path, load_config, save_config, write_atomic  # noqa: E402

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%Y-%m-%d %H:%M"
LIST_DAYS = 14
KEEP_WRITTEN = 62  # days whose write time is remembered


def note_settings(cfg: Optional[dict]) -> dict:
    note = (cfg or {}).get("note")
    return note if isinstance(note, dict) and note.get("folder") else {}


def require_note() -> dict:
    cfg = load_config()
    if not note_settings(cfg):
        sys.exit("daily note: not set up yet. Run: note.py setup --folder PATH --language LANG  "
                 f"({config_path()})")
    return cfg


def require_folder(note: dict) -> Path:
    folder = Path(note["folder"])
    if not folder.is_dir():
        sys.exit(f"daily note: folder not found: {folder} (is OneDrive syncing it?)")
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
    return folder / f"{day}.md"


# --------------------------------------------------------------------------
# Commands: setting up
# --------------------------------------------------------------------------

def cmd_setup(args) -> int:
    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"error: note folder not found: {folder}", file=sys.stderr)
        return 2
    cfg = load_config() or {"pic": "", "logbooks": [], "ignore": []}
    if args.pic:
        cfg["pic"] = args.pic.strip()
    if not cfg["pic"]:
        print("error: pass --pic with your name", file=sys.stderr)
        return 2
    note = dict(note_settings(cfg))
    note["folder"] = str(folder.resolve())
    note["language"] = args.language.strip()
    if args.sources is not None:
        note["sources"] = [s.strip() for s in args.sources.split(",") if s.strip()]
    note.setdefault("sources", [])
    note.setdefault("ignore", [])
    cfg["note"] = note
    path = save_config(cfg)
    print(f"saved {path}: name={cfg['pic']}, folder={note['folder']}, language={note['language']}, "
          f"sources={', '.join(note['sources']) or 'none'}")
    return 0


def cmd_ignore(args) -> int:
    cfg = require_note()
    note = cfg["note"]
    rest = [g for g in note.get("ignore") or [] if g.lower() != args.group.lower()]
    note["ignore"] = rest if args.remove else rest + [args.group]
    save_config(cfg)
    print(f"{args.group}: {'noted again' if args.remove else 'left out of your notes from now on'}")
    return 0


# --------------------------------------------------------------------------
# Commands: reading (these never write)
# --------------------------------------------------------------------------

def cmd_where(_args) -> int:
    cfg = load_config()
    note = note_settings(cfg)
    if not note:
        print(f"not set up (no daily note settings in {config_path()})")
        return 1
    folder = Path(note["folder"])
    print(f"name: {cfg['pic']}\n"
          f"note folder: {folder} ({'ok' if folder.is_dir() else 'NOT FOUND'})\n"
          f"language: {note.get('language') or '?'}\n"
          f"sources besides sessions and GitHub: {', '.join(note.get('sources') or []) or 'none'}\n"
          f"left out: {', '.join(note.get('ignore') or []) or 'nothing'}\n"
          f"config: {config_path()}")
    return 0


def cmd_list(args) -> int:
    note = require_note()["note"]
    folder = require_folder(note)
    until = datetime.strptime(parse_day(args.to), DATE_FORMAT)
    since = datetime.strptime(parse_day(args.since), DATE_FORMAT) if args.since else until - timedelta(days=LIST_DAYS - 1)
    if since > until:
        sys.exit("error: --from is after --to")
    written = note.get("written") or {}
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
    folder = require_folder(require_note()["note"])
    day = parse_day(args.date)
    path = note_path(folder, day)
    if not path.is_file():
        print(f"no note for {day} yet ({path})")
        return 0
    print(f"{path}\n")
    print(path.read_text(encoding="utf-8"), end="")
    return 0


# --------------------------------------------------------------------------
# Commands: writing
# --------------------------------------------------------------------------

def cmd_write(args) -> int:
    cfg = require_note()
    folder = require_folder(cfg["note"])
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
    written = dict(cfg["note"].get("written") or {})
    written[day] = datetime.now(WIB).strftime(TIME_FORMAT)
    cfg["note"]["written"] = dict(sorted(written.items())[-KEEP_WRITTEN:])
    save_config(cfg)
    print(f"{'replaced' if existed else 'wrote'} {path} ({len(lines)} lines)")
    return 0


def main(argv: List[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # a Windows pipe would use the ANSI code page
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("setup")
    p.add_argument("--folder", required=True, help="your own note folder, synced to the team's storage")
    p.add_argument("--language", required=True, help="the language notes are written in, such as Indonesian")
    p.add_argument("--pic", help="your name (default: the one your logbook settings have)")
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
    args = ap.parse_args(argv)
    return {"setup": cmd_setup, "ignore": cmd_ignore, "where": cmd_where, "list": cmd_list,
            "show": cmd_show, "write": cmd_write}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
