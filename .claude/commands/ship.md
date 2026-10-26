---
description: Finish a change in the team-skills repo — run the tests, raise the changed skill's VERSION, commit, push the branch and open a pull request. Use when a change here looks done and the person asks to commit, push, open a PR or ship it.
---

# Ship a change

An agent never merges: merging is the person's call (`gh pr merge` always asks). Shipping ends at an open pull request.

Commands say `python3`. On Windows use `python`: there `python3` is often a Microsoft Store stub that runs nothing.

## 1. Branch

- `git fetch origin`, then `git status -sb`.
- On `main`, or on a branch whose PR is already merged: `git switch -c <short-name> origin/main`. Uncommitted changes come along.
- Behind `origin/main` (`git merge-base --is-ancestor origin/main HEAD` fails): `git merge origin/main`. Never rebase a pushed branch.
- Done when: you are on your own branch and it contains `origin/main`.

## 2. Verify

- `python3 -I -m unittest discover -s tests -v`; on macOS also `/usr/bin/python3 -I -m unittest discover -s tests` (Python 3.9, what people actually run).
- Read `git diff origin/main` in full, plus untracked files from `git status`. It holds only this change.
- A change to how a script behaves is tried for real: `day.py` on a recent day, `teamlog.py` only against a temp folder with `TEAM_LOGBOOK_CONFIG` (`CLAUDE.md` rule 5). A `SKILL.md` change is tried with `/try`.
- Done when: both test runs pass and the diff is only this change.

## 3. Raise VERSION

- For each skill with a change under `skills/<name>/`, read `git show origin/main:skills/<name>/VERSION` and write a higher one to `skills/<name>/VERSION`. Raise the minor number (0.5.0 → 0.6.0), as every release so far has.
- No bump when only tests, CI, README, `CLAUDE.md` or `.claude/` changed.
- Done when: every changed skill's `VERSION` is above the one on `origin/main`.

## 4. Commit and push

- Stage files by name, not `git add -A`.
- Title: `team-logbook 0.6.0: <what changed, in a few words>`; for a change outside any skill, `ci: …` or a short plain title. Body: why, in a sentence or two (`team-logbook 0.5.0: simpler file headers` is the model).
- `git push -u origin <branch>`.
- Done when: the push succeeds. If the hook blocks it, fix what it names; do not get round it.

## 5. Open the pull request

- `gh pr create --title "<commit title>" --body-file <file>`, body in this shape:
  - `## What changed`: what is different for the person using the skill, in plain words, with the new `VERSION`.
  - `## How to check`: the commands run and their result (`… → 24 OK; CI runs Linux, Windows and 3.9`).
  - For a change outside any skill, say that `VERSION` stays.
- Done when: `gh pr view` shows the PR and `gh pr checks` is running or green.

## 6. Report

In the person's language: the PR link, what was checked and how, and that after merging, each laptop runs `npx skills update -g <skill>` for each changed skill and opens a new session to get the change.
