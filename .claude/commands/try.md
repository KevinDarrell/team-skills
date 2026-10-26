---
description: Run this repo's working copy of team-logbook (or, with "note", a-day-in-my-life) end to end against sandbox folders, never the live logbook or anyone's notes, to see a SKILL.md or script change working before shipping it. Arguments, all optional - a day (YYYY-MM-DD), "fresh" to start the sandbox over, "old" to start from a 0.5.0 config, "note" to try a-day-in-my-life instead of the logbook.
argument-hint: "[YYYY-MM-DD] [fresh] [old] [note]"
---

# Try a skill from the working copy

Arguments: $ARGUMENTS

The installed `/team-logbook` runs the copy under `~/.claude/skills`, not this repo. This runs the repo's `skills/team-logbook/SKILL.md` and scripts instead, writing only to `.claude/sandbox/` (git-ignored). Run every command from the repo root. Commands say `python3`; on Windows use `python`.

## 1. Sandbox

- With `fresh` in the arguments, delete `.claude/sandbox/` first.
- Read the person's name and own folder from their real settings, which only reads them: `python3 -I skills/team-logbook/scripts/teamlog.py where`. Not set up → use `Ana` and `AN`.
- Make two project folders if missing: `mkdir -p .claude/sandbox/alpha/BD .claude/sandbox/beta`. `BD` stands for a teammate already on project Alpha.
- With `note` in the arguments, also make a note folder: `mkdir -p .claude/sandbox/notes/<own>`, and leave `.claude/sandbox/day-config.json` missing (delete it with `fresh`), so a-day-in-my-life's setup interview runs. When it asks, give it that folder; for sources, name only connectors this session really has.
- With `old` in the arguments and no `.claude/sandbox/config.json` yet, write a config in the 0.5.0 shape to it, as a real one looks: `{"pic": "<name>", "folder": "<absolute path of .claude/sandbox/alpha>", "own": "<own>", "web_url": "https://example.sharepoint.com/sites/Sandbox/Shared%20Documents/Alpha"}`. That tries the upgrade path: one logbook with a web address, no project settings yet.
- Otherwise leave the config missing, so the skill's step 1 runs its setup interview. The answers to give it: shared folder `.claude/sandbox/alpha`, project `Alpha`, SharePoint address `https://example.sharepoint.com/sites/Sandbox/Alpha`. For a second project, the person says "add project Beta" and gives `.claude/sandbox/beta`.
- To try Items from a tracker, give Alpha the project's real tracker when the skill asks (or later with `settings --logbook Alpha --tracker <link> --item-format "<format>"`). The skill only reads the tracker, so that is safe.
- To see a teammate's answer reach the person, give the teammate a config of its own, `.claude/sandbox/teammate.json`: `setup --pic Budi --folder .claude/sandbox/alpha --own-folder BD`, then `map` one of the day's groups to Alpha with a label.
- Done when: the sandbox folders exist, and the config is either missing or in the 0.5.0 shape.

## 2. Run the working copy's skill

Read `skills/team-logbook/SKILL.md` as it is now in this repo (with `note` in the arguments, `skills/a-day-in-my-life/SKILL.md`) and follow it from step 1 to step 5, for the day in the arguments (else today in WIB), with two changes:

- `S` is `skills/team-logbook` (with `note`, `skills/a-day-in-my-life`), this repo's copy.
- Every `teamlog.py` command starts with `TEAM_LOGBOOK_CONFIG=.claude/sandbox/config.json` (or `teammate.json` when acting as the teammate), and every `note.py` command with `A_DAY_IN_MY_LIFE_CONFIG=.claude/sandbox/day-config.json`, written out in full each time. Shell variables do not survive between Bash calls, and without it the command writes to the person's live logbook (the hook blocks that).

`day.py` reads the person's real sessions; it only reads, so that is fine. Ask the questions the skill asks and wait for the person's answers and go-ahead: that conversation is part of what is being tried.

## 3. Report

- Show each sandbox `logbook.md`, the person's `logbook-entries.md` and `logbook-sources.json`, and `.claude/sandbox/alpha/logbook-settings.json`. With `note`, show the note written under `.claude/sandbox/notes/<own>/` instead.
- List every place where `SKILL.md` was unclear, where you had to guess, or where a script's output did not match what the skill says. That list is what the change under test is judged on.
- Done when: the person has seen the sandbox files and the list.
