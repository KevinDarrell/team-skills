#!/usr/bin/env python3
"""The personal logbooks: one read-only table per person, combining their rows from every
project's team logbook, in a folder the team shares (for example the SharePoint library
"Work Log").

Rows are written only in the project logbooks, by team-logbook. This script reads them and
writes, inside the work log folder:

  worklog-settings.json        who is who (PIC name -> folder, such as "Budi Santoso" -> BD)
                               and which project logbooks to read, as paths next to the work log
                               folder (OneDrive syncs each library side by side, so the same
                               relative path works on every laptop)
  <person folder>/logbook.md   that person's rows from every project, in time order; generated

A project logbook not found on this laptop keeps that project's rows from the person's current
logbook.md, so a laptop that syncs fewer projects never wipes the others' rows.

Commands:

  worklog.py setup --folder PATH                 point this laptop at the work log folder
  worklog.py person PIC --folder NAME [--remove] whose rows go to which folder; a person who logs
                                                 under several spellings ("Budi", "Budi Santoso")
                                                 gets one line each, same folder. The first one
                                                 added titles their logbook
  worklog.py project FOLDER [--remove]           read this project logbook (its shared folder)
  worklog.py where                               the settings, people, projects and paths
  worklog.py build                               rewrite every person's logbook.md; also adds
                                                 the project logbooks this laptop's team-logbook
                                                 knows and the work log does not yet. --log FILE
                                                 appends the output there (for a scheduled run)
  worklog.py show [--person P] [--since D] [--until D]
                                                 rows from the project logbooks (never writes)

This laptop's pointer lives in ~/.config/personal-logbook/config.json (PERSONAL_LOGBOOK_CONFIG
overrides). Times are WIB (UTC+7), as the project logbooks write them. Stdlib only; Python 3.9+,
macOS, Linux and Windows.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WIB = timezone(timedelta(hours=7), "WIB")
COLUMNS = ["No", "Timestamp (WIB)", "Project", "Item", "Description", "Status", "Reference"]
KEYS = ["timestamp", "project", "item", "description", "status", "reference"]
TEAM_KEYS = ["timestamp", "pic", "project", "item", "description", "status", "reference"]
TS_FORMAT = "%Y-%m-%d %H:%M"
LOGBOOK = "logbook.md"
SETTINGS = "worklog-settings.json"
TEAM_SETTINGS = "logbook-settings.json"

Row = Dict[str, str]


# --------------------------------------------------------------------------
# Settings and paths
# --------------------------------------------------------------------------

def config_path() -> Path:
    return Path(os.environ.get("PERSONAL_LOGBOOK_CONFIG")
                or Path.home() / ".config" / "personal-logbook" / "config.json")


def team_config_path() -> Path:
    return Path(os.environ.get("TEAM_LOGBOOK_CONFIG") or Path.home() / ".config" / "team-logbook" / "config.json")


def read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


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


def write_json(path: Path, data: dict) -> None:
    write_atomic(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def require_folder() -> Path:
    folder = (read_json(config_path()) or {}).get("folder")
    if not folder:
        sys.exit(f"personal-logbook: not set up yet. Run: worklog.py setup --folder PATH  ({config_path()})")
    if not Path(folder).is_dir():
        sys.exit(f"personal-logbook: work log folder not found: {folder} (is OneDrive syncing it?)")
    return Path(folder)


def load_settings(folder: Path) -> dict:
    data = read_json(folder / SETTINGS) or {}
    if not isinstance(data.get("people"), dict):
        data["people"] = {}
    if not isinstance(data.get("projects"), list):
        data["projects"] = []
    return data


def project_dir(folder: Path, path: str) -> Path:
    """A project logbook's folder: relative paths start beside the work log folder."""
    return Path(path) if Path(path).is_absolute() else folder.parent / Path(path)


def stored_path(folder: Path, project: Path) -> str:
    """A project folder as settings keep it: relative to the work log's parent when it is there."""
    try:
        return project.resolve().relative_to(folder.parent.resolve()).as_posix()
    except ValueError:
        return str(project.resolve())


def project_name(project: Path) -> str:
    return str((read_json(project / TEAM_SETTINGS) or {}).get("project") or project.name)


def own_pic() -> str:
    return str((read_json(team_config_path()) or {}).get("pic") or "").strip()


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------

def cell(text: str) -> str:
    return " ".join((text or "").split()).replace("|", "\\|")


def uncell(text: str) -> str:
    return text.strip().replace("\\|", "|")


def parse_table(text: str) -> List[List[str]]:
    """Data rows of the first Markdown table in text, as lists of cell strings."""
    rows, seen_header = [], False
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if seen_header and rows:
                break
            continue
        cells = [uncell(c) for c in re.split(r"(?<!\\)\|", line.strip("|"))]
        if not seen_header:
            seen_header = True
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    return rows


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def team_rows(project: Path, name: str) -> List[Row]:
    """Every person's rows in one project logbook, read from their entries files by position (so a
    retitled column changes nothing), conflict copies folded in once. Project is the project's name."""
    seen, rows = set(), []
    for path in sorted(p for p in project.glob("*/logbook-entries*.md") if p.is_file()):
        for cells in parse_table(read_text(path)):
            if len(cells) < len(TEAM_KEYS):
                continue
            r = dict(zip(TEAM_KEYS, cells))
            r["project"] = name
            key = tuple(r[k] for k in TEAM_KEYS)
            if key not in seen:
                seen.add(key)
                rows.append(r)
    return rows


def sort_key(r: Row) -> Tuple[str, str, str]:
    return r["timestamp"], r["project"].lower(), r["item"].lower()


def table(header: List[str], rows: List[List[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Collecting
# --------------------------------------------------------------------------

def collect(folder: Path, data: dict) -> Tuple[List[Row], List[Tuple[str, str]], List[str]]:
    """(rows of every project found, (path, name) of projects not found, warnings)."""
    rows, missing, warnings = [], [], []
    for p in data["projects"]:
        where = project_dir(folder, p["path"])
        if where.is_dir():
            rows += team_rows(where, project_name(where))
        else:
            missing.append((p["path"], p.get("name") or Path(p["path"]).name))
            warnings.append(f"project logbook not found on this laptop: {where}; kept {p.get('name')!r} rows "
                            "from each person's current logbook.md")
    return rows, missing, warnings


def folder_of(data: dict, pic: str) -> Optional[str]:
    return next((f for p, f in data["people"].items() if p.lower() == pic.strip().lower()), None)


def register_team_projects(folder: Path, data: dict) -> List[str]:
    """Add the project logbooks this laptop's team-logbook knows and the work log does not."""
    known = {project_dir(folder, p["path"]).resolve() for p in data["projects"]}
    added = []
    for book in (read_json(team_config_path()) or {}).get("logbooks") or []:
        where = Path(str(book.get("folder") or ""))
        if book.get("folder") and where.is_dir() and where.resolve() not in known:
            data["projects"].append({"path": stored_path(folder, where), "name": project_name(where)})
            known.add(where.resolve())
            added.append(project_name(where))
    return added


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def cmd_setup(args) -> int:
    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"error: work log folder not found: {folder}", file=sys.stderr)
        return 2
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"folder": str(folder.resolve())}, indent=2) + "\n", encoding="utf-8")
    print(f"saved {path}: folder={folder.resolve()}")
    return 0


def cmd_person(args) -> int:
    folder = require_folder()
    data = load_settings(folder)
    data["people"] = {p: f for p, f in data["people"].items() if p.lower() != args.pic.strip().lower()}
    if args.remove:
        print(f"{args.pic}: removed (the folder and its logbook.md stay; delete them by hand if wanted)")
    else:
        own = (args.folder or "").strip().strip("/\\")
        if not own or os.sep in own or "/" in own:
            print("error: --folder is a folder name inside the work log folder, such as BD", file=sys.stderr)
            return 2
        data["people"][args.pic.strip()] = own
        (folder / own).mkdir(exist_ok=True)
        print(f"{args.pic.strip()} -> {own}/{LOGBOOK}")
    write_json(folder / SETTINGS, data)
    return 0


def cmd_project(args) -> int:
    folder = require_folder()
    data = load_settings(folder)
    where = Path(args.folder).expanduser()
    if args.remove:
        wanted = args.folder.strip().lower()
        keep = [p for p in data["projects"]
                if wanted not in (p["path"].lower(), str(p.get("name", "")).lower())
                and project_dir(folder, p["path"]).resolve() != where.resolve()]
        print(f"{args.folder}: {'removed' if len(keep) < len(data['projects']) else 'was not read'}")
        data["projects"] = keep
    else:
        if not where.is_dir():
            print(f"error: project folder not found: {where}", file=sys.stderr)
            return 2
        if not any(where.glob("*/logbook-entries*.md")) and not (where / TEAM_SETTINGS).exists():
            print(f"error: no team logbook in {where} (no logbook-settings.json or */logbook-entries.md)",
                  file=sys.stderr)
            return 2
        path = stored_path(folder, where)
        data["projects"] = [p for p in data["projects"] if project_dir(folder, p["path"]).resolve() != where.resolve()]
        data["projects"].append({"path": path, "name": project_name(where)})
        print(f"reading {project_name(where)!r} from {path}"
              + ("" if not Path(path).is_absolute() else
                 " (outside the work log's parent folder: other laptops will not find it)"))
    write_json(folder / SETTINGS, data)
    return 0


def cmd_where(_args) -> int:
    folder = (read_json(config_path()) or {}).get("folder")
    if not folder:
        print(f"not set up ({config_path()} missing)")
        return 1
    folder = Path(folder)
    print(f"work log folder: {folder} ({'ok' if folder.is_dir() else 'NOT FOUND'})")
    if not folder.is_dir():
        return 1
    data = load_settings(folder)
    print("people:" + ("" if data["people"] else " none yet"))
    for pic, own in sorted(data["people"].items()):
        print(f"  {pic} -> {folder / own / LOGBOOK}")
    print("project logbooks read:" + ("" if data["projects"] else " none yet"))
    for p in data["projects"]:
        where = project_dir(folder, p["path"])
        print(f"  {p.get('name')!r}: {where} ({'ok' if where.is_dir() else 'NOT FOUND on this laptop'})")
    return 0


def cmd_build(_args) -> int:
    folder = require_folder()
    data = load_settings(folder)
    added = register_team_projects(folder, data)
    if added:
        write_json(folder / SETTINGS, data)
        print(f"now reading the project logbooks of {', '.join(repr(a) for a in added)} (from team-logbook)")
    if not data["projects"]:
        print("no project logbooks to read yet: add one with `project FOLDER`")
        return 1
    rows, missing, warnings = collect(folder, data)
    missing_names = {name.lower() for _, name in missing}
    strangers: Dict[str, int] = {}
    by = own_pic()
    folders: Dict[str, List[str]] = {}  # a person's folder -> every PIC spelling they log under
    for pic, own in data["people"].items():
        folders.setdefault(own, []).append(pic)
    for own, pics in sorted(folders.items()):
        pic, spellings = pics[0], {p.lower() for p in pics}
        target = folder / own / LOGBOOK
        mine = [{k: r[k] for k in KEYS} for r in rows if r["pic"].strip().lower() in spellings]
        mine += [dict(zip(KEYS, c[1: 1 + len(KEYS)])) for c in parse_table(read_text(target))
                 if len(c) >= len(COLUMNS) and c[2].lower() in missing_names]
        mine.sort(key=sort_key)
        body = table(COLUMNS, [[str(i)] + [r[k] for k in KEYS] for i, r in enumerate(mine, 1)])
        old = read_text(target)
        if old.endswith(body) and old.startswith(f"# Logbook: {pic}\n"):
            print(f"{pic}: {own}/{LOGBOOK} unchanged, {len(mine)} rows")
            continue
        now = datetime.now(WIB).strftime(TS_FORMAT)
        target.parent.mkdir(exist_ok=True)
        write_atomic(target, f"# Logbook: {pic}\n\n"
                             f"_Read only: built from the project logbooks, where rows are written. "
                             f"Last updated: {now} WIB{' by ' + by if by else ''}_\n\n" + body)
        print(f"{pic}: {own}/{LOGBOOK} written, {len(mine)} rows")
    for r in rows:
        if folder_of(data, r["pic"]) is None:
            strangers[r["pic"]] = strangers.get(r["pic"], 0) + 1
    for pic, n in sorted(strangers.items()):
        warnings.append(f"{n} rows by {pic!r} have no folder here: add them with `person {pic!r} --folder <initials>`")
    for path in sorted(folder.glob(f"*/logbook?*.md")):
        warnings.append(f"{path.parent.name}/{path.name}: looks like a OneDrive conflict copy; it is "
                        "generated, so it can be deleted")
    for w in warnings:
        print(f"warning: {w}")
    return 0


def cmd_show(args) -> int:
    folder = require_folder()
    data = load_settings(folder)
    rows, _, warnings = collect(folder, data)
    if args.person:
        wanted = args.person.strip().lower()
        pics = {p.lower() for p, f in data["people"].items() if wanted in (p.lower(), f.lower())} or {wanted}
        rows = [r for r in rows if r["pic"].strip().lower() in pics]
    rows = [r for r in rows if (not args.since or r["timestamp"][:10] >= args.since)
            and (not args.until or r["timestamp"][:10] <= args.until)]
    rows.sort(key=sort_key)
    for w in warnings:
        print(f"warning: {w}")
    if not rows:
        print("no rows")
        return 0
    print(table(["Timestamp (WIB)", "PIC"] + COLUMNS[2:], [[r["timestamp"], r["pic"]] + [r[k] for k in KEYS[1:]]
                                                            for r in rows]), end="")
    return 0


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("setup")
    p.add_argument("--folder", required=True, help="the synced work log folder, such as 'Work Log'")
    p = sub.add_parser("person")
    p.add_argument("pic", help="the name as the PIC column of the project logbooks writes it")
    p.add_argument("--folder", help="their folder inside the work log folder, such as BD")
    p.add_argument("--remove", action="store_true")
    p = sub.add_parser("project")
    p.add_argument("folder", help="a project logbook's shared folder, such as 04 Working Folders")
    p.add_argument("--remove", action="store_true", help="stop reading it (by folder, path or name)")
    sub.add_parser("where")
    p = sub.add_parser("build")
    p.add_argument("--log", help="append the output to this file instead, for a scheduled run")
    p = sub.add_parser("show")
    p.add_argument("--person", help="a PIC name or folder, such as BD")
    p.add_argument("--since", help="YYYY-MM-DD")
    p.add_argument("--until", help="YYYY-MM-DD")
    args = ap.parse_args(argv)
    if getattr(args, "log", None):
        log = Path(args.log).expanduser()
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as fh, redirect_stdout(fh), redirect_stderr(fh):
            print(f"--- {datetime.now(WIB).strftime(TS_FORMAT)} WIB")
            try:
                return cmd_build(args)
            except SystemExit as stop:
                print(stop)
                return 1
    return {"setup": cmd_setup, "person": cmd_person, "project": cmd_project, "where": cmd_where,
            "build": cmd_build, "show": cmd_show}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
