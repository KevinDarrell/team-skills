---
name: team-logbook
description: Add the day's work to the project's shared logbook table (logbook.md in a folder the project's team shares, such as a SharePoint folder) — one row per piece of work, with No, Timestamp, PIC, Project, Item, Description, Status and Reference — for whoever runs it, on every project they log to. Use when asked to update the team logbook, log today's work for the team, fill in the shared logbook, or change the team logbook's settings.
---

# Team logbook

Each project keeps one table, `logbook.md`, in a folder everyone on the project syncs to their laptop: usually a SharePoint folder through OneDrive, but any shared folder works (Google Drive, Dropbox, a network drive). Everyone on the project reads it, managers included, to see how the work is moving. Each person's agent writes only that person's rows, to `<own folder>/logbook-entries.md`; `logbook.md` is rebuilt from everyone's entries and kept in time order. A person can log to several projects: each project's folder is one logbook. All times are WIB.

**Talking with the person**
- Use their language from the first question to the report, even when the instructions, script output and rows are in English: the language of their latest message, and when they mix two, the one most of it is in. Only the rows are written in the logbook's language.
- **Draft first, ask once.** A daily run asks nothing before the draft: guess from the evidence (which logbook, which tracker row, which part, which status) and put every guess in one review message (step 4), which the person corrects in one go. Only setting up (step 1) asks beforehand, one question per message.
- Number what you ask, so a short answer ("2 Done, 3 skip") cannot be read two ways. Ask in the positive ("Shall I leave it out?", not "Not logged?").
- Show, don't describe: when a choice changes what the rows look like, show a sample row.

Commands below say `python3`. On Windows use `python`: there `python3` is often a Microsoft Store stub that runs nothing. `S` stands for this skill's folder (`~/.claude/skills/team-logbook` on macOS and Linux, `%USERPROFILE%\.claude\skills\team-logbook` on Windows).

## 1. Check the version and the setup

- Run `python3 -I S/scripts/teamlog.py check-update`. On `UPDATE AVAILABLE`, tell the person before anything else: a newer version exists, and they update it themselves by running `npx skills update -g team-logbook` in a terminal (the `-g` matters: without it, global skills are skipped), then opening a new session. Ask whether to continue with the installed version now or update first; never run the update yourself.
- Run `python3 -I S/scripts/teamlog.py where`.
- If it says "not set up", ask the person, one thing at a time:
  - their name as it should appear in the PIC column;
  - where the project's logbook lives: a folder everyone on the project syncs (SharePoint through OneDrive, Google Drive, Dropbox, a network drive), and its path on this laptop. Rows join teammates' only when everyone points at the same shared folder; a folder only this person sees works, but stays theirs alone. For OneDrive, the path is under `~/Library/CloudStorage/OneDrive-SharedLibraries-<organisation>/` on macOS and `C:\Users\<user>\<organisation>\` on Windows. Find it with them; do not guess;
  - the name of their own folder inside it, usually their initials. List the folders already there, so they see the pattern.
  - If that folder has no `logbook-settings.json` yet, this person is the first of the project to set up, so also ask for the project settings below. They are shared with the whole project: say so, and save them only after they agree.

  Then run `python3 -I S/scripts/teamlog.py setup --pic <Name> --folder <shared folder> --own-folder <own> [--project <name> --language <language> --web-url <url>]`, and `settings` for a tracker.
- A logbook that shows `project settings: none yet` (set up before projects had settings): ask for the project settings, suggesting the web address `where` already shows, and after they agree run `python3 -I S/scripts/teamlog.py settings --logbook "<name where shows>" --name <project> --language <language> --web-url <url>`.
- **Project settings**, asked one at a time:
  - the project's name as its readers know it (`Project Alpha`, not the folder name). Every row's Project column holds it;
  - the language rows are written in (English unless the team prefers another);
  - for a SharePoint folder, its web address, so attachment links open in a browser: open the folder on SharePoint in a browser and copy the address bar. That address is usually a view (`.../Forms/AllItems.aspx?id=...`); the script turns it into the folder's own address and refuses one it cannot use. Other storage: skip it; attachment links are then paths inside the folder;
  - whether the project keeps a tracker of its planned work, such as a Notion database of activities. If it does, ask for its link, read it (see "Reading the tracker" in step 2), and propose how an Item is written: the tracker's own field names for the activity, then `: {part}` for the piece of it a row is about, such as `{Initiative} - {Activity}: {part}`. Save it with `settings --logbook <logbook> --tracker <link> --item-format "<format>"`. Keep `{part}`: an activity runs for weeks, so an Item naming only the activity stays `In progress` for weeks, while each part can be finished.
  - Before saving, show one sample row as the logbook will print it, built from these settings and the person's recent work, with every column title. A format string means little on its own; a row shows it, and is when people notice what they want changed (a column title, say).
- After `settings --name`, the logbook is called by its new name (the script says so); use that with `--logbook`. Its folder's name still works too.
- Done when: `where` shows every logbook's shared folder as `ok`, with project settings.

## 2. Collect the day

- Day: today in WIB unless the person names one.
- Run `python3 -I S/scripts/day.py --date YYYY-MM-DD` and compose only from its output; never read raw transcripts. It groups the day by repo, or by folder for work outside a repo, and under each group's name prints `from:`, the GitHub repo and folders it came from.
- Run `python3 -I S/scripts/teamlog.py route "<group>" "<group>" ...` with every group `day.py` printed, except `(outside any repo)`. Quote each one: folder names can contain spaces.
  - `-> <logbook>, Project '<label>'`: that group's rows go to that logbook, with that Project.
  - `unknown`: the logbook does not know it yet. If it has work worth a row today, place it by your best guess in step 3 and say so in the review; otherwise leave it for a day it does.
  - `ambiguous`: two logbooks claim it. Place it by your best guess, as for `unknown`.
  - `ignored`: no rows from it.
- Run `python3 -I S/scripts/teamlog.py names`. Per logbook it prints the rules its rows follow (language, what the Project column holds, the tracker and its Item format, renamed column titles) and the Projects and Items already used.
- **Reading the tracker**, for a logbook whose rules name one: read its rows with the connected tool. For Notion: fetch the link to find its field names and saved views, then read the rows through a saved view that shows every row, one with no filter in its configuration (view mode, which has no query quota), keeping the fields the Item format names, the status and each row's page URL. Use a SQL query only when there is no such view: on most plans SQL shares one limit across the whole workspace, and every teammate's run would spend it. Only read: never change the tracker. If the tool is missing or the read fails, tell the person (the tracker's app has to be connected in their claude.ai connector settings) and carry on with `names` and their answers.
- Run `python3 -I S/scripts/teamlog.py show --date YYYY-MM-DD --pic <Name>` to see what is already logged that day, so a re-run updates rows instead of adding twins.
- Done when: you know where each group goes (or that it is still unknown), each logbook's rules and the names already in use, the tracker's rows where there is one, and the rows already logged.

## 3. Draft the rows

**One row per thing the person made or changed** that day: a feature, a document, a fix, a design, a decision written down. A day usually has several. Group many prompts and commits about the same thing into one row.

**Not a row:** reviewing, approving or merging someone else's work; merging one's own work (that is the moment its row turns `Done`, not a separate row); meetings and discussions that produced nothing; set-up chores such as installing tools. Sessions under `(outside any repo)` and sessions that were about something else (disk cleanup, a personal question) get no row unless the person says so.

**A repo or folder the logbook does not know yet** (`unknown` or `ambiguous` in step 2), when it has work worth a row: draft its rows in the likeliest logbook (the only one, or the one its work points to) and list it in the review's notes, named by its `from:` line, so the person can say where it really belongs. Nothing is remembered until they have seen it.

**Work that left no trace here.** Much work never touches this laptop's sessions or GitHub: a design in another tool, a document, a workshop that produced an output. The review's last note asks about it. For a person with no activity in `day.py` at all, there is nothing to draft: ask this first, offering the Projects and Items from `names` to pick from, and draft from their answer.

| Column | What goes in |
|---|---|
| Logbook | not a column of the table: the `logbook` key of each row in step 4's JSON. The project's logbook, from `route` or from the person's answer; needed only when they have several |
| Timestamp | `YYYY-MM-DD HH:MM`, WIB: the person's own last activity on that item that day, as printed by `day.py`: a session's end, a commit, or a PR's `your_last_activity`. Never a PR's `last_update_by_anyone`, which can be a teammate's. For work the person describes, the time they give, or the end of their working day |
| Project | when the rules say `Project is always '<name>'`, that name (the script fills it in). Otherwise the label `route` gives; for work the person describes, a Project from `names` or one they name |
| Item | with a tracker: see "Items from a tracker". Without one: the part, the thing made, in three to six words ("AI agent guard", "Answer key template"). Either way, reuse the exact Item name from `names` when the same work continues |
| Description | titled as the rules say (for example `Details`); the JSON key stays `description`. See "Writing the description" |
| Status | one of `Planned`, `In progress`, `In review`, `Done`, `Blocked`, by the evidence rules below |
| Reference | links that open: see "Reference and attachments" |

The same Project and Item on the same day is one row: a second thing done under that Item that day goes into that row's description, not a new row.

### Items from a tracker

- Each piece of work belongs to one tracker row, the activity. The Item is the Item format filled with that row's fields, exactly as the tracker writes them, and `{part}`: the piece of that activity the row is about, in three to six words (`Initiative 1: Customer Portal - Build back-end: Login API`). Every teammate's rows for that activity then start the same way.
- A part is the size of one thing finished: a feature, an engine, a screen, a document, often one PR or a few. When the same part continues, reuse its exact name from `names`; a new part gets a new name.
- Pick the activity from the evidence: PR titles, branch names, prompts, what the person says. When two could fit, take the likelier and say so in the review's notes. Work that serves several activities at once (a decision that spans initiatives) goes under the one it moves most, also noted. Never split one piece of work into several rows to cover them all.
- Work that fits no activity: the Item is `Not in tracker: <part>`, so readers see work outside the plan. The review's notes suggest adding it to the tracker.
- Status follows the evidence for the part, like any row: its PR merged is `Done`. Whether the whole activity is finished is the tracker's to say, not the logbook's; the tracker's own status is never copied into a row.
- A format without `{part}` (set before version 0.7.0) makes the Item the whole activity. Write such rows as before, and suggest in the review adding `: {part}` with `settings --item-format`.

**Status by evidence** (adapted from `standup-digest` by Les Orchard, MIT; see `SOURCE.md`):

| Evidence | Status |
|---|---|
| The person's own PR merged that day (`merged today`), or their commit on `main` | Done |
| The person's own PR open at the end of that day (`state=open`, including `open (that day; merged later, ...)`) | In review; when it shows `approved by`, say in the description that it is approved and waits to be merged |
| Commits on a branch with no PR, or uncommitted files | In progress |
| Only discussed in prompts and notes | Planned |
| Waiting on someone else, said so in the session | Blocked, naming who it waits on |
| Work the person describes | what they say; `Done` only when they say it is finished |

A prompt is what was asked and an assistant note is what the agent said; neither proves anything happened. `Done` needs a merged PR or a commit behind it, or the person's own word for work done elsewhere.

`day.py` prints each PR's state as it stood at the end of that day, so a day logged the next morning reads the same as one logged that evening. Several pieces of evidence under one row (two PRs merged, two still open) take the least finished status, and the description says which parts are done.

A PR opened on an earlier day is a row today only when the person did something on it today: `your_last_activity` shows a time, or the day's commits or sessions touched it. Changes by someone else (`your_last_activity=none today`) are not the person's work, even on their own PR.

### Writing the description

Rows are written in the logbook's language, which `names` prints (English unless the project chose another); talk to the person in their own. Write the description the way the person would type a quick update to a teammate: one to three short sentences in plain, everyday words, saying what is now different. Start with the action ("Built", "Fixed", "Added", "Drafted"), name the concrete result, give the scope when it helps a reader (which screens, which documents, which part), and add what is left only if something is.

| Instead of | Write |
|---|---|
| An automatic safeguard that prevents client documents and secret keys from being uploaded, as well as preventing direct changes to the main version without review. | Built a guard so the AI assistant can't upload client documents or passwords to GitHub. Tested on Windows too. |
| A working routine for multiple AI sessions at once: marking work as taken, handing work over to the next session, and finishing work until it is ready for review. | Set up ground rules so several AI sessions can run side by side without stepping on each other. |

Leave out: file and branch names, tool names, decision numbers, lists after a colon, stacked clauses ("as well as", "including", "which"), filler words ("ensure", "leverage", "comprehensive", "robust", "seamless"), and anything from a client document, secrets, personal data or costs.

### Reference and attachments

- GitHub work: a Markdown link per PR or commit, full URL, such as `[PR #6](https://github.com/<owner>/<repo>/pull/6)`. Several links are separated by ` · `.
- Work from a tracker row: also a link to that row, such as `[Tracker](<the row's page URL>)`.
- A file the person wants attached (a screenshot, a short document): run `python3 -I S/scripts/teamlog.py attach <file> --logbook <logbook>`. It copies the file into `<own folder>/logbook-attachments/<day>/`, which syncs with the logbook, and prints the link to put in the Reference column.
- A file that already lives in shared storage (a client document on SharePoint, a tender pack): link its web address instead of attaching a copy, so the file stays in its one place.
- Empty when there is nothing to point at.

## 4. Review once, then write

Everyone on the project reads the logbook, so nothing is written before the person has seen it. They see it once, in one message:

- **The draft**, a table per logbook with the rows numbered.
- **Numbered notes**, only for what you guessed or left out, one line each:
  - a new repo or folder and where you put it, named by its `from:` line ("`web-mockup` (`<owner>/web-mockup`, `~/developer/...`) is new: I put it under `<logbook>`, and it will be remembered for the whole project");
  - an activity you chose between two, or for work that spans several;
  - rows marked `Not in tracker`, suggesting the activity be added to the tracker;
  - what you left out and why, in a few words;
  - last: "Anything else today that isn't here, such as work outside this laptop or a file to attach?"
- **One way to answer**: "ok" writes it all; otherwise corrections by number ("2 Done; note 1: it's Beta's; note 3: leave it out for good").

Then:

- Apply the corrections. Show the table again only when the corrections changed which rows there are; otherwise write.
- Remember what the notes settled, now that the person has seen it:
  - a new repo or folder kept where you put it, or moved: `teamlog.py map "<group>" --logbook <logbook>` (for a logbook whose Project column holds labels, see `names`, add `--label "<what readers call it>"`);
  - one the person says belongs to a project not set up on this laptop: offer `setup` for it (step 1), or leave it unknown and skip its rows today;
  - one to leave out for good (personal work, tools, another employer): `teamlog.py ignore "<group>"`.
- Save the agreed rows to a temporary JSON file, a list of objects with keys `logbook`, `timestamp`, `project`, `item`, `description`, `status`, `reference`. Never include a PIC: the script fills in the person's own.
- Correcting a row already logged, the person's own only, goes through the same file, never by editing an entries file:
  - a new Item name for it (a typo, a format that changed): the corrected row with `"was": "<its Item before>"`, on the same day. It replaces that row instead of adding a twin;
  - a row logged by mistake: `{"logbook", "timestamp": "<its day>", "item": "<its Item>", "delete": true}`.

  The script finds the row by day and Item, and writes nothing if one is not there.
- Run `python3 -I S/scripts/teamlog.py add --rows <file.json>`. Per logbook, it adds new rows, replaces a same-day row for the same item, and rebuilds `logbook.md` in time order with everyone's rows, which is how a row logged late slots in at the right place.
- A `warning:` line about a conflict copy means the sync app (OneDrive, Google Drive) saved two versions of an entries file (for example `logbook-entries-<laptop>.md`). The rows are already merged; tell the person the copy can be deleted.
- Lines starting `personal logbooks:` come from the `personal-logbook` skill, which `add` runs by itself when this laptop has it set up: each person's read-only table, combining their rows from every project. Pass its warnings on as that skill says.
- Done when: the script prints the counts for each logbook and `logbook.md` has the rows.

## 5. Report

In the person's language: how many rows were added or updated in each logbook, the path of each `logbook.md`, and that the sync app uploads it by itself. When `add` printed `personal logbooks:` lines, add one line saying which personal tables were updated. Mention any rows you left out and why.

## Changing the settings

When the person asks to change the logbook's settings, add a project, or stop logging something:

- Another project: `setup` again with that project's shared folder, as in step 1.
- The project's settings: `python3 -I S/scripts/teamlog.py settings --logbook <logbook>` with any of:
  - `--name`, `--language`, `--web-url`;
  - `--tracker <link> --item-format "<format>"` for the tracker Items come from, such as `"{Initiative} - {Activity}: {part}"` (`--tracker ""` removes it);
  - `--column "Description=Details"` to retitle a column (`--column "Description="` restores it);
  - `--project-column label` to make the Project column the repo or folder's label instead of the project's name (`name`, the default).

  The whole project shares these; confirm before saving.
- Where a repo or folder goes: `map "<group>" --logbook <logbook> --label "<label>"`, or `unmap "<group>" --logbook <logbook>`.
- Never log a repo or folder (theirs only): `ignore "<group>"`; `ignore "<group>" --remove` to log it again.
- Show `where` afterwards.

## Rules the scripts hold

- An agent writes only its own person's files: `<own folder>/logbook-entries.md` and `<own folder>/logbook-sources.json`. Another person's rows are never edited. `logbook-settings.json` is written only at project setup or through `settings`, after the person agrees.
- `logbook.md` is generated. Editing it by hand is lost at the next rebuild; corrections go through this skill. Never edit an entries file by hand either, not even the person's own: renames and deletions go through `add` (step 4).
- Continuing work gets a new row on each new day, with the same Item name, so the logbook shows each day's state. A part is small enough to finish, so its last row says `Done`.
