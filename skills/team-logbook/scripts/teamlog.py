#!/usr/bin/env python3
"""The team logbook: one table per project, in a folder the project's team shares and syncs.

Layout, inside a project's shared folder (for example "04 Working Folders"):

  logbook.md                        the project's table, rebuilt from every person's entries
  logbook-settings.json             the project's settings: name, language, SharePoint address,
                                    what the Project column holds, renamed column titles, and the
                                    tracker its Items come from; written at project setup or by
                                    `settings`, after the person agrees
  <own folder>/logbook-entries.md   one person's rows; only that person's agent writes it
  <own folder>/logbook-sources.json the repos and folders that person routes to this logbook and
                                    the Project label each gets; only that person's agent writes it
  <own folder>/logbook-attachments/<day>/   files attached to that person's rows

A person can log to several projects; each project's folder is one logbook in their settings.

Commands:

  teamlog.py setup --pic NAME --folder PATH --own-folder NAME [--web-url URL]
                   [--project NAME] [--language LANG]
        add a project's shared folder to your logbooks (or update it). With --project, also
        create the project's settings when the folder has none yet
  teamlog.py settings --logbook NAME [--name N] [--language LANG] [--web-url URL]
                   [--project-column name|label] [--column TITLE=NEW]...
                   [--tracker URL] [--item-format TEXT]
        change a project's settings, which the whole team shares. --project-column name (the
        default once a project has settings) makes every row's Project the project's name; label
        keeps the label of the repo or folder. --column Description=Details retitles a column.
        --tracker and --item-format name the tracker Items come from and how an Item is written
        from one of its rows, such as '{Initiative} - {Activity}: {part}', where {part} is the
        piece of the activity a row is about
  teamlog.py map GROUP --logbook NAME [--label LABEL]
        route a repo or folder, as day.py names it, to a logbook, with the Project label its
        rows get (default: GROUP)
  teamlog.py unmap GROUP --logbook NAME
  teamlog.py ignore GROUP [--remove]                 never log this repo or folder (yours only)
  teamlog.py where                                   your settings, logbooks and paths
  teamlog.py route GROUP...                          the logbook and Project label of each group
  teamlog.py names [--logbook NAME] [--limit N]      Project and Item names already used, newest first
  teamlog.py show [--date YYYY-MM-DD] [--pic NAME] [--logbook NAME]
                                                     rows already logged (default: today, everyone)
  teamlog.py add --rows FILE.json                    add or update your rows, then rebuild logbook.md
  teamlog.py rebuild [--logbook NAME]                rebuild logbook.md from every entries file
  teamlog.py attach FILE [--date YYYY-MM-DD] [--logbook NAME]
                                                     copy a file into your attachments, print its link
  teamlog.py check-update                            say whether a newer version of this skill exists

--logbook takes a project name (or the folder path) and can be left out when you have one logbook.

Only your own files are ever written, plus logbook-settings.json when you set a project up or
change its settings. logbook.md is rebuilt from all entries files, sorted by time, so nobody edits
it by hand and two agents never edit the same rows. Times are WIB (UTC+7) whatever the laptop's
time zone.

A row in --rows is {"logbook", "timestamp": "YYYY-MM-DD HH:MM", "project", "item",
"description", "status", "reference"}; "logbook" can be left out when you have one logbook. The
PIC always comes from your settings, and so does Project when the project's Project column holds
its name. A row for an item you already logged that same day replaces that day's row; on a later
day it is a new row, so the logbook keeps each day's state. A row with "was": "<old Item>" renames
that day's row of yours instead of adding a twin; {"timestamp", "item", "delete": true} takes that
day's row of yours out. Either writes nothing if the row is not there. Column titles can be renamed per
project; rows are read by position, so a renamed title never changes how a table is read.

Settings live in ~/.config/team-logbook/config.json (TEAM_LOGBOOK_CONFIG overrides). A file
from version 0.5.0 (one folder) is read as one logbook and rewritten only by `setup` or `ignore`.
Stdlib only; Python 3.9+, macOS, Linux and Windows.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, unquote, urlsplit

WIB = timezone(timedelta(hours=7), "WIB")
COLUMNS = ["Timestamp (WIB)", "PIC", "Project", "Item", "Description", "Status", "Reference"]
KEYS = ["timestamp", "pic", "project", "item", "description", "status", "reference"]
STATUSES = ["Planned", "In progress", "In review", "Done", "Blocked"]
TS_FORMAT = "%Y-%m-%d %H:%M"
LOGBOOK = "logbook.md"
ENTRIES = "logbook-entries.md"
SETTINGS = "logbook-settings.json"
SOURCES = "logbook-sources.json"
ATTACHMENTS = "logbook-attachments"
DEFAULT_LANGUAGE = "English"
REPO = "KevinDarrell/team-skills"
VERSION_PATH = "skills/team-logbook/VERSION"

Row = Dict[str, str]


# --------------------------------------------------------------------------
# Settings and paths
# --------------------------------------------------------------------------

def config_path() -> Path:
    return Path(os.environ.get("TEAM_LOGBOOK_CONFIG") or Path.home() / ".config" / "team-logbook" / "config.json")


def read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def load_config() -> Optional[dict]:
    """Your settings as {pic, logbooks, ignore, note}. A 0.5.0 file ({pic, folder, own, web_url})
    reads as one logbook; reading never writes it back. `note` holds your daily note's settings
    (see note.py), carried through so saving the logbook's settings keeps them."""
    raw = read_json(config_path())
    if raw is None:
        return None
    books = raw.get("logbooks")
    if not isinstance(books, list):
        books = [{k: raw[k] for k in ("folder", "own", "web_url") if raw.get(k)}] if raw.get("folder") else []
    cfg = {
        "pic": str(raw.get("pic") or "").strip(),
        "logbooks": [b for b in books if isinstance(b, dict) and b.get("folder") and b.get("own")],
        "ignore": [str(g) for g in raw.get("ignore") or []],
    }
    if isinstance(raw.get("note"), dict):
        cfg["note"] = raw["note"]
    return cfg


def save_config(cfg: dict) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return path


@dataclass
class Logbook:
    """One project's shared folder, as one person sees it."""

    folder: Path
    own: str
    personal_web_url: str = ""

    @property
    def settings(self) -> dict:
        return read_json(self.folder / SETTINGS) or {}

    @property
    def name(self) -> str:
        return str(self.settings.get("project") or self.folder.name)

    @property
    def language(self) -> str:
        return str(self.settings.get("language") or DEFAULT_LANGUAGE)

    @property
    def web_url(self) -> str:
        return str(self.settings.get("web_url") or self.personal_web_url or "").rstrip("/")

    @property
    def project_column(self) -> str:
        """'name': every row's Project is the project's name. 'label': the label its repo or folder
        is mapped to. A folder with no settings yet keeps 0.5.0's behaviour, 'label'."""
        settings = self.settings
        return str(settings.get("project_column") or ("name" if settings else "label"))

    @property
    def headers(self) -> List[str]:
        """The table's column titles, after the project's renames (such as Description -> Details)."""
        renames = {k.lower(): v for k, v in (self.settings.get("columns") or {}).items() if v}
        return [str(renames.get(c.lower()) or c) for c in COLUMNS]

    @property
    def tracker(self) -> dict:
        tracker = self.settings.get("tracker")
        return tracker if isinstance(tracker, dict) and tracker.get("url") else {}

    @property
    def own_dir(self) -> Path:
        return self.folder / self.own


def folder_address(url: str) -> Tuple[str, Optional[str]]:
    """(address, problem): the shared folder's web address as attachment links need it, which is
    the folder's own path. SharePoint's address bar shows a view of the folder instead,
    .../Forms/AllItems.aspx?id=<the folder's path>&viewid=...; its id is turned into that path."""
    url = url.strip().rstrip("/")
    parts = urlsplit(url)
    path = parse_qs(parts.query).get("id", [""])[0] if parts.query else unquote(parts.path)
    if not parts.scheme or not parts.netloc or not path.startswith("/") or path.lower().endswith(".aspx"):
        return "", (f"{url!r} is not a folder's address. Open the folder on SharePoint and copy the address "
                    "bar (a .../AllItems.aspx?id=... address works), or give https://<host>/sites/<site>/<path>")
    return f"{parts.scheme}://{parts.netloc}{quote(path.rstrip('/'))}", None


def logbooks(cfg: dict) -> List[Logbook]:
    return [Logbook(Path(b["folder"]), b["own"], b.get("web_url") or "") for b in cfg["logbooks"]]


def require_config() -> dict:
    cfg = load_config()
    if not cfg or not cfg["pic"] or not cfg["logbooks"]:
        sys.exit("team-logbook: not set up yet. Run: teamlog.py setup --pic NAME --folder PATH "
                 f"--own-folder NAME  ({config_path()})")
    return cfg


def require_folder(book: Logbook) -> Logbook:
    if not book.folder.is_dir():
        sys.exit(f"team-logbook: shared folder of {book.name} not found: {book.folder} (is OneDrive syncing it?)")
    return book


def find_logbook(cfg: dict, name: Optional[str]) -> Optional[Logbook]:
    books = logbooks(cfg)
    if not name:
        return books[0] if len(books) == 1 else None
    wanted = name.strip().lower()
    for b in books:  # the folder's own name still works after the project is renamed
        if wanted in (b.name.lower(), str(b.folder).lower(), b.folder.name.lower()):
            return b
    return None


def pick_logbook(cfg: dict, name: Optional[str]) -> Logbook:
    book = find_logbook(cfg, name)
    if book is None:
        names = ", ".join(repr(b.name) for b in logbooks(cfg))
        sys.exit(f"team-logbook: {'no logbook named ' + repr(name) if name else 'several logbooks'}; "
                 f"pass --logbook with one of {names}")
    return require_folder(book)


def chosen(cfg: dict, name: Optional[str]) -> List[Logbook]:
    """The named logbook, or every logbook whose folder is there."""
    if name:
        return [pick_logbook(cfg, name)]
    return [b for b in logbooks(cfg) if b.folder.is_dir()]


def entries_files(folder: Path) -> List[Path]:
    """Every person's entries file, plus any sync conflict copies of one, one level down."""
    return sorted(p for p in folder.glob("*/logbook-entries*.md") if p.is_file())


def all_rows(book: Logbook) -> List[Row]:
    return [r for path in entries_files(book.folder) for r in read_entries(path)]


# --------------------------------------------------------------------------
# Sources: which repos and folders go to which logbook
# --------------------------------------------------------------------------

def read_sources(book: Logbook) -> Tuple[Dict[str, Tuple[str, str, str]], List[str]]:
    """Every person's routes into this logbook, as {group in lower case: (group, label, who)}.
    Your own file wins; between two others, the first folder in name order wins, with a warning."""
    merged: Dict[str, Tuple[str, str, str]] = {}
    warnings: List[str] = []
    own_file = book.own_dir / SOURCES
    others = sorted(p for p in book.folder.glob(f"*/{SOURCES}") if p.is_file() and p != own_file)
    for path in others:
        for group, label in ((read_json(path) or {}).get("sources") or {}).items():
            key, who = group.lower(), path.parent.name
            if key in merged and merged[key][1] != label:
                warnings.append(f"{book.name}: {merged[key][2]} labels {group} {merged[key][1]!r}, {who} labels it "
                                f"{label!r}; using {merged[key][1]!r}")
            merged.setdefault(key, (group, str(label), who))
    for group, label in ((read_json(own_file) or {}).get("sources") or {}).items():
        merged[group.lower()] = (group, str(label), book.own)
    return merged, warnings


def route(cfg: dict, group: str) -> Tuple[str, List[Tuple[Logbook, str, str]]]:
    """('ignored' | 'mapped' | 'earlier rows' | 'unknown', [(logbook, Project label, how)])."""
    if group.lower() in (g.lower() for g in cfg["ignore"]):
        return "ignored", []
    books = [b for b in logbooks(cfg) if b.folder.is_dir()]
    hits = []
    for b in books:
        hit = read_sources(b)[0].get(group.lower())
        if hit:
            hits.append((b, project_label(b, hit[1]), f"mapped by {hit[2]}"))
    if hits:
        return "mapped", hits
    for b in books:
        label = next((r["project"] for r in all_rows(b) if r["project"].lower() == group.lower()), None)
        if label:
            hits.append((b, project_label(b, label), "from earlier rows"))
    return ("earlier rows" if hits else "unknown"), hits


def project_label(book: Logbook, label: str) -> str:
    return book.name if book.project_column == "name" else label


# --------------------------------------------------------------------------
# Markdown tables
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


def read_entries(path: Path) -> List[Row]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return [dict(zip(KEYS, cells[: len(KEYS)])) for cells in parse_table(text) if len(cells) >= len(KEYS)]


def table(header: List[str], rows: List[List[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


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


# --------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------

def validate(row: Row) -> List[str]:
    problems = []
    try:
        datetime.strptime(row.get("timestamp", ""), TS_FORMAT)
    except ValueError:
        problems.append(f"timestamp {row.get('timestamp')!r} is not YYYY-MM-DD HH:MM")
    if row.get("status") not in STATUSES:
        problems.append(f"status {row.get('status')!r} is not one of {', '.join(STATUSES)}")
    for key in ("project", "item", "description"):
        if not (row.get(key) or "").strip():
            problems.append(f"{key} is empty")
    return problems


def same_day_key(row: Row) -> Tuple[str, str, str]:
    return row["timestamp"][:10], row["project"].strip().lower(), row["item"].strip().lower()


def merge_rows(existing: List[Row], new: List[Row]) -> Tuple[List[Row], int, int]:
    """Same item on the same day replaces that day's row; anything else is appended."""
    rows = list(existing)
    added = updated = 0
    for n in new:
        hit = next((i for i, r in enumerate(rows) if same_day_key(r) == same_day_key(n)), None)
        if hit is None:
            rows.append(n)
            added += 1
        else:
            rows[hit] = n
            updated += 1
    rows.sort(key=lambda r: (r["timestamp"], r["project"].lower(), r["item"].lower()))
    return rows, added, updated


def entries_text(pic: str, rows: List[Row], headers: Optional[List[str]] = None) -> str:
    return (
        f"# Logbook entries: {pic}\n\n"
        + table(headers or COLUMNS, [[r[k] for k in KEYS] for r in rows])
    )


def rebuild(folder: Path, by: str, headers: Optional[List[str]] = None) -> Tuple[int, List[str]]:
    """Rebuild logbook.md from every entries file. Returns (row count, warnings). Rows are read by
    position, so renamed column titles never change how a table is read."""
    warnings: List[str] = []
    seen, rows = set(), []
    for path in entries_files(folder):
        if path.name != ENTRIES:
            warnings.append(f"{path.parent.name}/{path.name}: looks like a OneDrive conflict copy; "
                            f"its rows are included once, then the file can be deleted")
        for r in read_entries(path):
            key = tuple(r[k] for k in KEYS)
            if key not in seen:
                seen.add(key)
                rows.append(r)
    rows.sort(key=lambda r: (r["timestamp"], r["pic"].lower(), r["project"].lower(), r["item"].lower()))
    now = datetime.now(WIB).strftime(TS_FORMAT)
    text = (
        "# Team Logbook\n\n"
        f"_Last updated: {now} WIB by {by}_\n\n"
        + table(["No"] + (headers or COLUMNS), [[str(i)] + [r[k] for k in KEYS] for i, r in enumerate(rows, 1)])
    )
    write_atomic(folder / LOGBOOK, text)
    return len(rows), warnings


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
        print(f"error: shared folder not found: {folder}", file=sys.stderr)
        return 2
    own = args.own_folder.strip().strip("/\\")
    if not own or os.sep in own or "/" in own:
        print("error: --own-folder is a folder name inside the shared folder, such as AN", file=sys.stderr)
        return 2
    web_url, problem = folder_address(args.web_url) if args.web_url else ("", None)
    if problem:
        print(f"error: --web-url {problem}", file=sys.stderr)
        return 2
    (folder / own).mkdir(exist_ok=True)
    cfg = load_config() or {"pic": "", "logbooks": [], "ignore": []}
    cfg["pic"] = args.pic.strip()
    entry = {"folder": str(folder.resolve()), "own": own}
    if web_url:
        entry["web_url"] = web_url
    cfg["logbooks"] = [b for b in cfg["logbooks"] if Path(b["folder"]).resolve() != folder.resolve()] + [entry]
    path = save_config(cfg)
    print(f"saved {path}: pic={cfg['pic']}, " + ", ".join(f"{k}={v}" for k, v in entry.items()))
    settings = folder / SETTINGS
    if args.project and not settings.exists():
        data = {"project": args.project.strip(), "language": (args.language or DEFAULT_LANGUAGE).strip()}
        if entry.get("web_url"):
            data["web_url"] = entry["web_url"]
        write_json(settings, data)
        print(f"created {settings}: " + ", ".join(f"{k}={v}" for k, v in data.items()))
    elif args.project:
        print(f"kept the project settings already in {settings} (change them with `settings`)")
    return 0


def cmd_settings(args) -> int:
    cfg = require_config()
    book = pick_logbook(cfg, args.logbook)
    data = dict(book.settings)
    web_url = args.web_url
    if web_url:
        web_url, problem = folder_address(web_url)
        if problem:
            print(f"error: --web-url {problem}", file=sys.stderr)
            return 2
    for key, value in (("project", args.name), ("language", args.language), ("web_url", web_url),
                       ("project_column", args.project_column)):
        if value is not None:
            data[key] = value.strip()
    if data.get("web_url") == "":
        del data["web_url"]
    for rename in args.column or []:
        old, _, new = rename.partition("=")
        if old.strip().lower() not in (c.lower() for c in COLUMNS):
            print(f"error: --column {rename!r}: {old.strip()!r} is not one of {', '.join(COLUMNS)}", file=sys.stderr)
            return 2
        columns = {k: v for k, v in (data.get("columns") or {}).items() if k.lower() != old.strip().lower()}
        if new.strip():
            columns[old.strip()] = new.strip()
        data["columns"] = columns
    if not data.get("columns"):
        data.pop("columns", None)
    if args.tracker is not None or args.item_format is not None:
        tracker = dict(data.get("tracker") or {})
        if args.tracker is not None:  # a copied link's "source=copy_link" says nothing about the tracker
            tracker["url"] = re.sub(r"[?&]source=copy_link\b", "", args.tracker.strip()).rstrip("?&")
        if args.item_format is not None:
            tracker["item"] = args.item_format.strip()
        if tracker.get("url"):
            data["tracker"] = tracker
        else:
            data.pop("tracker", None)
    if data == book.settings:
        print(f"no change; {book.folder / SETTINGS}: {json.dumps(data, ensure_ascii=False)}")
        return 0
    data.setdefault("project", book.name)
    renamed = data["project"] != book.name
    write_json(book.folder / SETTINGS, data)
    print(f"saved {book.folder / SETTINGS}: {json.dumps(data, ensure_ascii=False)}")
    if renamed:
        print(f"this logbook is now called {data['project']!r}: use that with --logbook from here on")
    return 0


def own_sources(book: Logbook) -> dict:
    return read_json(book.own_dir / SOURCES) or {"sources": {}}


def cmd_map(args) -> int:
    cfg = require_config()
    book = pick_logbook(cfg, args.logbook)
    data = own_sources(book)
    data.setdefault("sources", {})[args.group] = (args.label or args.group).strip()
    book.own_dir.mkdir(exist_ok=True)
    write_json(book.own_dir / SOURCES, data)
    print(f"{args.group} -> {book.name}, Project {project_label(book, data['sources'][args.group])!r} "
          f"({book.own}/{SOURCES})")
    return 0


def cmd_unmap(args) -> int:
    cfg = require_config()
    book = pick_logbook(cfg, args.logbook)
    data = own_sources(book)
    removed = [g for g in list(data.get("sources", {})) if g.lower() == args.group.lower()]
    for g in removed:
        del data["sources"][g]
    if removed:
        write_json(book.own_dir / SOURCES, data)
    print(f"{args.group}: {'removed from' if removed else 'was not in'} {book.own}/{SOURCES} of {book.name}")
    return 0


def cmd_ignore(args) -> int:
    cfg = require_config()
    rest = [g for g in cfg["ignore"] if g.lower() != args.group.lower()]
    cfg["ignore"] = rest if args.remove else rest + [args.group]
    save_config(cfg)
    print(f"{args.group}: {'logged again' if args.remove else 'ignored from now on'}")
    return 0


# --------------------------------------------------------------------------
# Commands: reading (these never write)
# --------------------------------------------------------------------------

def row_rules(book: Logbook) -> List[str]:
    """How this project's rows are written, one line each."""
    rules = [f"rows are written in {book.language}",
             f"Project is always {book.name!r}" if book.project_column == "name"
             else "Project is the label of the repo or folder the work came from"]
    tracker = book.tracker
    if tracker:
        item = tracker.get("item") or ""
        rules.append(f"Item comes from the tracker {tracker['url']}, written as "
                     f"{item or '(no format set: ask the person)'!r}"
                     + ("; {part} is the piece of the activity a row is about, in three to six words"
                        if "{part}" in item else
                        "; the format has no {part}, so a row names a whole activity (suggest adding ': {part}')"
                        if item else ""))
    renamed = [f"{c} is titled {h!r}" for c, h in zip(COLUMNS, book.headers) if c != h]
    if renamed:
        rules.append("columns: " + ", ".join(renamed))
    return rules


def cmd_where(_args) -> int:
    cfg = load_config()
    if not cfg or not cfg["logbooks"]:
        print(f"not set up ({config_path()} missing)")
        return 1
    print(f"pic: {cfg['pic']}")
    for b in logbooks(cfg):
        ok = b.folder.is_dir()
        print(f"\nlogbook {b.name!r}\n"
              f"  shared folder: {b.folder} ({'ok' if ok else 'NOT FOUND'})\n"
              f"  your entries: {b.own_dir / ENTRIES}\n"
              f"  team table: {b.folder / LOGBOOK}")
        if not ok:
            continue
        print(f"  project settings: {'; '.join(row_rules(b)) if b.settings else 'none yet (ask the person for them, then run settings)'}\n"
              f"  web address: {b.web_url or 'not set (attachment links will be paths inside the folder)'}")
        sources, warnings = read_sources(b)
        routed = ", ".join(f"{g} -> {label!r} ({who})" for g, label, who in sorted(sources.values()))
        print(f"  repos and folders routed here: {routed or 'none yet'}")
        for w in warnings:
            print(f"  warning: {w}")
    print(f"\nignored: {', '.join(cfg['ignore']) or 'nothing'}")
    return 0


def cmd_route(args) -> int:
    cfg = require_config()
    for group in args.groups:
        how, hits = route(cfg, group)
        if how == "ignored":
            print(f"{group} -> ignored")
        elif how == "unknown":
            print(f"{group} -> unknown: ask which logbook it belongs to, then map or ignore it")
        elif len(hits) > 1:
            options = "; ".join(f"{b.name} as {label!r} ({h})" for b, label, h in hits)
            print(f"{group} -> ambiguous: {options}; ask which")
        else:
            b, label, h = hits[0]
            print(f"{group} -> {b.name}, Project {label!r} ({h})")
    return 0


def cmd_names(args) -> int:
    cfg = require_config()
    for book in chosen(cfg, args.logbook):
        last: Dict[Tuple[str, str], Row] = {}
        for r in all_rows(book):
            key = (r["project"].lower(), r["item"].lower())
            if key not in last or r["timestamp"] > last[key]["timestamp"]:
                last[key] = r
        rows = sorted(last.values(), key=lambda r: r["timestamp"], reverse=True)[: args.limit]
        print(f"## {book.name}\n" + "".join(f"- {rule}\n" for rule in row_rules(book)), end="")
        if rows:
            print(table(["Project", "Item", "Last logged", "Last status", "By"],
                        [[r["project"], r["item"], r["timestamp"], r["status"], r["pic"]] for r in rows]), end="")
        else:
            print("no rows yet")
    return 0


def cmd_show(args) -> int:
    cfg = require_config()
    day = args.date or datetime.now(WIB).strftime("%Y-%m-%d")
    for book in chosen(cfg, args.logbook):
        rows = [r for r in all_rows(book)
                if r["timestamp"].startswith(day) and (not args.pic or r["pic"].lower() == args.pic.lower())]
        rows.sort(key=lambda r: r["timestamp"])
        print(f"## {book.name}")
        if not rows:
            print(f"no rows for {day}" + (f" by {args.pic}" if args.pic else ""))
            continue
        print(table(book.headers, [[r[k] for k in KEYS] for r in rows]), end="")
    return 0


# --------------------------------------------------------------------------
# Commands: writing rows
# --------------------------------------------------------------------------

def cmd_add(args) -> int:
    cfg = require_config()
    pic = cfg["pic"]
    try:
        raw = json.loads(Path(args.rows).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        print(f"error: cannot read rows from {args.rows}: {err}", file=sys.stderr)
        return 2
    # Per logbook: (logbook, rows to add or update, rows of yours to take out first as (day, Item, why)).
    batches: Dict[str, Tuple[Logbook, List[Row], List[Tuple[str, str, str]]]] = {}
    problems = []
    for i, r in enumerate(raw if isinstance(raw, list) else [raw], 1):
        book = find_logbook(cfg, r.get("logbook"))
        if book is None:
            names = ", ".join(repr(b.name) for b in logbooks(cfg))
            problems.append(f"row {i}: logbook {r.get('logbook')!r} is not one of {names}" if r.get("logbook")
                            else f"row {i}: no logbook; with several, each row names one of {names}")
            continue
        _, new, out = batches.setdefault(str(book.folder), (book, [], []))
        if r.get("delete"):  # {"timestamp", "item", "delete": true} takes that day's row of yours out
            item, day = " ".join(str(r.get("item", "")).split()), str(r.get("timestamp", ""))[:10]
            if not item or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                problems.append(f"row {i}: a delete needs the row's timestamp (or day) and its Item")
            out.append((day, item, "delete"))
            continue
        row = {k: " ".join(str(r.get(k, "")).split()) for k in KEYS}
        row["pic"] = pic
        if book.project_column == "name":
            row["project"] = book.name
        problems += [f"row {i}: {p}" for p in validate(row)]
        was = " ".join(str(r.get("was", "")).split())
        if was:  # "was": the Item this row had before, so a rename replaces it instead of adding a twin
            out.append((row["timestamp"][:10], was, "rename"))
        new.append(row)
    plans = []
    for book, new, out in batches.values():
        require_folder(book)
        existing = read_entries(book.own_dir / ENTRIES)
        for day, item, why in out:
            hit = next((n for n, e in enumerate(existing)
                        if e["timestamp"][:10] == day and e["item"].strip().lower() == item.lower()), None)
            if hit is None:
                problems.append(f"{book.name}: no row of yours on {day} with Item {item!r} to {why}")
            else:
                existing.pop(hit)
        plans.append((book, new, out, existing))
    if problems:
        print("error: nothing written\n  " + "\n  ".join(problems), file=sys.stderr)
        return 2
    for book, new, out, existing in plans:
        book.own_dir.mkdir(exist_ok=True)
        rows, added, updated = merge_rows(existing, new)
        renamed = sum(1 for _, _, why in out if why == "rename")
        deleted = len(out) - renamed
        write_atomic(book.own_dir / ENTRIES, entries_text(pic, rows, book.headers))
        total, warnings = rebuild(book.folder, pic, book.headers)
        print(f"{book.name}: {book.own}/{ENTRIES}: {max(added - renamed, 0)} added, {updated} updated, {renamed} renamed, "
              f"{deleted} deleted. {LOGBOOK}: {total} rows.")
        for w in warnings:
            print(f"warning: {w}")
    return 0


def cmd_rebuild(args) -> int:
    cfg = require_config()
    for book in chosen(cfg, args.logbook):
        total, warnings = rebuild(book.folder, cfg["pic"], book.headers)
        print(f"{book.name}: {LOGBOOK}: {total} rows.")
        for w in warnings:
            print(f"warning: {w}")
    return 0


def cmd_attach(args) -> int:
    """Copy a file into <own>/logbook-attachments/<day>/ and print a Markdown link for Reference."""
    cfg = require_config()
    book = pick_logbook(cfg, args.logbook)
    src = Path(args.file).expanduser()
    if not src.is_file():
        print(f"error: file not found: {src}", file=sys.stderr)
        return 2
    day = args.date or datetime.now(WIB).strftime("%Y-%m-%d")
    dest_dir = book.own_dir / ATTACHMENTS / day
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^\w.\- ]+", "-", src.name).strip() or "attachment"
    dest, n = dest_dir / name, 2
    while dest.exists():
        dest = dest_dir / f"{Path(name).stem}-{n}{Path(name).suffix}"
        n += 1
    shutil.copy2(src, dest)
    rel = f"{book.own}/{ATTACHMENTS}/{day}/{dest.name}"
    link = f"{book.web_url}/{quote(rel)}" if book.web_url else quote(rel)
    print(f"[{dest.name}]({link})")
    return 0


def cmd_check_update(_args) -> int:
    mine, latest = local_version(), latest_version()
    if latest is None:
        print(f"version {mine}: could not check for updates (gh unavailable or offline)")
    elif version_tuple(latest) > version_tuple(mine):
        print(f"UPDATE AVAILABLE: installed {mine}, latest {latest}. "
              "Ask the person to run `npx skills update -g team-logbook` in a terminal (with the -g), then start a new session.")
    else:
        print(f"version {mine}: up to date")
    return 0


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("setup")
    p.add_argument("--pic", required=True)
    p.add_argument("--folder", required=True, help="the project's synced shared folder, such as 04 Working Folders")
    p.add_argument("--own-folder", required=True, help="your folder inside it, such as AN")
    p.add_argument("--web-url", help="web address of the shared folder (SharePoint), so attachment links open")
    p.add_argument("--project", help="the project's name; creates its settings when the folder has none")
    p.add_argument("--language", help=f"language of the rows (default {DEFAULT_LANGUAGE})")
    p = sub.add_parser("settings")
    p.add_argument("--logbook")
    p.add_argument("--name")
    p.add_argument("--language")
    p.add_argument("--web-url")
    p.add_argument("--project-column", choices=["name", "label"],
                   help="name: every row's Project is the project's name; label: the repo or folder's label")
    p.add_argument("--column", action="append", metavar="TITLE=NEW",
                   help="rename a column, such as Description=Details; TITLE= restores it")
    p.add_argument("--tracker", help="the project's tracker (a Notion database URL); empty removes it")
    p.add_argument("--item-format", help="how an Item is written from a tracker row, such as "
                                         "'{Initiative} - {Activity}: {part}'")
    p = sub.add_parser("map")
    p.add_argument("group")
    p.add_argument("--logbook")
    p.add_argument("--label")
    p = sub.add_parser("unmap")
    p.add_argument("group")
    p.add_argument("--logbook")
    p = sub.add_parser("ignore")
    p.add_argument("group")
    p.add_argument("--remove", action="store_true")
    sub.add_parser("where")
    p = sub.add_parser("route")
    p.add_argument("groups", nargs="+")
    p = sub.add_parser("names")
    p.add_argument("--logbook")
    p.add_argument("--limit", type=int, default=50)
    p = sub.add_parser("show")
    p.add_argument("--date")
    p.add_argument("--pic")
    p.add_argument("--logbook")
    p = sub.add_parser("add")
    p.add_argument("--rows", required=True)
    p = sub.add_parser("rebuild")
    p.add_argument("--logbook")
    p = sub.add_parser("attach")
    p.add_argument("file")
    p.add_argument("--date")
    p.add_argument("--logbook")
    sub.add_parser("check-update")
    args = ap.parse_args(argv)
    return {"setup": cmd_setup, "settings": cmd_settings, "map": cmd_map, "unmap": cmd_unmap,
            "ignore": cmd_ignore, "where": cmd_where, "route": cmd_route, "names": cmd_names,
            "show": cmd_show, "add": cmd_add, "rebuild": cmd_rebuild, "attach": cmd_attach,
            "check-update": cmd_check_update}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
