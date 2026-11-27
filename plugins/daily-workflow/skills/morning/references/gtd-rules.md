# Notion ✅ GTD: model and planning rules

IDs are in `~/.ai/worklog/config.toml` under `[notion]`.

## Connection

- Tools: `notion-fetch` (pages, databases, views), `notion-query-data-sources` (SQL mode or `mode: "view"`), `notion-update-page`, `notion-create-pages`.
- SQL mode has an hourly limit. Use view mode or `notion-fetch`.

## Fields

| Field | Type | Values |
|---|---|---|
| Name | title | task name |
| Status | select | Inbox, Next Actions, In progress, Today candidates, Today, Done (today), Done, Agenda, Projects, Calendar, Icebox, Waiting for, Someday/Maybe, Errands |
| Category | multi_select | Work, Home (a card can have both) |
| Estimate | select | 0.25 x 🍅, 0.5 x 🍅, 1 x 🍅, 2 x 🍅, 3 x 🍅, 4 x 🍅, 5 x 🍅, 6 x 🍅, 10 x 🍅, None |
| Tags | multi_select | P1, P2, P3, ♻️ Recurring |
| Project | select | only existing options |
| Reminder | date | the day (or time) to work on the card |
| Due Date | date | hard deadline |
| URL | url | link, e.g. to the Jira ticket |

In SQL, dates are `date:Reminder:start`, `date:Due Date:start`, and the URL is `userDefined:URL`.

## Statuses

- **Next Actions**: the main to-do list. Cards planned for later have a Reminder on the planned day.
- **Today candidates**: only cards for the current days.
- **Today** / **In progress**: what is being done today / now.
- **Done (today)** / **Done**: finished.
- **Waiting for**: waiting on someone. The Reminder is the day to follow up.
- **Agenda**: cards named after a person (e.g. "Alice"), the body holds topics to discuss with them.
- **Errands**, **Calendar** (fixed appointments), **Projects**, **Someday/Maybe**, **Icebox**.

## Estimates and priorities

- Light task: ≤ 1 x 🍅. Heavy task: ≥ 2 x 🍅. `None` for Agenda, Errands and work tracked in Jira.
- One priority tag per card: P1, P2 or P3. ♻️ Recurring can sit next to it.

## Views used by the day plan

- Top (`view_top`): Reminder ≤ today or Due Date ≤ tomorrow, not Done. Main source of candidates.
- Overdue (`view_overdue`): Reminder or Due Date before today, not Done.
- Waiting For (`view_waiting_for`): only Waiting for. Take cards with Reminder ≤ today: follow-ups for today.
- Agenda / Errands (`view_agenda_errands`): Agenda cards. Match the card name to attendees of today's meetings.

## Workday plan (Work mode)

- Max 4 tasks: 1 deep focus (complex implementation, e.g. a sprint ticket from Jira), 1 heavy (≥ 2 x 🍅), 2 light (≤ 1 x 🍅).
- Days without a sprint ticket slot, planned from P1 cards: max 3 tasks, 1 heavy and 2 light.
- Outside the limit: ♻️ Recurring cards (e.g. "Morning code review", "Language practice", "GTD Weekly Review" on Friday, "Weekly team report"), Waiting for follow-ups, fixed Calendar appointments, Agenda topics.
- Only cards with Category Work (cards with both Work and Home count).
- The plan is saved as a Reminder on the day; the status stays Next Actions. Today candidates only for the current days.
- A sprint ticket from a project in `[worklog].jira_project_keys` that is in the deep focus slot and has no card yet (match by the card URL) gets a card: Category Work, URL `<[jira].base_url>/browse/<KEY>`, Estimate None, Reminder on the first day of the slot, Due Date on the last.

## Home mode plan

- Only cards with Category Home.
- Max 2 light (≤ 1 x 🍅) Home tasks, every day (the Saturday rule).
- Outside the limit as in Work mode: ♻️ Recurring, Waiting for follow-ups, Calendar appointments.
- No calendar block.

## Rules for changes

- Never change Notion without the user's consent. Show the change plan first, apply after an explicit yes.
- One exception: the inbox skill's capture creates new cards with Status Inbox without asking. It never changes existing cards; processing applies only what the user filled in on the inbox page.
- The Morning `apply` prompt pasted from the plan page sets Status `Done (today)` on the ticked Notion cards and carries out the clear notes for AI written on the page without asking again; an unclear note, or one that cannot be undone, is asked about first. It changes nothing else.
- Every card must have Status, Category and Estimate, otherwise it lands in the Inbox view.
- Tags and projects only from existing options. Never create a new project.
- Propose only the Reminders for today's tasks and the cards for sprint tickets above, nothing else unless the user asks.
