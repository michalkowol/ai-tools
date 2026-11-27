# daily-workflow

Personal Claude Code plugin with three parts that share one local Worklog:

- **Work Logger**: hooks write a Technical Checkpoint after every response and after git, PR, test and Jira events,
  without any LLM. A detached headless Haiku call turns them into Worklog Entries every 15 minutes of work and before
  compaction. `/daily-workflow:worklog` forces it now.
- **Morning**: `/daily-workflow:morning` plans the day before the daily, `update` corrects it from the daily
  transcript and schedules the Deep Work block, `home` plans home tasks.
- **Inbox**: `/daily-workflow:inbox` captures unanswered Slack messages, Slack to-dos, PRs waiting for review,
  own PRs that need action and important email into the Notion GTD Inbox, then renders the whole Inbox as an HTML
  page that shows one entry at a time with the AI proposal already chosen. PRs under 10 changed files waiting for review get no card:
  a recurring code review card in Notion covers them. `/daily-workflow:inbox knowledge` keeps a local knowledge
  base: md files built from every Slack to-do and from the followed channels.

## Setup

### Connectors

- Notion: install [makenotion/claude-code-notion-plugin](https://github.com/makenotion/claude-code-notion-plugin).
- Sign in to the claude.ai connectors used by Morning: Google Calendar, Gmail, Slack, Atlassian.
- `gh` needs the token described in the `ai` README (`repo`, `read:org`).

### Config

The first hook creates `~/.ai/worklog` as a local git repo with `config.toml` from
[config.example.toml](config.example.toml). Fill in `[worklog].jira_project_keys`,
`[github].team_repos`, `[slack].channels`, the `[notion]` IDs of your GTD database and views, `[jira].base_url`,
and check `[workday]`. For the "Reading list" outcome of the Inbox create an empty page in Notion and put its URL
into `[notion].reading_list`. `[knowledge].dir` is the folder of the knowledge base.

## Usage

| Command | What it does |
|---|---|
| `/daily-workflow:worklog` | checkpoint and summary of this session now, prints the new entries |
| `/daily-workflow:worklog today`, `… jira PROJ-1234` | read the Worklog |
| `/daily-workflow:morning` | morning plan: catch-up of unsummarized sessions, sources, plan, `open …` command for the host |
| `/daily-workflow:morning update` | after the daily: reads `~/.ai/worklog/meetings/<date>*.txt`, corrects the plan, creates the Deep Work block |
| `/daily-workflow:morning home` | home tasks from Calendar and Notion, no work sources, no calendar block |
| `/daily-workflow:morning apply …` | the prompt copied from the plan page: marks the ticked items done (Notion cards get Done (today)), carries out the notes for AI and keeps the order of the lists you rearranged |
| `/daily-workflow:inbox` | capture into the Notion Inbox, then the processing page with a proposal for every Inbox card |
| `/daily-workflow:inbox process` | only the processing page, no capture |
| `/daily-workflow:inbox apply …` | the prompt copied from the processing page: applies the answers to Notion |
| `/daily-workflow:inbox knowledge [days]` | builds or extends the knowledge base from every Slack to-do and the followed channels |

Drop the daily transcript into `~/.ai/worklog/meetings/` with the date in the name, e.g. `2026-11-23-daily.txt`.
Open the plan on the host with the printed command, e.g. `open ~/.ai/worklog/plans/2026-11-23.html`. The header and
the three acts of the day stay in a left column, the sections are cards with a "2/3" counter. Every item has a
checkbox and, on hover, a "+ note" button for a note for AI in free text (e.g. "set the reminder to 1 Dec", "move to
Waiting for"); the last card holds one more field for a note about the whole plan. In the task lists the items can be
reordered: drag the handle that shows on hover to the left of an item, or focus it and press the arrow keys. Ticks,
notes and the order are kept in the browser, and "Copy prompt" in the bottom bar copies a prompt that marks the
ticked items done in the plan and in Notion, carries out the notes and writes the new order into the plan, so
`update` keeps it. The page then shows every note with its result.

The inbox page works the same way (`open ~/.ai/worklog/inbox/2026-11-23-0930.html`). Each entry starts with the AI
proposal; `j` / `→` accepts it and moves on, so only change what is wrong: click a field or the title, `e` Done,
`#` Trash, `+` adds a card (an entry can become several cards), `n` a note for AI, `z` resets the entry, `?` help.
After the last entry the summary holds the prompt to paste into the session. Progress survives a page reload.
Capture creates new Inbox cards without asking. Every other Notion change comes from the pasted prompt.

Slack to-dos: capture takes the to-dos whose message is at most 30 days old (the search is `is:todos`; Slack has no
API for them, so completed ones cannot be told apart and to-dos typed by hand are not found). On the page a to-do
is a task like any other entry, or one of two outcomes with nothing to do: "Reading list" appends a bullet with the
link to one Notion page, "Reference" appends an entry to a file of the knowledge base. Both move the Inbox card to
Trash. Nothing is ever changed in Slack.

The knowledge base (`open ~/.ai/worklog/knowledge`) is a folder of md files: topic files with one entry per
source (date, summary, a short quote, the source and its links, with a summary of public pages behind them) and
`requests.md`, a list of the requests and tasks found in the to-dos. `/daily-workflow:inbox knowledge` reads every
to-do and the followed channels (`[slack].channels`: the last 30 days the first time, or the number of days given,
then only what is new), proposes the list of files on the first run and waits for your approval, and later adds
only what is not in the base yet; it asks before it creates a new file. Summaries are in English, quotes in the
original. Links to company systems are never fetched. Capture creates no card for a to-do the base already holds
as knowledge.

## Worklog layout

```
~/.ai/worklog/                          local git repo, no remote
  checkpoints/YYYY-MM-DD/<session>.jsonl  Technical Checkpoints, one file per session
  state/sessions/<session>.json           written by the session's hooks only
  state/cursors/<session>.json            summary cursor, written by the summarizer only
  entries/YYYY-MM/<session>.jsonl         Worklog Entries, one file per session
  days/YYYY-MM-DD.md                      generated day view
  plans/YYYY-MM-DD[-home].json|html       day plans
  plans/assets/                           plan page style and components, copied on every render
  inbox/YYYY-MM-DD-HHMM.json|html          inbox processing pages
  inbox/assets/                           page components, copied from the plugin on every render
  state/inbox.json                        inbox cursor and 30-day registry of captured URLs
  knowledge/<topic>.md, requests.md       knowledge base: topic files and the list of requests
  knowledge/README.md, .state.json        its index; the sources already in the base and the channel windows
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
  start of Morning (`summarize --all`) picks it up.
- Logs: `~/.ai/worklog/logs/worklog.log`, `summarizer.log`.

## Tests

```
python3 -m unittest discover -s plugins/daily-workflow/tests
```

The unittest run also runs `tests/inbox_logic.test.js` and `tests/plan_logic.test.js` with `node --test` (skipped
without `node`). The page assets live in `scripts/wl/assets/`: `inbox-logic.js` (pure logic, no DOM),
`inbox-components.js`, `inbox.css`, and `plan.js` / `plan.css` for the plan page.
