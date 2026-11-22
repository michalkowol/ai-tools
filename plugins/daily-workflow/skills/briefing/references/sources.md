# Sources: exact queries

`<since>` is `last_workday` from `worklog dates` (Monday → Friday), `<today>` and `<tomorrow>` come from the
same command. Run independent sources in parallel. A source that fails or is not connected goes to
`missing_sources` with a short reason and the briefing continues.

## Worklog (work mode)

- `worklog summarize --all --quiet` first: catch-up of sessions that never got summarized.
- `worklog context`: `entries` since the last workday and `open_threads` (latest entry per session that is not done
  or has next steps or blockers) from the last 14 days.
- Use it for: yesterday's work, unfinished work, decisions, blockers, and the "Yesterday" part of `daily_update`.

## GitHub (work mode)

- `worklog github` returns `review_requested` (direct and team requests, `requested_from_me_directly`),
  `team_repo_prs` (open PRs in `[github].team_repos`), `my_prs`, and `errors`.
- For the review order, weigh: a direct request, how long the author has waited (`age_hours`, `idle_hours`),
  re-review after changes (a `CHANGES_REQUESTED` review from you followed by new commits or comments), size,
  whether it blocks someone (mentions in Slack, the daily, sprint priority of the linked Jira issue),
  discussions in `last_comments`. Skip drafts unless you were asked directly. Bot PRs (`author_is_bot`, e.g.
  Renovate) block no person: group them in one line unless they are security fixes. Team PRs with no reviewer at all
  and older than a day are worth one line.
- `my_prs`: list the ones with `review_decision` `CHANGES_REQUESTED`, `ci` `failing`, or waiting for review
  for more than a day.
- Only open `gh pr view` for more context on the top few PRs if the JSON is not enough.

## Google Calendar (both modes)

- One fetch for today 00:00 → tomorrow 24:00 in the user's time zone. Only today's events are drawn and classified,
  tomorrow's are for prep items.
- Free windows: between `[workday].start` and `[workday].end`, outside meetings, leaving 10 min buffers around them.
- The daily: an event today whose title contains `[workday].daily_event_title`.
- Changes: cancelled events, conflicts that went away → Resolved. New overlapping events → Needs attention.
- Deep Work events created by the briefing carry `[deep_work].event_marker` in the description. Never change any
  other event.

## Jira (work mode)

Atlassian connector, `searchJiraIssuesUsingJql`:

- `assignee = currentUser() AND sprint in openSprints() AND statusCategory != Done ORDER BY priority DESC, updated DESC`
- Use it for the deep focus candidate (a ticket from a project in `[worklog].jira_project_keys` in its sprint
  slot), sprint status in `daily_update`, and for sprint tickets that have no Notion card yet (see `gtd-rules.md`).

## Slack (work mode)

Slack connector, `slack_search_public_and_private`, all with `after:<since>`. The user's Slack ID is in the tool
description ("Current logged in user's user_id is …") or `[slack].user_id`.

1. DMs and group DMs: `channel_types = "im,mpim"`, filters `after:<since>`.
2. Followed channels: for every channel in `[slack].channels`, filters `in:<channel> after:<since>`.
3. Direct mentions anywhere: keywords `["<@USER_ID>"]`, filters `after:<since>`, all channel types.
4. Slack To-dos (saved for later): filters `is:saved`, no date filter.

Before an item lands in Needs attention, open its thread once (`slack_read_thread`). If the user already replied
or reacted with any emoji, it moves to Resolved or is dropped. A group mention that anyone on the list could
answer is not a bottleneck. Unanswered asks of the user: messages from the user since `<since>` ending in a
question with no reply → `follow_ups`.

## Gmail (work mode)

- `in:inbox category:primary is:unread after:<since>`.
- Threads where someone asks the user something and the user has not replied: check the thread before listing.
- Sent asks without a reply: `in:sent after:<7 days ago>` with a question and no later message in the thread →
  `follow_ups`.
- Skip GitHub, Jira and other notification mail, those come from the source.

## Notion (both modes)

Use `notion-query-data-sources` with `mode: "view"` or `notion-fetch` on the views from `[notion]`
(see `gtd-rules.md`): Top, Overdue, Waiting For (Reminder ≤ today), Agenda / Errands (Agenda cards whose name
matches an attendee of today's meetings). Work mode keeps Category Work, home mode Category Home.

## Prep for tomorrow (work mode)

For tomorrow's events that the user organizes or that name a project: one Slack search `<project keyword>`
with `after:<7 days ago>`, and skim the linked doc if the event has one. A prep item needs a concrete anchor:
a doc to read, a decision the user will be asked for, an agenda to bring.

## Daily transcript (update stage)

`worklog meetings` lists `~/.ai/worklog/meetings/*<today>*.{txt,md}`. Read the daily transcript and extract:
what each developer said, blockers, agreed tasks, who needs help, decisions, and whether the user's priorities
should change.
