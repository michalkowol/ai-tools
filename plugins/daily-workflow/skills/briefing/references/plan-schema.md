# Plan JSON (`plans/YYYY-MM-DD.json`, home mode: `plans/YYYY-MM-DD-home.json`)

The plan JSON is the source of truth. `worklog render-plan <file>` renders the fixed HTML page
(light DOM web components), copies `plan.css` and `plan.js` into `plans/assets/`, re-renders every other
`plans/*.json` so old pages match the shared assets, and prints the `open ~/.ai/worklog/plans/….html` command for the
host. Every field is optional;
empty lists and empty sections are not rendered. All text is plain text: the renderer escapes it, and
only `http(s)` URLs become links. Write in English.

```json
{
  "v": 1,
  "date": "2026-11-23",
  "mode": "work",
  "stage": "morning",
  "generated_at": "2026-11-23T08:47:12+01:00",
  "headline": "Meetings bookend the day, the middle is yours.",
  "day_class": "normal",
  "timeline": [
    {"range": "9:00 – 11:00 AM", "note": "Daily at 9:10, then review the two waiting PRs."},
    {"range": "11 AM – 2 PM", "note": "Open stretch for PROJ-1234."},
    {"range": "2 PM onward", "note": "Architecture sync at 3, light tasks around it."}
  ],
  "priorities": [
    {"title": "PROJ-1234 event validation", "kind": "deep", "estimate": "", "url": "https://…",
     "why": "Sprint slot ends Wednesday, integration tests left (Worklog).",
     "source": {"label": "Jira", "url": "https://…"}}
  ],
  "outside_limit": [
    {"title": "Morning code review", "kind": "recurring", "note": "", "url": "https://…"}
  ],
  "deep_work": {"status": "proposed", "task": "PROJ-1234 event validation",
                "start": "11:00", "end": "13:00", "note": "Created after the daily.", "event_url": ""},
  "code_review": [
    {"title": "Batch processing for events", "repo": "org/shop", "number": 412, "url": "https://…",
     "author": "alice", "waiting": "26 h", "reason": "Direct request, author blocked on it, small diff."}
  ],
  "my_prs": [
    {"title": "Retry policy", "url": "https://…", "state": "changes-requested", "note": "2 comments from Bob."}
  ],
  "needs_attention": [
    {"title": "Answer Carol about the API contract", "text": "Asked in #team-proj yesterday at 16:40 whether …",
     "source": {"label": "in #team-proj", "url": "https://…"}}
  ],
  "resolved": [
    {"title": "Staging outage", "text": "Closed by Dave at 18:10, root cause DNS.", "source": {"label": "in #alerts", "url": "https://…"}}
  ],
  "meetings": [
    {"start": "09:10", "end": "09:25", "title": "Daily", "note": "", "agenda": []},
    {"start": "15:00", "end": "15:30", "title": "1:1 Alice", "note": "Agenda card", "agenda": ["Promotion plan"]}
  ],
  "tomorrow_prep": [{"title": "Agenda for the planning", "text": "You run it at 10:00 …", "source": {"label": "on your calendar", "url": ""}}],
  "follow_ups": [{"title": "Ping Erin about the contract", "text": "Waiting for since Thursday …", "source": {"label": "Notion", "url": "https://…"}}],
  "daily_update": {"yesterday": ["…"], "today": ["…"], "blockers": ["…"]},
  "post_daily": {"plan_changes": ["…"], "team_blockers": ["…"], "needs_help": ["…"], "agreed": ["…"], "decisions": ["…"]},
  "notion_changes": [{"card": "PROJ-1250 retry policy", "change": "New card: Work, Estimate None, Reminder 2026-11-23, Due 2026-11-25, URL Jira", "status": "proposed", "url": ""}],
  "missing_sources": [{"source": "Gmail", "reason": "connector not signed in"}]
}
```

## Field notes

- `mode`: `work` or `home`. `stage`: `morning` or `post-daily`.
- `day_class`: `heavy` (≥ 5 h of meetings or a cluster of 3+ back to back), `normal`, `open` (at most one short meeting). Computed from today's calendar only.
- `headline`: one sentence that names either the one thing that makes today distinct or the shape of the day, never both.
- `timeline`: exactly three acts, each a time range and one specific sentence from the calendar. No act repeats a list item.
- `priorities[].kind`: `deep`, `heavy` or `light`. Respect the limits in `gtd-rules.md`.
- `outside_limit[].kind`: `recurring`, `follow-up`, `calendar` or `agenda`.
- `deep_work.status`: `proposed` (morning with a daily today), `scheduled` (event created or moved), `none` (no window of `min_minutes`). Always `none` or absent in home mode.
- `code_review`: ordered, first = review first. `waiting` is a human duration.
- `my_prs[].state`: `waiting-review`, `changes-requested`, `ci-failing`, `approved`, `pending-ci`.
- `notion_changes[].status`: `proposed`, `applied` or `rejected`.
- `missing_sources`: one line per source that did not respond.
- `done` (on any object item) and `done_items` (top level, keys of plain-text items such as agenda points and daily
  bullets): written only by `worklog plan-done` from the page's "Copy done" prompt. Keep them when rewriting the plan
  (`update`), so ticked items stay ticked.
- The page puts a checkbox on every item. Its key is the section plus the item URL (`url`, `source.url` or
  `event_url`), or its title when there is no URL, so ticks kept in the browser survive a re-render. Keep titles and
  URLs stable between the morning plan and `update`.
