# daily-workflow

Personal Claude Code plugin with three parts that share one local Worklog:

- **Work Logger**: hooks write a Technical Checkpoint after every response and after git, PR, test and Jira events,
  without any LLM. A detached headless Haiku call turns them into Worklog Entries every 15 minutes of work and before
  compaction. `/daily-workflow:worklog` forces it now.
- **Daily Briefing**: `/daily-workflow:briefing` plans the day before the daily, `update` corrects it from the daily
  transcript and schedules the Deep Work block, `home` plans home tasks.
- **Inbox**: `/daily-workflow:inbox` captures unanswered Slack messages, saved Slack items, PRs waiting for review,
  own PRs that need action and important email into the Notion GTD Inbox, then renders the whole Inbox as an HTML
  page that shows one entry at a time with the AI proposal already chosen. PRs under 10 changed files waiting for review get no card:
  a recurring code review card in Notion covers them.

## Setup

### Connectors

- Notion: install [makenotion/claude-code-notion-plugin](https://github.com/makenotion/claude-code-notion-plugin).
- Sign in to the claude.ai connectors used by the briefing: Google Calendar, Gmail, Slack, Atlassian.
- `gh` needs the token described in the `ai` README (`repo`, `read:org`).

### Config

The first hook creates `~/.ai/worklog` as a local git repo with `config.toml` from
[config.example.toml](config.example.toml). Fill in `[worklog].jira_project_keys`,
`[github].team_repos`, `[slack].channels`, the `[notion]` IDs of your GTD database and views, `[jira].base_url`,
and check `[workday]`.

## Usage

| Command | What it does |
|---|---|
| `/daily-workflow:worklog` | checkpoint and summary of this session now, prints the new entries |
| `/daily-workflow:worklog today`, `… jira PROJ-1234` | read the Worklog |
| `/daily-workflow:briefing` | morning plan: catch-up of unsummarized sessions, sources, plan, `open …` command for the host |
| `/daily-workflow:briefing update` | after the daily: reads `~/.ai/worklog/meetings/<date>*.txt`, corrects the plan, creates the Deep Work block |
| `/daily-workflow:briefing home` | home tasks from Calendar and Notion, no work sources, no calendar block |
| `/daily-workflow:briefing done …` | the prompt copied from the plan page: marks the ticked items done, Notion cards get Done (today) |
| `/daily-workflow:inbox` | capture into the Notion Inbox, then the processing page with a proposal for every Inbox card |
| `/daily-workflow:inbox process` | only the processing page, no capture |
| `/daily-workflow:inbox apply …` | the prompt copied from the processing page: applies the answers to Notion |

Drop the daily transcript into `~/.ai/worklog/meetings/` with the date in the name, e.g. `2026-11-23-daily.txt`.
Open the plan on the host with the printed command, e.g. `open ~/.ai/worklog/plans/2026-11-23.html`. The header and
the three acts of the day stay in a left column, the sections are cards with a "2/3" counter. Every item has a
checkbox; ticks are kept in the browser, and "Copy done" in the bottom bar copies a prompt that marks them done in the
plan and in Notion.

The inbox page works the same way (`open ~/.ai/worklog/inbox/2026-11-23-0930.html`). Each entry starts with the AI
proposal; `j` / `→` accepts it and moves on, so only change what is wrong: click a field or the title, `e` Done,
`#` Trash, `+` adds a card (an entry can become several cards), `n` a note for AI, `z` resets the entry, `?` help.
After the last entry the summary holds the prompt to paste into the session. Progress survives a page reload.
Capture creates new Inbox cards without asking. Every other Notion change comes from the pasted prompt.

## Worklog layout

```
~/.ai/worklog/                          local git repo, no remote
  checkpoints/YYYY-MM-DD/<session>.jsonl  Technical Checkpoints, one file per session
  state/sessions/<session>.json           written by the session's hooks only
  state/cursors/<session>.json            summary cursor, written by the summarizer only
  entries/YYYY-MM/<session>.jsonl         Worklog Entries, one file per session
  days/YYYY-MM-DD.md                      generated day view
  plans/YYYY-MM-DD[-home].json|html       briefing plans
  plans/assets/                           plan page style and components, copied on every render
  inbox/YYYY-MM-DD-HHMM.json|html          inbox processing pages
  inbox/assets/                           page components, copied from the plugin on every render
  state/inbox.json                        inbox cursor and 30-day registry of captured URLs
  meetings/                               daily transcripts
  config.toml
  locks/, logs/                           per-session locks and logs (not committed)
```

Every file has a single writer, so parallel sessions in separate containers never share a lock.

## How it works

- Hooks (`hooks/hooks.json`) call `scripts/worklog.py hook <Event>`. All run async except `SessionEnd`.
- `Stop` records the turn: user prompts read from the transcript byte range since the last checkpoint,
  `last_assistant_message`, git state, repo, worktree (from `git rev-parse --git-dir`, since `cwd` is always
  `/workspace`) and the Jira key from the branch or worktree name.
- When 15 minutes passed since the last entry (`Stop`) or before compaction (`PreCompact`), the hook starts
  `worklog.py summarize` detached. It calls `claude -p` with Haiku, no tools, no MCP, hooks disabled and a JSON
  schema.
- `SessionEnd` only writes the final checkpoint: the container stops with the session. The catch-up at the
  start of the briefing (`summarize --all`) picks it up.
- Logs: `~/.ai/worklog/logs/worklog.log`, `summarizer.log`.

## Tests

```
python3 -m unittest discover -s plugins/daily-workflow/tests
```

The unittest run also runs `tests/inbox_logic.test.js` and `tests/plan_logic.test.js` with `node --test` (skipped
without `node`). The page assets live in `scripts/wl/assets/`: `inbox-logic.js` (pure logic, no DOM),
`inbox-components.js`, `inbox.css`, and `plan.js` / `plan.css` for the plan page.
