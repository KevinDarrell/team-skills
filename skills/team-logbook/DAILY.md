# Daily note

Each person keeps one note per day of everything they worked on, across every project: one Markdown file per day, `YYYY-MM-DD.md`, in a folder of their own that syncs to the team's storage (usually a SharePoint folder through OneDrive). The whole team can read it, so nothing is written before the person has seen the draft. It runs alongside the project logbook in `SKILL.md` and changes nothing there. All times are WIB.

Talk with the person as `SKILL.md` says: in their language, draft first and ask once, number what you ask. Commands say `python3` (on Windows, `python`); `S` stands for this skill's folder.

## 1. Check the version and the setup

- Run `python3 -I S/scripts/teamlog.py check-update` and handle `UPDATE AVAILABLE` as `SKILL.md` step 1 says.
- Run `python3 -I S/scripts/note.py where`.
- If it says "not set up", ask the person, one thing at a time:
  - their name as the note's title shows it. Skip this when they already keep a logbook: `teamlog.py where` prints it after `pic:`;
  - their note folder: a folder of their own inside the team's synced storage, one person one folder, and its path on this laptop. Find it with them; do not guess. OneDrive paths are as in `SKILL.md` step 1;
  - the language notes are written in. Suggest the one they talk to you in;
  - which sources to read besides this laptop's sessions and GitHub. List the connectors this session has that hold a day's work, and say which are connected: calendars (Google Calendar, Microsoft 365 for Outlook, Notion Calendar), meeting notes (Fireflies, Notion), or another they name. A connector that is not connected yet is connected by the person at claude.ai, Settings, Connectors, followed by a new session; Microsoft 365 can need their IT admin's approval first. Never connect one yourself.

  Then run `python3 -I S/scripts/note.py setup --folder <folder> --language <language> [--pic <Name>] --sources "<Source A>, <Source B>"`.
- Done when: `note.py where` shows the note folder as `ok`.

## 2. Collect the day

- Day: today in WIB unless the person names one. A day runs midnight to midnight, so work after midnight belongs to the next day's note.
- Run `python3 -I S/scripts/note.py list` first, every time:
  - a note `written HH:MM that day` was saved before its day was over. Run `day.py` for that day; if anything happened after that time (a session, a commit, a PR), bring that day's note up to date before today's, and say so in the review;
  - a weekday with `no note`: offer to write it, one note per day, oldest first. Claude Code deletes sessions after about 30 days, so an older day can only be written from what the person tells you.
- Run `python3 -I S/scripts/day.py --date YYYY-MM-DD --detail` and compose only from its output; never read raw transcripts. On a busy day, run it once per group with `--repo <group>`.
- Leave out the groups `note.py where` lists under `left out`. The logbook's own ignore list does not apply here: a repo kept out of every project's logbook can still be a day's work.
- Project names: when the person keeps a logbook, run `python3 -I S/scripts/teamlog.py route "<group>" ...`; a group routed to a logbook goes under that Project label. Any other group goes under its own name.
- Read each source `note.py where` lists, for that day (00:00 to 24:00 WIB), with its connector, only reading: from a calendar, the events the person attended (title, time, number of attendees), not the ones they declined; from meeting notes, the summary and the person's action items. A source that is missing or fails is named in the review; carry on without it.
- Run `python3 -I S/scripts/note.py show --date YYYY-MM-DD`. A note already there is the starting point: keep what the person added to it, and bring the rest up to date.
- Done when: you have the day's sessions in detail, its commits and PRs, each source's items or why it has none, and the earlier note if there is one.

## 3. Draft the note

**One heading per piece of work.** A feature, a fix, a document, research, a plan, a review of someone's work, an investigation, a meeting. Unlike the logbook, research, planning, reviews and discussions count here. Sessions, commits and PRs about one thing go under one heading; a long session that did several things is split.

**Not work:**
- sessions `day.py` names as Codex's automatic approval reviewer;
- a PR a session only mentions, unless a `github PR` line shows the person's own activity on it that day. A session's `pr ... state=MERGED` can be a PR merged days ago;
- a message that recaps an earlier day's work, as when a session is resumed days later ("what did we do here?");
- chores with nothing to show (installing tools), and sessions about something personal. Leave these out and say so in the review.

**Status**, after the heading's `·`, in the note's language: `Done`, `In progress`, `In review`, `Planned`, `Blocked`, by `SKILL.md`'s "Status by evidence". Research, a plan or a decision that reached its conclusion is `Done`; a discussion with no conclusion yet is `Discussed`; work with a problem still open can say so (`1 finding open`).

**The bullets** tell a teammate who was not there what was done:
- each result, step or part, with its PR number; nest the parts of a big step under it;
- the numbers that show scale or outcome: tests passing, links checked, items done;
- what was found (a bug, a problem, the answer to a research question), and what got in the way and how it was solved;
- each decision as its own bullet, `**Decision:** ...`; what is left as `**Next:** ...`.

Three to ten bullets for a large piece of work, one to three for a small one. One fact per bullet, in plain everyday words. A prompt is what was asked and an assistant note is what the agent said: neither proves anything happened, so `merged`, `done` and `fixed` need a commit, a merged PR or the person's word behind them.

Leave out: secrets, passwords and API keys, and where they are kept; personal data; costs and prices; wording copied from client documents (say what was checked and what it concluded); file paths and branch names, unless a reader needs one; filler ("ensure", "leverage", "comprehensive", "robust", "seamless").

**The shape**, with headings in the note's language (see the table below):

```markdown
# <Name> — <Weekday>, <D Month YYYY>

**Summary:** <two to four sentences: the day's main results, by project>

Active <first>–<last> WIB · <N> projects · <N> pieces of work · <N> meetings
Sources: Claude sessions (<N>) · GitHub (<N> PRs) · <each other source read>

---

## <Project>

### <Piece of work> · <Status>
<HH:MM>–<HH:MM> · <Kind> · PR #<n>, #<m>
- <bullets>

---

## Meetings and work outside this laptop

### <Meeting> · <HH:MM>–<HH:MM>
Meeting · <N> attendees · Source: <the calendar>
- <what came out of it>

---

## Next up
- <every **Next:** above, in one list>
```

- Projects with the most work come first; inside one, pieces of work in the order they started.
- Kind is one of Coding, Research, Planning, Review, Testing, Documents, Discussion, Admin, Meeting.
- Leave out a part with nothing in it: no meetings, no `Meetings and work outside this laptop` section.

A piece of work, filled in:

```markdown
### Login rate limit · Done
09:10–11:45 · Coding · PR #41, #42
- Added a limit of 5 failed logins per account per 10 minutes (#41)
  - The sixth attempt waits, and the person gets an email saying why
  - Admin accounts get the same limit, without the email
- Fixed a bug the new tests found: a correct password did not reset the count (#42)
- 212 tests pass, 9 of them new
- **Decision:** the limit counts per account, not per IP address, because the office shares one address
- **Next:** show the waiting time on the login page
```

| English | Indonesian |
|---|---|
| Summary | Ringkasan |
| Active · projects · pieces of work · meetings | Aktif · project · kerjaan · rapat |
| Sources | Sumber |
| Done, In progress, In review, Planned, Blocked, Discussed | Selesai, Sedang dikerjakan, In review, Direncanakan, Terhambat, Dibahas |
| Coding, Research, Planning, Review, Testing, Documents, Discussion, Admin, Meeting | Coding, Riset, Perencanaan, Review, Testing, Dokumen, Diskusi, Admin, Rapat |
| Decision / Next | Keputusan / Lanjut |
| Meetings and work outside this laptop | Rapat dan kegiatan di luar laptop |
| Next up | Lanjut berikutnya |

Another language: translate these the same way.

## 4. Review once, then write

- Show the whole draft in one message. Under it, numbered notes only for what you guessed or left out, one line each:
  - a piece of work whose project or status you guessed;
  - what you left out and why (a personal session, a reviewer session, a PR from an earlier day);
  - a source that could not be read;
  - a meeting with no notes: "What came out of <meeting>?";
  - last: "Anything else today that isn't here, such as work outside this laptop?"
- One way to answer: "ok" writes it; otherwise corrections by number.
- Apply the corrections. Show the draft again only when the corrections changed which pieces of work there are.
- A group the person wants kept out of their notes for good: `python3 -I S/scripts/note.py ignore "<group>"`.
- Save the agreed note to a temporary file and run `python3 -I S/scripts/note.py write --file <file> --date YYYY-MM-DD`. It replaces that day's note.
- Done when: the script prints the note's path.

## 5. Report

In the person's language: the note's path, and that the sync app uploads it by itself. Mention anything left out. For several days, one line per day.

## Changing the settings

- Folder, language or sources: `note.py setup` again with the new values; sources not passed stay as they were.
- Keep a group out, or let it back in: `note.py ignore "<group>"`, `note.py ignore "<group>" --remove`.
- Show `note.py where` afterwards.

## Reading notes back

Asked for a summary or a filter ("what did I do on Alpha this week", "what is blocked"): `note.py list` shows which days have a note; read those files from the note folder and answer from them. A teammate's notes are in their own folder next to it. Never edit another person's note.

## Rules the scripts hold

- Only the person's own note folder and their own settings are written.
- One file per day; writing replaces it. The storage's version history (OneDrive keeps one) holds the earlier versions.
