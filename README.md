# team-skills

Claude Code skills for teams. Public: anyone can install them, no access needed.

## Skills

| Skill | What it does |
|---|---|
| `team-logbook` | Adds the day's work to each project's shared logbook table (`logbook.md` in a folder the project's team syncs, usually on SharePoint): one row per thing made, with No, Timestamp (WIB), PIC, Project, Item, Description (or the project's own title for it), Status and Reference |
|  | Also writes each person's daily note: everything they did that day, across all projects, in detail, as one Markdown file per day in their own synced folder |

## Install (once per laptop)

A skill goes in once per laptop and then works in every Claude Code session, whatever folder it runs in.

### 1. Prepare the laptop

| You need | How |
|---|---|
| Claude Code | the desktop app or the terminal version |
| Node.js, for `npx` | nodejs.org |
| git and the GitHub CLI, `gh` | sign in with `gh auth login`. The install itself needs no account; `team-logbook` uses `gh` to read your PRs and to check for updates |
| Python 3 | macOS has it. On Windows, install it from python.org and tick "Add python.exe to PATH" |

### 2. Install

```
npx skills add KevinDarrell/team-skills --skill team-logbook -g -a claude-code
```

Then open a new Claude Code session.

### Update

```
npx skills update -g team-logbook
```

Then open a new Claude Code session. Keep the `-g`: without it, `npx skills update` looks only at skills installed for a project and leaves this global one as it was. Updates are never automatic: each run of `team-logbook` checks GitHub and tells you when a newer version exists.

### When the install fails

| You see | Cause | Fix |
|---|---|---|
| "Repository not found" | a typo in `KevinDarrell/team-skills` | copy the command above as it is |
| `gh auth status` says you are not logged in | `gh` is not signed in | `gh auth login` |
| "npx: command not found" | Node.js is missing | install Node.js |
| on Windows, `python3` opens the Microsoft Store or does nothing | the Store stub, not Python | install Python from python.org; the skill uses `python` there |

## Set up a project's logbook (once per project, per laptop)

Each project keeps its own logbook, in a folder everyone on the project syncs: usually a folder of the project's SharePoint site, but Google Drive, Dropbox or a network drive work too (for example `ProjectSite > Shared Documents > Project Data > 04 Working Folders`).

1. Install OneDrive and sign in with your work account.
2. In SharePoint, open the project's folder and click **Sync**. It appears in Finder (macOS) or File Explorer (Windows).
3. If the project's tracker is in Notion, connect Notion in your claude.ai connector settings, with access to the tracker's page. Without it, the agent cannot read the tracker and names Items without it.
4. In Claude Code, say "update team logbook". The first time, the agent asks for your name, the synced folder's path and your own folder in it (your initials, such as `AN`). The first person of a project also gives the project's name, the language its rows are written in, the folder's SharePoint address and, if the project keeps one, its tracker (such as a Notion database of activities: each Item then names the activity and the part of it the row is about, such as `Initiative 1: … - Build back-end: Login API`); these are saved in the folder for everyone. Each project can also retitle columns (Description → Details) or keep repo names in the Project column: ask the agent to change the logbook's settings. Your own answers go to `~/.config/team-logbook/config.json`.
5. Working on another project too? Say "add project <name> to my logbook" and give its synced folder.

```
04 Working Folders/
├── BD/logbook-entries.md    Budi's rows, written only by Budi's agent
├── BD/logbook-sources.json  which repos and folders Budi routes here, and their Project names
├── AN/logbook-entries.md    Ana's rows, written only by Ana's agent
├── AN/logbook-sources.json  the same, for Ana
├── logbook-settings.json    the project's name, language, SharePoint address, tracker and column titles
└── logbook.md               the project's table, rebuilt from everyone's rows, in time order
```

## Use

At the end of the day, in any Claude Code session: "update team logbook" (or `/team-logbook`). The agent drafts one row per piece of work from your sessions, commits and GitHub activity, and shows you the draft once, with numbered notes on anything it guessed and a question about work that left no trace on your laptop. Answer "ok", or correct it by number; it writes after you agree.

- The first time a repo or folder shows up, the agent puts its work under the likeliest project and says so in the draft's notes. Correct it there, or say to leave it out for good. Once you agree, it is remembered, and teammates on that project get it too.
- Each person's agent writes only their own files. `logbook.md` is rebuilt from everyone's rows, sorted by time, so do not edit it by hand.
- Work that continues the next day gets a new row with the same Item name.
- All times are WIB, whatever your laptop's time zone.

## Daily note (once per person)

Besides the project logbook, each person can keep a daily note: one file per day of everything they worked on, across all projects, with what was done, what was found, what was decided and what is next, under a heading per piece of work. It is read from the day's Claude Code and Codex sessions on the laptop, GitHub, and any calendar or meeting-notes connector the person chooses.

1. Make a folder of your own in the team's synced storage (for example `Daily Notes/AN` on SharePoint), synced to your laptop.
2. Optional: connect a calendar (Google Calendar, or Microsoft 365 for Outlook) or meeting notes (Fireflies) in your claude.ai connector settings, then open a new Claude Code session. Microsoft 365 can need your IT admin's approval first. Claude Code sees these connectors when it is signed in with the same claude.ai account.
3. In Claude Code, say "update my daily note" (or "catatan harian"). The first time, the agent asks for your note folder, the language notes are written in, and which connectors to read. Your answers go to `~/.config/team-logbook/config.json`.

Each run shows you the draft first and writes only after you agree, since the whole team can read the folder. Missed days can be written later, one note per day, for as long as the laptop still has the sessions (Claude Code keeps them about 30 days). Chats on claude.ai are not on the laptop, so they are not read; tell the agent about that work when it asks.

```
Daily Notes/
├── AN/2026-10-12.md   Ana's note for that day, written only by Ana's agent
├── AN/2026-10-13.md
└── BD/2026-10-12.md   Budi's
```

## Develop

Change a skill by pull request, and raise its `VERSION` (for example `0.2.0` → `0.3.0`) in the same change: the update reminder compares that file with the copy on `main`, so a change without a new version reaches nobody's reminder. Tests: `python3 -I -m unittest discover -s tests -v` (`python` on Windows); CI runs them on Linux, Windows and Python 3.9.

Working here with Claude Code: `CLAUDE.md` holds the rules, `/try` runs the working copy of a skill against a sandbox folder, `/ship` takes a change to an open pull request, and a hook (`.claude/hooks/gate.py`) blocks commits on `main`, a changed skill without a new `VERSION`, failing tests, and dev runs that would write to the live logbook.
