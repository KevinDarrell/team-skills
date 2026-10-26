# Source

`scripts/standup_digest.py` is vendored from [lmorchard/lmorchard-agent-skills `standup-digest`](https://github.com/lmorchard/lmorchard-agent-skills/tree/210f7beebf5c59d6c10fa6b1c49146f238872181/standup-digest) at commit `210f7beebf5c`.
Licence: MIT, Copyright (c) 2025 Les Orchard. Full text: `LICENSE-standup-digest.txt`.

It reads session transcripts under `~/.claude/projects` and `~/.codex/sessions`, and runs only read-only commands: `git log`, `git status`, `git rev-parse`, `git remote get-url`, `git config user.email`, and `gh pr view` / `gh issue view` to check each referenced PR's real state.

**Change from upstream:** one line in `record_timestamp()`. Claude Code writes UTC timestamps ending in `Z`, which `datetime.fromisoformat` accepts only from Python 3.11; on macOS's Python 3.9 every record was dropped and the digest came back empty. The patch turns a trailing `Z` into `+00:00`.

**Ours:** `SKILL.md`, `scripts/note.py` (the notes and their settings), and `scripts/day.py` (builds a WIB day window, adds GitHub activity, groups by repo, or by folder outside a repo, and with `--detail` re-reads each session for the daily note).

**Shared with team-logbook:** `scripts/day.py` and `scripts/standup_digest.py` are the same files as in `skills/team-logbook/scripts/`, byte for byte, because each skill installs on its own. Change both copies in the same pull request; `tests/test_day.py` fails when they differ.

**Updating the extractor:** download `standup-digest/scripts/standup_digest.py` at a newer commit into an empty folder, read it, re-apply the patch if upstream has not fixed it, run `day.py` on a recent day, then replace the file here and in `skills/team-logbook/scripts/` by pull request.
