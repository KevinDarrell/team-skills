---
name: personal-logbook
description: Build each person's read-only logbook — their rows from every project's team logbook combined into one table per person (logbook.md in their folder inside a shared folder, such as the SharePoint library "Work Log") — and answer what someone worked on across projects. Use when asked to update or rebuild the personal logbooks, the per-person work log, see what one person did across all projects, add a person or a project to the work log, or right after logging to a team logbook. Rows are still written only through team-logbook.
---

# Personal logbook

Work is logged per project, in each project's team logbook (`team-logbook`). The personal logbook is a read-only view on top of that: one table per person, `<work log folder>/<their folder>/logbook.md`, with that person's rows from every project in time order, so a manager opens one file to see one person's week. Nobody writes rows here; `build` rewrites the tables from the project logbooks.

The work log folder is a folder the team syncs, usually a SharePoint library through OneDrive (such as `Work Log`). It holds:

- `worklog-settings.json`: who is who (each PIC spelling the project logbooks use -> that person's folder, such as `Budi` and `Budi Santoso` -> `BD`) and which project logbooks to read. Project paths are kept relative to the folder the work log sits in, since OneDrive syncs each library side by side, so the same settings work on every laptop.
- `<folder>/logbook.md` per person: generated, read only.

A project logbook a laptop does not sync keeps that project's rows from the person's current table, so a laptop with fewer projects never wipes rows it cannot see.

**Talking with the person**: use their language (the one most of their latest message is in), even though the script output is in English. Ask one thing per message, numbered when there are several.

Commands below say `python3`. On Windows use `python`: there `python3` is often a Microsoft Store stub that runs nothing. If `python` is blocked too (an Application Control policy, a shim that will not run), use a real interpreter directly, such as the one under `%APPDATA%\uv\python\cpython-*\python.exe`. `S` stands for this skill's folder (`~/.claude/skills/personal-logbook` on macOS and Linux, `%USERPROFILE%\.claude\skills\personal-logbook` on Windows).

## 1. Check the setup

- Run `python3 -I S/scripts/worklog.py where`.
- If it says "not set up", find the work log folder with the person (for OneDrive: under `~/Library/CloudStorage/OneDrive-SharedLibraries-<organisation>/` on macOS, `C:\Users\<user>\<organisation>\` on Windows; do not guess), then run `python3 -I S/scripts/worklog.py setup --folder "<work log folder>"`.
- If `where` lists no people or misses someone, list the folders already in the work log folder and ask who each belongs to, then run `person "<PIC>" --folder <folder>` for each. The PIC is the name exactly as the project logbooks' PIC column writes it; a person who logs under several spellings gets one `person` line per spelling, same folder. The first spelling added titles their table, so add the full name first.
- Done when: `where` shows the folder as `ok` and the people.

## 2. Build

- Run `python3 -I S/scripts/worklog.py build`. It first adds any project logbook this laptop's `team-logbook` knows and the work log does not yet read, then rewrites each person's `logbook.md` (or says it is unchanged).
- Its warnings, each passed on in one line:
  - `rows by '<PIC>' have no folder here`: someone logs under a name the work log does not know. Ask whose it is: a new spelling of someone listed (`person "<PIC>" --folder <their folder>`) or a new person (their initials as the folder name, confirmed with them).
  - `project logbook not found on this laptop`: that project's rows were kept from the current tables. Fine, unless the project ended: then `project "<name>" --remove`, after the person agrees, since that removes its rows from everyone's tables at the next build.
  - `conflict copy`: two laptops built at once and OneDrive kept both. The tables are generated, so the copy can be deleted.
- Done when: every person's table is written or unchanged.

## 3. Answer from it

- When the person asks what someone did ("what did Budi do this week?"), run `python3 -I S/scripts/worklog.py show --person <PIC or folder> --since YYYY-MM-DD [--until YYYY-MM-DD]`. It reads the project logbooks directly and never writes.
- Summarise from its rows: per project, what was finished, what is in review or in progress, and what is blocked and on whom. Quote Items as written.
- Done when: every row in the range is in the summary, under its project.

## 4. Report

- In the person's language: which tables were written or unchanged and how many rows each has, the work log folder's path, that the sync app uploads it by itself, and any warning left open.
- Done when: the person knows where the tables are and what, if anything, is left for them.

## After logging to a team logbook

`team-logbook`'s `add` and `rebuild` run `build` by themselves when this laptop has the personal logbooks set up, and print its output as `personal logbooks:` lines. When a team-logbook write printed no such lines (a copy of team-logbook without that step), run `build` here, so the tables catch up, and mention it in one line of that report.

## Changing the settings

- Another project logbook: `project "<its shared folder>"` (the folder holding `logbook-settings.json` and everyone's own folders). One outside the folder the work log sits in is stored as an absolute path, which other laptops will not find; the script says so.
- Stop reading a project: `project "<name or folder>" --remove`.
- A new person or spelling: `person "<PIC>" --folder <folder>`; `person "<PIC>" --remove` stops matching that spelling (their table is kept until deleted by hand).
- These settings are shared with everyone who builds; confirm before changing them, then show `where`.

## Rules the script holds

- It never writes to a project logbook. Rows, corrections and deletions go through `team-logbook` in that project; the next `build` carries them over.
- The tables are generated: editing one by hand is lost at the next build.
- Everyone's table can be rebuilt by anyone, like a team `logbook.md`, since the result depends only on the project logbooks.
