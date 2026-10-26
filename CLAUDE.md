# team-skills

Claude Code skills for teams, installed on each laptop with `npx skills add` (install, setup and use: `README.md`). Public: keep client names, people's names, internal addresses and real tracker links out of every file, examples and tests included. Three skills: `skills/team-logbook/` (a shared logbook table per project), `skills/personal-logbook/` (a read-only table per person, built from the project logbooks) and `skills/a-day-in-my-life/` (each person's detailed note per day, across projects).

## How team-logbook fits together

| File | Role |
|---|---|
| `SKILL.md` | What the agent does when someone says "update team logbook". Changing its wording changes behaviour on every laptop |
| `scripts/day.py` | Prints one person's day (sessions, commits, PRs) grouped by repo, or by folder for sessions outside a GitHub repo, every time in WIB. Read-only. `--detail` (for a-day-in-my-life) re-reads each transcript for the day's every prompt and agent message within a budget, plus files changed, skills, web research, subagents and test runs; without it the output is what the logbook reads |
| `scripts/standup_digest.py` | Vendored from upstream with a one-line patch; `day.py` builds on it. Change it only by the procedure in `SOURCE.md` |
| `scripts/teamlog.py` | One logbook per project, in the project's synced folder. Each person's agent writes only its own `<own folder>/logbook-entries.md` and `<own folder>/logbook-sources.json` (which repos and folders it routes there), then rebuilds `logbook.md` from everyone's entries. `logbook-settings.json` (project name, language, SharePoint address, whether the Project column holds the project's name or a repo label, column titles, the tracker and its Item format) is written only at project setup or by `settings`. Reading a tracker is the agent's job through a connector (Notion), not a script's. A person's config lists all their logbooks; a 0.5.0 config (one folder) still reads as one |
| `VERSION` | `teamlog.py check-update` compares it with the copy on `main` to tell people a newer version exists |

## How personal-logbook fits together

| File | Role |
|---|---|
| `SKILL.md` | What the agent does when someone says "update the personal logbooks" or asks what a person did across projects |
| `scripts/worklog.py` | Reads every project logbook listed in `<work log>/worklog-settings.json` (paths relative to the work log's parent, since OneDrive syncs libraries side by side) and rewrites `<person folder>/logbook.md` per person, matching PIC spellings to folders. Never writes to a project logbook. A project not found on a laptop keeps its rows from the current table. `build` also adds the project logbooks the laptop's team-logbook config lists. Its pointer is `~/.config/personal-logbook/config.json` (`PERSONAL_LOGBOOK_CONFIG`) |
| `teamlog.py` `build_personal()` | After `add` and `rebuild`, runs `worklog.py build` from the sibling skill folder when the personal config exists; its output is prefixed `personal logbooks:` and it never fails the team write |

## How a-day-in-my-life fits together

| File | Role |
|---|---|
| `SKILL.md` | What the agent does for "a day in my life" or "update my daily note": one note per person per day of everything they did, drafted from `day.py --detail` and the person's chosen connectors (calendar, meeting notes), reviewed, then written. Changing its wording changes behaviour on every laptop |
| `scripts/day.py`, `scripts/standup_digest.py` | The same files as team-logbook's, byte for byte, since each skill installs on its own. Change both copies in one PR; `tests/test_day.py` fails when they differ |
| `scripts/note.py` | `<note folder>/<folder name>-YYYY-MM-DD.md`, one folder per person named after them (`KD/KD-2026-10-23.md`), written only by `write` after the person agrees; remembers when each note was written, so `list` flags a note saved before its day was over. Its own settings (name, folder, language, connectors, ignore list) in `~/.config/a-day-in-my-life/config.json`; its own `check-update` |
| `VERSION` | Compared with the copy on `main` by `note.py check-update` |

## Rules

1. **Every change goes through a pull request.** GitHub cannot protect `main` on this plan, so the hook blocks committing on `main` and pushing to it. Local `main` is often stale: branch from `origin/main` after `git fetch`.
2. **A change under `skills/<name>/` raises that skill's `VERSION` in the same PR.** Every release so far raised the minor number (0.4.0 → 0.5.0). Tests, CI, README and `.claude/` changes need no bump. Commit and PR titles: `team-logbook 0.6.0: <what changed>`, or `ci: …` for changes outside a skill.
3. **Python 3.9+, stdlib only.** macOS's `/usr/bin/python3` is 3.9, and that is what people run. Keep `from __future__ import annotations`; no `match`, no `X | Y` outside annotations. Two bugs here only showed up on 3.9: `Path.write_text(newline=...)` (3.10+) and `datetime.fromisoformat` on a trailing `Z` (3.11+).
4. **macOS, Linux and Windows.** Commands in `SKILL.md` say `python3`, with the note that Windows uses `python`. Write text through `open(path, "w", encoding="utf-8", newline="\n")`, as `write_atomic` does (`Path.write_text` takes no `newline` on 3.9); build paths with `pathlib`. OneDrive can hold a file lock on Windows, which `write_atomic` retries.
5. **Never touch the live logbook or anyone's notes while developing.** The saved configs point at the team's real table and the person's real note folder on SharePoint. Run the repo's `teamlog.py` only with `TEAM_LOGBOOK_CONFIG=<temp folder>/config.json` on the same command line, after a `setup` against a temp shared folder; the hook blocks `add`, `rebuild`, `setup`, `attach`, `settings`, `map`, `unmap` and `ignore` without it. Likewise the repo's `note.py` `setup`, `write` and `ignore` need `A_DAY_IN_MY_LIFE_CONFIG=<temp folder>/config.json`. `where`, `route`, `names`, `show`, `note.py list` and `day.py` only read. On a laptop with personal logbooks set up, `add` and `rebuild` also build them: put `PERSONAL_LOGBOOK_CONFIG=<temp folder>/personal.json` on the same command line, or the live work log gets rebuilt and the temp project registered in it. The tests set both, and the hook blocks `add` and `rebuild` without it on such a laptop, as it blocks the repo's `worklog.py` `setup`, `person`, `project` and `build` without `PERSONAL_LOGBOOK_CONFIG`.
6. **The installed copy is separate.** `/team-logbook` runs `~/.claude/skills/team-logbook`, a link to `~/.agents/skills/team-logbook`, which changes only through `npx skills update -g team-logbook` after a merge (without `-g`, the update skips global skills); the same goes for `personal-logbook` and `a-day-in-my-life`. Editing this repo does not change it, and the installed copy is never edited by hand.
7. **Two versions share one folder.** People update at different times, so a new version keeps `logbook.md` and `logbook-entries.md` byte-identical in format, adds no column, reads rows by position (so a retitled column reads the same; an older version rebuilding `logbook.md` just puts the default titles back), and puts new files where an older `*/logbook-entries*.md` glob cannot see them. Check a format change by running the previous `teamlog.py` (`git show main:skills/team-logbook/scripts/teamlog.py`) and the new one on the same scratch folder.
8. **`SKILL.md` style.** Numbered steps of short imperative bullets, each ending in `Done when:`. Plain English, no filler. Rows in the logbook are English, notes are in the language each person chose; the agent talks to the person in their own language.

## Commands

- Tests: `python3 -I -m unittest discover -s tests -v` (`python` on Windows). On macOS also run them with `/usr/bin/python3` (3.9). CI runs Linux, Windows and Python 3.9.
- One day's raw material: `python3 -I skills/team-logbook/scripts/day.py --date YYYY-MM-DD`. `--no-verify` skips git and gh, so sessions can't be matched to a repo and all land under `(outside any repo)`.
- The table, against a temp folder:
  ```
  d=$(mktemp -d); mkdir -p "$d/shared"
  TEAM_LOGBOOK_CONFIG=$d/config.json python3 -I skills/team-logbook/scripts/teamlog.py setup --pic Ana --folder "$d/shared" --own-folder AN
  TEAM_LOGBOOK_CONFIG=$d/config.json python3 -I skills/team-logbook/scripts/teamlog.py add --rows rows.json
  ```
  Shell variables do not survive between Bash calls, so write the temp path out in each command.
- Trying the working copy's whole skill: `/try [YYYY-MM-DD] [fresh] [note]` follows the repo's team-logbook `SKILL.md` (with `note`, a-day-in-my-life's) against `.claude/sandbox/` (git-ignored). Use it for every `SKILL.md` change: its wording is the product, and no unit test reads it.
- Finishing a change: `/ship` (`.claude/commands/ship.md`: tests, `VERSION`, commit, push, PR). It is a command, not a skill, so `npx skills add` never offers it. An agent never merges.

## Harness

`.claude/settings.json` allows routine git, gh and test commands, asks before `gh pr merge`, and runs `.claude/hooks/gate.py` before every Bash command. The gate blocks committing on `main` or pushing to it, `git commit` or `gh pr create` with failing tests, `git push` or `gh pr create` with a changed skill whose committed `VERSION` is not above `origin/main`'s, and the repo's `teamlog.py` writing without `TEAM_LOGBOOK_CONFIG` `note.py` writing without `A_DAY_IN_MY_LIFE_CONFIG`, or `worklog.py` writing (and, where personal logbooks are set up, `teamlog.py add` and `rebuild`) without `PERSONAL_LOGBOOK_CONFIG`. It reads command text, so it is a net against slips, not a sandbox. When it blocks something that is genuinely needed, ask the person to run it in their own terminal. Its tests are `tests/test_gate.py`.

## Tests

`tests/test_teamlog.py` drives `teamlog.py` as two people sharing one temp folder; `tests/test_note.py` drives `note.py` against a temp note folder. `tests/test_day.py` runs `day.py` on synthetic transcripts with the home folder pointed at a temp dir and a fake verifier in place of git and gh, so no real `~/.claude/projects` is read. Write fixtures by hand; never copy a real transcript into this repo, since they hold client and session content. Session times in fixtures are UTC with a trailing `Z`, as Claude Code writes them; put them either side of WIB midnight (17:00Z) when the day boundary matters.
